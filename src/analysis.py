"""
CreditPulse analysis: KPIs, scorecard validation and charts.

    python src/analysis.py

Writes outputs/summary.json and three charts. Every headline number in the README comes from here
or from outputs/sql_results.txt.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
from portfolio import auc, loan_status

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)
NAVY, TEAL, GREY, RED = "#1F3A5F", "#2A9D8F", "#9AA5B1", "#C0392B"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

apps = pd.read_csv(os.path.join(DATA, "applications.csv"))
loans = pd.read_csv(os.path.join(DATA, "loans.csv"), parse_dates=["disbursement_date"])
reps = pd.read_csv(os.path.join(DATA, "repayments.csv"))
df = loan_status(loans, apps, reps)
active = df[~df.is_closed]

s = {}
decided = apps[apps.application_status != "Pending"]
s["applications"] = int(len(apps))
s["approval_rate_pct"] = round(100 * (decided.application_status == "Approved").mean(), 1)
s["top_rejection_reason"] = decided.rejection_reason.value_counts().index[0]
s["top_rejection_share_pct"] = round(100 * decided.rejection_reason.value_counts(normalize=True).iloc[0], 1)
s["loans_disbursed"] = int(len(df))
s["active_loans"] = int(len(active))
s["outstanding_crore"] = round(active.outstanding.sum() / 1e7, 2)
s["npa_loans"] = int((active.asset_class == "NPA").sum())
s["gnpa_pct"] = round(100 * active.loc[active.asset_class == "NPA", "outstanding"].sum() / active.outstanding.sum(), 2)
s["par30_pct"] = round(100 * active.loc[active.current_dpd > 30, "outstanding"].sum() / active.outstanding.sum(), 2)
s["sma1_sma2_loans"] = int(active.asset_class.isin(["SMA-1", "SMA-2"]).sum())

# Scorecard validation: "bad" = ever 30+ days late. Uses only application data, so this is a fair test.
df["bad"] = df.max_days_late >= 30
band = df.groupby("score_band").agg(loans=("loan_id", "size"), ever30=("bad", "mean"),
                                    npa=("asset_class", lambda x: (x == "NPA").mean()))
s["band_ever30_pct"] = {b: round(100 * v, 1) for b, v in band.ever30.items()}
s["band_npa_pct"] = {b: round(100 * v, 1) for b, v in band.npa.items()}
s["band_d_vs_a_ever30_ratio"] = round(band.ever30["D"] / band.ever30["A"], 1)
s["scorecard_auc_ever30"] = round(float(auc(-df.scorecard_points, df.bad)), 3)

prod = active.groupby("loan_type").apply(
    lambda d: pd.Series({"gnpa": 100 * d.loc[d.asset_class == "NPA", "outstanding"].sum() / d.outstanding.sum(),
                         "par30": 100 * d.loc[d.current_dpd > 30, "outstanding"].sum() / d.outstanding.sum(),
                         "npa_count_pct": 100 * (d.asset_class == "NPA").mean()}))
s["gnpa_by_product_pct"] = prod.gnpa.round(2).to_dict()
s["npa_count_rate_by_product_pct"] = prod.npa_count_pct.round(1).to_dict()
# Same NPA loans divided by ALL loans ever disbursed: short loans that were repaid have left the active book,
# which makes the active-book ratio look worse for short-tenure products.
cohort = df.groupby("loan_type").agg(disbursed=("loan_id", "size"), closed=("is_closed", "sum"),
                                     npa=("asset_class", lambda x: (x == "NPA").sum()))
s["npa_of_all_disbursed_by_product_pct"] = (100 * cohort.npa / cohort.disbursed).round(1).to_dict()
s["closed_loans_by_product"] = cohort.closed.astype(int).to_dict()

br = active.groupby("branch").apply(lambda d: pd.Series({
    "gnpa": 100 * d.loc[d.asset_class == "NPA", "outstanding"].sum() / d.outstanding.sum(),
    "npa_loans": (d.asset_class == "NPA").sum()}))
top = br.gnpa.idxmax()
s["worst_branch"] = top
s["worst_branch_gnpa_pct"] = round(float(br.gnpa.max()), 2)
s["worst_branch_npa_loans"] = int(br.loc[top, "npa_loans"])

# ---------------------------------------------------------------- charts
def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=150)
    plt.close(fig)


fig, ax = plt.subplots(figsize=(7, 3.8))
x = np.arange(len(band))
ax.bar(x - 0.2, 100 * band.ever30, 0.4, color=NAVY, label="Ever 30+ days late")
ax.bar(x + 0.2, 100 * band.npa, 0.4, color=RED, label="NPA today")
for i, (a, b) in enumerate(zip(band.ever30, band.npa)):
    ax.text(i - 0.2, 100 * a + 0.5, f"{100 * a:.1f}%", ha="center", fontsize=8)
    ax.text(i + 0.2, 100 * b + 0.5, f"{100 * b:.1f}%", ha="center", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels([f"Band {b}\n({n} loans)" for b, n in band.loans.items()])
ax.set_ylabel("% of loans")
ax.set_title(f"Each lower score band goes late more often (AUC {s['scorecard_auc_ever30']})", loc="left")
ax.legend(frameon=False, fontsize=8)
save(fig, "scorecard_validation.png")

p = prod.sort_values("gnpa")
fig, ax = plt.subplots(figsize=(7, 3.6))
y = np.arange(len(p))
ax.barh(y + 0.2, p.gnpa, 0.4, color=RED, label="GNPA % (outstanding)")
ax.barh(y - 0.2, p.par30, 0.4, color=GREY, label="PAR 30 % (outstanding)")
for i, (g, q) in enumerate(zip(p.gnpa, p.par30)):
    ax.text(g + 0.2, i + 0.2, f"{g:.1f}%", va="center", fontsize=8)
    ax.text(q + 0.2, i - 0.2, f"{q:.1f}%", va="center", fontsize=8)
ax.set_yticks(y)
ax.set_yticklabels(p.index)
ax.axvline(s["gnpa_pct"], color=NAVY, ls="--", lw=1)
ax.text(s["gnpa_pct"] + 0.2, len(p) - 0.45, f"portfolio GNPA {s['gnpa_pct']}%", fontsize=8, color=NAVY)
ax.set_xlabel("% of outstanding principal")
ax.set_title("Asset quality by product (active loans, 30 Sep 2026)", loc="left")
ax.legend(frameon=False, fontsize=8, loc="lower right")
save(fig, "asset_quality_by_product.png")

df["vintage"] = df.disbursement_date.dt.year.astype(str) + "-H" + np.where(df.disbursement_date.dt.month <= 6, "1", "2")
v = df.groupby("vintage").agg(loans=("loan_id", "size"), ever30=("bad", "mean"))
fig, ax = plt.subplots(figsize=(7, 3.4))
ax.plot(v.index, 100 * v.ever30, color=NAVY, marker="o")
for i, val in enumerate(v.ever30):
    ax.text(i, 100 * val + 0.6, f"{100 * val:.1f}%", ha="center", fontsize=8)
ax.set_ylabel("Ever 30+ days late (%)")
ax.set_ylim(0, 100 * v.ever30.max() * 1.25)
ax.set_title("Vintage view: older loans have had more time to go late", loc="left")
save(fig, "vintage_ever30.png")

with open(os.path.join(OUT, "summary.json"), "w") as f:
    json.dump(s, f, indent=2)
print(json.dumps(s, indent=2))
