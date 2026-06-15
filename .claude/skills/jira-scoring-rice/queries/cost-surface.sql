-- Face-value cost surface per program × validity.
-- Replace the <...> placeholders with the real schema names from business.json (stack.offer_schema).
-- Face values are placeholders — verify against the business's plan / discount pricing and update.
SELECT
  program,
  <validity_attr>,
  grants,
  face_value,
  grants * face_value AS total_face_cost
FROM (
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
    COUNT(*) AS grants,
    -- Map each validity bucket (or discount tier) to its face value from the business's pricing.
    CASE <validity_attr>
      WHEN <short_validity>  THEN <short_face_value>
      WHEN <medium_validity> THEN <medium_face_value>
      WHEN <long_validity>   THEN <long_face_value>
      ELSE 0
    END AS face_value
  FROM <offer_table>
  WHERE <created_attr> >= ':SINCE' AND <created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
    AND <is_free_or_discounted>
  GROUP BY program, <validity_attr>
) x
ORDER BY total_face_cost DESC;
</content>
