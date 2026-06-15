-- Full offer inventory: every (trigger, validity, segment) combination in window.
-- Replace the <...> placeholders with the real schema names from business.json (stack.offer_schema).
-- Replace :SINCE and :UNTIL with 'YYYY-MM-DD'.
SELECT
  <trigger_attr>,
  <validity_attr>,
  <segment_attr>,
  COUNT(*)                       AS grants,
  COUNT(DISTINCT <subject_id>)   AS unique_subjects,
  MIN(<created_attr>)            AS first_seen,
  MAX(<created_attr>)            AS last_seen
FROM <offer_table>
WHERE <created_attr> >= ':SINCE' AND <created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY <trigger_attr>, <validity_attr>, <segment_attr>
ORDER BY grants DESC;
</content>
