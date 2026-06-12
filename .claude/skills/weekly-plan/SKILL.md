---
name: weekly-plan
description: "Weekly sprint planning and capacity review — pulls Jira tickets, reviews carry-overs, and assigns next-week priorities per team member. Use when asked about 'weekly plan', 'next week plan', 'friday planning', 'team priorities', or '/weekly-plan'."
argument-hint: "[--person name] [--no-publish]"
---

# Weekly Planning Coordinator

Every Friday or sprint transition, compile next week's plan by auditing Jira workload, reviewing team member capacity, and allocating high-priority items.

## Step 0: Bootstrap

1. Read `.env` to load environment variables:
   - `JIRA_PROJECT_KEY` (referred to as `PROJECT_KEY` below)
   - `CONFLUENCE_SPACE_KEY`
   - `CONFLUENCE_PARENT_PAGE_ID`
2. Read `team.json` from the project root.
3. Parse `$ARGUMENTS`:
   - `--person name` — plan for one specific team member only.
   - `--no-publish` — skip publishing to Confluence.

Constants:
- JIRA_CLI: `python3 tools/jira-api.py`

---

## Step 1: Gather Data

Run these Jira queries in parallel using `python3 tools/jira-api.py search`. Pass `--max-results 100`.

```bash
# In Progress (carry-overs)
python3 tools/jira-api.py search --max-results 100 --fields summary,status,assignee,priority,labels,created,updated,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = 'In Progress' ORDER BY priority DESC"

# To Do (candidates for next week)
python3 tools/jira-api.py search --max-results 100 --fields summary,status,assignee,priority,labels,created,updated,issuetype,parent \
  "project = ${PROJECT_KEY} AND status = 'To Do' AND priority in (Highest, High, Medium) ORDER BY priority DESC, created DESC"

# Recently completed
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
Group team-wide workload by epic/parent module. Classify issues by type (Bugs, Stories, Tasks).

### Per-Person Analysis
For each team member (using `team.json` roster):
1. **Carry-overs**: List their current "In Progress" items.
2. **Capacity Check**: If they have >=10 items, flag as overloaded and avoid adding new items.
3. **New Priorities**: From the "To Do" backlog, match items to their domains of expertise (from `team.json`). Suggest items up to 10 total items per person.
4. **Blocked Items**: Highlight any of their items that are blocked.

### Flags to Surface
- Team members with 0 items (idle).
- Team members with >10 items (overloaded).
- Blocked items >3 days old (check updated date).
- High/Highest priority unassigned items.

---

## Step 3: Generate Plan

Produce:
1. **Terminal Summary**: Under 50 lines showing Epic summaries, per-person items count, and key warnings/flags.
2. **Confluence Document**: A beautifully formatted HTML document listing:
   - High-level project metrics
   - Epic/module groupings
   - Detailed per-person priority lists with clickable Jira links
   - Highlighted flags and blockers

---

## Step 4: Deliver

1. **Publish to Confluence** (unless `--no-publish` is passed):
   - Publish page under Space: `CONFLUENCE_SPACE_KEY`, Parent ID: `CONFLUENCE_PARENT_PAGE_ID`.
   - Title format: `Weekly Plan — {Date Range}`.
2. **Assignments**: Propose owner suggestions for unassigned items.
3. **Report to User**: Output a brief completion log with a link to the Confluence page.
