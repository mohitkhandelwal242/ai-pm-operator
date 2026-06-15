---
name: monthly-board-prep
description: "Monthly Analysis — leadership-deck format month-over-month (MoM) comparison driven by business.json. Pulls two consecutive months of your product's metrics, computes deltas, and renders a leadership-style markdown deck with sections derived from your revenue_model and key_metrics, then optionally auto-publishes to Confluence. Use when asked for 'monthly analysis', 'month over month', 'MoM report', 'leadership monthly', 'board prep', or '/monthly-analysis'."
---

# Monthly Analysis — MoM Leadership Report

Generate a leadership-deck monthly analysis. Compares two consecutive months (or any user-specified pair) across the metrics defined in `business.json`, computes month-over-month deltas, and renders an executive markdown deck. Optionally auto-publishes to Confluence.

**The report is DRIVEN BY `business.json`.** It does not assume any vertical. Read the business profile first and let it decide which sections and metrics appear.

Historical context for trendlines (if present): `historical/monthly-snapshots.tsv`. This file is optional — if it is missing, skip trend commentary.

---

## Step 0 — Read the business profile

Read `business.json` at the start. The relevant fields:

- `company.{name, product_name, industry, business_type, revenue_model}`
- `metrics.north_star` — the single headline metric the deck leads with
- `metrics.key_metrics[]` — the list of metrics to compare MoM (each entry typically has a name, optional unit/currency, and optional category)

**Derive the report sections from `revenue_model` and `key_metrics`.** Group `key_metrics` by their category (or infer a sensible grouping) and render one report section per group. Always lead with the north-star metric. Examples of how `revenue_model` shapes the default sections:

| `revenue_model` | Suggested default sections (override with whatever `key_metrics` actually contains) |
|---|---|
| `subscription` / SaaS | MRR/ARR, New vs Churned MRR, Net Revenue Retention, Activation, Active Users, Churn rate |
| `marketplace` | GMV, Take rate, Net revenue, Active buyers, Active sellers, Liquidity / match rate |
| `transactional` / e-commerce | Revenue, Orders, AOV, Conversion rate, Repeat-purchase rate, New vs returning customers |
| `advertising` | Revenue, Impressions, Fill rate, eCPM, DAU/MAU, Session depth |
| `usage-based` | Revenue, Consumption units, Active accounts, Expansion, Net Revenue Retention |

These are starting points only. The actual sections must reflect the metrics present in `business.json` — never hardcode a vertical.

If a metric needed for the deck is missing from `business.json`, ask the user once and write it back.

---

## Step 1 — Resolve months

Default invocation: **current calendar month vs previous calendar month** based on today's date (e.g. invoked May 4 → Apr vs Mar). Override with explicit args: `/monthly-analysis 2026-04 2026-03` (current, prior).

Bind:
- `YEAR_A`, `MONTH_A` → current/latest month
- `YEAR_B`, `MONTH_B` → prior month

---

## Step 2 — Verify the data source is reachable

The skill reads metric values from whatever data store the business uses (SQL warehouse, analytics API, etc.). Confirm connectivity before querying. If the project uses a DB tunnel:

```bash
bash tools/setup-db-tunnel.sh status || bash tools/setup-db-tunnel.sh start
```

Read connection credentials from `.env`. Do not hardcode hosts, schemas, or credentials.

---

## Step 3 — Pull the core comparison

Run a parameterized two-month comparison against your product's metrics store. See `queries/monthly-comparison.sql` for an **example template** — replace the placeholder table/column names with your own schema. Substitute `:YEAR_A/:MONTH_A` (current) and `:YEAR_B/:MONTH_B` (prior).

The query should return one row per `(category, metric_name)` with `current_value`, `prior_value`, and `pct_change`. The categories should map to the metric groups you derived in Step 0.

**Data-availability check:** if a category has notably fewer rows for the latest month than the prior month, some metrics weren't loaded yet. Render those as `(data not available for {Month YYYY})` instead of computing a misleading delta. Never silently impute, average, or carry forward.

---

## Step 4 — Pull retention / churn detail (optional)

If `business.json` lists retention or churn metrics (e.g. churn rate, reactivations, account/customer status buckets), pull them with a dedicated query. See `queries/retention-churn-monthly.sql` for an **example template**.

```bash
# Access to a separate analytics schema/API may be restricted for some users.
# If the query fails (e.g. "SELECT command denied"):
#   1. Try the analytics API path (API key in .env), if configured.
#   2. If that also fails, OMIT the retention/churn section entirely and add a
#      single line in the report:
#      "Retention/Churn: data not available for {Month YYYY}".
#   Do NOT publish prior-month numbers under the latest-month header — that
#   would mislead leadership. Missing > stale.
```

If both months have data, compute and render whatever retention metrics `business.json` defines, for example:
- Active account/customer count (start vs end)
- Net churn (raw delta + rate %)
- Churn rate, reactivation count
- Any status/engagement buckets the business tracks (e.g. cohorts by activity level)
- Commentary on whether a move was driven by a one-off event (e.g. a bulk billing run) vs a sustained trend

---

## Step 5 — Render the report

Output a Markdown file at `reports/monthly-analysis-{monthA-yy}-vs-{monthB-yy}.md`. Structure (sections come from Step 0, so this is a skeleton — adapt the numbered sections to the business's actual metric groups):

1. **Title** — `{Product} Monthly Analysis — {Month A YYYY} vs {Month B YYYY}`
2. **Summary** — one paragraph leading with the north-star metric and the top 3–4 numbers
3. **Key Takeaways** — table with columns `# | Signal | Verdict`. Verdict is one of: `Strong | Key Driver | Positive | Watch | New | Pending`. 10–14 rows
4. **Numbered metric sections** — one per metric group derived from `key_metrics`/`revenue_model`. Each section is a metric table with `{Month B} | {Month A} | Change` columns followed by a `**Highlights:**` paragraph. Order them with the north-star group first, then revenue, then engagement/retention, etc.
5. **Root Cause Analysis — Major Changes (Data-Backed)** — for every headline metric that moved >10% MoM, run a sliced variation of the source query (see `queries/source-queries-example.sql`) across the dimensions the business cares about (e.g. segment, region, channel, plan, platform, day-of-month). Goal: explain WHY each move happened, not just THAT it happened. Include:
   - Gains (>10% increase) — one-row-per-metric narrative table with the data-backed reason
   - Declines (>10% decrease) — one-row-per-metric narrative table with the data-backed reason
   - For any move a segment/dimension slice doesn't explain, also drill on day-of-month (single-day spike vs sustained drift) and channel/platform.
6. **Retention/Churn section** — only if Step 4 returned data for both months. Otherwise insert a single line: `Retention/Churn: data not yet available for {Month YYYY}.` and continue.
7. **Leadership Notes — Copy/Paste for Slide** (REQUIRED — never skip)
8. **Footer** — `Report generated: {date} | Data source: {your metrics store} | Generated via /monthly-analysis skill`

### Required Leadership Notes format (Section 7)

Each section is a **header + multiple short observation lines** (one observation per line, separated by single newlines so they render as separate paragraphs in Confluence). Format every metric as `prior → current (+X.X%)` with sign. **No bullet symbols, no tables.** Use one header per metric group, for example:

```
### Core Metrics ({Month A}'YY vs {Month B}'YY)
{4–6 short prose lines, one observation per line, north-star metric first}

### Revenue & Monetization ({Month A}'YY vs {Month B}'YY)
{6–7 short prose lines}

### Acquisition & Activation ({Month A}'YY vs {Month B}'YY)
{1 lead summary line, then 1 line per metric}

### Engagement ({Month A}'YY vs {Month B}'YY)
{1 lead line + 1 line per engagement metric}

### Retention / Churn ({Month A}'YY vs {Month B}'YY)
{If data available: 1 line per metric + 1 "Key takeaway:" paragraph at end}
{If data missing: a single line "Data not yet available for {Month YYYY}."}
```

(Use the section headers that match the business's metric groups — the above are illustrative.) This format must NOT be one big paragraph and must NOT be bullet-listed. It is short, dense, line-broken prose that the user copies section-by-section directly into a slide.

**Missing-data rule (general):** any metric where the latest month is null/zero must be rendered as `(data not available for {Month YYYY})`. Never silently impute, average, or carry forward.

**Tone:** terse, executive-style, numbers-first. Format currency amounts using the currency/unit declared in `business.json` (fall back to the metric's own unit). Use `+X.X%` deltas with sign. Never use emojis.

---

## Step 6 — Auto-publish to Confluence (optional)

Create a new page under the parent of the existing `Monthly Analysis` series. Use the Atlassian MCP `createPage`:

- cloudId: `${CONFLUENCE_CLOUD_ID}`
- spaceId/spaceKey: `${CONFLUENCE_SPACE_KEY}`
- parentId: `${CONFLUENCE_PARENT_PAGE_ID}` — or discover it by searching for an existing `Monthly Analysis` page and using its parent. If the lookup fails, ask the user once for the parent page id.
- Title: `{Product} Monthly Analysis {MonthA YYYY} vs {MonthB YYYY}`
- contentFormat: `markdown`
- Body: contents of the Markdown file from Step 5

After publishing, return the URL to the user.

### Confluence target
- spaceKey: `${CONFLUENCE_SPACE_KEY}`
- parentId: `${CONFLUENCE_PARENT_PAGE_ID}`
- cloudId: `${CONFLUENCE_CLOUD_ID}`

### Direct REST API path (fallback when MCP isn't available)
The Atlassian MCP `createPage` is preferred. If unavailable, post directly via REST:

```python
import os, requests, markdown
from requests.auth import HTTPBasicAuth
html = markdown.markdown(open('REPORT.md').read(), extensions=['tables', 'fenced_code'])
auth = HTTPBasicAuth(os.environ['ATLASSIAN_EMAIL'], os.environ['ATLASSIAN_API_TOKEN'])
r = requests.post(f"{os.environ['ATLASSIAN_BASE_URL']}/wiki/api/v2/pages", auth=auth, json={
    "spaceId": "${CONFLUENCE_SPACE_KEY}",
    "parentId": "${CONFLUENCE_PARENT_PAGE_ID}",
    "status": "current",
    "title": "{Product} Monthly Analysis — {Month A YYYY} vs {Month B YYYY}",
    "body": {"representation": "storage", "value": html}
})
```

---

## Step 7 — Append to historical snapshot (optional)

If the latest month's data is fully populated, append a column to `historical/monthly-snapshots.tsv` (create it if absent). This keeps a long-tail trend file usable for future YoY analyses. Use the same metric names as `business.json` so the file stays generic.

---

## Reference: data sources & known gaps

| Section | Source | Known gaps |
|---|---|---|
| Core metric groups (from `key_metrics`) | Your product's metrics store / warehouse | Latest month may have fewer rows than prior month — loading lag |
| Retention / Churn detail | Separate analytics schema or API (if configured) | May not be auto-loaded; latest month may be missing for the first several days. Access may require additional DB grants — request from your data team or use the analytics API. |
| Segment / region breakdown | May require a separate aggregation if not in the main metrics table | Scope in if the user asks for segment-level analysis |

## Self-check before publishing

- [ ] Sections were derived from `business.json` (`key_metrics` + `revenue_model`), not hardcoded
- [ ] North-star metric leads the Summary and the first metric section
- [ ] Every section either contains data OR explicitly says "data not available for {Month YYYY}"
- [ ] No prior-month numbers rendered under the latest-month header
- [ ] All currency figures use the unit declared in `business.json`
- [ ] Significant mix shifts (e.g. plan-mix, segment-mix) are called out
- [ ] Headline section names 3–5 wins and 2–3 watch-items for next month
- [ ] Confluence URL returned to the user (if publishing was requested)
- [ ] **Leadership Notes — Copy/Paste for Slide** section is present with `### Section ({MA}'YY vs {MB}'YY)` headers and **multiple short observation lines per section, one observation per line** in `prior → current (+X.X%)` format. NOT a single dense paragraph; NOT bullet-listed
