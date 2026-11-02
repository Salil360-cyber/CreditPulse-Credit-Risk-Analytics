-- CreditPulse: load the CSV files.
--
-- psql (from the repository root):
--     psql -d creditpulse -f sql/01_schema.sql -f sql/02_load.sql
-- pgAdmin: right-click each table -> Import/Export Data -> Import, file from data/,
--     Format csv, Header ON. Load in this order: customers, applications, loans, repayments.

\copy customers    FROM 'data/customers.csv'    WITH (FORMAT csv, HEADER true)
\copy applications FROM 'data/applications.csv' WITH (FORMAT csv, HEADER true)
\copy loans        FROM 'data/loans.csv'        WITH (FORMAT csv, HEADER true)
\copy repayments   FROM 'data/repayments.csv'   WITH (FORMAT csv, HEADER true)

SELECT 'customers' AS table_name, COUNT(*) FROM customers
UNION ALL SELECT 'applications', COUNT(*) FROM applications
UNION ALL SELECT 'loans', COUNT(*) FROM loans
UNION ALL SELECT 'repayments', COUNT(*) FROM repayments;
