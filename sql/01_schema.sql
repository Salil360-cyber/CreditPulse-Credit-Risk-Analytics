-- CreditPulse: table definitions (PostgreSQL). Run first.

DROP TABLE IF EXISTS repayments, loans, applications, customers CASCADE;

CREATE TABLE customers (
    customer_id          VARCHAR(12) PRIMARY KEY,
    customer_name        VARCHAR(60) NOT NULL,
    gender               VARCHAR(10) NOT NULL,
    age                  INT         NOT NULL,
    city                 VARCHAR(30) NOT NULL,
    state                VARCHAR(30) NOT NULL,
    employment_type      VARCHAR(15) NOT NULL,       -- Salaried / Self-Employed
    occupation           VARCHAR(30) NOT NULL,
    years_in_business    INT,                        -- only for Self-Employed
    monthly_income       NUMERIC(12,2) NOT NULL,
    credit_bureau_score  INT         NOT NULL,       -- 300-900
    existing_loans_count INT         NOT NULL,       -- loans with other lenders
    existing_emi         NUMERIC(12,2) NOT NULL,     -- monthly EMIs on those loans
    customer_since       DATE        NOT NULL
);

CREATE TABLE applications (
    application_id     VARCHAR(12) PRIMARY KEY,
    customer_id        VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    application_date   DATE        NOT NULL,
    loan_type          VARCHAR(20) NOT NULL,
    requested_amount   NUMERIC(14,2) NOT NULL,
    tenure_months      INT         NOT NULL,
    interest_rate      NUMERIC(5,2) NOT NULL,
    foir               NUMERIC(6,4) NOT NULL,        -- (all EMIs incl. the new one) / monthly income
    scorecard_points   INT         NOT NULL,         -- application scorecard, 0-100
    score_band         CHAR(1)     NOT NULL,         -- A (best) to D
    application_status VARCHAR(10) NOT NULL CHECK (application_status IN ('Approved', 'Rejected', 'Pending')),
    rejection_reason   VARCHAR(30)
);

CREATE TABLE loans (
    loan_id            VARCHAR(12) PRIMARY KEY,
    application_id     VARCHAR(12) NOT NULL UNIQUE REFERENCES applications(application_id),
    customer_id        VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    loan_type          VARCHAR(20) NOT NULL,
    disbursed_amount   NUMERIC(14,2) NOT NULL,
    disbursement_date  DATE        NOT NULL,
    tenure_months      INT         NOT NULL,
    interest_rate      NUMERIC(5,2) NOT NULL,
    emi_amount         NUMERIC(12,2) NOT NULL,
    branch             VARCHAR(30) NOT NULL,
    loan_officer       VARCHAR(30) NOT NULL
);

-- One row per instalment that has fallen due on or before the business date (2026-09-30).
CREATE TABLE repayments (
    repayment_id    VARCHAR(12) PRIMARY KEY,
    loan_id         VARCHAR(12) NOT NULL REFERENCES loans(loan_id),
    customer_id     VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    installment_no  INT         NOT NULL,
    due_date        DATE        NOT NULL,
    due_amount      NUMERIC(12,2) NOT NULL,
    paid_date       DATE,                         -- NULL = not paid by the business date
    paid_amount     NUMERIC(12,2) NOT NULL,
    payment_status  VARCHAR(15) NOT NULL CHECK (payment_status IN ('Paid on Time', 'Paid Late', 'Unpaid')),
    days_late       INT         NOT NULL,         -- paid late: days late; unpaid: days overdue today; on time: 0
    UNIQUE (loan_id, installment_no)
);

CREATE INDEX idx_rep_loan_status ON repayments(loan_id, payment_status);
CREATE INDEX idx_loans_customer  ON loans(customer_id);
