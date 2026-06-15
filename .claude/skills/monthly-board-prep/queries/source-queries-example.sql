-- EXAMPLE TEMPLATE — replace table/column names with your product's schema. The skill reads metrics from business.json.
-- ============================================================================
-- SOURCE / RAW METRIC QUERIES
-- ============================================================================
-- These illustrate how the rows in `your_metrics_table` are produced each
-- month. For the /monthly-analysis skill: use these (with WHERE-clause
-- variations on segment / region / channel / plan dimensions) to investigate
-- any metric that moved >10% MoM. Pattern:
--   1. Run the base query for {prior, current} month -> confirm the delta
--   2. Add a segment/region GROUP BY -> find which slice drove it
--   3. Add a daily breakdown -> sustained shift vs single-day spike
--
-- Naming convention: each query writes one (category, metric_name, value) row.
-- Date pattern: every query keys off "previous month" via
--   DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')  AS month_start
--   DATE_FORMAT(CURDATE(),                              '%Y-%m-01')  AS month_end
-- For ad-hoc backfills, replace those with explicit dates.
--
-- Date semantics: half-open [month_start, month_end) — INCLUDES the first day,
-- EXCLUDES the first day of next month.
-- ============================================================================
-- Adapt every table/column below to your schema. Placeholders used here:
--   your_metrics_table   -- the aggregated (year, month, category, metric_name, value) store
--   users                -- one row per customer/account
--   subscriptions        -- one row per paid plan / order
--   sessions             -- engagement events
--   payments             -- successful transactions
-- ============================================================================


-- ============================================================================
-- USERS / CUSTOMERS category
-- ============================================================================

-- Total customers (cumulative)
INSERT INTO your_metrics_table
SELECT MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)) AS month,
       YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))  AS year,
       COUNT(*) AS value, 'Total Customers' AS metric_name, 'Users' AS category, NOW()
FROM users
WHERE created_at < DATE_FORMAT(CURDATE(), '%Y-%m-01');

-- New customers (this month)
INSERT INTO your_metrics_table
SELECT MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)), YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)),
       COUNT(*), 'New Customers', 'Users', NOW()
FROM users
WHERE created_at >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
  AND created_at <  DATE_FORMAT(CURDATE(), '%Y-%m-01');

-- Active customers (your active definition) — users WHERE last_active >= month_start
--   AND created_at < month_end. This is the MAU-equivalent headline metric.

-- Activation rate % — share of new customers who reached your activation event
INSERT INTO your_metrics_table
SELECT MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)), YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)),
       ROUND(100 * COUNT(DISTINCT CASE WHEN s.user_id IS NOT NULL THEN u.id END)
             / NULLIF(COUNT(DISTINCT u.id), 0), 2),
       'Paid Conversion %', 'Users', NOW()
FROM users u
LEFT JOIN subscriptions s
  ON s.user_id = u.id AND s.type = 'paid' AND MONTH(s.created_at) = MONTH(u.created_at)
WHERE u.created_at >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
  AND u.created_at <  DATE_FORMAT(CURDATE(), '%Y-%m-01');


-- ============================================================================
-- ACQUISITION category
-- ============================================================================

-- New signups by platform — users, COUNT(DISTINCT id), GROUP BY platform
-- New signups by channel — JOIN attribution on utm_source / media_source
-- Returning vs new — split on whether a prior record exists


-- ============================================================================
-- SUBSCRIPTIONS / ORDERS category
-- ============================================================================

-- Paid subscription count by plan length — subscriptions, GROUP BY plan_period,
--   price > 0
-- Valid subscriptions at end of month — subscriptions, expiry_date > month_end,
--   created_at < month_end
-- Free / promotional grants — price = 0, GROUP BY promo_source/segment_id
--   (label each grant program by its source so the report can break them out)


-- ============================================================================
-- REVENUE category
-- ============================================================================

-- Revenue by plan tenure (net of tax)
--   net formula example: CASE WHEN tax_amount = 0 THEN price/1.18 ELSE price END
-- Total revenue (net of tax) — same without the plan filter
-- Revenue per paying customer — sum(net) / NULLIF(count(distinct user_id), 0)
-- % revenue from each plan tenure — share of net revenue per tenure x 100


-- ============================================================================
-- PLATFORM / SEGMENT category
-- ============================================================================

-- Revenue by platform & segment — subscriptions, GROUP BY platform, segment
-- Share of revenue from each platform/segment


-- ============================================================================
-- ENGAGEMENT category
-- ============================================================================

-- Core usage volume — sessions/payments aggregate over the month window
-- Unique active customers performing the core action — COUNT(DISTINCT user_id)
-- Average actions per active customer — total actions / distinct active users
-- Completion / success rate % — SUM(success)/NULLIF(count(*),0)*100


-- ============================================================================
-- LTV category
-- ============================================================================

-- 12-month average LTV (cohort) — users JOIN subscriptions, sub.created_at
-- within 12 months of user.created_at, grouped by cohort-maturity month.
INSERT INTO your_metrics_table
SELECT MONTH(DATE_ADD(u.created_at, INTERVAL 12 MONTH)) AS month,
       YEAR(DATE_ADD(u.created_at, INTERVAL 12 MONTH))  AS year,
       ROUND(SUM(CASE WHEN s.tax_amount = 0 THEN s.price/1.18 ELSE s.price END)
             / NULLIF(COUNT(DISTINCT u.id), 0), 0) AS value,
       '12 Month Avg LTV (cohort)', 'LTV', NOW()
FROM users u
JOIN subscriptions s ON s.user_id = u.id
WHERE s.created_at >= u.created_at
  AND s.created_at < DATE_ADD(u.created_at, INTERVAL 12 MONTH)
  AND DATE_ADD(u.created_at, INTERVAL 12 MONTH) <= CURDATE()
GROUP BY YEAR(DATE_ADD(u.created_at, INTERVAL 12 MONTH)),
         MONTH(DATE_ADD(u.created_at, INTERVAL 12 MONTH));


-- ============================================================================
-- INVESTIGATING >10% MOVES — variation patterns
-- ============================================================================
-- When the headline MoM delta on any metric > 10% (positive or negative), pull
-- one or more of these slices to find the driver:
--
-- 1. By SEGMENT / REGION — add a JOIN to the customer table and
--    GROUP BY region (or segment). Use whatever bucket your business reports on.
--
-- 2. By CUSTOMER TYPE — add WHERE segment = '...' to confirm which side moved.
--
-- 3. By PLAN TENURE — for subscription metrics, GROUP BY plan_period.
--    Tells you whether a plan-mix shift drove the change.
--
-- 4. By PLATFORM — add WHERE platform IN (...) or GROUP BY platform — surfaces
--    channel-level shifts (e.g. one platform dropping while another grew).
--
-- 5. By ACQUISITION CHANNEL — JOIN attribution on media_source / utm_source.
--
-- 6. By DAY — replace MONTH(...) groupings with DATE(created_at). A single-day
--    spike (e.g. a bulk billing run) vs sustained drift have very different
--    actions — check this first.
--
-- 7. By CAMPAIGN — JOIN attribution on campaign / utm_campaign for paid
--    acquisition. Useful when new-customer numbers swing with no organic cause.

-- The /monthly-analysis skill's "Root Cause Analysis" step runs (1) and (3)
-- automatically for headline gains/declines >10%. Use the rest manually for any
-- metric the auto-RCA didn't explain.
