"""Tests for the CreditPulse rules and data. Run: python -m pytest -q"""
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import config as C  # noqa: E402
from portfolio import auc, loan_status  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
CUST = pd.read_csv(os.path.join(DATA, "customers.csv"))
APPS = pd.read_csv(os.path.join(DATA, "applications.csv"))
LOANS = pd.read_csv(os.path.join(DATA, "loans.csv"))
REPS = pd.read_csv(os.path.join(DATA, "repayments.csv"))


# ---------------------------------------------------------------- rules
def test_asset_class_boundaries():
    assert [C.asset_class(d) for d in (0, 1, 30, 31, 60, 61, 90, 91)] == \
        ["Standard", "SMA-0", "SMA-0", "SMA-1", "SMA-1", "SMA-2", "SMA-2", "NPA"]


def test_emi_formula_known_value():
    # 5,00,000 at 12% for 60 months -> EMI 11,122.22 (standard textbook value)
    assert round(C.emi(500_000, 12, 60), 2) == 11122.22


def test_auc_perfect_and_random():
    assert auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert auc([1, 1, 1, 1], [0, 1, 0, 1]) == 0.5


# ---------------------------------------------------------------- data
def test_names_match_gender():
    first = CUST.customer_name.str.split().str[0]
    assert first[CUST.gender == "Male"].isin(C.MALE_NAMES).all()
    assert first[CUST.gender == "Female"].isin(C.FEMALE_NAMES).all()


def test_no_payment_after_business_date():
    paid = pd.to_datetime(REPS.paid_date.dropna())
    assert (paid <= pd.Timestamp(C.AS_OF_DATE)).all()
    assert (pd.to_datetime(REPS.due_date) <= pd.Timestamp(C.AS_OF_DATE)).all()


def test_emi_matches_formula_for_every_loan():
    calc = [C.emi(p, r, n) for p, r, n in zip(LOANS.disbursed_amount, LOANS.interest_rate, LOANS.tenure_months)]
    assert (abs(LOANS.emi_amount - pd.Series(calc)) <= 0.01).all()


def test_underwriting_rules_explain_every_decision_except_planted():
    a = APPS.merge(CUST, on="customer_id")
    a = a[a.application_status != "Pending"]
    low = a.credit_bureau_score < C.MIN_BUREAU_SCORE
    # Every rejection for Low Credit Score really has a low score, every High FOIR really is above the limit.
    assert (a.loc[a.rejection_reason == "Low Credit Score", "credit_bureau_score"] < C.MIN_BUREAU_SCORE).all()
    assert (a.loc[a.rejection_reason == "High FOIR", "foir"] > C.MAX_FOIR).all()
    # Approved loans pass the rules, except the 3 planted policy exceptions (low score).
    ok = a[a.application_status == "Approved"]
    exceptions = ok.credit_bureau_score < C.MIN_BUREAU_SCORE
    assert exceptions.sum() == 3
    assert (ok.loc[~exceptions, "foir"] <= C.MAX_FOIR).all()


def test_one_repayment_row_per_instalment_due():
    as_of = pd.Timestamp(C.AS_OF_DATE)
    counts = REPS.groupby("loan_id").size()
    loans = LOANS.copy()
    loans["due_so_far"] = [
        sum(1 for k in range(1, n + 1) if pd.Timestamp(d) + pd.DateOffset(months=k) <= as_of)
        for d, n in zip(loans.disbursement_date, loans.tenure_months)]
    # The 4 planted loans had their disbursement date moved, so skip them here.
    planted = LOANS.merge(APPS, on="application_id").query("disbursement_date < application_date").loan_id
    loans = loans[~loans.loan_id.isin(planted)]
    assert (loans.loan_id.map(counts).fillna(0).astype(int) == loans.due_so_far).all()


def test_portfolio_kpis_are_in_a_realistic_range():
    df = loan_status(LOANS, APPS, REPS)
    act = df[~df.is_closed]
    gnpa = act.loc[act.asset_class == "NPA", "outstanding"].sum() / act.outstanding.sum()
    assert 0.01 < gnpa < 0.08
