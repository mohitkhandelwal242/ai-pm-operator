-- EXAMPLE TEMPLATE — replace table/column names with your product's schema. The skill reads metrics from business.json.
--
-- Monthly comparison query for the /monthly-analysis skill.
-- Pulls all metrics from your metrics store for two months side-by-side.
--
-- Substitute :YEAR_A / :MONTH_A (current) and :YEAR_B / :MONTH_B (prior).
-- Example: April 2026 vs March 2026 -> A=(2026,4), B=(2026,3)
--
-- Expected shape of `your_metrics_table` (adapt to your schema):
--   year        smallint
--   month       tinyint
--   category    varchar   -- maps to a report section / metric group
--   metric_name varchar
--   value       decimal

SELECT
  a.category,
  a.metric_name,
  a.value   AS current_value,
  b.value   AS prior_value,
  CASE WHEN b.value IS NULL OR b.value = 0 THEN NULL
       ELSE ROUND(((a.value - b.value) / b.value) * 100, 2)
  END AS pct_change
FROM (
  SELECT category, metric_name, SUM(value) AS value
  FROM your_metrics_table
  WHERE year = :YEAR_A AND month = :MONTH_A
  GROUP BY category, metric_name
) a
LEFT JOIN (
  SELECT category, metric_name, SUM(value) AS value
  FROM your_metrics_table
  WHERE year = :YEAR_B AND month = :MONTH_B
  GROUP BY category, metric_name
) b
  ON a.category = b.category AND a.metric_name = b.metric_name
ORDER BY a.category, a.metric_name;

-- The set of categories should mirror the metric groups you derive from
-- business.json (e.g. Revenue, Acquisition, Activation, Engagement, Retention).
