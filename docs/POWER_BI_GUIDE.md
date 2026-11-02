# Power BI build guide (planned)

The dashboard is **not built yet**. Build it on the loan status, so Power BI shows exactly what SQL shows.

## 1. Data

Easiest route: in PostgreSQL run `sql/04_analysis.sql`, then export the view to CSV:

```sql
\copy (SELECT * FROM v_loan_status) TO 'outputs/loan_status.csv' WITH (FORMAT csv, HEADER true)
```

Load into Power BI: `loan_status.csv`, `customers.csv`, `applications.csv`.
Relationships: `customers[customer_id]` → `loan_status[customer_id]` and → `applications[customer_id]` (one-to-many).
Add a date table and link it to `loan_status[disbursement_date]`.

## 2. Measures

```
Active Outstanding = CALCULATE(SUM(loan_status[outstanding]), loan_status[is_closed] = FALSE())
NPA Outstanding = CALCULATE([Active Outstanding], loan_status[asset_class] = "NPA")
GNPA % = DIVIDE([NPA Outstanding], [Active Outstanding])
PAR 30 % = DIVIDE(CALCULATE([Active Outstanding], loan_status[current_dpd] > 30), [Active Outstanding])
Active Loans = CALCULATE(COUNTROWS(loan_status), loan_status[is_closed] = FALSE())
NPA Loans = CALCULATE([Active Loans], loan_status[asset_class] = "NPA")
Ever 30+ % = DIVIDE(CALCULATE(COUNTROWS(loan_status), loan_status[max_days_late] >= 30), COUNTROWS(loan_status))
Approval Rate % = DIVIDE(
    CALCULATE(COUNTROWS(applications), applications[application_status] = "Approved"),
    CALCULATE(COUNTROWS(applications), applications[application_status] <> "Pending"))
Branch GNPA Rank = RANKX(ALL(loan_status[branch]), [GNPA %], , DESC)
```

## 3. Pages

1. **Portfolio overview:** cards (Active Loans, Active Outstanding, GNPA %, PAR 30 %, NPA Loans); outstanding by asset_class (bar, in order Standard → NPA); GNPA % by loan_type.
2. **Underwriting:** Approval Rate % by loan_type; rejections by rejection_reason.
3. **Scorecard:** Ever 30+ % by score_band; NPA rate by score_band.
4. **Branches & collections:** GNPA % by branch with rank; table of SMA-1 / SMA-2 loans sorted by current_dpd.

## 4. Check your numbers

| Measure (no filters) | Expected |
| --- | --- |
| Active Loans | 1,750 |
| Active Outstanding | ₹110.98 crore |
| GNPA % / PAR 30 % | 3.96% / 4.59% |
| NPA Loans | 91 |
| Approval Rate % | 52.6% |
| Ever 30+ % by band A / B / C / D | 5.9% / 13.5% / 18.4% / 30.9% |
