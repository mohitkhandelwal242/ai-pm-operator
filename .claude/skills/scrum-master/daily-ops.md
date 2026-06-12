# Daily Ops — Kanban Hygiene (runs every day)

Automated daily hygiene pass. Fixes three recurring problems without human intervention:
1. Unassigned tickets → assign to Product Manager
2. Stale tickets (10+ days no progress) → nudge comment
3. Throughput report (last 7d + last 30d, with optional sizing)

Always use `tools/jira-api.py` for ALL Jira operations.

---

## Step 0: Bootstrap

1. Read `.env` to load environment variables: `JIRA_PROJECT_KEY` (referred to as `PROJECT_KEY` below).
2. Read `team.json` from the project root.
3. Find the Product Manager / Project Manager in the team list (whose role contains "Product Manager" or "Project Manager"). Note their `atlassianId`, `email`, and `name`. If not found, default to the first member in `team.json`.
4. Read `scrum-state.md` to load `already_actioned` — never repeat actions on the same ticket for the same reason within 10 days.

---

## Step 1: Assign Unassigned Tickets to Product Manager

### Fetch unassigned open tickets
```bash
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND assignee is EMPTY AND created <= -1d ORDER BY created ASC" \
  --fields "summary,status,created,labels" \
  --max-results 50
```

### For each unassigned ticket NOT in `already_actioned`:
1. Assign to the Product Manager:
   ```bash
   python3 tools/jira-api.py edit ${KEY}-XXX --assignee "<PM_atlassianId>"
   ```
2. Add a comment with @mention of the Product Manager using ADF format:
   ```bash
   python3 tools/jira-api.py comment ${KEY}-XXX --adf '{
     "version": 1,
     "type": "doc",
     "content": [{
       "type": "paragraph",
       "content": [
         {"type": "text", "text": "Daily ops: no owner found — assigning to "},
         {"type": "mention", "attrs": {"id": "<PM_atlassianId>", "text": "@<PM_Name>"}},
         {"type": "text", "text": " to triage. Please assign to the right owner or close if not needed."}
       ]
     }]
   }'
   ```
3. Add to `already_actioned`: `${KEY}-XXX: assigned to PM (date)`

---

## Step 2: Nudge Stale Tickets (10+ days, no progress)

### Fetch stale open tickets
```bash
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND updated <= -10d ORDER BY updated ASC" \
  --fields "summary,status,assignee,updated,labels" \
  --max-results 100
```

### For each stale ticket NOT in `already_actioned`:
Infer the right person to tag:
- Match the ticket's summary keywords against `team.json` `domains` arrays to find the best-fit team member.
- If the assignee is already set and exists in `team.json`, tag them directly.
- If no match, fall back to the Product Manager.

Add a comment **with @mention** using ADF format:
```bash
python3 tools/jira-api.py comment ${KEY}-XXX --adf '{
  "version": 1,
  "type": "doc",
  "content": [{
    "type": "paragraph",
    "content": [
      {"type": "text", "text": "Are we doing anything on this? It'\''s been sitting here for X days with no update. "},
      {"type": "mention", "attrs": {"id": "<accountId>", "text": "@<Name>"}},
      {"type": "text", "text": " — please either move it forward or close it if it'\''s no longer relevant."}
    ]
  }]
}'
```
Replace `<accountId>` with the inferred person's `atlassianId` and `<Name>` with their display name.
Add to `already_actioned`: `${KEY}-XXX: stale nudge comment (date)`.

---

## Step 3: Throughput Report

### Sizing labels context
Sizing is optional via labels: `size-xs` (weight 1), `size-s` (weight 2), `size-m` (weight 3), `size-l` (weight 5), `size-xl` (weight 8).
If a ticket has no size label, count it in raw throughput only.

### Fetch completed tickets in last 7 days & last 30 days
Using `status changed to` Done or Deployment JQL:
```bash
# Last 7 days
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status changed to Done after -7d ORDER BY updated DESC" \
  --fields "summary,assignee,labels,issuetype" \
  --max-results 100

# Last 30 days
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status changed to Done after -30d ORDER BY updated DESC" \
  --fields "summary,assignee,labels,issuetype" \
  --max-results 200
```

### Calculate metrics
For each period (7d and 30d):
1. **Raw throughput**: total completed tickets
2. **Sized throughput**: sum of size weights for tickets with size labels
3. **By Developer**: who completed what
4. **By type**: breakdown by Bug, Story, Task
5. **Weekly average** (30d only): raw throughput / 4

---

## Step 4: Update State File
Append details to `scrum-state.md`.

---

## Step 5: Print Summary
Print a clean daily ops run summary in your output under 40 lines.
