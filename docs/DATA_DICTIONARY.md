# Data dictionary

All data is synthetic. Business date: **2026-09-30**. Amounts in INR. Dates are YYYY-MM-DD.

## customers.csv (3,000 rows)

| Column | Meaning |
| --- | --- |
| customer_id | CUST-10001 … |
| customer_name, gender | First name always matches the gender |
| age | 23–60 |
| city, state | City and its state; the city decides the branch |
| employment_type | Salaried or Self-Employed |
| occupation | Job matching the employment type |
| years_in_business | Only for Self-Employed (empty for Salaried) |
| monthly_income | Monthly income |
| credit_bureau_score | 300–900 |
| existing_loans_count | Loans with other lenders |
| existing_emi | Monthly EMIs on those loans |
| customer_since | Relationship start date |

## applications.csv (5,000 rows)

| Column | Meaning |
| --- | --- |
| application_id | APP-50001 … |
| application_date | 2023-01-01 to 2026-09-30 |
| loan_type | Home Loan, Auto Loan, Personal Loan, Business Loan, Consumer Durable |
| requested_amount, tenure_months, interest_rate | Requested terms |
| foir | (existing EMIs + EMIs on other CreditPulse loans still running + this EMI) ÷ monthly income |
| scorecard_points, score_band | Application scorecard (see README) |
| application_status | Approved, Rejected, Pending (last 14 days) |
| rejection_reason | Low Credit Score, High FOIR, Unstable Employment, Incomplete Documentation |

## loans.csv (2,608 rows)

One loan per approved application, disbursed 3–15 days after applying.

| Column | Meaning |
| --- | --- |
| loan_id, application_id, customer_id | Keys |
| loan_type, disbursed_amount, tenure_months, interest_rate | Same as the application |
| disbursement_date | Disbursement date |
| emi_amount | P × r × (1+r)^n ÷ ((1+r)^n − 1), r = monthly rate |
| branch, loan_officer | Branch in the customer's city, one of its two officers |

## repayments.csv (48,263 rows)

One row per EMI that fell due on or before the business date. EMI k is due k months after disbursement.

| Column | Meaning |
| --- | --- |
| repayment_id | REP-100001 … |
| loan_id, customer_id | Keys |
| installment_no | 1, 2, 3 … |
| due_date, due_amount | When and how much was due |
| paid_date | Empty if not paid by the business date |
| paid_amount | 0 if unpaid |
| payment_status | Paid on Time, Paid Late, Unpaid |
| days_late | Paid Late: days late. Unpaid: days overdue on the business date. Paid on Time: 0 |

Borrowers who stop paying may later "cure": they pay all missed EMIs at once, and those rows become Paid Late.

## Derived (not stored): loan status

Built by `v_loan_status` (SQL) and `portfolio.py` (Python):

| Field | Rule |
| --- | --- |
| current_dpd | Business date − due date of the oldest Unpaid EMI (0 if none) |
| asset_class | Standard 0 · SMA-0 1–30 · SMA-1 31–60 · SMA-2 61–90 · NPA 90+ |
| outstanding | Principal left after the EMIs actually paid (amortisation formula) |
| is_closed | All EMIs of the tenure have been paid |

## Planted data-quality problems

| Problem | Count | Found by |
| --- | --- | --- |
| Partial payments marked Paid on Time | 5 | DQ check 3 |
| Loans disbursed before the application date | 4 | DQ check 1 |
| Approved below the minimum bureau score | 3 | DQ check 2 |
