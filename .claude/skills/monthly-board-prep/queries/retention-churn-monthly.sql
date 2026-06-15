-- EXAMPLE TEMPLATE — replace table/column names with your product's schema. The skill reads metrics from business.json.
--
-- Retention / churn detail source for the /monthly-analysis skill.
-- This populates the optional Retention/Churn section. Render it only if
-- business.json declares retention/churn metrics.
--
-- Source: your analytics/retention table (placeholder: your_retention_table).
-- NOTE: this may live in a separate schema or behind an analytics API and may
-- require additional grants. If access is denied, fall back to your analytics
-- API, or OMIT the section entirely. Do NOT publish stale prior-month numbers
-- under the latest-month header.
--
-- Substitute :YEAR (e.g. 2026) to pull a full year of monthly snapshots.
-- The skill compares the latest two months for which non-null data exists.

SELECT
  snapshot_date,
  month,
  metric,
  total
FROM (
  SELECT snapshot_date, month, 'active_account_count' AS metric, SUM(active_account_count) AS total
    FROM your_retention_table
    WHERE snapshot_date BETWEEN DATE(CONCAT(:YEAR, '-01-01')) AND DATE(CONCAT(:YEAR + 1, '-01-01'))
    GROUP BY snapshot_date, month
  UNION ALL
  SELECT snapshot_date, month, 'churned_count', SUM(churned_count)
    FROM your_retention_table
    WHERE snapshot_date BETWEEN DATE(CONCAT(:YEAR, '-01-01')) AND DATE(CONCAT(:YEAR + 1, '-01-01'))
    GROUP BY snapshot_date, month
  UNION ALL
  SELECT snapshot_date, month, 'reactivation_count', SUM(reactivation_count)
    FROM your_retention_table
    WHERE snapshot_date BETWEEN DATE(CONCAT(:YEAR, '-01-01')) AND DATE(CONCAT(:YEAR + 1, '-01-01'))
    GROUP BY snapshot_date, month
  UNION ALL
  SELECT snapshot_date, month, 'inactive_count', SUM(inactive_count)
    FROM your_retention_table
    WHERE snapshot_date BETWEEN DATE(CONCAT(:YEAR, '-01-01')) AND DATE(CONCAT(:YEAR + 1, '-01-01'))
    GROUP BY snapshot_date, month
  -- Add UNION ALL blocks for whatever engagement/status buckets business.json
  -- defines (e.g. low_activity, medium_activity, high_activity cohorts).
) x
ORDER BY month, metric;

-- Derived metrics the report can render:
--   Net churn        = (prior active_account_count) - (current active_account_count) + (new accounts in month)
--   Net churn rate % = Net churn / prior active_account_count
--   Churn %          = churned_count / active_account_count
--   Reactivation     = reactivation_count
--   Status-bucket %  = each engagement/status bucket / active_account_count
--
-- Optional filter dimensions: segment, region, plan, channel, platform.
-- Add WHERE clauses as needed to match your analytics dashboard.
