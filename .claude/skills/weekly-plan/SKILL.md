---
name: weekly-plan
description: "Weekly sprint planning and capacity review — pulls Jira tickets, reviews carry-overs, and assigns next-week priorities per team member. Use when asked about 'weekly plan', 'next week plan', 'friday planning', 'team priorities', or '/weekly-plan'."
argument-hint: "[--person name] [--no-publish]"
allowed-tools: [Read, Write, Bash, WebSearch]
---

# Weekly Planning Coordinator

Every Friday or sprint transition, compile next week's plan by auditing Jira workload, reviewing team member capacity, and allocating high-priority items.

**Iron Law: FOCUS OVER VOLUME.** Each person gets up to 10 items max. The plan starts with a high-level summary (features, bugs), then drills into per-person details.

---

## Step 0: Bootstrap

Read silently:
1. `.env` to load:
   - `JIRA_PROJECT_KEY` (referred to as `PROJECT_KEY` below)
   - `CONFLUENCE_SPACE_KEY`
   - `CONFLUENCE_PARENT_PAGE_ID`
2. `team.json` — full roster with domains, aliases, Jira accountIds.
3. Parse `$ARGUMENTS`:
   - `--person name` — plan for one specific team member only.
   - `--no-publish` — skip Confluence.

Constants:
- JIRA_CLI: `python3 tools/jira-api.py`

Build the person list from `team.json`. For each person, note their `domains` array for smart assignment.

---

## Step 1: Gather Data

Run these Jira queries in parallel using `python3 tools/jira-api.py search`. **Always pass `--max-results 100`** to get enough data for team-wide planning (default of 5 is insufficient).

Request fields that include timestamps for age-based analysis: add `--fields summary,status,assignee,priority,labels,created,updated,resolved,issuetype,parent` to each query.

```bash
# In Progress (carry-overs)
python3 tools/jira-api.py search --max-results 100 --fields summary,status,assignee,priority,labels,created,updated,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = 'In Progress' ORDER BY priority DESC"

# To Do (candidates for next week)
python3 tools/jira-api.py search --max-results 100 --fields summary,status,assignee,priority,labels,created,updated,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = 'To Do' AND priority in (Highest, High, Medium) ORDER BY priority DESC, created DESC"

# Recently completed (context for what shipped)
python3 tools/jira-api.py search --max-results 50 --fields summary,status,assignee,priority,resolved,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = Done AND resolved >= -7d ORDER BY resolved DESC"

# Blocked items
python3 tools/jira-api.py search --max-results 50 --fields summary,status,assignee,priority,labels,created,updated,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = 'In Progress' AND labels in (blocked, on-hold)"

# Unassigned items
python3 tools/jira-api.py search --max-results 50 --fields summary,status,assignee,priority,labels,created,issuetype,parent \
  "project = ${PROJECT_KEY} AND status in ('To Do', 'In Progress') AND assignee is EMPTY ORDER BY priority DESC"
```

---

## Step 2: Analyze

### High-Level Summary First
Before per-person plans, produce a team-wide summary:
1. **Group issues by epic/parent** — use the `parent` field to cluster related Jira issues under their epic.
2. **Classify by type**: features (Story/Task under epics), bugs (Bug type), tech debt, ops.
3. **Summarize**: "Next week: 3 new features in development, 2 bugs to fix, 1 tech debt item".
4. **List features by name** with their epics and constituent Jira issues (one feature/epic can have 3-4 child issues).

### Per-Person Analysis
For each team member:
1. **Carry-overs** — list their In Progress items (these continue next week).
2. **Capacity check** — if carry-overs >= 10, flag as overloaded; do not add new items.
3. **New priorities** — from To Do backlog, match items to person's domains (from `team.json`). Suggest enough to fill up to ~10 total items.
4. **Blocked items** — flag any of their items that are blocked, with reason if available from labels/comments. Use the `updated` timestamp to compute age.

### Flags to Surface
- Team members with 0 items (idle — need assignment).
- Team members with >10 items (overloaded — need re-prioritization).
- Blocked items >3 days old (compute from `updated` field — stale blocks).
- Unassigned items with High/Highest priority (need owners).
- Items carried over >2 weeks (compute from `created`/`updated` — chronic carry-over).

---

## Step 3: Generate Plan

### Console Summary (under 50 lines)

```
## Weekly Plan — {next week date range}

### Summary
- 3 features in development, 2 bugs to fix, 1 tech debt
- Features: Feature A (EPIC-${PROJECT_KEY}-XXX), Feature B (EPIC-${PROJECT_KEY}-YYY)
- Bugs: Crash fix (${PROJECT_KEY}-AAA)

### Feature: Feature A (Epic ${PROJECT_KEY}-XXX)
| Key      | Summary                    | Assignee | Status      |
|----------|----------------------------|----------|-------------|
| ${PROJECT_KEY}-XX01 | Backend handler            | Kavish   | In Progress |
| ${PROJECT_KEY}-XX02 | Android client             | Umesh    | To Do       |

### {Person Name} ({alias}) — {N items}
| # | Key      | Summary                          | Status      | Priority |
|---|----------|----------------------------------|-------------|----------|
| 1 | ${PROJECT_KEY}-XXXX | Carry-over: fix bug              | In Progress | High     |
| 2 | ${PROJECT_KEY}-YYYY | New: implement feature           | To Do       | Medium   |

### Flags
⚠️ Umesh has 12 items — needs re-prioritization
⚠️ ${PROJECT_KEY}-12345 blocked for 5 days — unblock before Monday
⚠️ 3 unassigned High-priority items need owners
```

### Confluence HTML
Structured plan with:
- **High-level summary** at top: feature count, bug count, feature names with epics.
- **Feature/epic sections**: grouped Jira issues under each epic.
- **Per-person sections**: carry-over vs new items clearly marked, links to each Jira issue.
- Flags and recommendations at bottom.
- Week-over-week comparison: items planned last week vs completed.

---

## Step 4: Deliver

1. **Publish to Confluence** (unless `--no-publish`):
   - Space: `CONFLUENCE_SPACE_KEY`, Parent: `CONFLUENCE_PARENT_PAGE_ID`.
   - Title: `Weekly Plan — {date range}`.
   - Format: HTML storage format.
2. **Unassigned items** — suggest assignments based on `team.json` domains.
3. **Blocked items** — suggest creating follow-up Jira comments to unblock.

---

## Final: Report to User

Concise summary:
- High-level: "{N} features, {M} bugs, {P} tech debt items for next week"
- Feature names and their epics
- Number of carry-overs vs new items
- Any flags (overloaded, blocked, unassigned)
- Link to Confluence plan (omit if `--no-publish`)
- "Review and adjust assignments before Monday"
