---
name: scrum-master
description: "Kanban board manager that audits flow health, finds blockers, follows up on stale items, and keeps Jira clean. Use when asked to run scrum, check blockers, do a sweep, check stale issues, or '/scrum-master', '/scrum'. Maintains persistent state in scrum-state.md across runs. Has a daily-ops subskill (see daily-ops.md) that auto-assigns unassigned tickets to the PM, nudges stale tickets, and produces throughput reports."
argument-hint: "[--focus flow-health|blockers|stale-issues|pr-review-lag|dod-gaps|backlog-grooming|throughput|confluence-hygiene] [--no-email]"
allowed-tools: [Read, Write, Bash, WebSearch]
---

# Kanban Flow Manager

Automated Kanban sweep: audit flow health, surface blockers, follow up on stale items, keep Jira clean. The project uses **Kanban** (not Scrum) — no sprints, no sprint boundaries. Analysis is flow-based: work-in-progress (WIP), cycle time, throughput, and stall detection across all open issues.

## Subskills

This skill has a **daily-ops** subskill designed to run every day automatically:
- **Trigger**: "run daily ops", "daily kanban", "daily jira ops", or any morning routine
- **Instructions**: See [daily-ops.md](daily-ops.md) in this directory
- **What it does**:
  1. Auto-assigns all unassigned tickets to the PM for triage
  2. Adds "Are we doing anything?" nudge comment on tickets stale 10+ days
  3. Generates throughput report (7d + 30d) with T-shirt sizing support

When the user asks to run daily ops, load and follow `daily-ops.md` instead of the main skill flow.

---

## Step 0: Bootstrap

### 0a) Read configuration & team roster
- Read `.env` to load environment variables: `JIRA_PROJECT_KEY` (referred to as `PROJECT_KEY` below).
- Read `team.json` from the project root. Extract for each member:
  - `name`, `alias`, `atlassianId`, `email`, `role`, `domains`
- Build a lookup: `atlassianId → name` (used to humanize Jira assignee fields).
- Find the Product Manager / Project Manager in the roster (role contains "Product Manager" or "Project Manager"). Store their `atlassianId`, `name`, and `email` for triages and escalations.
- Find the Coordinator / PM Support member in the roster (role contains "Coordinator" or "Support"). Store their `email` for CC.

### 0b) Read state file
- Read `scrum-state.md` from the project root (if it exists).
- Extract:
  - `last_run` timestamp
  - `open_blockers` — list of `{ key, description, found_date }`
  - `follow_up_items` — list of `{ key, action, due_date, done: bool }`
  - `already_actioned` — set of `{ key, action_taken }` (never repeat these)
  - `next_run_focus` — the area to prioritize this run
  - `past_insights` — historical observations
- If no state file exists, initialize all as empty and set `next_run_focus = "flow-health"`.

### 0c) Determine focus
- Use the `--focus` flag if passed. Otherwise, use `next_run_focus` from state as the **primary** audit area for this run.
- Rotate through areas to ensure full coverage across runs:
  ```
  flow-health → blockers → stale-issues → pr-review-lag → dod-gaps → backlog-grooming → throughput → confluence-hygiene → ceremony-reminders → flow-health → ...
  ```
- After completing the primary focus, do a **quick scan** of the remaining areas (lighter checks).

---

## Step 1: Fetch Live Kanban Data

Run all Jira queries in parallel for speed. Use `tools/jira-api.py` for ALL Jira operations.

```bash
# All open issues (entire backlog — Kanban has no sprint boundary)
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) ORDER BY updated ASC" \
  --fields "summary,status,assignee,priority,labels,updated,created" \
  --max-results 100

# Blocker-labeled issues
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND (labels=blocker OR labels=impediment)" \
  --fields "summary,status,assignee,updated,labels" \
  --max-results 50

# In-Review issues (PR review lag)
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status='In Review' ORDER BY updated ASC" \
  --fields "summary,assignee,updated,labels" \
  --max-results 50

# Stalled issues — not updated in 10+ days, not done
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND updated <= -10d ORDER BY updated ASC" \
  --fields "summary,assignee,updated,status,priority" \
  --max-results 100

# Deployment-status issues (common stall point)
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status=Deployment ORDER BY updated ASC" \
  --fields "summary,assignee,updated,priority" \
  --max-results 100

# Unassigned open issues (flow risk)
python3 tools/jira-api.py search \
  "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND assignee is EMPTY AND created <= -7d ORDER BY created ASC" \
  --fields "summary,created,labels,issuetype,status" \
  --max-results 30
```

Store all results for the audit steps below.

---

## Step 2: Primary Focus Audit

Run the audit for `next_run_focus`. Be thorough on this area.

### Focus: `flow-health`
1. **WIP overload**: Count open issues per assignee across all In-Progress statuses (In Progress, In Review, Deployment). Flag if anyone owns >5 open items.
2. **Stalled Deployment queue**: Count issues in `Deployment` status. Anything >14 days in Deployment is suspect.
3. **Unassigned open issues**: Any issue open >7 days with no assignee is a flow risk.
4. **Age distribution**: Group all open issues by age bucket (0-7d, 7-30d, 30-90d, >90d). Flag the >90d bucket as critical.

Actions:
- For WIP-overloaded assignees: add to `follow_up_items` for human to rebalance.
- For Deployment issues >30 days not in `already_actioned`: add a nudge comment asking to close or escalate.
- For unassigned issues >30 days: add label `needs-triage` if not already present.

### Focus: `blockers`
Check:
1. Issues labeled `blocker` or `impediment`.
2. Issues where recent comments contain words: `blocked`, `waiting on`, `dependency`, `can't proceed`, `stuck`.
3. Open blockers from previous state — check if they've been resolved (status changed to Done).

Actions:
- For new blockers not in `already_actioned`: add comment + escalation note.
  ```bash
  python3 tools/jira-api.py comment ${KEY}-XXX "Kanban sweep: this issue is flagged as a blocker. @assignee — what's needed to unblock? I'll follow up in 24h."
  ```
- For blockers resolved since last run: remove from `open_blockers`, add to `past_insights`.
- For blockers open >3 days: add to `follow_up_items` with human escalation.

### Focus: `stale-issues`
**Step 0 — Ask threshold before running:**
Before running, ask: "How many days without update should count as stale? (default: 10 days)"
Use the answer (or 10 if no answer) as `STALE_DAYS`.

JQL: `project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND updated <= -${STALE_DAYS}d ORDER BY updated ASC`

**Workflow — ask before emailing, one person at a time:**
1. Fetch all stale issues and group by assignee.
2. Show a summary: "Found X stale tickets across N people: [Name1: N tickets, Name2: N tickets, ...]"
3. For each assignee (one at a time), show their ticket list and ask: "Send email to [Name] for X tickets? (yes/skip)"
4. Only send after confirmation — never auto-send.
5. Email format: individual per person, CC the Coordinator (`COORDINATOR_EMAIL`) and PM (`PM_EMAIL`).
6. Email asks them to close done tickets or add a comment on anything still pending, with a 3-day deadline.
7. Do NOT use the word "sprint" in emails — the project uses Kanban.
8. Add each emailed assignee to `already_actioned` so they aren't re-emailed on the next run.

### Focus: `pr-review-lag`
Find issues in "In Review" status with no update in 2+ days.
For each lagging review not in `already_actioned`:
1. Comment:
   ```bash
   python3 tools/jira-api.py comment ${KEY}-XXX "Kanban sweep: this PR has been in review for 2+ days with no update. Could a reviewer please prioritize this to keep flow moving?"
   ```
2. Add to `follow_up_items` with assignee's name.

### Focus: `dod-gaps`
Find stories that are "Done" but missing QA sign-off, or stories "In Review"/"Done" with empty description.
For each gap not in `already_actioned`:
1. Comment:
   ```bash
   python3 tools/jira-api.py comment ${KEY}-XXX "Kanban sweep: DoD check — this story appears to be missing acceptance criteria or QA sign-off. Please update before marking Done."
   ```

### Focus: `backlog-grooming`
Find open issues that are unassigned and older than 7 days.
Actions:
- Group by age (7-14d, 14-30d, >30d).
- For items >30d old and low priority, add label `needs-triage`:
  ```bash
  python3 tools/jira-api.py edit ${KEY}-XXX --labels "needs-triage"
  ```
- Add oldest 5 ungroomed items to `follow_up_items` for the PM to review.

### Focus: `throughput`
Measure flow throughput:
1. Count issues moved to Done in the last 7 days: `project=${PROJECT_KEY} AND status=Done AND updated >= -7d`.
2. Count issues moved to Done in the previous 7 days (7-14d ago) for trend comparison.
3. Count currently in-flight (In Progress + In Review + Deployment).
4. Compute: throughput trend (up/flat/down week-over-week).
5. Flag if in-flight count is >3x the weekly throughput (WIP accumulation risk).

Generate a flow insight and add to `past_insights`.

### Focus: `confluence-hygiene`
If Confluence variables are set, search for recent team pages (last 14 days) in the team space:
CQL: `space=${CONFLUENCE_SPACE_KEY} AND type=page AND created>=-14d ORDER BY created DESC`
Check if they link back to Jira issues. Flag pages with no Jira links as potentially unlinked, and add to `follow_up_items` for the PM.

### Focus: `ceremony-reminders`
Based on today's day of week:
- **Monday**: Weekly kickoff — surface top 3 blocked/stalled items for the team to focus on. Flag any issues that have been In Progress >14 days without movement.
- **Wednesday**: Mid-week flow check — is WIP accumulating? Any new blockers?
- **Friday**: End-of-week wrap — how many items moved to Done? What's still stuck?
- **Daily**: Standup context — who has blockers?

---

## Step 3: Quick Scans (Secondary Areas)

After the primary focus, do lighter checks on the other areas. Take action only if something is clearly broken and not in `already_actioned`.

Quick scan checklist:
- [ ] Any new blocker labels added since last run?
- [ ] Any issue moved to In-Progress with no assignee?
- [ ] Any Done issue that was reopened?
- [ ] Any issue with >5 comments in the last 24h?
- [ ] Deployment queue size vs last run — growing or shrinking?

---

## Step 4: Follow-up Resolution Check

Review `follow_up_items` from previous state:
For each open follow-up:
1. Fetch current status of that issue: `python3 tools/jira-api.py search "issue=${KEY}-XXX" --fields "status,updated,assignee"`
2. If issue is now Done/Resolved: mark follow-up as complete in state.
3. If issue is past due date and still open: escalate — add to output as "Overdue Follow-up" and email the assignee (CC PM).
   Use the MS365/SMTP email utility if configured:
   - Subject: `[Follow-up] ${KEY}-XXX needs attention`
   - To: assignee's `email` from team.json

---

## Step 5: Write Updated State File

Write `scrum-state.md` to the project root with all current state.

Format:
```markdown
# Scrum State
Last run: <ISO timestamp>
Run count: <N>

## Open Blockers
- PROJECT-XXX: <description> (found: <date>)

## Follow-up Items
- [ ] PROJECT-XXX: <action needed> (due: <date>, assigned: <name>)
- [x] PROJECT-YYY: <action completed> (resolved: <date>)

## Past Insights
- <observation> (<date>)

## Already Actioned (skip on next run)
- PROJECT-XXX: <what was done> (<date>)

## Next Run Focus
- <next area from rotation>

## Throughput History
- Week of <date>: <N> items completed | In-flight: <N>
```

Rules:
- Prune `already_actioned` older than 14 days.
- Prune `past_insights` older than 30 days.
- Prune completed follow-ups older than 7 days.
- Cap state file at 300 lines.

---

## Step 6: Output Summary

Print a clean, scannable run summary under 50 lines. Bold the most critical item.

```
## Kanban Sweep — <timestamp>
**Focus**: <primary area audited>

### Actions Taken
- ${PROJECT_KEY}-XXX: <what was done> [<action type>: comment/label/email]

### New Findings
- ${PROJECT_KEY}-XXX: <finding> → <recommended action>

### Open Follow-ups (needs human)
- ${PROJECT_KEY}-XXX: <issue> → Assigned to <name> (due: <date>)

### Blockers
- ${PROJECT_KEY}-XXX: <blocker description> (open since: <date>)

### Flow Snapshot
- Total open: N | In Progress: N | In Review: N | Deployment: N | Unassigned: N
- Throughput (last 7d): N items completed
- Flow risk: <healthy / accumulating / critical>

### Next Run Focus
<area> — <why this area next>
```

---

## Key Constraints

- **NEVER** comment on the same issue twice for the same reason — check `already_actioned` first.
- **NEVER** use the word "sprint" in Jira comments or emails.
- **NEVER** use Atlassian MCP for Jira operations — use `tools/jira-api.py` only.
- State file path: `<root>/scrum-state.md`
