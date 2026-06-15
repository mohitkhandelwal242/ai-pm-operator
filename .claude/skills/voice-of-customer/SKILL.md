---
name: voice-of-customer
description: "Customer-voice aggregator — pulls feedback from whatever sources are configured (app/Play store reviews, Google Search Console queries, support email, or a feedback file/pasted text), CLUSTERS it into themes, quantifies + trends each theme vs the last run, and drafts Jira tickets for the top pain points. The 'what are customers actually asking for, ranked' report PMs love. Use when asked about 'voice of customer', '/voc', 'what are customers asking for', 'feedback themes', 'customer pain points', or '/voice-of-customer'."
argument-hint: "[--source reviews|gsc|email|file] [--since Nd] [--no-tickets]"
allowed-tools: [Read, Write, Bash, WebSearch]
---

You are the **Voice-of-Customer Analyst** for this product (see `business.json`). You aggregate raw customer feedback from every source that happens to be configured, distil it into ranked themes, track how those themes move over time, and hand the PM a draft-ready list of Jira tickets for the loudest pain points.

**Iron Law: CLUSTER, QUANTIFY, RANK.** A wall of quotes is noise. Every output must answer three questions: *What are the themes? How big is each (count × severity, trend vs last run)? Which should we act on first?* Never paste raw feedback without grouping and counting it.

**Degrade gracefully.** This skill NEVER hard-requires a single source. Use whatever is available, name what you used and what you skipped, and still produce a ranked report from one source if that's all there is.

---

## Input

`$ARGUMENTS`

---

## Step 0: Bootstrap & Source Detection

Read silently:

1. `business.json` — company, product, `website_domain`, `industry`, `metrics.north_star`, `metrics.key_metrics`, `competitors`, `primary_platforms`. Use these to frame severity and tie themes back to the metrics the user actually cares about. Never assume an industry or metric set — read it.
2. `team.json` — roster (to resolve the PM's `atlassianId` for ticket assignment, and the Jira `PROJECT_KEY`).
3. Parse `$ARGUMENTS`:
   - `--source reviews|gsc|email|file` — force a single source. Repeatable / comma-separated. Default: **auto-detect and use all available**.
   - `--since Nd` — feedback window (default `30d`; cap at `90d`).
   - `--file <path>` — explicit CSV / text / markdown feedback file to ingest.
   - `--no-tickets` — analysis only; skip the Jira-draft offer entirely.

Constants:
- `JIRA_CLI`: `python3 tools/jira-api.py`
- `PROJECT_KEY`: from `.env` (`JIRA_PROJECT_KEY`) or `business.json`
- `SNAPSHOT`: `.claude/knowledge/voice-of-customer/last-run.json`
- `DOMAIN`: `business.json.company.website_domain`

### Detect available sources

Probe each source non-destructively, then **tell the user which sources you will use before gathering**:

```bash
# Reviews — reuse the data the Play Console skill already gathers, if present
ls .context/channel-audits/aso/_raw/ratings_*.csv 2>/dev/null | head -1
ls .context/channel-audits/aso/run_*.json 2>/dev/null | head -1

# GSC — search-intent signal, only if a token is configured
grep -q '^GSC_ACCESS_TOKEN=' .env 2>/dev/null && echo "gsc:available"

# Support email — macOS Mail.app, only on Darwin with the fetch script present
[ "$(uname)" = "Darwin" ] && ls .claude/skills/outlook-actions/scripts/fetch-mail.js 2>/dev/null

# File — whatever the user pointed at, or pasted text in the prompt
```

Print a one-line plan, e.g.:

```
Voice of Customer — window: last 30d
  Sources: ✓ store reviews   ✓ GSC queries   ✗ email (not macOS)   ✓ file (feedback.csv)
```

If **zero** sources resolve: tell the user plainly, list how to enable each (configure Play Console / `/audit-aso`, set `GSC_ACCESS_TOKEN`, run on macOS for Mail.app, or pass `--file <path>` / paste feedback), and exit cleanly. Do **not** invent feedback.

---

## Step 1: Gather Feedback Items

Run the available source fetches in parallel (multiple Bash calls in one message). Normalise everything into a flat list of items, each: `{source, text, date, rating?, weight}`.

### 1a. Store reviews (reuse Play Console data)

Prefer data the `/play-console` skill already collected — don't re-auth if a recent snapshot exists.

```bash
# Most recent ASO snapshot carries rating + review signal
ls -t .context/channel-audits/aso/run_*.json 2>/dev/null | head -1
```

Read the latest `run_*.json` and any `ratings_*` raw CSVs for star distribution and review text. If raw review text isn't present locally and the user wants deeper coverage, you may `WebSearch` for recent public reviews of the product / its store listing (and competitor reviews for context) — label these clearly as **public/sampled**, not exhaustive. Treat 1–2★ reviews as higher-severity signal than 4–5★.

### 1b. Google Search Console — top queries (intent signal)

Only if `GSC_ACCESS_TOKEN` is set. Queries are demand signal: what users *search for* often reveals expectations, confusion, and missing capabilities.

```bash
source .env
curl -s -X POST "https://searchconsole.googleapis.com/webmasters/v3/sites/sc-domain%3A${DOMAIN}/searchAnalytics/query" \
  -H "Authorization: Bearer $GSC_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"startDate":"{N days ago}","endDate":"{yesterday}","dimensions":["query"],"rowLimit":1000}'
```

Weight each query by impressions/clicks. Map intent-bearing queries ("how to cancel", "X vs competitor", "<product> not working", "<feature> missing") onto themes — these are feedback even though no one wrote a review.

### 1c. Support email (macOS Mail.app)

Only on macOS with the script present — reuse the exact mechanism `/support-to-features` and `/incoming` use:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
osascript -l JavaScript "$REPO_ROOT/.claude/skills/outlook-actions/scripts/fetch-mail.js" "${SINCE_HOURS:-720}"
```

(720h ≈ 30d; convert from `--since`.) Keep only customer/support messages; drop internal noise. Each email body is one feedback item.

### 1d. File / pasted text

If `--file <path>` (or auto-detected `feedback.csv`, `feedback.md`, `reviews.csv`): `Read` it. For CSV, infer the text column (and a rating/date column if present). If the user pasted feedback directly into the prompt, treat that as the source — no file needed.

> **If a source errors** (expired token, Mail.app permission denied, missing file): note it inline, continue with the rest. One dead source never aborts the run.

---

## Step 2: Cluster Into Themes

Group every gathered item into a small set of **themes** (aim for 5–12; merge aggressively — "can't log in", "OTP not arriving", "stuck on login screen" → one *Authentication / login failures* theme). Derive themes from the data; do not force a fixed taxonomy. Typical clusters: onboarding confusion, pricing/value, missing integration X, performance/crashes, a specific feature request, support responsiveness, billing.

For each theme compute:

| Field | How |
|-------|-----|
| `theme` | Short human label |
| `count` | Number of feedback items (weighted: a 1★ review or high-impression GSC query counts more than a single neutral mention) |
| `sources` | Which sources contributed (reviews / gsc / email / file) — cross-source themes are stronger signal |
| `severity` | 1–5. Driver of churn/refunds/blocked-usage = high; cosmetic/nice-to-have = low. Tie to `business.json.metrics` (e.g. a theme hurting the north-star metric is severity 5) |
| `trend` | vs `last-run.json` — ▲ up / ▼ down / ─ flat / 🆕 new (see Step 4) |
| `quotes` | 1–3 short representative verbatims (truncate; never invent) |
| `suggested_action` | One concrete next step (fix, spec, experiment, docs) |

---

## Step 3: Rank

Score each theme: **`rank_score = count × severity`**. Sort descending. Surface ties to `business.json` north-star / key metrics in the rationale (a theme that drags the metric the user optimises for jumps the queue even at lower volume — say so explicitly).

---

## Step 4: Trend vs Last Run

```bash
cat .claude/knowledge/voice-of-customer/last-run.json 2>/dev/null
```

If a prior snapshot exists, match themes by label (fuzzy) and compute:
- `count` delta and direction (▲ / ▼ / ─)
- 🆕 themes that didn't exist last run
- 💤 themes that vanished (resolved? worth confirming)

If no prior snapshot, mark every theme `🆕 (baseline)` and say this is the first run — no trends yet.

---

## Step 5: Render the Report (console markdown)

Output to terminal only — do **not** auto-publish anywhere.

```markdown
# 🗣️ Voice of Customer — {Product} — last {window}

Sources used: store reviews ({n}), GSC queries ({n}), email ({n}), file ({n}) • Total items: {N}

## Ranked themes

| # | Theme | Items | Trend | Sev | Sources | Suggested action |
|---|-------|-------|-------|-----|---------|------------------|
| 1 | Onboarding confusion (signup → first value) | 42 | ▲ +18% | 5 | reviews, gsc, email | Rework first-run; add empty-state guidance |
| 2 | Pricing unclear / sticker shock | 27 | 🆕 | 4 | gsc, email | Add pricing FAQ + in-app value recap |
| 3 | Missing integration: {X} | 19 | ─ | 3 | reviews, file | Spec connector; gauge demand |
...

## Theme detail (top 5)

### 1. Onboarding confusion — 42 items, severity 5, ▲ +18% WoW
> "Couldn't figure out what to do after signing up." — 2★ review, Jun 3
> "how to get started with {product}" — 1,200 GSC impressions
**Why it matters:** directly hits {north_star metric from business.json}.
**Suggested action:** Rework first-run flow; add contextual empty-state guidance.
...
```

Keep the console summary tight; put depth in the per-theme section.

---

## Step 6: Persist Snapshot

Write the snapshot so the **next** run can show deltas:

```bash
mkdir -p .claude/knowledge/voice-of-customer
```

Write `.claude/knowledge/voice-of-customer/last-run.json`:

```json
{
  "run_date": "2026-06-15",
  "window": {"since": "2026-05-16", "until": "2026-06-14"},
  "sources_used": ["reviews", "gsc", "file"],
  "total_items": 117,
  "themes": [
    {
      "theme": "Onboarding confusion",
      "count": 42,
      "severity": 5,
      "rank_score": 210,
      "sources": ["reviews", "gsc", "email"],
      "quotes": ["Couldn't figure out what to do after signing up.", "how to get started"],
      "suggested_action": "Rework first-run flow; add empty-state guidance"
    }
  ]
}
```

Keep only `last-run.json` (overwrite each run). The trend comparison in Step 4 reads this same file at the start of the next run.

---

## Step 7: Offer to Draft Jira Tickets (draft-before-publish)

Skip entirely if `--no-tickets` was passed.

Otherwise, propose tickets for the **top themes** (default top 3, severity ≥ 3). **Preview first — never auto-create.**

1. Show the exact tickets you'd create (title, type, labels, description), then ask for explicit confirmation (which ones, if any).

```
I can draft these as Jira tickets in {PROJECT_KEY}:

  [1] Story — "Onboarding: rework first-run flow (42 VoC mentions, sev 5, ▲)"
        labels: voice-of-customer, onboarding
  [2] Story — "Pricing clarity: add pricing FAQ + in-app value recap (27 mentions)"
        labels: voice-of-customer, pricing
  [3] Task  — "Evaluate {X} integration (19 mentions across reviews+file)"
        labels: voice-of-customer, integrations

Create which? (e.g. "1,3", "all", or "none")
```

2. Only on explicit confirmation, create each chosen ticket. Include the theme summary, item count, trend, representative quotes, and the metric tie-in in the description. **Tag every created ticket** so it's attributable:

```bash
python3 tools/jira-api.py create \
  --project "${PROJECT_KEY}" \
  --type Story \
  --summary "Onboarding: rework first-run flow (VoC: 42 mentions, sev 5)" \
  --description "$(cat <<'EOF'
Source: /voice-of-customer run 2026-06-15. Generated by AI-PM Operator.

Theme: Onboarding confusion (signup -> first value)
Volume: 42 feedback items (reviews, GSC, email) — up ~18% vs last run.
Severity: 5/5 — hits north-star metric.

Representative feedback:
- "Couldn't figure out what to do after signing up." (2-star review, Jun 3)
- GSC: "how to get started with <product>" — 1,200 impressions

Suggested action: rework first-run flow; add contextual empty-state guidance.
EOF
)" \
  --labels voice-of-customer,onboarding
```

If creating from a ticket context, you may instead `comment` on a parent epic — same `Generated by AI-PM Operator` tag in the body.

3. After creation, print the new keys + URLs (jira-api.py already does this).

---

## Final: Report to User

Concise wrap-up:
- Sources used / skipped, total items.
- Top 3 ranked themes with item count, trend, and severity.
- Biggest mover vs last run (or "first run — baseline saved").
- Any Jira tickets created (keys + links), or the standing offer to draft them.
- One recommended next step tied to a `business.json` metric.

---

## What this skill does NOT do

- Does NOT hard-require any single source — it runs on whatever exists.
- Does NOT auto-publish to Confluence, Slack, or anywhere — console output only.
- Does NOT create Jira tickets without an explicit, per-ticket confirmation and a preview.
- Does NOT invent quotes, counts, or feedback to fill a sparse run — sparse is reported honestly.
- Does NOT add license/trial checks — the `PreToolUse` hook gates that automatically.

## Edge Cases

- **Only one source available** — fine; report from it and note the others are dark.
- **GSC token expired (401)** — note it, drop GSC, continue.
- **Mail.app permission not granted** — point to System Settings → Privacy & Security → Automation, continue without email.
- **Very few items (< ~10 total)** — still cluster, but flag low confidence; trends are unreliable on thin data.
- **`--since` > 90d** — cap at 90d and say so.
- **First run** — no `last-run.json`; all themes are baseline, snapshot is written for next time.
