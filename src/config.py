"""
CreditPulse configuration: every rule and threshold in one place.
All data in this project is synthetic. Amounts are in INR.
"""
from datetime import date

SEED = 7
START_DATE = date(2023, 1, 1)      # first application date
AS_OF_DATE = date(2026, 9, 30)     # business date (month-end)

N_CUSTOMERS = 3_000
N_APPLICATIONS = 5_000

# First names by gender (used by the generator and checked by the tests).
MALE_NAMES = ["Amit", "Rahul", "Rohit", "Vikram", "Suresh", "Rajesh", "Karan", "Yash", "Manoj", "Abhishek",
        "Gaurav", "Vivek", "Arjun", "Nikhil", "Sanjay", "Farhan", "Imran", "Pranav", "Harsh", "Aditya"]
FEMALE_NAMES = ["Priya", "Sneha", "Pooja", "Anjali", "Kavita", "Neha", "Ritu", "Shreya", "Deepika", "Ananya",
          "Nidhi", "Sonal", "Isha", "Meera", "Aarti", "Divya", "Swati", "Kiran", "Ayesha", "Tanvi"]

# ---------------------------------------------------------------- Underwriting rules
# Applied in this order; the first rule that fails gives the rejection reason.
MIN_BUREAU_SCORE = 650             # below this -> "Low Credit Score"
MAX_FOIR = 0.50                    # (existing EMIs + new EMI) / monthly income above this -> "High FOIR"
MIN_SELF_EMPLOYED_YEARS = 2        # self-employed with fewer years in business -> "Unstable Employment"
DOCS_INCOMPLETE_RATE = 0.04        # share of applications rejected for incomplete documents
PENDING_DAYS = 14                  # applications in the last 14 days are still Pending

# Loan products: (min amount, max amount, tenure choices in months, interest rate range %)
PRODUCTS = {
    "Home Loan":        (1_500_000, 7_500_000, [120, 180, 240], (8.3, 9.8)),
    "Auto Loan":        (300_000, 1_500_000, [36, 48, 60], (9.0, 11.5)),
    "Personal Loan":    (100_000, 1_000_000, [12, 24, 36, 48], (11.5, 18.0)),
    "Business Loan":    (500_000, 3_000_000, [24, 36, 48, 60], (12.0, 17.0)),
    "Consumer Durable": (20_000, 150_000, [6, 9, 12], (14.0, 24.0)),
}

# ---------------------------------------------------------------- Asset classification (RBI style)
# Based on CURRENT days past due = days since the oldest unpaid instalment's due date.
def asset_class(dpd):
    if dpd <= 0:
        return "Standard"
    if dpd <= 30:
        return "SMA-0"
    if dpd <= 60:
        return "SMA-1"
    if dpd <= 90:
        return "SMA-2"
    return "NPA"


# ---------------------------------------------------------------- Application scorecard
# Uses ONLY information known at application time, so it can be tested against what happened later.
def scorecard_points(bureau_score, foir, employment_type, existing_loans):
    pts = 0
    pts += 40 if bureau_score >= 800 else 30 if bureau_score >= 750 else 20 if bureau_score >= 700 else 10
    pts += 30 if foir <= 0.30 else 20 if foir <= 0.40 else 10
    pts += 15 if employment_type == "Salaried" else 8
    pts += {0: 15, 1: 10, 2: 5}.get(existing_loans, 0)
    return pts


def score_band(points):
    if points >= 80:
        return "A"
    if points >= 65:
        return "B"
    if points >= 50:
        return "C"
    return "D"


def emi(principal, annual_rate_pct, months):
    r = annual_rate_pct / 1200
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)
