"""
Generate the synthetic CreditPulse dataset into data/.

    python src/generate_data.py

Seeded and reproducible. The lending process is simulated in date order:
customers apply -> underwriting rules decide -> approved loans are disbursed ->
monthly EMIs fall due -> borrowers pay on time, pay late, or stop paying.
Nothing happens after the business date (AS_OF_DATE).
A few data-quality problems are planted on purpose (see PLANTED).
"""
import csv
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

import config as C

rng = np.random.default_rng(C.SEED)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
AS_OF = C.AS_OF_DATE

PLANTED = {
    "loans_disbursed_before_application": 4,
    "partial_payments_marked_on_time": 5,
    "approved_below_min_bureau_score": 3,
}

# ------------------------------------------------------------------ Reference data
MALE, FEMALE = C.MALE_NAMES, C.FEMALE_NAMES
SURNAMES = ["Sharma", "Patil", "Gupta", "Nair", "Reddy", "Kulkarni", "Verma", "Iyer", "Singh", "Joshi",
            "Deshmukh", "Chavan", "Rao", "Menon", "Jain", "Pillai", "Shaikh", "Mehta", "Das", "Bose"]
# city -> (state, branch)
CITIES = {
    "Mumbai": ("Maharashtra", "Andheri Branch"), "Pune": ("Maharashtra", "FC Road Branch"),
    "Nagpur": ("Maharashtra", "Sitabuldi Branch"), "Gondia": ("Maharashtra", "Gondia Main Branch"),
    "Delhi": ("Delhi", "Connaught Place Branch"), "Bengaluru": ("Karnataka", "Koramangala Branch"),
    "Hyderabad": ("Telangana", "Banjara Hills Branch"), "Chennai": ("Tamil Nadu", "T Nagar Branch"),
    "Kolkata": ("West Bengal", "Salt Lake Branch"), "Ahmedabad": ("Gujarat", "CG Road Branch"),
}
CITY_W = np.array([16, 10, 6, 4, 14, 13, 10, 10, 9, 8], float)
OFFICERS = {}
_officer_pool = ["Rohit Sharma", "Kavya Menon", "Arjun Verma", "Divya Rao", "Imran Shaikh", "Neha Joshi",
                 "Sameer Kulkarni", "Lata Iyer", "Varun Mehta", "Pallavi Das", "Ajay Reddy", "Sunita Pillai",
                 "Mohit Jain", "Rekha Nair", "Tarun Bose", "Geeta Patil", "Naveen Rao", "Asha Gupta",
                 "Kunal Singh", "Meena Chavan"]
for i, (_, (_, br)) in enumerate(CITIES.items()):
    OFFICERS[br] = _officer_pool[2 * i: 2 * i + 2]

SALARIED_JOBS = ["Software Engineer", "Teacher", "Nurse", "Bank Employee", "Govt Employee", "Accountant",
                 "Sales Executive", "Manager"]
SELF_JOBS = ["Trader", "Shop Owner", "Contractor", "Doctor", "Freelance Designer", "Consultant"]


def add_months(d, k):
    return (pd.Timestamp(d) + pd.DateOffset(months=k)).date()


def rand_date(lo, hi):
    return lo + timedelta(days=int(rng.integers(0, (hi - lo).days + 1)))


# ------------------------------------------------------------------ Customers
customers = []
for i in range(C.N_CUSTOMERS):
    gender = rng.choice(["Male", "Female"], p=[0.6, 0.4])
    first = rng.choice(MALE if gender == "Male" else FEMALE)
    city = rng.choice(list(CITIES), p=CITY_W / CITY_W.sum())
    emp = rng.choice(["Salaried", "Self-Employed"], p=[0.7, 0.3])
    income = float(np.clip(rng.lognormal(np.log(65_000), 0.55), 20_000, 600_000))
    n_exist = int(rng.choice([0, 1, 2, 3], p=[0.45, 0.33, 0.15, 0.07]))
    customers.append({
        "customer_id": f"CUST-{10001 + i}",
        "customer_name": f"{first} {rng.choice(SURNAMES)}",
        "gender": gender,
        "age": int(rng.integers(23, 61)),
        "city": city, "state": CITIES[city][0],
        "employment_type": emp,
        "occupation": rng.choice(SALARIED_JOBS if emp == "Salaried" else SELF_JOBS),
        "years_in_business": int(rng.integers(0, 21)) if emp == "Self-Employed" else None,
        "monthly_income": round(income, 0),
        "credit_bureau_score": int(np.clip(rng.normal(735, 55), 300, 900)),
        "existing_loans_count": n_exist,
        "existing_emi": round(sum(income * rng.uniform(0.06, 0.16) for _ in range(n_exist)), 0),
        "customer_since": rand_date(date(2015, 1, 1), date(2022, 12, 31)),
    })
cust = {c["customer_id"]: c for c in customers}

# ------------------------------------------------------------------ Applications and loans
products = list(C.PRODUCTS)
prod_w = np.array([18, 18, 30, 14, 20], float)
type_effect = {"Home Loan": -0.9, "Auto Loan": -0.3, "Personal Loan": 0.35, "Business Loan": 0.3,
               "Consumer Durable": 0.45}

app_dates = sorted(rand_date(C.START_DATE, AS_OF) for _ in range(C.N_APPLICATIONS))
active = {cid: [] for cid in cust}        # customer -> list of (maturity date, emi) for CreditPulse loans
applications, loans, latent = [], [], {}
pending_cutoff = AS_OF - timedelta(days=C.PENDING_DAYS)

for i, ad in enumerate(app_dates):
    c = cust[rng.choice(list(cust))]
    ptype = rng.choice(products, p=prod_w / prod_w.sum())
    lo, hi, tenures, (r_lo, r_hi) = C.PRODUCTS[ptype]
    tenure = int(rng.choice(tenures))
    rate = round(float(rng.uniform(r_lo, r_hi)), 2)
    target_share = rng.uniform(0.08, 0.38)            # share of income the applicant wants to spend on this EMI
    amount = float(np.clip(target_share * c["monthly_income"] / C.emi(1, rate, tenure), lo, hi))
    amount = round(amount / 1000) * 1000
    new_emi = C.emi(amount, rate, tenure)
    own_emi = sum(e for mat, e in active[c["customer_id"]] if mat > ad)
    foir = round((c["existing_emi"] + own_emi + new_emi) / c["monthly_income"], 4)  # rule uses the stored value
    points = C.scorecard_points(c["credit_bureau_score"], foir, c["employment_type"], c["existing_loans_count"])

    reason = None
    if ad > pending_cutoff:
        status = "Pending"
    elif c["credit_bureau_score"] < C.MIN_BUREAU_SCORE:
        status, reason = "Rejected", "Low Credit Score"
    elif foir > C.MAX_FOIR:
        status, reason = "Rejected", "High FOIR"
    elif c["employment_type"] == "Self-Employed" and c["years_in_business"] < C.MIN_SELF_EMPLOYED_YEARS:
        status, reason = "Rejected", "Unstable Employment"
    elif rng.random() < C.DOCS_INCOMPLETE_RATE:
        status, reason = "Rejected", "Incomplete Documentation"
    else:
        status = "Approved"

    app = {"application_id": f"APP-{50001 + i}", "customer_id": c["customer_id"], "application_date": ad,
           "loan_type": ptype, "requested_amount": amount, "tenure_months": tenure, "interest_rate": rate,
           "foir": foir, "scorecard_points": points, "score_band": C.score_band(points),
           "application_status": status, "rejection_reason": reason}
    applications.append(app)

    if status == "Approved":
        disb = ad + timedelta(days=int(rng.integers(3, 16)))
        branch = CITIES[c["city"]][1]
        loan_id = f"LOAN-{70001 + len(loans)}"
        e = round(C.emi(amount, rate, tenure), 2)
        loans.append({"loan_id": loan_id, "application_id": app["application_id"], "customer_id": c["customer_id"],
                      "loan_type": ptype, "disbursed_amount": amount, "disbursement_date": disb,
                      "tenure_months": tenure, "interest_rate": rate, "emi_amount": e, "branch": branch,
                      "loan_officer": rng.choice(OFFICERS[branch])})
        active[c["customer_id"]].append((add_months(disb, tenure), e))
        # Hidden "true" risk of the borrower: related to, but not equal to, the scorecard inputs.
        logit = (-5.1 + 0.017 * (720 - c["credit_bureau_score"]) + 3.2 * (foir - 0.35)
                 + type_effect[ptype] + (0.35 if c["employment_type"] == "Self-Employed" else 0)
                 + rng.normal(0, 0.6))
        latent[loan_id] = 1 / (1 + np.exp(-logit))

# Planted: approved despite bureau score below the minimum (policy exceptions).
low = [a for a in applications if a["rejection_reason"] == "Low Credit Score"
       and a["application_date"] < date(2025, 6, 30)]
for a in rng.choice(low, PLANTED["approved_below_min_bureau_score"], replace=False):
    a["application_status"], a["rejection_reason"] = "Approved", None
    c = cust[a["customer_id"]]
    disb = a["application_date"] + timedelta(days=int(rng.integers(3, 16)))
    branch = CITIES[c["city"]][1]
    loan_id = f"LOAN-{70001 + len(loans)}"
    loans.append({"loan_id": loan_id, "application_id": a["application_id"], "customer_id": c["customer_id"],
                  "loan_type": a["loan_type"], "disbursed_amount": a["requested_amount"], "disbursement_date": disb,
                  "tenure_months": a["tenure_months"], "interest_rate": a["interest_rate"],
                  "emi_amount": round(C.emi(a["requested_amount"], a["interest_rate"], a["tenure_months"]), 2),
                  "branch": branch, "loan_officer": rng.choice(OFFICERS[branch])})
    latent[loan_id] = 0.03

# ------------------------------------------------------------------ Repayments
repayments = []
for ln in loans:
    h = latent[ln["loan_id"]]                       # monthly chance the borrower stops paying
    p_late = min(0.04 + 4 * h, 0.35)
    defaulted = False
    arrears = []                                    # instalments missed while in default
    for k in range(1, ln["tenure_months"] + 1):
        due = add_months(ln["disbursement_date"], k)
        if due > AS_OF:
            break
        if not defaulted and rng.random() < h:
            defaulted = True
        elif defaulted and len(arrears) <= 3 and rng.random() < 0.35:
            # Borrower cures: clears all missed instalments a few days after this due date.
            cure = due + timedelta(days=int(rng.integers(0, 10)))
            if cure <= AS_OF:
                for r in arrears:
                    r.update(paid_date=cure, paid_amount=r["due_amount"], payment_status="Paid Late",
                             days_late=(cure - r["due_date"]).days)
                arrears, defaulted = [], False
        if defaulted:
            paid = None
        elif rng.random() < p_late:
            paid = due + timedelta(days=int(min(rng.geometric(0.12), 60)))
        else:
            paid = due - timedelta(days=int(rng.integers(0, 4)))
        if paid is not None and paid > AS_OF:      # would be paid after the business date -> unpaid today
            paid = None
        if paid is None:
            status, amount, dpd = "Unpaid", 0.0, (AS_OF - due).days
        elif paid <= due:
            status, amount, dpd = "Paid on Time", ln["emi_amount"], 0
        else:
            status, amount, dpd = "Paid Late", ln["emi_amount"], (paid - due).days
        rec = {"loan_id": ln["loan_id"], "customer_id": ln["customer_id"], "installment_no": k,
               "due_date": due, "due_amount": ln["emi_amount"], "paid_date": paid,
               "paid_amount": amount, "payment_status": status, "days_late": dpd}
        repayments.append(rec)
        if defaulted:
            arrears.append(rec)
for i, r in enumerate(repayments):
    r["repayment_id"] = f"REP-{100001 + i}"

# Planted: loans disbursed before the application date.
for ln in rng.choice([l for l in loans if l["disbursement_date"] > date(2023, 3, 1)],
                     PLANTED["loans_disbursed_before_application"], replace=False):
    app = next(a for a in applications if a["application_id"] == ln["application_id"])
    ln["disbursement_date"] = app["application_date"] - timedelta(days=int(rng.integers(2, 10)))
# Planted: partial payments labelled "Paid on Time".
for r in rng.choice([r for r in repayments if r["payment_status"] == "Paid on Time"],
                    PLANTED["partial_payments_marked_on_time"], replace=False):
    r["paid_amount"] = round(r["due_amount"] * float(rng.uniform(0.3, 0.8)), 2)


# ------------------------------------------------------------------ Write
def write(name, cols, rows):
    with open(os.path.join(DATA, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[k] is None else r[k] for k in cols])


os.makedirs(DATA, exist_ok=True)
write("customers.csv", ["customer_id", "customer_name", "gender", "age", "city", "state", "employment_type",
                        "occupation", "years_in_business", "monthly_income", "credit_bureau_score",
                        "existing_loans_count", "existing_emi", "customer_since"], customers)
write("applications.csv", ["application_id", "customer_id", "application_date", "loan_type", "requested_amount",
                           "tenure_months", "interest_rate", "foir", "scorecard_points", "score_band",
                           "application_status", "rejection_reason"], applications)
write("loans.csv", ["loan_id", "application_id", "customer_id", "loan_type", "disbursed_amount", "disbursement_date",
                    "tenure_months", "interest_rate", "emi_amount", "branch", "loan_officer"], loans)
write("repayments.csv", ["repayment_id", "loan_id", "customer_id", "installment_no", "due_date", "due_amount",
                         "paid_date", "paid_amount", "payment_status", "days_late"], repayments)
print(f"customers {len(customers)}, applications {len(applications)}, loans {len(loans)}, repayments {len(repayments)}")
print("planted:", PLANTED)
