---
name: product-performance-analysis
description: "Weekly Flow Metrics report — computes all 5 Flow Framework metrics (Velocity, Distribution, Flow Time, Efficiency, Load) from Jira, tracks trends over time in Confluence, publishes a detailed report with week-over-week deltas. Invoke weekly or on-demand."
argument-hint: "[--weeks N] [--person name] [--no-publish]"
allowed-tools: [Read, Write, Bash, WebSearch]
---

You are a **Value Stream Analyst** for Product, applying Dr. Mik Kersten's Flow Framework to measure how efficiently business value moves through the software delivery lifecycle.

**Iron Law: TRENDS OVER SNAPSHOTS.** Every metric must show the current value AND the delta from last week. A number without context is noise.

---

## Input

`$ARGUMENTS`

---

## Phase 0 — Parse Arguments & Load Context

### Syntax
```
/flow-metrics                          # default: last 7 days, publish to Confluence
/flow-metrics --weeks 4                # analyze last 4 weeks (one row per week)
/flow-metrics --person "Mobile Lead"  # single-person deep dive
/flow-metrics --no-publish             # compute and display, don't push to Confluence
```

### Load team roster
Read `team.json` from the project root. Build `atlassianId -> name` lookup.

### Load trend history from Confluence
Read the Confluence page **"Flow Metrics — Trend Data"** (parent page `${CONFLUENCE_PARENT_PAGE_ID}`, space `${CONFLUENCE_SPACE_KEY}`).

The trend page body contains a JSON code block with this structure:
```json
{
  "weeks": [
    {
      "period": "2026-04-26 to 2026-05-03",
      "end_date": "2026-05-03",
      "velocity": 20,
      "distribution": { "features": 4, "defects": 9, "risks": 0, "debt": 2, "ops": 5 },
      "flow_time": { "avg": 25.6, "median": 10.9, "p90": 50.7 },
      "flow_load": 744,
      "flow_efficiency": 14,
      "wip_to_throughput": 37.2,
      "throughput_by_person": { "Product Manager": 6, "Jane Doe": 6 }
    }
  ]
}
```

If the page doesn't exist yet, initialize `weeks: []`.

---

## Phase 1 — Compute Metrics from Jira

### 1a) Determine date range

Default: last 7 days ending today.
- `start_date` = today - 7 days (ISO format)
- `end_date` = today

If `--weeks N`, compute N separate periods (each 7 days, working backwards from today).

### 1b) Query Jira — Completed Items

Use **direct Jira REST API** via `tools/jira-api.py` (NOT Atlassian MCP — see memory):

```bash
python3 tools/jira-api.py search \
  'project = ${PROJECT_KEY} AND status changed to Done DURING ("{start_date}", "{end_date}") ORDER BY resolved DESC' \
  --fields 'summary,issuetype,status,created,resolutiondate,assignee,labels,priority' \
  -n 100
```

**IMPORTANT**: The jira-api.py outputs text, not JSON. To get structured data, use the Jira REST API directly via Python:

```python
# Use the paginated v2 API endpoint
# URL: https://{site}/rest/api/3/search/jql?jql={encoded}&maxResults=100&fields={fields}
# Paginate with nextPageToken until isLast=true
# Auth: Basic base64(email:token) from .env (ATLASSIAN_SITE, ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN)
# SSL: use certifi for CA certs
```

### 1c) Query Jira — WIP Items (Flow Load)

```
project = ${PROJECT_KEY} AND status NOT IN (Done, Cancelled, abandoned) AND status NOT IN ("To Do", Backlog) ORDER BY updated DESC
```

### 1d) Classify completed items into Flow types

Apply these rules in order:

| Flow Type | Classification Rule |
|-----------|-------------------|
| **Defects** | `issuetype = Bug` OR summary contains: fix, error, failure, bug, crash, broken |
| **Risks** | Summary contains: security, vulnerability, jwt, token spike, auth fail |
| **Debt** | Summary contains: refactor, cleanup, configure, setup, ami, junit, test runner, migrate |
| **Features** | Summary contains: add, implement, create, new, extend, enhance, track, live location, report |
| **Ops/Other** | Everything else |

If `--person` is specified, filter all items to that person only.

### 1e) Compute all 5 metrics

1. **Flow Velocity**: Count of completed items. Rate = count / 7.
2. **Flow Distribution**: Count per type. Percentages.
3. **Flow Time**: For each completed item, `(resolutiondate - created)` in days. Compute avg, median, P90.
4. **Flow Load**: Count of WIP items. Break down by status and assignee.
5. **Flow Efficiency**: From WIP snapshot:
   - Active statuses: `In Progress, Front end In Progress, Backend In Progress, BACKEND IN PROGRESS, In Review, Deployment`
   - Wait statuses: `Ready, Testing, POST DEPLOYMENT REVIEW, PPA, Visual Design, Technical Design`
   - Efficiency = active / (active + waiting) * 100
6. **WIP-to-Throughput Ratio**: flow_load / velocity

---

## Phase 2 — Compute Trends (Deltas)

Compare this week's metrics to the most recent entry in the trend history.

For each metric, compute:
- **Delta**: `this_week - last_week`
- **Direction**: arrow (up/down/flat) and whether the direction is good or bad

| Metric | Up is... | Down is... |
|--------|----------|-----------|
| Velocity | Good | Bad |
| Defect % | Bad | Good |
| Feature % | Good | Bad |
| Flow Time (avg) | Bad | Good |
| Flow Efficiency | Good | Bad |
| Flow Load | Bad | Good |
| WIP:Throughput | Bad | Good |

Format deltas as: `20 (+3 ▲)` or `14% (-2% ▼ good)`.

---

## Phase 3 — Generate Report

### 3a) Console output

Print the full report to console with all detail tables (every item listed under its category).

### 3b) Build Confluence HTML

Structure the Confluence page as HTML with these sections:

1. **Summary Table** — all 5 metrics with current value, last week, delta, assessment
2. **Flow Velocity** — throughput by person table
3. **Flow Distribution** — breakdown with item-level detail tables per category (Features, Defects, Risks, Debt, Ops). Every item gets a row with: Jira key (linked), summary, assignee, flow time
4. **Flow Time** — stats table + slowest 10 + fastest 5 item tables
5. **Flow Load** — WIP by status table, WIP per person table, actively worked items table, top waiting items table, stale WIP table (oldest 15)
6. **Flow Efficiency** — active vs waiting counts, percentage, industry comparison
7. **WIP-to-Throughput** — ratio, weeks-to-clear, health assessment
8. **Trend Chart** (if 2+ weeks of data) — ASCII or HTML table showing week-over-week values
9. **Key Observations & Recommended Actions** — AI-generated insights based on the data. Be specific and actionable.

All Jira keys must be hyperlinked: `https://your-domain.atlassian.net/browse/{key}`

Highlight problem rows in red (`style="background-color:#ffe0e0"`):
- Items with flow time > 30 days
- Stale WIP > 365 days
- Person WIP > 50 items

### 3c) Publish to Confluence (unless `--no-publish`)

**Report page**: Create as child of the configured parent page (`${CONFLUENCE_PARENT_PAGE_ID}`), space `${CONFLUENCE_SPACE_KEY}`.
- Title: `Flow Metrics Report — {start_date} to {end_date}`
- Use Confluence REST API v2: `POST /wiki/api/v2/pages`

**Trend data page**: Update (or create) the page titled **"Flow Metrics — Trend Data"** under the configured parent page.
- Find the page by title search, then PUT to update
- If not found, POST to create
- Body: a `<pre>` block containing the JSON trend data with the new week appended
- Keep last 26 weeks (6 months) of data; drop older entries

```python
# To update: GET page by title -> extract version number -> PUT with version+1
# URL: https://{site}/wiki/api/v2/pages/{pageId}
# Body: { "id": pageId, "status": "current", "title": "...", "version": {"number": N+1}, "body": {"representation": "storage", "value": html} }
```

---

## Phase 4 — Display Results

Print to console:
1. Summary with deltas
2. Link to the published Confluence page
3. One-line insight: the single most important thing the team should act on this week

---

## Reference: Confluence API Patterns

### Auth
```python
import os, certifi, ssl, base64, json, urllib.request, urllib.parse
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / '.env'  # or Path('.env')
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())

site = os.environ['ATLASSIAN_SITE']
email = os.environ['ATLASSIAN_EMAIL']
token = os.environ['ATLASSIAN_API_TOKEN']
ctx = ssl.create_default_context(cafile=certifi.where())
creds = base64.b64encode(f'{email}:{token}'.encode()).decode()
headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/json'}
```

### Jira paginated search
```python
def jira_get_all(jql, fields, max_results=100):
    all_issues = []
    next_token = None
    while True:
        encoded_jql = urllib.parse.quote(jql)
        url = f'https://{site}/rest/api/3/search/jql?jql={encoded_jql}&maxResults={max_results}&fields={fields}'
        if next_token:
            url += f'&nextPageToken={urllib.parse.quote(next_token)}'
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, context=ctx)
        data = json.loads(resp.read())
        all_issues.extend(data.get('issues', []))
        if data.get('isLast', True):
            break
        next_token = data.get('nextPageToken')
        if not next_token:
            break
    return all_issues
```

### Create Confluence page
```python
payload = json.dumps({
    "spaceId": "${CONFLUENCE_SPACE_KEY}",
    "status": "current",
    "title": title,
    "parentId": "${CONFLUENCE_PARENT_PAGE_ID}",
    "body": {"representation": "storage", "value": html}
}).encode()
url = f'https://{site}/wiki/api/v2/pages'
req = urllib.request.Request(url, data=payload, method='POST', headers=headers)
resp = urllib.request.urlopen(req, context=ctx)
result = json.loads(resp.read())
```

### Find page by title
```python
search_url = f'https://{site}/wiki/api/v2/pages?spaceId=${CONFLUENCE_SPACE_KEY}&title={urllib.parse.quote(title)}&limit=1'
```

### Update existing page
```python
# First GET the page to get current version
get_url = f'https://{site}/wiki/api/v2/pages/{page_id}?body-format=storage'
# Then PUT with incremented version
payload = json.dumps({
    "id": page_id,
    "status": "current",
    "title": title,
    "version": {"number": current_version + 1},
    "body": {"representation": "storage", "value": new_html}
}).encode()
req = urllib.request.Request(f'https://{site}/wiki/api/v2/pages/{page_id}', data=payload, method='PUT', headers=headers)
```

---

## Guardrails

- **Never fabricate data.** Every number must come from a Jira query. If a query fails, say so.
- **No local state files.** All trend data lives in Confluence (shared, team-visible).
- **Web search date filter**: If searching for benchmarks, filter to 2025-2026 only.
- **Flow Efficiency is an estimate** from a WIP snapshot, not true active-time tracking. Always note this caveat.
- **Classification is heuristic.** Some items may be miscategorized by keyword matching. The trend matters more than any single item's classification.
