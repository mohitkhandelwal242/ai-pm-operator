-- Orphan / misconfigured offer rules — patterns to flag for cleanup.
-- Replace the <...> placeholders with the real schema names from business.json (stack.offer_schema).

-- (A) Single-occurrence short-validity rules.
--     Exclude any program that is short-validity by design (list its trigger in NOT IN).
SELECT
  <trigger_attr>,
  <validity_attr>,
  <segment_attr>,
  COUNT(*)             AS n,
  MIN(<created_attr>)  AS first_seen,
  MAX(<created_attr>)  AS last_seen
FROM <offer_table>
WHERE <created_attr> >= ':SINCE' AND <created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
  AND <validity_attr> = <short_validity>
  AND <trigger_attr> NOT IN (<by_design_short_validity_triggers>)
GROUP BY <trigger_attr>, <validity_attr>, <segment_attr>
HAVING n <= 3
ORDER BY first_seen;

-- (B) Trigger-string variants that look like the same action (naming inconsistency).
-- Heuristic: lowercase + collapse underscores → canonical group; flag groups with > 1 variant.
SELECT
  REPLACE(REPLACE(LOWER(<trigger_attr>),'_',' '),'  ',' ') AS canonical_trigger,
  COUNT(DISTINCT <trigger_attr>)                            AS variant_count,
  COUNT(*)                                                  AS grants,
  GROUP_CONCAT(DISTINCT <trigger_attr> SEPARATOR ' | ')     AS variants
FROM <offer_table>
WHERE <created_attr> >= ':SINCE' AND <created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY canonical_trigger
HAVING variant_count > 1
ORDER BY grants DESC;
</content>
