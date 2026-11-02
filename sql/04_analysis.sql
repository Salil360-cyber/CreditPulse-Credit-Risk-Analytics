-- CreditPulse: portfolio analysis. Business date 2026-09-30.

-- Loan status as of the business date: one row per loan.
--   current_dpd   = days since the OLDEST unpaid instalment fell due (0 if nothing is unpaid)
--   asset_class   = Standard / SMA-0 (1-30) / SMA-1 (31-60) / SMA-2 (61-90) / NPA (90+)
--   outstanding   = principal still owed after the instalments actually paid (amortisation formula)
DROP VIEW IF EXISTS v_loan_status;
CREATE VIEW v_loan_status AS
WITH r AS (
    SELECT loan_id,
           COUNT(*) FILTER (WHERE payment_status <> 'Unpaid')       AS instalments_paid,
           MIN(due_date) FILTER (WHERE payment_status = 'Unpaid')   AS oldest_unpaid_due,
           MAX(days_late)                                           AS max_days_late
    FROM repayments
    GROUP BY loan_id
)
SELECT l.*, a.score_band, a.scorecard_points,
       COALESCE(r.instalments_paid, 0)                                     AS instalments_paid,
       COALESCE(r.max_days_late, 0)                                        AS max_days_late,
       COALESCE(DATE '2026-09-30' - r.oldest_unpaid_due, 0)                AS current_dpd,
       CASE WHEN r.oldest_unpaid_due IS NULL
              OR r.oldest_unpaid_due >= DATE '2026-09-30'          THEN 'Standard'   -- due today = not overdue yet
            WHEN DATE '2026-09-30' - r.oldest_unpaid_due <= 30     THEN 'SMA-0'
            WHEN DATE '2026-09-30' - r.oldest_unpaid_due <= 60     THEN 'SMA-1'
            WHEN DATE '2026-09-30' - r.oldest_unpaid_due <= 90     THEN 'SMA-2'
            ELSE 'NPA' END                                                 AS asset_class,
       COALESCE(r.instalments_paid, 0) >= l.tenure_months                  AS is_closed,
       GREATEST(0, ROUND(
           l.disbursed_amount * POWER(1 + l.interest_rate / 1200, COALESCE(r.instalments_paid, 0))
         - l.emi_amount * (POWER(1 + l.interest_rate / 1200, COALESCE(r.instalments_paid, 0)) - 1) / (l.interest_rate / 1200)
       , 2))                                                               AS outstanding
FROM loans l
JOIN applications a ON a.application_id = l.application_id
LEFT JOIN r ON r.loan_id = l.loan_id;

-- Q1. Application funnel by product
SELECT loan_type,
       COUNT(*) AS applications,
       COUNT(*) FILTER (WHERE application_status = 'Approved') AS approved,
       ROUND(100.0 * COUNT(*) FILTER (WHERE application_status = 'Approved')
             / NULLIF(COUNT(*) FILTER (WHERE application_status <> 'Pending'), 0), 1) AS approval_rate_pct
FROM applications
GROUP BY loan_type
ORDER BY approval_rate_pct DESC;

-- Q2. Why applications are rejected
SELECT rejection_reason, COUNT(*) AS rejected,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
FROM applications
WHERE application_status = 'Rejected'
GROUP BY rejection_reason
ORDER BY rejected DESC;

-- Q3. Portfolio headline (active loans only)
SELECT COUNT(*)                                                                   AS active_loans,
       ROUND(SUM(outstanding) / 1e7, 2)                                           AS outstanding_cr,
       COUNT(*) FILTER (WHERE asset_class = 'NPA')                                AS npa_loans,
       ROUND(100.0 * SUM(outstanding) FILTER (WHERE asset_class = 'NPA') / SUM(outstanding), 2) AS gnpa_pct,
       ROUND(100.0 * SUM(outstanding) FILTER (WHERE current_dpd > 30)  / SUM(outstanding), 2)  AS par30_pct
FROM v_loan_status
WHERE NOT is_closed;

-- Q4. Asset classification (active loans)
SELECT asset_class, COUNT(*) AS loans, ROUND(SUM(outstanding) / 1e5, 1) AS outstanding_lakh,
       ROUND(100.0 * SUM(outstanding) / SUM(SUM(outstanding)) OVER (), 2) AS share_of_book_pct
FROM v_loan_status
WHERE NOT is_closed
GROUP BY asset_class
ORDER BY CASE asset_class WHEN 'Standard' THEN 1 WHEN 'SMA-0' THEN 2 WHEN 'SMA-1' THEN 3 WHEN 'SMA-2' THEN 4 ELSE 5 END;

-- Q5. Risk by product (active loans)
SELECT loan_type, COUNT(*) AS active_loans,
       COUNT(*) FILTER (WHERE asset_class = 'NPA') AS npa_loans,
       ROUND(100.0 * SUM(outstanding) FILTER (WHERE asset_class = 'NPA') / SUM(outstanding), 2) AS gnpa_pct,
       ROUND(100.0 * SUM(outstanding) FILTER (WHERE current_dpd > 30)  / SUM(outstanding), 2) AS par30_pct
FROM v_loan_status
WHERE NOT is_closed
GROUP BY loan_type
ORDER BY gnpa_pct DESC;

-- Q6. Does the application scorecard work? Outcomes by score band (all disbursed loans)
SELECT score_band, COUNT(*) AS loans,
       ROUND(100.0 * COUNT(*) FILTER (WHERE max_days_late >= 30) / COUNT(*), 1) AS ever_30plus_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE asset_class = 'NPA') / COUNT(*), 1) AS npa_now_pct
FROM v_loan_status
GROUP BY score_band
ORDER BY score_band;

-- Q7. Vintage: how loans disbursed in each half-year have performed
SELECT EXTRACT(YEAR FROM disbursement_date)::int || '-H' || CASE WHEN EXTRACT(MONTH FROM disbursement_date) <= 6 THEN 1 ELSE 2 END AS vintage,
       COUNT(*) AS loans,
       ROUND(100.0 * COUNT(*) FILTER (WHERE max_days_late >= 30) / COUNT(*), 1) AS ever_30plus_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE asset_class = 'NPA') / COUNT(*), 1) AS npa_now_pct
FROM v_loan_status
GROUP BY 1
ORDER BY 1;

-- Q8. Branches ranked by GNPA (active loans)
SELECT branch, COUNT(*) AS active_loans,
       ROUND(100.0 * SUM(outstanding) FILTER (WHERE asset_class = 'NPA') / SUM(outstanding), 2) AS gnpa_pct,
       RANK() OVER (ORDER BY SUM(outstanding) FILTER (WHERE asset_class = 'NPA') / SUM(outstanding) DESC NULLS LAST) AS risk_rank
FROM v_loan_status
WHERE NOT is_closed
GROUP BY branch
ORDER BY risk_rank;

-- Q9. Collections priority list: SMA-1 and SMA-2 loans, before they become NPA
SELECT v.loan_id, c.customer_name, v.loan_type, v.branch, v.asset_class, v.current_dpd, v.outstanding
FROM v_loan_status v
JOIN customers c ON c.customer_id = v.customer_id
WHERE v.asset_class IN ('SMA-1', 'SMA-2')
ORDER BY v.current_dpd DESC, v.outstanding DESC;
