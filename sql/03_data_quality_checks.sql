-- CreditPulse: data-quality and policy checks. Run after loading.

DROP VIEW IF EXISTS v_dq_exceptions;
CREATE VIEW v_dq_exceptions AS

-- 1. Loan disbursed before its application was made
SELECT 'Loan disbursed before application' AS check_name, l.loan_id AS record_id,
       'Applied ' || a.application_date || ', disbursed ' || l.disbursement_date AS detail
FROM loans l JOIN applications a ON a.application_id = l.application_id
WHERE l.disbursement_date < a.application_date

UNION ALL
-- 2. Policy exception: approved although the bureau score is below the 650 minimum
SELECT 'Approved below minimum bureau score', a.application_id, 'Score ' || c.credit_bureau_score
FROM applications a JOIN customers c ON c.customer_id = a.customer_id
WHERE a.application_status = 'Approved' AND c.credit_bureau_score < 650

UNION ALL
-- 3. Marked "Paid on Time" but less than the EMI was paid
SELECT 'Partial payment marked Paid on Time', repayment_id, 'Paid ' || paid_amount || ' of ' || due_amount
FROM repayments
WHERE payment_status = 'Paid on Time' AND paid_amount < due_amount

UNION ALL
-- 4. Payment dated after the business date
SELECT 'Payment after business date', repayment_id, 'Paid ' || paid_date
FROM repayments
WHERE paid_date > DATE '2026-09-30'

UNION ALL
-- 5. Unpaid instalment that still has a paid date or amount
SELECT 'Unpaid instalment with payment recorded', repayment_id, 'paid_date ' || COALESCE(paid_date::text, '-')
FROM repayments
WHERE payment_status = 'Unpaid' AND (paid_date IS NOT NULL OR paid_amount > 0)

UNION ALL
-- 6. Repayment booked to a different customer than the loan
SELECT 'Repayment customer differs from loan', r.repayment_id, r.customer_id || ' vs ' || l.customer_id
FROM repayments r JOIN loans l ON l.loan_id = r.loan_id
WHERE r.customer_id <> l.customer_id

UNION ALL
-- 7. EMI does not match the standard formula P*r*(1+r)^n / ((1+r)^n - 1), tolerance 1 rupee
SELECT 'EMI does not match formula', loan_id, 'EMI ' || emi_amount
FROM loans
WHERE ABS(emi_amount - disbursed_amount * (interest_rate / 1200) * POWER(1 + interest_rate / 1200, tenure_months)
                      / (POWER(1 + interest_rate / 1200, tenure_months) - 1)) > 1

UNION ALL
-- 8. Approved application without a loan, or loan without an approved application
SELECT 'Approval and loan do not match', a.application_id, a.application_status
FROM applications a FULL JOIN loans l ON l.application_id = a.application_id
WHERE (a.application_status = 'Approved') <> (l.loan_id IS NOT NULL);

SELECT c.check_name, COUNT(d.record_id) AS exceptions
FROM (VALUES ('Loan disbursed before application'), ('Approved below minimum bureau score'),
             ('Partial payment marked Paid on Time'), ('Payment after business date'),
             ('Unpaid instalment with payment recorded'), ('Repayment customer differs from loan'),
             ('EMI does not match formula'), ('Approval and loan do not match')) AS c(check_name)
LEFT JOIN v_dq_exceptions d ON d.check_name = c.check_name
GROUP BY c.check_name
ORDER BY exceptions DESC, c.check_name;
