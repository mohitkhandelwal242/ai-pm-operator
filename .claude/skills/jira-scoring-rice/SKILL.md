---
name: jira-scoring-rice
description: "Offer / discount / promotion ROI audit — inventories every active offer, discount and promo rule in production, classifies each by its actual program (read from the segment/campaign attribute, not the surface trigger), measures conversion of each program against a cohort, surfaces orphan / misconfigured / duplicate offer rules, and estimates the cost given away. Works for any revenue model in business.json (subscription, transaction, ads). Publishes to Confluence with kill / keep / consolidate recommendations. Use when asked about 'offer audit', 'discount audit', 'promo inventory', 'offer ROI', 'free offers in production', or '/audit-offers'."
---

# /audit-offers — Offer / Discount / Promotion ROI Audit

End-to-end audit of every active offer, discount or promotion in production. The skill classifies each offer by its **actual program** (read from the segment / campaign attribute, not the surface trigger — the same UI trigger often fulfils multiple programs), computes conversion program-by-program, and surfaces:

- Programs working well (scale candidates)
- Programs giving away value with near-zero conversion (kill / shorten candidates)
- Orphan rules / misconfigured short-validity passes
- Naming inconsistencies (multiple trigger-string variants of the same action)
- Cost surface (value given away per quarter)

Produces a console summary + a Confluence page.

---

## Step 0 — Load business context

Read `business.json` first. This skill adapts to the business's revenue model:

- `company.revenue_model` — `subscription`, `transaction`, `ads`, or a mix. This determines what "an offer" and "conversion" mean (see table below).
- `metrics.key_metrics[]` — the metrics the business already tracks; align "conversion" and "cost" to these where possible.
- `stack.analytics` / `stack.code_repos[]` — where the offer data and offer-config logic live.

| revenue_model | "Offer" means | "Conversion" means | "Cost given away" means |
|---|---|---|---|
| subscription | A free / discounted subscription grant | Recipient later buys a paid plan | Face value of the granted plan |
| transaction | A discount / coupon / credit on a transaction | Recipient completes a paid (full-price) transaction afterwards | Discount amount × redemptions |
| ads | A free / boosted placement or credit | Advertiser later runs a paid campaign | Value of the free impressions / credit |

Whenever this doc says **`<offer_table>`**, **`<segment_attr>`**, **`<trigger_attr>`**, **`<validity_attr>`**, **`<value_attr>`** or **`<paid_event>`**, substitute the real names from the business's schema (discover them from `stack.code_repos[]` / `stack.analytics`). If they cannot be found, ask the user once and write the mapping back to `business.json` under `stack.offer_schema`.

---

## CRITICAL — the segment/campaign attribute is the truth, not the surface trigger

This is the central lesson of this skill. A single surface **`<trigger_attr>`** (e.g. one button or one entry screen) commonly fulfils several distinct programs, distinguished only by a **`<segment_attr>`** (segment id / campaign id / rule id):

| `<trigger_attr>` | `<segment_attr>` | Actual program |
|---|---|---|
| `TRIGGER_A` | `campaign_x:0` | Campaign X (short validity) |
| `TRIGGER_A` | `campaign_y:0` | Campaign Y (short validity) |
| `TRIGGER_A` | `bootstrap:new_market` | New-market bootstrap (long validity) |

**Always classify by `<segment_attr>` first**, then by `<trigger_attr>`, then by `<validity_attr>`.

**Beware retention rewards masquerading as acquisition offers.** Some "free" grants are loyalty / retention rewards handed to users who are *already paying*. If most recipients of a program already had a prior paid conversion, that program's apparent "conversion" is mostly existing payers renewing — pooling it with acquisition offers double-counts payers and inflates the program's feeder value. Detect these (e.g. ">X% of recipients had a prior paid event") and report them in a separate **retention** bucket, excluded from the acquisition-offer ROI comparison.

Typical naming conventions to expect in `<segment_attr>` (substitute the business's actual prefixes):
- `<campaign_prefix>:N` — a named campaign, variant N
- `manual:support` — manually / support-issued grants
- a long structured segment string (cohort / market / device) — often a bootstrap or cohort program when paired with a long validity
- empty / NULL → fall back to `<trigger_attr>` (e.g. signup / email-verification / non-domestic grants)

---

## Prerequisites

Environment variables (from `.env`):
- Data-source credentials used by the other audit skills (DB tunnel, analytics API, etc.)
- `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN` — Confluence publishing
- `${CONFLUENCE_SPACE_KEY}`, `${CONFLUENCE_PARENT_PAGE_ID}`, `${CONFLUENCE_CLOUD_ID}` — Confluence target

---

## Arguments

| Argument | Action |
|----------|--------|
| *(empty)* | 30-day inventory + 90-day cohort conversion (default) |
| `7d` or `weekly` | Last 7 days inventory only |
| `30d` or `monthly` | 30 days inventory + 90d cohort conversion |
| `90d` or `quarterly` | 90 days both |
| `program <name>` | Deep-dive into one program by its `<segment_attr>` prefix |
| `orphans` | Only show misconfigured / one-off rules |
| `kill-list` | Only show programs with < 5% conversion + suggested replacements |

---

## Execution Steps

### Step 1 — Set Date Ranges

| Arg | Inventory window | Cohort window (for conversion) |
|-----|---|---|
| `7d` / `weekly` | 7 days | 28 days |
| `30d` / `monthly` / empty | 30 days | 90 days |
| `90d` / `quarterly` | 90 days | 90 days |

### Step 2 — Collect Data

The SQL below is a reference template against a relational offer table. If the business stores offers elsewhere (analytics warehouse, feature-flag service), translate the same logic to that source. Replace the `<...>` placeholders with the real schema names resolved in Step 0.

#### 2a. Full Inventory by trigger × validity × segment

```sql
-- See queries/inventory.sql
SELECT <trigger_attr>, <validity_attr>, <segment_attr>,
  COUNT(*) AS grants, COUNT(DISTINCT <subject_id>) AS unique_subjects,
  MIN(<created_attr>) AS first_seen, MAX(<created_attr>) AS last_seen
FROM <offer_table>
WHERE <created_attr> >= '{since}' AND <created_attr> < DATE_ADD('{until}', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY <trigger_attr>, <validity_attr>, <segment_attr>
ORDER BY grants DESC;
```

#### 2b. Program Classification (segment-driven)

```sql
-- See queries/program-classification.sql
SELECT
  CASE
    WHEN <trigger_attr> LIKE 'FREE_%' THEN <trigger_attr>
    WHEN <segment_attr> LIKE '<campaign_a_prefix>%' THEN 'Campaign A'
    WHEN <segment_attr> LIKE '<campaign_b_prefix>%' THEN 'Campaign B'
    WHEN <segment_attr> LIKE 'manual:support%' THEN 'Manual / support'
    WHEN <validity_attr> = <long_validity> AND <segment_attr> LIKE '<bootstrap_pattern>%' THEN 'New-market bootstrap'
    WHEN <validity_attr> = <long_validity> AND <segment_attr> LIKE '<cohort_pattern>%' THEN 'Cohort (long validity)'
    WHEN <segment_attr> IS NULL OR <segment_attr> = '' THEN 'NULL segment'
    ELSE 'Unclassified'
  END AS program,
  <validity_attr>,
  COUNT(*) AS grants,
  COUNT(DISTINCT <trigger_attr>) AS distinct_triggers,
  COUNT(DISTINCT <subject_id>) AS unique_subjects
FROM <offer_table>
WHERE <created_attr> >= '{since}' AND <created_attr> < DATE_ADD('{until}', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY program, <validity_attr>
ORDER BY grants DESC;
```

#### 2c. Conversion Per Program (cohort)

```sql
-- See queries/program-conversion.sql
SELECT program, got_offer, later_paid,
       ROUND(100*later_paid/NULLIF(got_offer,0), 2) AS conv_pct,
       revenue,
       ROUND(revenue/NULLIF(later_paid,0), 0) AS rev_per_converter
FROM (
  SELECT
    /* same CASE expression as 2b */
    COUNT(DISTINCT offer.<subject_id>) AS got_offer,
    COUNT(DISTINCT paid.<subject_id>)  AS later_paid,
    ROUND(SUM(paid.<amount_attr>), 0)  AS revenue
  FROM <offer_table> offer
  LEFT JOIN <paid_event> paid
    ON paid.<subject_id> = offer.<subject_id>
    AND paid.<amount_attr> > 0
    AND paid.<created_attr> > offer.<created_attr>
  WHERE offer.<created_attr> >= '{cohort_since}' AND offer.<created_attr> < DATE_ADD('{cohort_until}', INTERVAL 1 DAY)
    AND offer.<is_free_or_discounted>
  GROUP BY program
) x
ORDER BY got_offer DESC;
```

#### 2d. Orphan / Misconfigured Rule Detection

Two patterns that indicate broken offer-config:

```sql
-- (A) trigger/segment combos that fire only 1-3 times in window with a rare/short validity
SELECT <trigger_attr>, <validity_attr>, <segment_attr>, COUNT(*) AS n,
       MIN(<created_attr>) AS first_seen, MAX(<created_attr>) AS last_seen
FROM <offer_table>
WHERE <created_attr> >= '{since}' AND <created_attr> < DATE_ADD('{until}', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
  AND <validity_attr> = <short_validity>
GROUP BY <trigger_attr>, <validity_attr>, <segment_attr>
HAVING n <= 3
ORDER BY first_seen;

-- (B) trigger string variants that look like the same action (naming inconsistency)
SELECT
  REPLACE(REPLACE(LOWER(<trigger_attr>),'_',' '),'  ',' ') AS canonical_trigger,
  COUNT(DISTINCT <trigger_attr>) AS variant_count,
  COUNT(*) AS grants,
  GROUP_CONCAT(DISTINCT <trigger_attr> SEPARATOR ' | ') AS variants
FROM <offer_table>
WHERE <created_attr> >= '{since}' AND <created_attr> < DATE_ADD('{until}', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY canonical_trigger
HAVING variant_count > 1
ORDER BY grants DESC;
```

#### 2e. Cost Surface Estimate

Build a face-value lookup keyed by `<validity_attr>` (for subscription/credit grants) or by discount amount (for transaction coupons). The values below are placeholders — verify them against the business's real plan pricing / discount config and update.

| `<validity_attr>` (example bucket) | Plan / tier | Approx face value |
|---|---|---:|
| short | short pass | (from pricing) |
| medium | 1-month | (from pricing) |
| long | multi-month | (from pricing) |

```sql
-- See queries/cost-surface.sql
SELECT
  /* program CASE */ AS program,
  <validity_attr>,
  COUNT(*) AS grants,
  <face_value_lookup> AS face_value,
  COUNT(*) * <face_value_lookup> AS total_face_cost
FROM <offer_table>
WHERE <created_attr> >= '{since}' AND <created_attr> < DATE_ADD('{until}', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY program, <validity_attr>
ORDER BY total_face_cost DESC;
```

### Step 3 — Analyze

Compute and organize:

1. **Top programs by volume** (grant count)
2. **Top programs by conversion** (cohort %)
3. **Cost vs return matrix** — programs in the high-cost / low-conversion quadrant are the kill candidates
4. **Orphan rules** — flag every (trigger, validity, segment) combo with ≤3 occurrences
5. **Trigger string normalization opportunities** — list canonical groups (e.g. `Recent Chat Screen Opened` vs `Recent_Chat_Screen_Opened`)
6. **Face-value spend per program per quarter**
7. **Retention vs acquisition split** — move any program where most recipients already had a prior paid event into a separate retention bucket (see CRITICAL section)

### Step 4 — Recommendations

Built from the matrix (express thresholds in the business's own currency / metric units):

| Pattern | Recommendation |
|---|---|
| Program conv < 5% AND high face cost | **Kill or shorten validity** — biggest waste |
| Program conv < 5% AND low face cost | **Shorten to shortest validity tier** |
| Program conv > 25% AND volume increasing | **Scale** — broaden trigger criteria |
| Multiple trigger string variants of same action | **Consolidate to canonical name** (engineering ticket) |
| One-off short-validity rules with single occurrence | **Clean up offer-config table** (orphans) |
| Long-validity pass with conv < 5% | **Cut to a shorter validity** — long passes kill urgency |

#### Standard playbook entries

1. **Signup / verification grants** — these frequently have ~0% conversion at long validity. Shorten unless data improves.
2. **Bootstrap / new-market programs** — usually the biggest face-cost line. Pilot a shorter-validity variant in 1-2 markets and compare conversion before any rollout.
3. **Top performers** — consider a tiered follow-on trigger to extend the winning loop.

### Step 5 — Publish

#### Console Output

- Top 10 programs by volume
- Top 10 by conversion
- Orphan list (≤3 occurrences, short-validity)
- Trigger normalization candidates
- Face-cost line items

#### Confluence Report

Idempotent: find-or-update by title in your Confluence space `${CONFLUENCE_SPACE_KEY}` (cloudId `${CONFLUENCE_CLOUD_ID}`, parent `${CONFLUENCE_PARENT_PAGE_ID}`).

- Title: `Offer Inventory & ROI Audit — {since} → {until}`
- Sections: Executive Summary · Program Classification · Conversion Matrix · Cost Surface · Orphan Rules · Trigger Normalization · Recommendations · Open Questions

#### Jira Ticket Triggers

For any program in the kill quadrant (high cost, <5% conversion), open an issue in project `${PROJECT_KEY}` assigned to the offer-config owner via `tools/jira-api.py`.

---

## Key Constants

| Constant | Value |
|----------|-------|
| Offer identifier | `<is_free_or_discounted>` predicate (from business schema) |
| Confluence space | `${CONFLUENCE_SPACE_KEY}` (from .env) |
| Jira project | `${PROJECT_KEY}` (from .env) |

---

## Benchmarks (tune to the business; treat as starting defaults)

| Metric | Baseline | Good | Great |
|---|---|---|---|
| Program conversion | 15% | >25% | >35% |
| Face cost per converter | high | medium | low |
| Orphan rule count (≤3 occurrences) | <10 | <5 | 0 |
| Trigger string variants per canonical action | <2 | 1 | 1 |

---

## When to Run

- **Monthly** (full inventory): default arg, publish to Confluence
- **Quarterly** (deep cohort review): 90d arg
- **After any offer-config change** — `kill-list` arg to verify removed programs really stopped
- **Before any new offer launch** — to make sure the new `<segment_attr>` is unique and naming is consistent

---

## Routine Integration

```yaml
- id: audit-offers-monthly
  name: Offer inventory & ROI audit
  owner: PM
  schedule: 1st of month, morning
  skill: /audit-offers
  effort: M
```

---

## Related Skills

- `/monthly-analysis` — uses rolled-up monthly metrics; this skill recomputes offer ROI from raw offer data
- `/sub-cohort` — cohort retention; useful for understanding what "conversion" means downstream

---

## SQL Files

- `queries/inventory.sql`
- `queries/program-classification.sql`
- `queries/program-conversion.sql`
- `queries/orphan-rules.sql`
- `queries/cost-surface.sql`
</content>
</invoke>
