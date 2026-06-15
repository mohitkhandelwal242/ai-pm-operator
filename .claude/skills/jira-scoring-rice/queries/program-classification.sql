-- Program classification driven by the segment/campaign attribute (not the surface trigger alone).
-- Replace the <...> placeholders with the real schema names from business.json (stack.offer_schema).
-- Replace :SINCE and :UNTIL with 'YYYY-MM-DD'.
SELECT
  CASE
    WHEN <trigger_attr> LIKE 'FREE_%'                                            THEN <trigger_attr>
    WHEN <segment_attr> LIKE '<campaign_a_prefix>%'                              THEN 'Campaign A'
    WHEN <segment_attr> LIKE '<campaign_b_prefix>%'                              THEN 'Campaign B'
    WHEN <segment_attr> LIKE 'manual:support%'                                   THEN 'Manual / support'
    WHEN <validity_attr> = <long_validity> AND <segment_attr> LIKE '<bootstrap_pattern>%' THEN 'New-market bootstrap'
    WHEN <validity_attr> = <long_validity> AND <segment_attr> LIKE '<cohort_pattern>%'    THEN 'Cohort (long validity)'
    WHEN <segment_attr> IS NULL OR <segment_attr> = ''                           THEN 'NULL segment'
    ELSE 'Unclassified'
  END AS program,
  <validity_attr>,
  COUNT(*)                                  AS grants,
  COUNT(DISTINCT <trigger_attr>)            AS distinct_triggers,
  COUNT(DISTINCT <subject_id>)              AS unique_subjects,
  COUNT(DISTINCT <segment_attr>)            AS distinct_segments
FROM <offer_table>
WHERE <created_attr> >= ':SINCE' AND <created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
  AND <is_free_or_discounted>
GROUP BY program, <validity_attr>
ORDER BY grants DESC;
</content>
