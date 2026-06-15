---
name: prioritize
description: "General backlog prioritization — pulls the backlog from Jira, scores each item with RICE or ICE, ranks them, and recommends what to build next. Scores are tied to the business's own metrics from business.json (north star, key metrics, revenue model), assumptions are stated explicitly, and unknowns are confirmed with you rather than invented. Optionally writes scores back to Jira and publishes a summary to Confluence (draft-before-publish). Use when asked to 'prioritize backlog', 'rank the backlog', 'what should I build next', 'rice scoring', 'ice scoring', or '/prioritize'. (Distinct from /audit-offers, which is an offer/discount ROI audit.)"
argument-hint: "[--framework rice|ice] [--top N] [--epic KEY] [--no-publish]"
allowed-tools: [Read, Write, Bash]
---

# /prioritize — Backlog Prioritization (RICE / ICE)

Pull the backlog from Jira, score every candidate with a transparent prioritization framework, rank them, and tell the user what to build next — with each recommendation tied to the business's own metrics.

**Iron Law: NEVER INVENT NUMBERS.** Every Reach / Impact / Confidence / Effort value is derived from a real signal (story points, labels, issue type, `business.json`) or confirmed by the user. State every assumption inline. A score with a fabricated input is worse than no score.

---

## Step 0: Bootstrap

Read silently:
1. `.env` to load:
   - `JIRA_PROJECT_KEY` (referred to as `PROJECT_KEY` below)
   - `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_PARENT_PAGE_ID`, `CONFLUENCE_CLOUD_ID`
2. `business.json` — required context. Pull out:
   - `metrics.north_star` — the single metric the ranking should serve.
   - `metrics.key_metrics[]` — the metrics Impact is measured against.
   - `company.revenue_model` — `subscription`, `transaction`, `ads`, or a mix; shapes how Impact is interpreted.
   - `company.target_users` — used for Reach sizing.
3. `team.json` — roster, to size Effort against real capacity and name owners in recommendations.
4. Parse `$ARGUMENTS`:
   - `--framework rice|ice` — scoring model. Default: `rice`.
   - `--top N` — how many items to recommend. Default: `5`.
   - `--epic KEY` — scope the backlog to one epic's children only.
   - `--no-publish` — console output only; never touch Jira or Confluence.

Constants:
- JIRA_CLI: `python3 tools/jira-api.py`

If `business.json` has no `north_star` or empty `key_metrics`, ask the user once for the one metric this ranking should optimise, then continue (and offer to write it back to `business.json`).

---

## Step 1: Pull the Backlog

Default backlog query (statuses are configurable — confirm with the user if their board uses different names):

```bash
python3 tools/jira-api.py search --max-results 100 \
  --fields summary,status,assignee,priority,labels,issuetype,parent,created,updated \
  "project = ${PROJECT_KEY} AND status in (Backlog, 'To Do', 'Selected for Development') ORDER BY priority DESC, created ASC"
```

Scope to one epic if `--epic KEY` was passed:

```bash
python3 tools/jira-api.py search --max-results 100 \
  --fields summary,status,assignee,priority,labels,issuetype,parent,created,updated \
  "project = ${PROJECT_KEY} AND parent = ${EPIC_KEY} AND status in (Backlog, 'To Do', 'Selected for Development') ORDER BY priority DESC"
```

Story points usually live in a custom field (e.g. `customfield_10016`). If Effort must come from points, add that field to `--fields` and read it. If points are absent, fall back to issue type + priority as a t-shirt Effort proxy and flag that it is a proxy.

---

## Step 2: Score Each Item

### RICE (default) — score = (Reach × Impact × Confidence) / Effort

Derive each input from a real signal. Use these scales (state them in the output so the numbers are interpretable):

| Input | Scale | Derive from |
|---|---|---|
| **Reach** | # of users/events per quarter (or a 1–10 proxy) | `company.target_users` size, audience labels (`all-users`, `power-users`, `new-users`), issue scope in the summary |
| **Impact** | 3 = massive, 2 = high, 1 = medium, 0.5 = low, 0.25 = minimal | Effect on `metrics.north_star` / `metrics.key_metrics`; revenue/retention/activation labels; issue type (a revenue Story usually beats a minor Bug) |
| **Confidence** | 100% / 80% / 50% (high / medium / low) | Evidence strength: linked data/PRD/experiment = high; reasoned estimate = medium; guess = low |
| **Effort** | person-weeks (or story points) | Story points / estimate field; else issue type + priority proxy |

### ICE (`--framework ice`) — score = Impact × Confidence × Ease

Lighter alternative — drop Reach and Effort, replace Effort with **Ease** (1–10, where 10 = trivial). Use the same Impact and Confidence derivations as above.

### Confirm unknowns — do not guess

After a first pass, list every item where a critical input had no real signal (e.g. no story points AND no useful labels). Present these as a short batch and ASK the user to confirm or fill them before finalising — e.g. "JIRA-142 'Add referral bonus' — no points; I'm assuming Effort = 3 wk and Impact = 2 (revenue). Confirm or correct?" Apply their answers, then compute final scores.

---

## Step 3: Rank & Output

### Console — ranked table

Sort by score descending. Show the framework and scales used at the top.

```
## Backlog Prioritization — ${PROJECT_KEY} (RICE) — {N} items
Scales: Reach=users/qtr · Impact 0.25–3 · Confidence 50/80/100% · Effort person-weeks

| # | Item                          | Key       |  R   |  I  |  C   | E  | Score | Rationale                                   |
|---|-------------------------------|-----------|------|-----|------|----|-------|---------------------------------------------|
| 1 | Add referral bonus            | PROJ-142  | 5000 | 2.0 | 0.8  | 3  | 2667  | Drives north star (signups); revenue label  |
| 2 | Fix checkout crash            | PROJ-118  | 3000 | 3.0 | 1.0  | 1  | 9000  | High-impact bug, low effort, certain        |
```

(For ICE: columns become I · C · Ease · Score.)

### Recommended next

```
### Recommended next: top {N}
1. PROJ-118 — Fix checkout crash — biggest score; protects {north_star}, ~1 wk.
2. PROJ-142 — Referral bonus — strongest lever on {a key_metric}; needs PRD to raise confidence.
...
```

Each line: one-sentence justification explicitly naming the `business.json` metric it serves. Note any item whose rank depends on an assumption the user only confirmed verbally.

---

## Step 4: Write Back (optional — explicit confirmation + preview first)

Skip entirely if `--no-publish`. Otherwise ask the user **before** any side effect and show a preview (draft-before-publish):

### 4a. Scores back to Jira
Offer either a label or a comment per item. Preview the exact change, then on confirmation:

```bash
# Rank label (e.g. for the top items)
python3 tools/jira-api.py edit PROJ-118 --labels "$(existing labels),priority-rank-1"

# Or a score comment (always tagged)
python3 tools/jira-api.py comment PROJ-118 \
  "RICE score: 9000 (R=3000, I=3.0, C=1.0, E=1). Rank #1. Serves north star: {north_star}.

Generated by AI-PM Operator"
```

Preserve existing labels when editing (read them from Step 1 and append). Never overwrite.

### 4b. Confluence summary
Idempotent: find-or-update by title in `${CONFLUENCE_SPACE_KEY}` (cloudId `${CONFLUENCE_CLOUD_ID}`, parent `${CONFLUENCE_PARENT_PAGE_ID}`). Preview the page body, then publish on confirmation.

- Title: `Backlog Prioritization — ${PROJECT_KEY} — {date}`
- Sections: Method & scales · Ranked table · Recommended next {N} · Assumptions & open questions
- Footer line on the page: `Generated by AI-PM Operator`

---

## Final: Report to User

Concise summary:
- "{N} backlog items scored with {RICE|ICE}."
- The top {N} recommendations with their one-line justifications.
- Any assumptions the user should sanity-check.
- Links to anything written (Jira labels/comments, Confluence page) — or "console only" if `--no-publish`.
- "Re-run after refining estimates or confirming the flagged assumptions for a tighter ranking."
