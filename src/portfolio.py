"""
Loan status as of the business date, computed in Python.

This mirrors the SQL view v_loan_status in sql/04_analysis.sql, so the two can
be checked against each other.
"""
import numpy as np
import pandas as pd

import config as C


def loan_status(loans, apps, reps):
    """Return one row per loan with current DPD, asset class, outstanding principal and closed flag."""
    as_of = pd.Timestamp(C.AS_OF_DATE)
    reps = reps.copy()
    reps["due_date"] = pd.to_datetime(reps["due_date"])
    g = reps.groupby("loan_id")
    paid = g.payment_status.apply(lambda s: (s != "Unpaid").sum())
    oldest_unpaid = reps[reps.payment_status == "Unpaid"].groupby("loan_id").due_date.min()
    max_late = g.days_late.max()

    df = loans.merge(apps[["application_id", "score_band", "scorecard_points"]], on="application_id")
    df["instalments_paid"] = df.loan_id.map(paid).fillna(0).astype(int)
    df["max_days_late"] = df.loan_id.map(max_late).fillna(0).astype(int)
    df["current_dpd"] = (as_of - df.loan_id.map(oldest_unpaid)).dt.days.fillna(0).astype(int)
    df["asset_class"] = df.current_dpd.apply(C.asset_class)
    df["is_closed"] = df.instalments_paid >= df.tenure_months

    r = df.interest_rate / 1200
    k = df.instalments_paid
    bal = df.disbursed_amount * (1 + r) ** k - df.emi_amount * ((1 + r) ** k - 1) / r
    df["outstanding"] = np.maximum(bal, 0).round(2)
    return df


def auc(scores_bad_high, is_bad):
    """Area under the ROC curve via ranks (Mann-Whitney). 0.5 = no skill, 1.0 = perfect."""
    s = pd.Series(scores_bad_high).rank()
    y = pd.Series(is_bad).astype(bool).values
    n1, n0 = y.sum(), (~y).sum()
    return (s[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
