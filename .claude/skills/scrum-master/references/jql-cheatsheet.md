# JQL Cheatsheet — Kanban & Scrum Queries

## Core Flow Queries

```jql
# All active open issues
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned)

# Issues by status
project=${PROJECT_KEY} AND status="In Progress"
project=${PROJECT_KEY} AND status="In Review"
project=${PROJECT_KEY} AND status="Deployment"
project=${PROJECT_KEY} AND status="Done"

# Unestimated stories/tasks
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND story_points is EMPTY AND issuetype=Story

# Missing description/acceptance criteria
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND description is EMPTY

# Overloaded assignee (replace ID)
project=${PROJECT_KEY} AND assignee=<atlassianId> AND status="In Progress"
```

## Blocker Queries

```jql
# Blocker/impediment label
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND (labels=blocker OR labels=impediment)

# Issues mentioning "blocked" in comments (text search)
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND comment ~ "blocked"
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND comment ~ "waiting on"
project=${PROJECT_KEY} AND status NOT IN (Done, abandoned) AND comment ~ "can't proceed"
```

## Staleness Queries

```jql
# In Progress, no update in 3 days
project=${PROJECT_KEY} AND status="In Progress" AND updated <= -3d

# In Review, no update in 2 days
project=${PROJECT_KEY} AND status="In Review" AND updated <= -2d

# Any open issue not updated in 10 days
project=${PROJECT_KEY} AND updated <= -10d AND status NOT IN (Done, abandoned)
```

## Backlog Grooming Queries

```jql
# Ungroomed: no assignee, no estimate, old
project=${PROJECT_KEY} AND status=Open AND assignee is EMPTY AND created <= -7d

# Needs-triage label
project=${PROJECT_KEY} AND labels="needs-triage" ORDER BY created ASC

# High priority backlog items
project=${PROJECT_KEY} AND status=Open AND priority in (Highest, High) ORDER BY priority ASC
```

## Throughput / Completion Queries

```jql
# Done in last 7 days
project=${PROJECT_KEY} AND status=Done AND updated >= -7d

# Moved to Deployment status in last 7 days
project=${PROJECT_KEY} AND status changed to Deployment after -7d
```

## Definition of Done Gaps

```jql
# Done stories missing QA sign-off label
project=${PROJECT_KEY} AND status=Done AND issuetype=Story AND labels not in (qa-approved, qa-done)

# Stories moved to Done without In Review step (jumped status)
project=${PROJECT_KEY} AND status=Done AND issuetype=Story AND updated >= -1d
```

## Date Arithmetic

| Expression | Meaning |
|-----------|---------|
| `updated <= -3d` | Not updated in last 3 days |
| `created >= -7d` | Created in last 7 days |
| `created <= -14d` | Created more than 14 days ago |
| `due <= now()` | Overdue |
| `due >= now() AND due <= 3d` | Due in next 3 days |

## Usage with jira-api.py

```bash
# Always quote the JQL string
python3 tools/jira-api.py search "project=${PROJECT_KEY} AND status NOT IN (Done, abandoned)" --fields "summary,status,assignee,priority,updated" --max-results 100

# Escape quotes inside JQL with single quotes around whole string
python3 tools/jira-api.py search 'project=${PROJECT_KEY} AND status="In Progress"' --fields "summary,assignee,updated"
```
