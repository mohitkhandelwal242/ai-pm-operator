---
name: daily-briefing
description: "The morning-habit orchestrator — one command produces a single, concise, proactive digest of everything a PM needs to know today: board health, what's newly on your plate, metric movement, and competitor deltas. Degrades gracefully — only runs the sections whose data and credentials exist. Use when asked for '/briefing', 'morning briefing', 'monday briefing', 'daily briefing', '/standup', 'what needs me today', 'catch me up', or as the first thing each morning."
argument-hint: "[--since Nd] [--no-email]"
allowed-tools: [Read, Bash, WebSearch]
---

# Daily Briefing — Product

The first thing you run each morning. One command assembles a single, tight digest of everything that needs a Product Manager's attention today, pulled from whatever sources this install has configured. A CTO or PM should read the whole thing in under 2 minutes.

**Iron Law: DEGRADE GRACEFULLY, LEAD WITH THE PUNCHLINE.** Never error because a source isn't configured — silently skip any section whose data or credentials are missing. Always open with the synthesized "Top 3 that need you today"; the supporting sections come after.

This is a read-and-summarize orchestrator. It does **not** auto-publish, comment, transition, email, or notify anyone. Output is console markdown only.

---

## Input

`$ARGUMENTS`

---

## Step 0: Bootstrap & Source Detection

Read silently:
1. `business.json` — company, product, industry, metrics (`north_star`, `key_metrics`), competitors, stack. **Use this for all context — never assume an industry, metric, or competitor.**
2. `team.json` — full roster. Find the Product Manager / Project Manager (role contains "Product Manager" or "Project Manager"); store their `name`, `alias`, `atlassianId`, `email`. This is "you" for the briefing.
3. `.env` — to detect which integrations are configured (see detection table below). Do **not** print secrets.
4. Parse `$ARGUMENTS`:
   - `--since Nd` — look-back window for board + incoming sections (default `2d`; Monday default `3d` to cover the weekend). Cap at `14d`.
   - `--no-email` — skip the email half of the "Incoming for you" section.

Constants:
- JIRA_CLI: `python3 tools/jira-api.py`
- PROJECT_KEY: `${JIRA_PROJECT_KEY}` (a.k.a. `${PROJECT_KEY}`)

### Source detection (decide which sections run)

Probe each source and build an availability map. A source that is absent is **skipped silently**, not errored.

| Section | Runs when |
|---|---|
| 1. Board health | `JIRA_URL` + `JIRA_EMAIL` + `JIRA_TOKEN` + `JIRA_PROJECT_KEY` are all set |
| 2a. Incoming Jiras | same Jira creds as above + PM resolved from `team.json` |
| 2b. Email actions | `--no-email` NOT passed AND a mail source exists (`.claude/skills/outlook-actions/scripts/fetch-mail.js` present, or `ATLASSIAN`/IMAP mail creds set). If none, skip the email half only. |
| 3. Metric pulse | `GA4_PROPERTY_ID` (or `GA_PROPERTY_ID`) is set in `.env` |
| 4. Competitor deltas | `.claude/knowledge/competitor-audit/last-scan.json` exists AND has a non-null `scan_date` |
| 5. Top 3 | always — synthesized from whatever sections ran |

Quick probe (single call, don't fail the run if a grep returns nothing):
```bash
echo "== .env keys ==" ; grep -E '^(JIRA_URL|JIRA_EMAIL|JIRA_TOKEN|JIRA_PROJECT_KEY|GA4_PROPERTY_ID|GA_PROPERTY_ID)=' .env 2>/dev/null | sed 's/=.*/=<set>/'
echo "== mail ==" ; ls .claude/skills/outlook-actions/scripts/fetch-mail.js 2>/dev/null
echo "== competitor scan ==" ; ls .claude/knowledge/competitor-audit/last-scan.json 2>/dev/null
```

**Announce up front** (one line, before any section), e.g.:
> Briefing for **{PM name}** · {date} · window {Nd} · sections running: Board health, Incoming, Competitor deltas (Metric pulse skipped — GA4 not configured).

This tells the user immediately what's covered and what isn't, so a missing section never reads as a bug.

---

## Step 1: Gather Data (run available sections in parallel)

Run every available source's fetch in parallel — issue the Bash calls in a single message. If a Jira call returns a 401 / "Client must be authenticated", treat Jira as unavailable for this run (surface a one-line note, continue with the rest). **Summarize, don't audit** — pull just enough to flag what needs attention.

### 1. Board health (Jira)

Mirror the kinds of checks `scrum-master` runs, but only to *count and surface* — do not take any action.

```bash
# Blocked / impediment-labeled, still open
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND statusCategory != Done AND (labels = blocker OR labels = impediment OR labels = blocked)" \
  --fields "summary,status,assignee,priority,updated,labels" --max-results 30

# Stale — open and untouched 10+ days
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND statusCategory != Done AND updated <= -10d ORDER BY updated ASC" \
  --fields "summary,status,assignee,priority,updated" --max-results 50

# Unassigned and aging (>3d, flow risk)
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND statusCategory != Done AND assignee IS EMPTY AND created <= -3d ORDER BY created ASC" \
  --fields "summary,status,priority,created" --max-results 30

# High/Highest priority still open (what's at stake)
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND statusCategory != Done AND priority IN (Highest, High) ORDER BY priority DESC, updated ASC" \
  --fields "summary,status,assignee,priority,updated" --max-results 30
```

Reduce to counts + the 3–5 sharpest items (e.g. oldest blocker, highest-priority stale issue).

### 2. Incoming for you

**2a. Newly assigned Jiras** (assigned to the PM by someone else, in the window):
```bash
USER_ID="$(python3 -c 'import json,sys; r=json.load(open("team.json")); pm=next((p for p in r if "Product Manager" in p.get("role","") or "Project Manager" in p.get("role","")), None); print(pm["atlassianId"] if pm else "")')"
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND assignee = \"$USER_ID\" AND reporter != \"$USER_ID\" AND statusCategory != Done AND created >= -${SINCE_DAYS}d ORDER BY priority DESC, created DESC" \
  --fields "summary,reporter,priority,status,created" --max-results 30
```

**2b. Email action items** — only if a mail source exists and `--no-email` was not passed. Reuse the existing mail fetcher if present (do not hard-require it):
```bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
osascript -l JavaScript "$REPO_ROOT/.claude/skills/outlook-actions/scripts/fetch-mail.js" "${SINCE_HOURS:-48}" 2>/dev/null
```
Classify only the clear action items (addressed to the PM, asking for a decision/reply). If the fetcher is missing or errors, skip the email half silently — never block the briefing on it.

### 3. Metric pulse (only if GA4 configured)

If `GA4_PROPERTY_ID` is set, pull a short window for the `north_star` / `key_metrics` from `business.json` and produce a **1–3 line "what moved"** note — only genuine anomalies (e.g. ">20% day-over-day swing"), not a full report. If GA4 is not configured, skip entirely. (For the full analysis, point the user at `/weekly-metrics`.)

### 4. Competitor deltas (only if last-scan.json exists)

```bash
cat .claude/knowledge/competitor-audit/last-scan.json 2>/dev/null
```
If present and `scan_date` is non-null, summarize **only what is new** since that scan: new entrants in `discovery.new_competitors_added`, fresh `news_headlines`, notable rating/feature/hiring/pricing changes in `competitors`. 1–4 bullets, business-agnostic, drawn from `business.json` competitors. If the file is absent or an empty baseline (`scan_date: null`), skip — optionally one line: "No competitor scan yet — run /competitor-tracker to seed one."

---

## Step 2: Synthesize "Top 3 that need you today"

From whatever sections ran, distill the **three** most decision-worthy items for the PM today. Rank by leverage, roughly:
1. A blocker or high-priority issue stalling delivery.
2. Something newly on the PM's plate that needs a decision/reply now.
3. A real metric anomaly or a competitor move with strategic implication.

Each line: the punchline + the concrete artifact (Jira key, sender, metric, competitor) + the suggested next move. If fewer than 3 things genuinely need attention, list fewer — never pad. If nothing does, say so plainly ("Clear runway — no fires; go do focused work.").

---

## Step 3: Render the Briefing (console markdown)

Lead with the Top 3. Keep total length tight — aim for under ~40 lines. Omit any section that didn't run (don't print empty headers).

```markdown
# ☀️ Daily Briefing — {Product name} · {date}
_{PM name} · window {Nd} · sections: {list}_

## 🎯 Top 3 that need you today
1. **{punchline}** → {artifact} · {suggested move}
2. **{punchline}** → {artifact} · {suggested move}
3. **{punchline}** → {artifact} · {suggested move}

---

## 🩺 Board health
- Blocked: {N} · Stale (10d+): {N} · Unassigned (3d+): {N} · High-pri open: {N}
- Sharpest: ${PROJECT_KEY}-XXXX {summary} — {why it matters} ({assignee or Unassigned})
- ${PROJECT_KEY}-YYYY {summary} — stale {D}d

## 📥 Incoming for you
**New Jiras assigned to you ({N})**
| Key | Pri | Reporter | Created | Summary |
|-----|-----|----------|---------|---------|
| ${PROJECT_KEY}-XXXX | High | {name} | {date} | {summary} |
> If 0: "No new Jiras landed on your plate — clean slate."

**Email actions ({M})**  _(omit block if email source not available or --no-email)_
| Sender | Subject | Suggested action |
|--------|---------|------------------|
| {name} | {subject} | {action} |

## 📈 Metric pulse   _(only if GA4 configured)_
- {north_star} {↑/↓ X%} {window} — {one-line read}.

## 🔭 Competitor deltas   _(only if last-scan.json exists)_
- {Competitor}: {what changed since last scan} → {implication for {Product}}.
```

End with a single-line footer summarizing what was and wasn't covered, e.g.:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Covered: Board, Incoming, Competitor · Skipped: Metric pulse (GA4 not set)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 4: One Optional Follow-up

Offer at most ONE next step, only if clearly useful — otherwise stay silent:
- High-priority blocker → "Want me to run /scrum-master --focus blockers?"
- Heavy inbox → "Want the full /incoming walk-through?"
- Metric anomaly → "Want the full /weekly-metrics report?"

---

## What this skill does NOT do

- Does NOT error or stop because a source is unconfigured — it skips that section and says so.
- Does NOT publish to Confluence, post to Slack, send email, or push notifications.
- Does NOT modify Jira (no comments, transitions, labels, or assignments) — it only reads.
- Does NOT run the full scrum audit, full GA report, or full competitor scan — those are their own skills; this is the 2-minute summary that points to them.
- Does NOT assume an industry, metric set, or competitor — everything comes from `business.json`.

## Edge Cases

- **Nothing configured but Jira** — that's fine; run Board health + Incoming Jiras, skip the rest, still produce a Top 3 (or "Clear runway").
- **Jira token expired (401)** — surface one line ("Atlassian token expired — refresh at https://id.atlassian.com/manage-profile/security/api-tokens and update JIRA_TOKEN in .env"), continue with non-Jira sections.
- **PM not found in team.json** — skip the "newly assigned" half, note it once, keep the rest.
- **Empty competitor baseline (`scan_date: null`)** — treat as not-yet-scanned; skip with a one-line nudge.
- **Monday run** — widen the default window to 3d to capture weekend activity; you may label the digest "Monday briefing".
- **Everything quiet** — short is correct. A 6-line "all clear" briefing is a successful run, not a failure.
