-- Conversion per program (cohort): of subjects who got an offer in window,
-- how many completed a paid event strictly after the offer?
-- Replace the <...> placeholders with the real schema names from business.json (stack.offer_schema).
-- Replace :SINCE and :UNTIL — the COHORT window is wider than the inventory window
-- (typically inventory=last 30d, cohort=last 90d).
SELECT
  program,
  got_offer,
  later_paid,
  ROUND(100*later_paid/NULLIF(got_offer,0), 2)   AS conv_pct,
  revenue,
  ROUND(revenue/NULLIF(later_paid,0), 0)         AS rev_per_converter
FROM (
  SELECT
    CASE
      WHEN offer.<trigger_attr> LIKE 'FREE_%'                                           THEN offer.<trigger_attr>
      WHEN offer.<segment_attr> LIKE '<campaign_a_prefix>%'                             THEN 'Campaign A'
      WHEN offer.<segment_attr> LIKE '<campaign_b_prefix>%'                             THEN 'Campaign B'
      WHEN offer.<segment_attr> LIKE 'manual:support%'                                  THEN 'Manual / support'
      WHEN offer.<validity_attr> = <long_validity>
           AND offer.<segment_attr> LIKE '<bootstrap_pattern>%'                         THEN 'New-market bootstrap'
      WHEN offer.<validity_attr> = <long_validity>
           AND offer.<segment_attr> LIKE '<cohort_pattern>%'                            THEN 'Cohort (long validity)'
      WHEN offer.<segment_attr> IS NULL OR offer.<segment_attr> = ''                    THEN 'NULL segment'
      ELSE 'Unclassified'
    END AS program,
    COUNT(DISTINCT offer.<subject_id>) AS got_offer,
    COUNT(DISTINCT paid.<subject_id>)  AS later_paid,
    ROUND(SUM(paid.<amount_attr>), 0)  AS revenue
  FROM <offer_table> offer
  LEFT JOIN <paid_event> paid
    ON paid.<subject_id> = offer.<subject_id>
    AND paid.<amount_attr> > 0
    AND paid.<created_attr> > offer.<created_attr>
  WHERE offer.<created_attr> >= ':SINCE' AND offer.<created_attr> < DATE_ADD(':UNTIL', INTERVAL 1 DAY)
    AND offer.<is_free_or_discounted>
  GROUP BY program
) x
ORDER BY got_offer DESC;
</content>
