---
name: release-notes-writer
description: "Generate slide content for the Product section of a leadership weekly / release-notes deck. Aggregates user-visible product ships from the last 4 weeks across all of the business's repos (the current git repo + every repo in business.json → stack.code_repos[]) plus Jira Done items in ${PROJECT_KEY}, groups them by theme, and produces per-experiment slides with measured impact tables. Use when asked for 'leadership product slides', 'product week deck', 'release notes deck', 'what shipped to production', '/leadership-product-weekly', or '/product-weekly'."
---

# Leadership Product Weekly — Slide Content Generator

Generate slide-by-slide markdown for the **Product** section of the business's leadership weekly / release-notes deck. The output is paste-ready for Google Slides.

**Audience:** leadership (CEO / founders / exec team). They want to know *what user-visible product shipped* and *what measurable impact each had* — not a git log, not infra/tooling work.

The skill is generic: it builds the Product section from whatever repos and Jira project the business has configured. There is no hard-coded deck or repo list — everything comes from `business.json` and `.env`.

---

## Step 0 — Load business context & resolve window

Read `business.json` first:
- `stack.code_repos[]` — the set of repos to scan (in addition to the current git repo).
- `metrics.key_metrics[]` — the metrics to lead impact tables with.
- `company.revenue_model` / `company.product_name` — framing for the slide narrative.

Resolve the window:
- Default: **last 4 weeks ending today**.
- Override: `/leadership-product-weekly 2026-04-19 2026-05-19` (start, end).

Bind:
- `START_DATE` → start of window (default: today − 28 days, midnight local)
- `END_DATE` → end of window (default: today, 23:59 local)
- `MONTH_TAG` → e.g. "May '26, Week 3" derived from `END_DATE`'s month + ISO week-of-month

---

## Step 1 — Resolve repos

Build the repo set from `business.json` → `stack.code_repos[]`, plus the current git repository:

```bash
source .env 2>/dev/null
# Current repo (always included)
CURRENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null)
echo "current: $CURRENT_REPO"

# Additional repos come from business.json → stack.code_repos[] (paths or clone URLs).
# Parse them and resolve each to a local checkout path. If a repo is a remote URL with no
# local checkout, either skip it (note it in the footer) or shallow-clone to a temp dir.
python3 - <<'PY'
import json, pathlib
b = json.loads(pathlib.Path("business.json").read_text())
for r in b.get("stack", {}).get("code_repos", []):
    print(r)
PY
```

If `stack.code_repos[]` is empty, scan only the current repo and note in the footer that no additional repos were configured (suggest the user add them to `business.json`).

**Exclude from analysis** (infra/tooling, not user-visible): apply the business's own conventions. As defaults, exclude repos whose name/role indicates they are not user-facing — internal AI tooling/automation, analytics/ETL jobs, QA-doc-only repos, config/secrets repos, boilerplate/template repos, and data-science/research repos. If `business.json` tags repos with a role/visibility attribute, use that; otherwise infer from the repo name and confirm ambiguous ones with the user.

**Include**: every user-facing repo — mobile apps, user-facing backends/services, and web apps.

---

## Step 2 — Gather git ships (parallel per repo)

For each included repo, fetch commits merged to the default branch in the window. **Run in parallel batches of 5-6 repos.**

```bash
cd "$REPO_PATH"
git fetch origin --quiet 2>/dev/null
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main

git log "origin/$DEFAULT_BRANCH" \
  --since="${START_DATE}T00:00:00" --until="${END_DATE}T23:59:59" \
  --format="%h | %s | %aN | %ai" --no-merges
```

Aggregate to a table: `{repo, sha, subject, author, date, jira_key}`. Extract `jira_key` from commit messages (`${PROJECT_KEY}-\d+` pattern).

---

## Step 3 — Pull Jira Done + In Progress

```bash
cd $(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Shipped (Done) in window
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND status = Done AND resolved >= ${START_DATE} AND resolved <= ${END_DATE} ORDER BY resolved DESC" \
  --max-results 100

# Items updated to Done in window (catches items resolved earlier but ship-dated here)
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND status = Done AND updated >= ${START_DATE} AND updated <= ${END_DATE} ORDER BY updated DESC" \
  --max-results 100

# In flight — for the "In Design / In Flight" slide
python3 tools/jira-api.py search \
  "project = ${PROJECT_KEY} AND status in ('In Progress', 'In Design', Testing) AND updated >= ${START_DATE} ORDER BY updated DESC" \
  --max-results 60
```

Dedupe across all three queries by issue key.

**Filter labels to skip** (infra/process tickets): `retro`, `self-improve`, `devops-only`, `ci`, `monitoring`, `tooling`.

**Boost labels** (definitely include): any goal/execution tags your team uses, plus `revenue`, `growth`, `retention`, `activation`, `churn`, and labels matching your `metrics.key_metrics[]` themes.

---

## Step 4 — Classify each item

Walk every Jira issue + every git-only commit cluster and tag with **one of**:

| Tag | Meaning | Include? |
|---|---|---|
| `user-visible` | Feature/UX/flow/offer change users see or feel | ✅ Yes |
| `bug-material` | Bug fix that materially changed user behavior (e.g. payment retry, missing notification) | ✅ Yes |
| `infra` | Backend perf, DB migration, dependency bump, refactor | ❌ Skip |
| `tooling` | CI, monitoring, scripts | ❌ Skip |
| `test` | Test additions/changes only | ❌ Skip |
| `devops` | Infra/deploy/config | ❌ Skip |

Use the Jira `summary + description + labels + epic name` + commit-message text to classify. When ambiguous, lean **include** — the user can prune at the slide review.

---

## Step 5 — Group by theme

Bucket every included item into a theme. Use the same theme buckets as your other reporting skills so themes stay consistent across decks. Derive the buckets from `metrics.key_metrics[]` and `company.revenue_model`; as generic defaults:

1. **Monetization** — plans, pricing, conversion flow, checkout, refunds, offers
2. **Retention & churn** — loyalty, renewals, win-back, account-save flows
3. **Activation (first value)** — onboarding, first-use flow, guidance
4. **Core product** — the main user workflow of `company.product_name`
5. **Growth loops** — referral, promo codes, campaigns
6. **Cross-platform / platform-specific** — Android-only, iOS-only, Web changes
7. **Other / one-offs** — anything that doesn't fit (call this out — repeat offenders mean we need a new theme bucket)

---

## Step 6 — Measure impact for top 3-5 items (the hard part)

Pick the 3-5 items with the highest potential impact (revenue-relevant, retention-relevant, large user reach, or tagged with a goal label). For each, **run a query against the business's analytics source** (`stack.analytics`) to measure actual impact.

Reuse query patterns from existing skills where applicable:

| Item type | Query pattern source |
|---|---|
| Offer / discount / promo program | `.claude/skills/audit-offers/SKILL.md` (segment-aware classification) |
| Plan / page-level experiment | page-level analytics tables (served views, conversions, conv %, value-per-view) |
| Core-workflow change | the relevant event/transaction tables aggregated by week |
| Activation / first-use | cohort: new users in week N who reached first value within 7/14 days |
| Cross-platform impact | events joined on `deviceType` / platform |

**Required metric shape:** for each item, produce a small table the slide can show:

```
| <segment / week / page> | <count> | <conv% or rate> | <revenue or core-metric> |
```

If a query is too expensive or the metric isn't measurable yet (feature too new, < 1 week in prod), record it as "Impact: too early to measure (shipped <N> days ago)" and still include the item — leadership wants to know it's live.

---

## Step 7 — Render the slide content

Output a single markdown file at `weekly_reports/leadership-product-${END_DATE}.md` with this structure (each `## SLIDE N` block is one slide):

```markdown
# Leadership Weekly — Product Week
**Window:** {START_DATE} → {END_DATE} ({N} days)
**Generated:** {today}

---

## SLIDE 1 — Section divider

> **{Month} '{YY}, Product**

(full-bleed divider slide — title only)

---

## SLIDE 2 — Product Items (Done)

**Title:** Product Items (Done)

- **{Item 1 title}** — {1-line what shipped + 1-clause impact/learning}
- **{Item 2 title}** — {...}
- **{Item 3 title}** — {...}
- **{Item 4 title}** — {...}
- **{Item 5 title}** — {...}

(Max 5-7 bullets. Lead with the strongest. Bold title, short prose, no nested bullets.)

---

## SLIDE 3 — Product Items (In Design / In Flight)

**Title:** Product Items (In Design)

1. **{Item title}** — {1-2 lines on what it does and why}
2. **{Item title}** — {...}
3. **{Item title}** — {...}

(Numbered. Max 5 items. Focus on items with a clear hypothesis leadership should know is coming.)

---

## SLIDE 4..N — Per-experiment data slides

For each of the 3-5 highest-impact items from Step 6, render ONE slide like this:

**Title:** {Short experiment name}

**Observation (one line):** {The hypothesis or finding}

**Data table:**

| <col1> | <col2> | <col3> | <col4> |
|---|---|---|---|
| ... | ... | ... | ... |

**Takeaway (one line, optional):** {Only if the data has a clear directional read}

---

## SLIDE N+1 — Window summary (optional)

If many small items shipped that don't merit their own slide, append a single "Also shipped" appendix slide:

**Title:** Also shipped this window

| Item | Theme | Ship date | Status |
|---|---|---|---|
| ... | ... | ... | ... |

(Max 10 rows. Anything more = signal that the Done slide should be longer.)

---

## Footer (not a slide — internal context for the user)

- Repos with activity: {N} of {total}
- Total commits to main: {N}
- Jira items resolved: {N}
- User-visible items shipped: {N}
- Top theme by volume: {theme}
- Items with measured impact: {N}
- Items too early to measure: {N}
```

### Tone rules

- **Numbers, not adjectives.** "+27% conv lift" beats "improved conversion."
- **Past tense for shipped, present-continuous for in-flight.** "Reduced offer from 7 → 3 days" / "Building activation flow"
- **No emojis.**
- **No git internals.** Never write "PR #89 merged" or "${PROJECT_KEY}-15366 closed" on slides — those are internal. Use product names.
- **One slide = one idea.** If a slide needs more than 6 short bullets, split it.

---

## Step 8 — Hand-off

Print the markdown file path and a summary block to the user:

```
Slides drafted: weekly_reports/leadership-product-{END_DATE}.md

Slide count: {N}
- 1 section divider
- 1 Done list slide
- 1 In Design list slide
- {3-5} per-experiment data slides
- {0-1} "also shipped" appendix

Highest-impact items chosen:
1. {Item name} — {1-line impact}
2. {Item name} — {1-line impact}
3. {Item name} — {1-line impact}

Items skipped as "too early to measure": {N}
Items skipped as infra/tooling: {N}

Review and paste into your slide deck.
```

Do NOT auto-publish to Google Slides or Confluence by default — this is a slide-content generator. The user reviews the markdown and pastes manually.

---

## Step 9 — Optional: Confluence backup

If the user passes `--confluence` (or asks to publish as a Confluence page instead of `.md`), publish under a dedicated weekly-reports folder in your configured Confluence space so all weekly deck content lives in one place:

- spaceId: `${CONFLUENCE_SPACE_KEY}` (from .env)
- parentId: `${CONFLUENCE_PARENT_PAGE_ID}` (from .env)
- cloudId: `${CONFLUENCE_CLOUD_ID}` (from .env)
- Title pattern: `Leadership Weekly — Product — {Month} '{YY} ({START_DATE} to {END_DATE})`.

Publish via the v2 REST API using `ATLASSIAN_EMAIL` + `ATLASSIAN_API_TOKEN` from `.env`. Convert the markdown with the `markdown` lib (`extensions=['tables','fenced_code','sane_lists']`) and **strip internal `<!-- -->` comment blocks** before posting (they hold tooling notes, not slide content).

**Idempotency — update, do NOT delete+recreate.** The v2 API rejects creating a page whose title matches a just-deleted (trashed) page, so delete+`POST` fails with a `KeyError: 'id'` on the create. Instead: list `GET /wiki/api/v2/pages/{PARENT}/children`, find the child whose `title` matches; if found `PUT /wiki/api/v2/pages/{id}` with `version.number = current+1`; else `POST /wiki/api/v2/pages`.

---

## Self-check before printing

- [ ] Every item is classified (user-visible / bug-material / infra / tooling / test / devops)
- [ ] Repos excluded as infra/tooling/non-user-facing have ZERO items in the output
- [ ] Each per-experiment slide has a real data table (or explicitly says "too early to measure")
- [ ] Done list ≤ 7 bullets; In Design list ≤ 5 items
- [ ] No emojis, no PR numbers, no Jira keys on slides (keys live in the markdown comments only)
- [ ] Window dates match what the user asked for
- [ ] Goal-tagged items are prioritised in the Done list

---

## Known gotchas

- **PRs vs Jira keys.** Many commits don't reference Jira. Cluster orphan commits by file path + message pattern and bring them to the Jira list manually. Don't double-count.
- **Pre-merge work invisible.** Branches not yet merged to the default branch won't appear. This is intentional — Product week shows what's *in production*, not what's *in progress*. The In Design / In Flight slide picks up branch work via the Jira "In Progress" query.
- **Cross-platform double-counting.** A single feature often ships in 3-4 repos (backend + android + ios + web). Group by Jira parent or epic so it shows up as ONE item on the slide.
- **Offer classification.** Use the `audit-offers` segment-aware logic, not raw surface-trigger strings — the surface trigger lies. See `.claude/skills/audit-offers/SKILL.md`.
- **Metric-rollup lag.** The latest week may not have rolled-up metrics yet. Prefer raw queries against the source tables for very recent windows.

---

## Sibling skills (full weekly deck workflow)

If the user wants to produce **the entire deck** for a given week, run these in order:

| Section | Skill | What it produces |
|---|---|---|
| Monthly data | `/monthly-analysis` | MoM comparison report |
| Churn | `/sub-cohort` + churn product-items impact analysis | Churn slides |
| **Product** | **`/leadership-product-weekly`** | This skill |
| Marketing | `/audit-google-ads` + `/audit-meta` + `/email-roi` | Marketing performance slides |
</content>
