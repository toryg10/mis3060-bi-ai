"""
03_validate.py - Part D: referential integrity, rule checks, cross-table
reconciliations, IQR outliers and a raw-vs-clean data quality scorecard.

Runs every check on BOTH stages (data/raw and data/clean) and writes:
  reports/data_quality_scorecard.csv  one row per table per stage
  reports/validation_details.csv      every individual check, both stages
  reports/iqr_outliers.csv            IQR fences and counts per column, both stages
  reports/iqr_outlier_rows.csv        the flagged rows themselves (clean stage)
  reports/ri_orphans.csv              every orphan key found, both stages

Scorecard definitions (all %, computed only over the ORIGINAL raw columns, so
the flag columns added by 02_clean.py cannot inflate the clean stage):
  completeness        filled cells / cells that should be filled
                      (cells that are blank by design are excluded, e.g. sector on ETFs)
  key_uniqueness      rows that are not a repeat of an earlier row's primary key
                      or business key (the first occurrence counts as unique)
  type_validity       non-blank cells that parse as the column's declared type
  rule_pass           row-level rule evaluations passed / evaluated, across all
                      bound, code-list, sign, recompute and plausibility rules
                      (row-weighted: big tables dominate; see validation_details.csv
                      for each rule on its own)
  reconciliation_pass cross-table reconciliations passed / evaluated
  referential_match   non-blank FK values found in their dimension / FK values checked
Plausibility rules test the defects 02_clean.py FLAGGED but could not fix, so the
clean stage is not shown as perfect when it is not.

check_referential_integrity() is written to be reused as-is in Assignment 5.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
STAGES = {"raw": BASE / "data" / "raw", "clean": BASE / "data" / "clean"}
REPORTS = BASE / "reports"
REPORTS.mkdir(exist_ok=True)

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


# =====================================================================
# 1. REUSABLE REFERENTIAL INTEGRITY CHECK  (keep for Assignment 5)
# =====================================================================
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every value of fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared as text with surrounding whitespace trimmed, so a format
    difference ('45.0' vs '45') counts as an orphan while stray spaces do not.
    Blank / missing keys are NOT orphans: they are reported as the null-key rate.

    Returns a dict:
        fact_rows            rows in fact_df
        null_keys            rows whose key is blank or missing
        null_key_rate        null_keys / fact_rows
        checked              rows with a non-null key
        matched              checked rows whose key exists in the dimension
        match_rate           matched / checked   (1.0 when nothing to check)
        orphan_row_count     checked - matched
        orphan_rows          DataFrame: the fact rows that do not match
        distinct_orphan_keys sorted list of the unmatched key values
        dim_key_unique       True if dim_key is unique, i.e. a valid "one" side
    """
    def as_text(s):
        return s.astype("string").str.strip()

    f = as_text(fact_df[fact_key])
    blank = f.isna() | (f == "")
    d = as_text(dim_df[dim_key]).dropna()
    dim_keys = set(d)
    nonnull = f[~blank]
    match = nonnull.isin(dim_keys)
    orphan_idx = nonnull.index[~match.to_numpy()]
    return {
        "fact_rows": len(f),
        "null_keys": int(blank.sum()),
        "null_key_rate": float(blank.mean()) if len(f) else 0.0,
        "checked": len(nonnull),
        "matched": int(match.sum()),
        "match_rate": float(match.mean()) if len(nonnull) else 1.0,
        "orphan_row_count": len(orphan_idx),
        "orphan_rows": fact_df.loc[orphan_idx],
        "distinct_orphan_keys": sorted(nonnull[~match].unique().tolist()),
        "dim_key_unique": bool(d.is_unique),
    }


# The 13 relationships: 10 ID-based + 3 to the date table
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

# =====================================================================
# 2. CONFIG: keys, types, bounds
# =====================================================================
PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

# Business keys: the columns that identify one real-world thing. A row repeating an
# earlier row's business key is a duplicate even when its primary key is new.
BUSINESS_KEY = {
    "dim_advisor": ["first_name", "last_name", "region"],
    "dim_benchmark": ["ticker_proxy"],
    "dim_client": "ALL_EXCEPT client_id last_name",      # same person entered twice
    "dim_date": ["date"],
    "dim_security": ["ticker"],
    "fact_fees": ["client_id", "fee_date"],              # one fee row per client per month
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],  # one snapshot per client-month
    "fact_transactions": "ALL_EXCEPT txn_id client_id",  # same transaction copied to another client
}

ID_PAT, INT_PAT = r"^\d+$", r"^-?\d+$"
NUM_PAT = r"^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$"
DATE_PAT, ZIP_PAT = r"^\d{4}-\d{2}-\d{2}$", r"^\d{5}$"
TYPES = {  # anything not listed (and not *_id) is free text
    "years_experience": "int", "aum_target_mm": "num", "age": "int", "zip_code": "zip",
    "initial_aum": "num", "client_since": "date", "is_active": "bool", "date": "date",
    "year": "int", "quarter": "int", "month": "int", "week_of_year": "int",
    "is_month_end": "flag", "is_quarter_end": "flag", "is_year_end": "flag",
    "is_trading_day": "flag", "is_etf": "bool", "expense_ratio_bps": "num",
    "fee_date": "date", "aum_basis": "num", "bps_charged": "num", "amount": "num",
    "snapshot_date": "date", "aum": "num", "return_ytd": "num", "benchmark_return_ytd": "num",
    "active_alpha_ytd": "num", "cash_pct": "num", "txn_date": "date", "shares": "num",
    "price": "num",
}

US_STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
ALLOWED = {
    ("dim_advisor", "region"): {"Northeast", "Southeast", "Mid-Atlantic", "Midwest", "West"},
    ("dim_benchmark", "asset_class"): {"Equity", "Fixed Income", "Multi-Asset", "International",
                                       "Small Cap", "Emerging", "Cash"},
    ("dim_client", "state"): US_STATES,
    ("dim_client", "risk_profile"): {"Conservative", "Moderately Conservative", "Balanced",
                                     "Moderately Aggressive", "Aggressive"},
    ("dim_client", "client_tier"): {"Retail", "HNW", "UHNW"},
    ("dim_client", "primary_account_type"): ACCOUNT_TYPES,
    ("dim_security", "asset_class"): {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"},
    ("dim_security", "sector"): {"Communication Services", "Consumer Discretionary",
                                 "Consumer Staples", "Energy", "Financials", "Healthcare",
                                 "Industrials", "Technology", "Materials", "Real Estate", "Utilities"},
    ("fact_fees", "fee_type"): {"Management", "Advisory", "Custodial", "Performance"},
    ("fact_transactions", "txn_type"): {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal",
                                        "Advisory Fee"},
    ("fact_portfolio_snapshot", "account_type"): ACCOUNT_TYPES,
    ("dim_date", "month_name"): {"January", "February", "March", "April", "May", "June", "July",
                                 "August", "September", "October", "November", "December"},
    ("dim_date", "day_of_week"): {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                                  "Saturday", "Sunday"},
}
# Natural business bounds (low, high); None = unbounded on that side
BOUNDS = {
    ("dim_advisor", "years_experience"): (0, 60),
    ("dim_advisor", "aum_target_mm"): (0.01, None),
    ("dim_client", "age"): (18, 110),
    ("dim_client", "initial_aum"): (0.01, None),
    ("dim_date", "year"): (2020, 2024), ("dim_date", "quarter"): (1, 4),
    ("dim_date", "month"): (1, 12), ("dim_date", "week_of_year"): (1, 53),
    ("dim_security", "expense_ratio_bps"): (0, 300),
    ("fact_fees", "aum_basis"): (0.01, None),
    ("fact_fees", "bps_charged"): (0, 100),         # same soft ceiling as the audit (decision log L17)
    ("fact_fees", "amount"): (0.01, None),
    ("fact_portfolio_snapshot", "year"): (2020, 2024),
    ("fact_portfolio_snapshot", "month"): (1, 12),
    ("fact_portfolio_snapshot", "aum"): (0.01, None),
    ("fact_portfolio_snapshot", "cash_pct"): (0, 1),
    ("fact_portfolio_snapshot", "return_ytd"): (-1, None),           # can't lose more than 100%
    ("fact_portfolio_snapshot", "benchmark_return_ytd"): (-1, None),
    ("fact_transactions", "price"): (0.01, None),
    ("fact_transactions", "amount"): (0.01, None),
}
DATE_BOUNDS = {("dim_client", "client_since"): ("1990-01-01", "2024-12-31")}
CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}


# =====================================================================
# helpers
# =====================================================================
def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


def is_blank(s):
    return s.str.strip() == ""


def to_date(s):
    return pd.to_datetime(s.str.strip(), format="%Y-%m-%d", errors="coerce")


def type_ok(s, kind):
    v = s.str.strip()
    patterns = {"id": ID_PAT, "int": INT_PAT, "num": NUM_PAT, "zip": ZIP_PAT}
    if kind in patterns:
        return v.str.match(patterns[kind])
    if kind == "bool":
        return v.isin({"True", "False"})
    if kind == "flag":
        return v.isin({"0", "1"})
    if kind == "date":
        return v.str.match(DATE_PAT) & to_date(v).notna()
    return pd.Series(True, index=s.index)


def col_type(col):
    return "id" if col.endswith("_id") else TYPES.get(col, "text")


def structural_blank(t, df):
    """Cells where blank is correct by design (not missing data)."""
    m = pd.DataFrame(False, index=df.index, columns=df.columns)
    if t == "dim_security":
        m["sector"] = df.is_etf == "True"
        m["expense_ratio_bps"] = df.is_etf == "False"
    if t == "fact_transactions":
        cash = df.txn_type.isin(CASH_TYPES)
        for c in ("security_id", "shares", "price"):
            m[c] = cash
    return m


def business_key(t, cols):
    spec = BUSINESS_KEY[t]
    if isinstance(spec, str):
        drop = set(spec.split()[1:])
        return [c for c in cols if c not in drop]
    return spec


# =====================================================================
# 3. ROW-LEVEL RULES -> (table, kind, rule, checked, passed)
# =====================================================================
def rules(T):
    out = []

    def r(t, kind, name, applicable, passed):
        out.append((t, kind, name, int(applicable.sum()), int((applicable & passed).sum())))

    for (t, c), allowed in ALLOWED.items():
        s = T[t][c]
        r(t, "code list", f"allowed values: {c}", ~is_blank(s), s.isin(allowed))
    for (t, c), (lo, hi) in BOUNDS.items():
        v = num(T[t][c])
        ok = pd.Series(True, index=v.index)
        if lo is not None:
            ok &= v >= lo
        if hi is not None:
            ok &= v <= hi
        r(t, "bound", f"range {c} in [{lo}, {hi}]", v.notna(), ok)
    for (t, c), (lo, hi) in DATE_BOUNDS.items():
        d = to_date(T[t][c])
        r(t, "bound", f"date {c} in [{lo}, {hi}]", d.notna(), (d >= lo) & (d <= hi))

    tx = T["fact_transactions"]
    typ = tx.txn_type
    sh, pr, amt = num(tx.shares), num(tx.price), num(tx.amount)
    bs = typ.isin({"Buy", "Sell"})
    r("fact_transactions", "sign", "Buy/Sell shares > 0", bs & sh.notna(), sh > 0)
    r("fact_transactions", "sign", "Dividend shares > 0", (typ == "Dividend") & sh.notna(), sh > 0)
    r("fact_transactions", "recompute", "Buy/Sell amount = |shares| x price",
      bs & sh.notna() & pr.notna(), (sh.abs() * pr - amt).abs() <= 0.01)
    r("fact_transactions", "structure", "trade rows have a security", ~typ.isin(CASH_TYPES),
      ~is_blank(tx.security_id))
    r("fact_transactions", "structure", "cash rows have no security", typ.isin(CASH_TYPES),
      is_blank(tx.security_id))

    fee = T["fact_fees"]
    a, b, p = num(fee.aum_basis), num(fee.bps_charged), num(fee.amount)
    r("fact_fees", "recompute", "amount = aum_basis x bps / 10000 / 12",
      a.notna() & b.notna() & p.notna(), (a * b / 10000 / 12 - p).abs() <= 0.01)

    sn = T["fact_portfolio_snapshot"]
    rt, bm, al = num(sn.return_ytd), num(sn.benchmark_return_ytd), num(sn.active_alpha_ytd)
    r("fact_portfolio_snapshot", "recompute", "alpha = return - benchmark",
      rt.notna() & bm.notna() & al.notna(), (rt - bm - al).abs() <= 5e-5 + 1e-9)
    sd = to_date(sn.snapshot_date)
    r("fact_portfolio_snapshot", "recompute", "year/month match snapshot_date", sd.notna(),
      (sd.dt.year == num(sn.year)) & (sd.dt.month == num(sn.month)))

    dt = T["dim_date"]
    dd = to_date(dt.date)
    r("dim_date", "recompute", "calendar columns match date", dd.notna(),
      (dd.dt.year == num(dt.year)) & (dd.dt.month == num(dt.month))
      & (dd.dt.quarter == num(dt.quarter)) & (dd.dt.day_name() == dt.day_of_week))
    r("dim_date", "structure", "weekends are not trading days", dd.dt.dayofweek >= 5,
      dt.is_trading_day == "0")

    sec = T["dim_security"]
    etf = sec.is_etf == "True"
    r("dim_security", "structure", "ETF: no sector, has expense ratio", etf,
      is_blank(sec.sector) & ~is_blank(sec.expense_ratio_bps))
    r("dim_security", "structure", "non-ETF: has sector, no expense ratio", sec.is_etf == "False",
      ~is_blank(sec.sector) & is_blank(sec.expense_ratio_bps))

    # Plausibility: the defects 02_clean.py FLAGGED but could not fix (D8-D11).
    # They fail in BOTH stages on purpose: flagging is not fixing.
    dv = (typ == "Dividend") & sh.notna() & pr.notna()
    r("fact_transactions", "plausibility", "Dividend is not the whole position value (D8)", dv,
      (sh * pr - amt).abs() > 0.01)
    r("fact_portfolio_snapshot", "plausibility", "return_ytd <= +100% (D9)", rt.notna(), rt <= 1)
    r("fact_portfolio_snapshot", "plausibility", "aum not at the $1,000 floor (D10)",
      num(sn.aum).notna(), num(sn.aum) != 1000)
    r("fact_fees", "plausibility", "aum_basis not at the $1,000 floor (D10)", a.notna(), a != 1000)
    trading = tx.txn_date.map(dt.drop_duplicates("date").set_index("date").is_trading_day)
    r("fact_transactions", "plausibility", "Buy/Sell on a trading day (D11)", bs & trading.notna(),
      trading == "1")
    return out


# =====================================================================
# 4. CROSS-TABLE RECONCILIATIONS -> (table, kind, rule, checked, passed)
# =====================================================================
def reconciliations(T):
    out = []
    cli = T["dim_client"].drop_duplicates("client_id").set_index("client_id")
    fee, sn, tx = T["fact_fees"], T["fact_portfolio_snapshot"], T["fact_transactions"]

    def add(t, name, ok, passed):
        out.append((t, "reconciliation", name, int(ok.sum()), int((ok & passed).sum())))

    # R1: fee's AUM basis equals the same client's snapshot AUM for that month
    aum = sn.drop_duplicates(["client_id", "snapshot_date"]) \
            .set_index(sn.client_id + "|" + sn.snapshot_date).aum
    a = (fee.client_id + "|" + fee.fee_date).map(aum)
    ok = a.notna()
    add("fact_fees", "R1 aum_basis = snapshot aum (same client, month)", ok,
        (num(fee.aum_basis) - num(a.fillna(""))).abs() <= 0.01)

    # R2: each fact's advisor equals the client's advisor in dim_client
    for t, f in (("fact_fees", fee), ("fact_portfolio_snapshot", sn), ("fact_transactions", tx)):
        adv = f.client_id.map(cli.advisor_id)
        add(t, "R2 advisor_id = client's advisor in dim_client", adv.notna(), adv == f.advisor_id)

    # R3: snapshot account type equals the client's primary account type
    acct = sn.client_id.map(cli.primary_account_type)
    add("fact_portfolio_snapshot", "R3 account_type = client's primary_account_type", acct.notna(),
        acct == sn.account_type)

    # R4: stated risk profile agrees with the snapshot benchmark. Only clients whose profile was
    # STATED in the source are tested; profiles filled in from the benchmark (D7) are excluded,
    # because testing a fill against the evidence that produced it would pass by construction.
    bench_for = {"Aggressive": "1", "Moderately Aggressive": "1", "Balanced": "3",
                 "Conservative": "8", "Moderately Conservative": "8"}
    imputed = cli.get("risk_profile_imputed", pd.Series("0", index=cli.index))
    stated = cli.risk_profile.where((cli.risk_profile != "") & (imputed != "1"))
    expected = sn.client_id.map(stated).map(bench_for)
    add("fact_portfolio_snapshot", "R4 benchmark matches stated risk profile", expected.notna(),
        expected == sn.benchmark_id)
    return out


# =====================================================================
# 5. IQR OUTLIERS (unbounded numeric columns; transactions split by type)
# =====================================================================
IQR_COLUMNS = [("dim_client", "initial_aum", None), ("fact_portfolio_snapshot", "aum", None),
               ("fact_fees", "amount", None), ("fact_transactions", "amount", "txn_type")]


def iqr(T, stage):
    """Returns (summary rows, per-row flags). Fences are computed per group when a group
    column is given, because a Deposit and a Dividend are different distributions."""
    summary, flagged_rows = [], []
    for t, c, group in IQR_COLUMNS:
        df = T[t]
        groups = df.groupby(group) if group else [("all", df)]
        for g, sub in groups:
            v = num(sub[c])
            q1, q3 = v.quantile(0.25), v.quantile(0.75)
            lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            out = (v < lo) | (v > hi)
            summary.append({"stage": stage, "table": t, "column": c, "group": g,
                            "q1": round(q1, 2), "q3": round(q3, 2), "lower_fence": round(lo, 2),
                            "upper_fence": round(hi, 2), "rows": int(v.notna().sum()),
                            "flagged": int(out.sum()), "pct_flagged": round(100 * out.mean(), 2),
                            "max": round(v.max(), 2)})
            if out.any():
                flagged_rows.append(pd.DataFrame({
                    "stage": stage, "table": t, "column": c, "group": g,
                    "key_column": PK[t], "key": sub.loc[out, PK[t]], "value": sub.loc[out, c],
                    "side": (v[out] > hi).map({True: "high", False: "low"})}))
    rows = pd.concat(flagged_rows, ignore_index=True) if flagged_rows else pd.DataFrame()
    return summary, rows


def iqr_sentence(T, rows):
    """One sentence on whether flagged means wrong, built from this run's numbers."""
    c = T["dim_client"]
    hi_keys = set(rows.loc[(rows.table == "dim_client") & (rows.side == "high"), "key"])
    hi = c.client_id.isin(hi_keys)
    uhnw = int((c.client_tier[hi] == "UHNW").sum())
    share = f"all {uhnw}" if uhnw == hi.sum() else f"{uhnw} of the {int(hi.sum())}"
    tx = T["fact_transactions"]
    out_keys = set(rows.loc[rows.table == "fact_transactions", "key"])
    div = tx.txn_type == "Dividend"
    whole = div & ((num(tx.shares) * num(tx.price) - num(tx.amount)).abs() <= 0.01)
    inside = int((whole & ~tx.txn_id.isin(out_keys)).sum())
    return (f"Flagged does not mean wrong ({share} high initial_aum outliers "
            f"are UHNW clients, who should be large), and unflagged does not mean right "
            f"({inside:,} of the {int(whole.sum()):,} dividends that equal the whole position sit "
            f"inside the IQR fences; the D8 plausibility rule finds them, the outlier screen does not).")


# =====================================================================
# 6. SCORECARD
# =====================================================================
def pct(passed, checked):
    return round(100 * passed / checked, 2) if checked else None


def validate(stage, raw_cols):
    T = {t: pd.read_csv(STAGES[stage] / f"{t}.csv", dtype=str, keep_default_na=False) for t in TABLES}
    details, score, orphans = [], [], []

    ri = {}
    for ft, fc, dt_, dc in RELATIONSHIPS:
        res = check_referential_integrity(T[ft], fc, T[dt_], dc)
        ri.setdefault(ft, []).append(res)
        rel = f"{ft}.{fc} -> {dt_}.{dc}"
        details.append({"stage": stage, "section": "referential integrity", "kind": "foreign key",
                        "table": ft, "check": rel, "checked": res["checked"], "passed": res["matched"],
                        "failed": res["orphan_row_count"], "pass_pct": pct(res["matched"], res["checked"]),
                        "note": f"null-key rate {res['null_key_rate']:.2%}; "
                                f"{len(res['distinct_orphan_keys'])} distinct orphan keys; "
                                f"dimension key unique: {res['dim_key_unique']}"})
        if res["orphan_row_count"]:
            o = res["orphan_rows"]
            orphans.append(pd.DataFrame({"stage": stage, "relationship": rel, "key_column": PK[ft],
                                         "key": o[PK[ft]], "orphan_value": o[fc]}))

    rule_rows = rules(T)
    rec_rows = reconciliations(T)
    for t, kind, name, checked, passed in rule_rows + rec_rows:
        details.append({"stage": stage, "section": "reconciliation" if kind == "reconciliation" else "rule",
                        "kind": kind, "table": t, "check": name, "checked": checked, "passed": passed,
                        "failed": checked - passed, "pass_pct": pct(passed, checked), "note": ""})

    for t in TABLES:
        df = T[t][raw_cols[t]]                     # original columns only
        allowed_blank = structural_blank(t, df)
        blank = df.apply(is_blank)
        must_fill = df.size - int((allowed_blank & blank).to_numpy().sum())
        missing = int((blank & ~allowed_blank).to_numpy().sum())

        repeat = df[PK[t]].duplicated(keep="first") | df.duplicated(business_key(t, df.columns), keep="first")

        typed = valid = 0
        for c in df.columns:
            nb = df[c][~is_blank(df[c])]
            typed += len(nb)
            valid += int(type_ok(nb, col_type(c)).sum())

        def total(rows):
            return (sum(ch for tt, _, _, ch, _ in rows if tt == t),
                    sum(pa for tt, _, _, _, pa in rows if tt == t))
        rc, rp = total(rule_rows)
        cc, cp = total(rec_rows)
        fk_checked = sum(x["checked"] for x in ri.get(t, []))
        fk_matched = sum(x["matched"] for x in ri.get(t, []))

        score.append({"table": t, "stage": stage, "rows": len(df),
                      "pct_completeness": pct(must_fill - missing, must_fill),
                      "pct_key_uniqueness": pct(len(df) - int(repeat.sum()), len(df)),
                      "pct_type_validity": pct(valid, typed),
                      "pct_rule_pass": pct(rp, rc),
                      "pct_reconciliation_pass": pct(cp, cc),
                      "pct_referential_match": pct(fk_matched, fk_checked),
                      "rule_evaluations": rc, "reconciliation_evaluations": cc,
                      "fk_values_checked": fk_checked})

    summary, rows = iqr(T, stage)
    return T, score, details, summary, rows, orphans


def main():
    raw_cols = {t: list(pd.read_csv(STAGES["raw"] / f"{t}.csv", dtype=str, nrows=0).columns)
                for t in TABLES}
    score, details, summary, orphans = [], [], [], []
    for stage in STAGES:
        T, s, d, iq, rows, o = validate(stage, raw_cols)
        score += s
        details += d
        summary += iq
        orphans += o
        if stage == "clean":
            clean_T, clean_rows = T, rows
        print(f"validated {stage}")

    sentence = iqr_sentence(clean_T, clean_rows)
    details.append({"stage": "clean", "section": "iqr interpretation", "kind": "",
                    "table": "dim_client / fact_transactions", "check": "does flagged mean wrong?",
                    "note": sentence})

    sc = pd.DataFrame(score)
    sc = sc.assign(_o=sc.stage.map({"raw": 0, "clean": 1})).sort_values(["table", "_o"]).drop(columns="_o")
    sc.to_csv(REPORTS / "data_quality_scorecard.csv", index=False)
    d = pd.DataFrame(details)
    d.to_csv(REPORTS / "validation_details.csv", index=False)
    pd.DataFrame(summary).to_csv(REPORTS / "iqr_outliers.csv", index=False)
    clean_rows.to_csv(REPORTS / "iqr_outlier_rows.csv", index=False)
    pd.concat(orphans, ignore_index=True).to_csv(REPORTS / "ri_orphans.csv", index=False)

    pd.set_option("display.width", 230, "display.max_columns", 20, "display.max_rows", 200)
    cols = ["table", "stage", "rows", "pct_completeness", "pct_key_uniqueness", "pct_type_validity",
            "pct_rule_pass", "pct_reconciliation_pass", "pct_referential_match"]
    print("\nDATA QUALITY SCORECARD (%; blank = not applicable)")
    print(sc[cols].fillna("").to_string(index=False))

    piv = lambda sec: d[d.section == sec].pivot_table(
        index=["table", "check"], columns="stage", values="pass_pct", aggfunc="first")[["raw", "clean"]]
    print("\nREFERENTIAL INTEGRITY: match rate % (13 relationships)")
    print(piv("referential integrity").to_string())
    print("\nCROSS-TABLE RECONCILIATIONS: pass %")
    print(piv("reconciliation").to_string())
    failing = d[(d.section == "rule") & (d.failed > 0)].pivot_table(
        index=["kind", "table", "check"], columns="stage", values="failed", aggfunc="sum")
    print("\nRULES WITH FAILURES (rows failed; plausibility = flagged in 02_clean, not fixable)")
    print(failing.reindex(columns=["raw", "clean"]).fillna(0).astype(int).to_string())

    s = pd.DataFrame(summary)
    print("\nIQR OUTLIERS (outside Q1 - 1.5*IQR .. Q3 + 1.5*IQR; transactions fenced per txn_type)")
    print(s[s.stage == "clean"][["table", "column", "group", "upper_fence", "flagged", "pct_flagged"]]
          .to_string(index=False))
    print("\n" + sentence)
    print("\nSaved reports/: data_quality_scorecard.csv, validation_details.csv, iqr_outliers.csv, "
          "iqr_outlier_rows.csv, ri_orphans.csv")


if __name__ == "__main__":
    main()
