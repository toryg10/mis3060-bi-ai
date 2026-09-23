"""
==============================================================================
Script:         hw02_eda.py
Purpose:        Exploratory Data Analysis (EDA) of Wildcat Capital's
                client transaction history (HW2, MIS3060).
Dataset:        02_Data/Raw/fact_transactions.csv
                (Wildcat Capital transactions, Jan 2020 - Dec 2024)
Author:         Tory (generated with Claude Cowork from hw02/specification.md)
Generated:      2026-09-22
How to run:     From the repository root:  python hw02/hw02_eda.py
Outputs:        hw02/hw02_profile.txt
                hw02/charts/hist_amount.png
                hw02/charts/box_amount_by_type.png
                hw02/charts/scatter_shares_amount.png
==============================================================================
"""

import os

import matplotlib

matplotlib.use("Agg")  # save charts to files without opening windows
import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# File locations (relative to the repository root)
# ---------------------------------------------------------------------------
DATA_PATH = os.path.join("02_Data", "Raw", "fact_transactions.csv")
OUTPUT_DIR = "hw02"
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
PROFILE_PATH = os.path.join(OUTPUT_DIR, "hw02_profile.txt")
EXPECTED_SHAPE = (298772, 9)

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)

# Everything passed to report() is printed to the terminal AND saved for the
# plain-text profile file (step 16).
profile_lines = []


def report(text=""):
    print(text)
    profile_lines.append(str(text))


def section(title):
    report()
    report("=" * 70)
    report(title)
    report("=" * 70)


def find_column(df, keyword):
    """Return the first column whose name contains the keyword (e.g. 'client')."""
    for col in df.columns:
        if keyword in col.lower():
            return col
    return None


# ---------------------------------------------------------------------------
# Step 1: Load the data
# ---------------------------------------------------------------------------
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Could not find {DATA_PATH}. Run this script from the repository root "
        "(the folder that contains 02_Data/ and hw02/)."
    )

df = pd.read_csv(DATA_PATH)
report("HW2 EDA PROFILE - fact_transactions.csv")

# ---------------------------------------------------------------------------
# Step 2: Shape
# ---------------------------------------------------------------------------
section("STEP 2: DATASET SHAPE")
report(f"Shape: {df.shape}  ->  {df.shape[0]:,} rows x {df.shape[1]} columns")

# ---------------------------------------------------------------------------
# Step 3: Column names and data types
# ---------------------------------------------------------------------------
section("STEP 3: COLUMN NAMES AND DATA TYPES")
report(df.dtypes.to_string())

# ---------------------------------------------------------------------------
# Step 4: Missing values
# ---------------------------------------------------------------------------
section("STEP 4: MISSING VALUES PER COLUMN")
report(df.isnull().sum().to_string())

# ---------------------------------------------------------------------------
# Step 5: Descriptive statistics for numeric columns
# ---------------------------------------------------------------------------
section("STEP 5: DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
report(df.describe().round(2).to_string())

# ---------------------------------------------------------------------------
# Step 6: txn_type value counts and percentages
# ---------------------------------------------------------------------------
section("STEP 6: TRANSACTION TYPE COUNTS AND PERCENTAGES")
type_counts = df["txn_type"].value_counts()  # sorted most -> least frequent
type_table = pd.DataFrame(
    {
        "count": type_counts,
        "percent": (type_counts / len(df) * 100).round(2),
    }
)
report(type_table.to_string())
report(f"Unique txn_type values: {df['txn_type'].nunique()}")

# ---------------------------------------------------------------------------
# Step 7: Unique clients, advisors, securities
# ---------------------------------------------------------------------------
section("STEP 7: UNIQUE CLIENTS, ADVISORS, AND SECURITIES")
for label, keyword in [("clients", "client"), ("advisors", "advisor"), ("securities", "security")]:
    col = find_column(df, keyword)
    if col is None:
        report(f"Unique {label}: no column found containing '{keyword}'")
    else:
        report(f"Unique {label} ({col}): {df[col].nunique():,}")

# ---------------------------------------------------------------------------
# Step 8: Date range
# ---------------------------------------------------------------------------
section("STEP 8: DATE RANGE OF txn_date")
report(f"txn_date stored as: {df['txn_date'].dtype}")
txn_dates = pd.to_datetime(df["txn_date"], errors="coerce")
report(f"Earliest txn_date: {txn_dates.min().date()}")
report(f"Latest txn_date:   {txn_dates.max().date()}")
unparsed = txn_dates.isna().sum() - df["txn_date"].isna().sum()
if unparsed > 0:
    report(f"Note: {unparsed:,} txn_date values could not be read as dates")

# ---------------------------------------------------------------------------
# Step 9: Duplicate txn_id check
# ---------------------------------------------------------------------------
section("STEP 9: DUPLICATE txn_id CHECK")
report(f"Duplicate txn_id values: {df['txn_id'].duplicated().sum():,}")

# ---------------------------------------------------------------------------
# Step 10: Mean, median, skewness of amount
# ---------------------------------------------------------------------------
section("STEP 10: amount - MEAN, MEDIAN, SKEWNESS")
amount_mean = df["amount"].mean()
amount_median = df["amount"].median()
amount_skew = df["amount"].skew()
report(f"Mean amount:     ${amount_mean:,.2f}")
report(f"Median amount:   ${amount_median:,.2f}")
direction = "right-skewed" if amount_skew > 0 else "left-skewed" if amount_skew < 0 else "symmetric"
report(f"Skewness amount: {amount_skew:.2f} ({direction})")

# ---------------------------------------------------------------------------
# Step 11: Group by txn_type
# ---------------------------------------------------------------------------
section("STEP 11: amount BY txn_type (sorted by mean, highest first)")
by_type = (
    df.groupby("txn_type")["amount"]
    .agg(count="count", mean_amount="mean", median_amount="median")
    .round(2)
    .sort_values("mean_amount", ascending=False)
)
report(by_type.to_string())

# ---------------------------------------------------------------------------
# Step 12: Correlation matrix and three strongest correlations
# ---------------------------------------------------------------------------
section("STEP 12: CORRELATION MATRIX (shares, price, amount)")
corr = df[["shares", "price", "amount"]].corr().round(2)
report(corr.to_string())

pairs = []
cols = corr.columns
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):  # skip self-correlations and repeats
        pairs.append((cols[i], cols[j], corr.iloc[i, j]))
pairs.sort(key=lambda p: abs(p[2]), reverse=True)

report()
report("Three strongest correlations (by absolute value):")
for rank, (a, b, r) in enumerate(pairs[:3], start=1):
    report(f"  {rank}. {a} - {b}: {r:.2f}")

# ---------------------------------------------------------------------------
# Step 13: shares min / max / negative count by txn_type
# ---------------------------------------------------------------------------
section("STEP 13: shares BY txn_type - MIN, MAX, NEGATIVE COUNT")
shares_by_type = df.groupby("txn_type")["shares"].agg(
    min_shares="min",
    max_shares="max",
    negative_count=lambda s: int((s < 0).sum()),
)
report(shares_by_type.round(2).to_string())
report(f"Total negative shares values: {int((df['shares'] < 0).sum()):,}")

# ---------------------------------------------------------------------------
# Step 14: Shape check
# ---------------------------------------------------------------------------
section("STEP 14: SHAPE CHECK")
if df.shape != EXPECTED_SHAPE:
    report(f"WARNING: expected shape {EXPECTED_SHAPE} but found {df.shape}!")
else:
    report(f"Shape check passed: {df.shape} matches the expected {EXPECTED_SHAPE}")

# ---------------------------------------------------------------------------
# Step 15: Charts
# ---------------------------------------------------------------------------
os.makedirs(CHART_DIR, exist_ok=True)

# 15a. Histogram of amount with mean and median lines
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"], bins=60, color="#4C72B0", edgecolor="white")
ax.axvline(amount_mean, color="#C44E52", linestyle="--", linewidth=2,
           label=f"Mean: ${amount_mean:,.2f}")
ax.axvline(amount_median, color="#DD8452", linestyle="-", linewidth=2,
           label=f"Median: ${amount_median:,.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Amount ($)")
ax.set_ylabel("Number of Transactions")
ax.legend()
fig.tight_layout()
hist_path = os.path.join(CHART_DIR, "hist_amount.png")
fig.savefig(hist_path, dpi=150)
plt.close(fig)

# 15b. Horizontal box plot of amount by txn_type
order = by_type.index.tolist()  # same order as step 11
fig, ax = plt.subplots(figsize=(10, 6))
ax.boxplot(
    [df.loc[df["txn_type"] == t, "amount"] for t in order],
    vert=False,
    patch_artist=True,
    boxprops=dict(facecolor="#A1C9F4"),
    flierprops=dict(marker=".", markersize=2, alpha=0.3),
)
ax.set_yticks(range(1, len(order) + 1))
ax.set_yticklabels(order)
ax.set_title("Transaction Amount by Transaction Type")
ax.set_xlabel("Amount ($)")
ax.set_ylabel("Transaction Type")
fig.tight_layout()
box_path = os.path.join(CHART_DIR, "box_amount_by_type.png")
fig.savefig(box_path, dpi=150)
plt.close(fig)

# 15c. Scatter of shares vs amount, colored by txn_type
# (rows with no shares, e.g. Deposits, have nothing to plot and are skipped)
fig, ax = plt.subplots(figsize=(10, 6))
for t in order:
    subset = df[(df["txn_type"] == t) & df["shares"].notna()]
    if len(subset) > 0:
        ax.scatter(subset["shares"], subset["amount"], s=3, alpha=0.3, label=t)
ax.set_title("Shares vs. Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Amount ($)")
ax.legend(title="txn_type", markerscale=4)
fig.tight_layout()
scatter_path = os.path.join(CHART_DIR, "scatter_shares_amount.png")
fig.savefig(scatter_path, dpi=150)
plt.close(fig)

print()
print("Charts saved:")
for p in (hist_path, box_path, scatter_path):
    print(f"  {p}")

# ---------------------------------------------------------------------------
# Step 16: Save the plain-text profile (steps 2-13 plus the shape check)
# ---------------------------------------------------------------------------
with open(PROFILE_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(profile_lines) + "\n")
print(f"Profile saved: {PROFILE_PATH}")
print("EDA complete.")
