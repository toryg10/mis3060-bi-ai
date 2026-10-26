"""
01_profile.py - Part A audit: generic column profiler + rule checks.

Usage:  python scripts/01_profile.py            (every CSV in data/raw)
        python scripts/01_profile.py a.csv ...  (specific files)

Outputs: reports/profile_raw.csv    one row per column, any table
         reports/dq_summary_raw.csv one row per check, tagged ERROR / WARN / INFO / PASS

The profiler and the generic checks work on ANY table. Rules that need
business knowledge (keys, code lists, ranges, reconciliations) are kept in
the CONFIG block and only run for tables that are present.
"""
import re
import sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
REPORTS = BASE / "reports"
REPORTS.mkdir(exist_ok=True)

NULL_TOKENS = {"none", "null", "nan", "n/a", "na", "-", "?"}  # text that may mean "missing"
INT_PAT = r"^-?\d+$"
FLOAT_PAT = r"^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$"
DATE_PAT = r"^\d{4}-\d{2}-\d{2}$"
BOOL_SET = {"true", "false"}
TYPE_THRESHOLD = 0.5   # a column takes the type that at least half its values parse as


# =====================================================================
# Reading
# =====================================================================
def read_table(path: Path) -> pd.DataFrame:
    """Read every column as text (assignment rule). utf-8-sig drops a BOM if present."""
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


# =====================================================================
# PART A1 - column profile (any table)
# =====================================================================
def shape(v: str) -> str:
    """Value pattern: letters -> A, digits -> 9.  '03897' -> '99999', '45.0' -> '99.9'"""
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]+", "A", v))


def parse_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.str.strip(), format="%Y-%m-%d", errors="coerce")


def type_shares(values: pd.Series) -> dict:
    if len(values) == 0:
        return {"bool": 0, "int": 0, "float": 0, "date": 0}
    v = values.str.strip()
    return {
        "bool": v.str.lower().isin(BOOL_SET).mean(),
        "int": v.str.match(INT_PAT).mean(),
        "float": v.str.match(FLOAT_PAT).mean(),
        "date": (v.str.match(DATE_PAT) & parse_date(v).notna()).mean(),
    }


def infer_type(sh: dict) -> str:
    if sh["bool"] >= TYPE_THRESHOLD:
        return "bool"
    if sh["date"] >= TYPE_THRESHOLD:
        return "date"
    if sh["float"] >= TYPE_THRESHOLD:
        return "int" if sh["int"] >= TYPE_THRESHOLD else "float"
    return "text"


def type_fail_mask(values: pd.Series, t: str) -> pd.Series:
    v = values.str.strip()
    if t == "int":
        return ~v.str.match(INT_PAT)
    if t == "float":
        return ~v.str.match(FLOAT_PAT)
    if t == "date":
        return ~(v.str.match(DATE_PAT) & parse_date(v).notna())
    if t == "bool":
        return ~v.str.lower().isin(BOOL_SET)
    return pd.Series(False, index=values.index)


def profile_column(table: str, col: str, s: pd.Series) -> dict:
    n = len(s)
    blank = s.str.strip() == ""
    nonblank = s[~blank]
    null_tok = nonblank.str.strip().str.lower().isin(NULL_TOKENS)
    values = nonblank[~null_tok]                         # real values only

    sh = type_shares(values)
    inferred = infer_type(sh)
    fail_pct = round(100 * type_fail_mask(values, inferred).mean(), 2) if len(values) else 0.0

    # whitespace: count each VALUE once, even if it has several problems
    ws_bad = (nonblank != nonblank.str.strip()) | nonblank.str.contains(r"\s{2,}")
    normalized = nonblank.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
    case_variants = nonblank.nunique() - normalized.nunique()

    shapes = values.str.strip().map(shape).value_counts()
    vmin = vmax = ""
    if inferred in ("int", "float"):
        nums = pd.to_numeric(values.str.strip(), errors="coerce").dropna()
        if len(nums):
            vmin, vmax = nums.min(), nums.max()
    elif inferred == "date":
        d = parse_date(values).dropna()
        if len(d):
            vmin, vmax = d.min().date(), d.max().date()

    return {
        "table": table, "column": col, "rows": n,
        "blank": int(blank.sum()), "blank_pct": round(100 * blank.mean(), 2) if n else 0.0,
        "null_tokens": int(null_tok.sum()),
        "distinct": int(nonblank.nunique()),
        "distinct_pct": round(100 * nonblank.nunique() / len(nonblank), 2) if len(nonblank) else 0.0,
        "inferred_type": inferred, "parse_fail_pct": fail_pct,
        "pct_int": round(100 * sh["int"], 1), "pct_float": round(100 * sh["float"], 1),
        "pct_date": round(100 * sh["date"], 1), "pct_bool": round(100 * sh["bool"], 1),
        "whitespace_issues": int(ws_bad.sum()), "case_variants": int(case_variants),
        "n_shapes": int(len(shapes)),
        "top_shapes": "; ".join(f"{k} ({v:,})" for k, v in shapes.head(3).items()),
        "min": vmin, "max": vmax,
        "top_values": "; ".join(f"{k} ({v:,})" for k, v in s.value_counts().head(3).items()),
    }


# =====================================================================
# PART A2 - CONFIG (Wildcat Capital business knowledge)
# =====================================================================
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id",
    "dim_client": "client_id", "dim_date": "date_id",
    "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}
NATURAL_KEYS = {  # must also be unique: they are join targets or business identifiers
    ("dim_date", "date"), ("dim_security", "ticker"), ("dim_benchmark", "ticker_proxy"),
}

# (fact table, fact column, dimension table, dimension column)
FOREIGN_KEYS = [
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

US_STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
FLAG_01 = {"0", "1"}

ALLOWED = {  # code lists; blanks are judged separately under completeness
    ("dim_advisor", "region"): {"Northeast", "Southeast", "Mid-Atlantic", "Midwest", "West"},
    ("dim_benchmark", "asset_class"): {"Equity", "Fixed Income", "Multi-Asset", "International",
                                       "Small Cap", "Emerging", "Cash"},
    ("dim_client", "state"): US_STATES,
    ("dim_client", "risk_profile"): {"Conservative", "Moderately Conservative", "Balanced",
                                     "Moderately Aggressive", "Aggressive"},
    ("dim_client", "client_tier"): {"Retail", "HNW", "UHNW"},
    ("dim_client", "primary_account_type"): ACCOUNT_TYPES,
    ("dim_client", "is_active"): {"True", "False"},
    ("dim_date", "is_month_end"): FLAG_01, ("dim_date", "is_quarter_end"): FLAG_01,
    ("dim_date", "is_year_end"): FLAG_01, ("dim_date", "is_trading_day"): FLAG_01,
    ("dim_security", "asset_class"): {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"},
    ("dim_security", "sector"): {"Communication Services", "Consumer Discretionary",
                                 "Consumer Staples", "Energy", "Financials", "Healthcare",
                                 "Industrials", "Technology", "Materials",
                                 "Real Estate", "Utilities"},
    ("dim_security", "is_etf"): {"True", "False"},
    ("fact_fees", "fee_type"): {"Management", "Advisory", "Custodial", "Performance"},
    ("fact_transactions", "txn_type"): {"Buy", "Sell", "Dividend", "Deposit",
                                        "Withdrawal", "Advisory Fee"},
    ("fact_portfolio_snapshot", "account_type"): ACCOUNT_TYPES,
}

RANGES = {  # (low, high, severity, note); None = no bound on that side
    ("dim_advisor", "years_experience"): (0, 60, "ERROR", ""),
    ("dim_advisor", "aum_target_mm"): (0.01, None, "ERROR", ""),
    ("dim_client", "age"): (18, 110, "ERROR", ""),
    ("dim_client", "initial_aum"): (0.01, None, "ERROR", ""),
    ("dim_date", "quarter"): (1, 4, "ERROR", ""),
    ("dim_date", "month"): (1, 12, "ERROR", ""),
    ("dim_date", "week_of_year"): (1, 53, "ERROR", ""),
    ("dim_security", "expense_ratio_bps"): (0, 300, "WARN", ""),
    ("fact_fees", "aum_basis"): (0.01, None, "ERROR", ""),
    ("fact_fees", "bps_charged"): (0, 100, "WARN", "Above 100 bps (1%/yr) is unusual for advisory fees"),
    ("fact_fees", "amount"): (0.01, None, "ERROR", ""),
    ("fact_portfolio_snapshot", "aum"): (0.01, None, "ERROR", ""),
    ("fact_portfolio_snapshot", "cash_pct"): (0, 1, "ERROR", ""),
    ("fact_portfolio_snapshot", "benchmark_return_ytd"): (-1, 1, "WARN", ""),
    ("fact_transactions", "shares"): (0.0001, None, "ERROR", ""),
    ("fact_transactions", "price"): (0.01, None, "ERROR", ""),
    ("fact_transactions", "amount"): (0.01, None, "ERROR", ""),
}
DATE_RANGES = {  # (earliest, latest) for business dates
    ("dim_client", "client_since"): ("1990-01-01", "2024-12-31"),
}

TRADE_TYPES = {"Buy", "Sell", "Dividend"}            # rows that need a security
CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}  # rows with no security


# =====================================================================
# PART A2 - helpers
# =====================================================================
FINDINGS = []


def add(severity, group, table, column, check, failed, checked, example="", note=""):
    FINDINGS.append({
        "severity": severity if failed else "PASS", "group": group,
        "table": table, "column": column, "check": check,
        "rows_failed": int(failed), "rows_checked": int(checked),
        "pct_failed": round(100 * failed / checked, 2) if checked else 0.0,
        "example": str(example)[:150], "note": note,
    })


def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


def is_blank(s):
    return s.str.strip() == ""


def norm_key(s):
    """Key as a join needs it: trimmed, and '45.0' -> '45'."""
    return s.str.strip().str.replace(r"\.0+$", "", regex=True)


def lookup(dim: pd.DataFrame, key: str, col: str) -> pd.Series:
    """key -> col mapping that survives duplicate keys (first one wins; duplicates
    are reported separately by the key checks) and normalized key text."""
    d = dim.assign(_k=norm_key(dim[key]))
    return d.drop_duplicates("_k").set_index("_k")[col]


def ex(values, k=3):
    return "; ".join(map(str, list(values)[:k]))


def have(T, *names):
    return all(n in T for n in names)


# =====================================================================
# GROUP 1 - column level
# =====================================================================
def check_generic_columns(T, prof):
    """Needs no config: runs on any table."""
    G = "1 Column level"
    for _, p in prof.iterrows():
        s = T[p.table][p.column]
        n = len(s)
        nonblank = s[~is_blank(s)]
        if p.blank:
            add("INFO", G, p.table, p.column, "Completeness: blank cells", p.blank, n,
                note="Decide: defect, or legitimate structure (blank by design)?")
        toks = nonblank[nonblank.str.strip().str.lower().isin(NULL_TOKENS)]
        if len(toks):
            add("INFO", G, p.table, p.column, "Completeness: null-like text", len(toks), n,
                ex(toks.unique()), "May mean 'missing', or may be a real value")
        values = nonblank[~nonblank.str.strip().str.lower().isin(NULL_TOKENS)]

        bad = values[type_fail_mask(values, p.inferred_type)]
        add("ERROR", G, p.table, p.column, f"Type: values not parseable as {p.inferred_type}",
            len(bad), len(values), ex(bad.unique()))
        if p.column.endswith("_id"):
            bad_id = nonblank[~nonblank.str.strip().str.match(INT_PAT)]
            add("ERROR", G, p.table, p.column, "Type: ID not stored as integer text",
                len(bad_id), len(nonblank), ex(bad_id.unique()), "e.g. '45.0' will not join to '45'")

        add("WARN", G, p.table, p.column, "Format: leading/trailing/double spaces",
            p.whitespace_issues, len(nonblank))
        add("WARN", G, p.table, p.column, "Format: same value in different case/spacing",
            p.case_variants, p.distinct)

        # pile-ups at the min or max of a near-unique numeric column (placeholder / floor / cap?)
        if p.inferred_type in ("int", "float") and p.distinct_pct > 50 and len(values) >= 100:
            v = num(values)
            for label, edge in (("minimum", v.min()), ("maximum", v.max())):
                hits = (v == edge).sum()
                add("WARN", G, p.table, p.column, f"Plausibility: rows piled at the {label}",
                    hits if hits >= 20 else 0, len(v), f"{label} = {edge}",
                    "A near-unique column should not repeat its edge value; placeholder or floor?")


def check_configured_columns(T):
    G = "1 Column level"
    for t, pk in PRIMARY_KEYS.items():
        if t not in T:
            continue
        s = T[t][pk].str.strip()
        add("ERROR", G, t, pk, "Key: primary key blank", (s == "").sum(), len(s))
        dup = s[s.duplicated(keep=False)]
        add("ERROR", G, t, pk, "Key: primary key not unique", len(dup), len(s), ex(dup.unique()))
    for t, c in NATURAL_KEYS:
        if t in T:
            s = T[t][c].str.strip().str.upper()
            dup = s[s.duplicated(keep=False) & (s != "")]
            add("ERROR", G, t, c, "Key: natural key not unique", len(dup), len(s), ex(dup.unique()))

    for (t, c), allowed in ALLOWED.items():
        if t in T:
            s = T[t][c]
            nb = s[~is_blank(s)]
            bad = nb[~nb.isin(allowed)]
            add("ERROR", G, t, c, "Validity: value not in allowed list", len(bad), len(nb),
                ex(bad.value_counts().index))

    for (t, c), (lo, hi, sev, note) in RANGES.items():
        if t in T:
            v = num(T[t][c]).dropna()
            bad = pd.Series(False, index=v.index)
            if lo is not None:
                bad |= v < lo
            if hi is not None:
                bad |= v > hi
            add(sev, G, t, c, f"Range: outside [{lo}, {hi}]", bad.sum(), len(v),
                ex(v[bad].unique()), note)

    for (t, c), (lo, hi) in DATE_RANGES.items():
        if t in T:
            d = parse_date(T[t][c]).dropna()
            bad = (d < lo) | (d > hi)
            add("ERROR", G, t, c, f"Range: date outside [{lo}, {hi}]", bad.sum(), len(d),
                ex(d[bad].dt.date.unique()), "Future dates or sentinels such as 1900-01-01")

    # returns: below -100% is impossible; above +100% is only suspicious
    if "fact_portfolio_snapshot" in T:
        r = num(T["fact_portfolio_snapshot"].return_ytd).dropna()
        add("ERROR", G, "fact_portfolio_snapshot", "return_ytd", "Range: return below -1 (-100%)",
            (r < -1).sum(), len(r), ex(r[r < -1].unique()), "Cannot lose more than everything")
        add("WARN", G, "fact_portfolio_snapshot", "return_ytd", "Range: return above +1 (+100%)",
            (r > 1).sum(), len(r), ex(r[r > 1].unique()),
            "Possible percent units mixed with decimals (compare the '12.34%' strings), "
            "or flows counted as return")


# =====================================================================
# GROUP 2 - single-table rules
# =====================================================================
def check_single_table(T):
    G = "2 Single-table"
    for t, df in T.items():                      # generic duplicate checks, any table
        if df.empty:
            continue
        pk = PRIMARY_KEYS.get(t, df.columns[0])
        cols = [c for c in df.columns if c != pk]
        norm = df[cols].apply(lambda s: s.str.strip().str.lower())
        exact = norm.duplicated(keep=False)
        add("ERROR", G, t, "(all)", "Duplicates: identical rows apart from the key",
            exact.sum(), len(df), ex(df.loc[exact, pk]))
        for c in cols:                           # near-duplicates: identical except ONE column
            others = [o for o in cols if o != c]
            if len(others) < 3:
                continue
            near = norm.duplicated(others, keep=False) & ~exact
            add("WARN", G, t, c, f"Near-duplicates: rows identical except '{c}'",
                near.sum(), len(df), ex(df.loc[near, [pk, c]].astype(str).agg("=".join, axis=1)),
                "Same entity entered twice with one field changed? Or a coincidence?")

    if "fact_transactions" in T:
        tx = T["fact_transactions"]
        typ = tx.txn_type.str.strip()
        trade, cash = typ.isin(TRADE_TYPES), typ.isin(CASH_TYPES)
        miss = trade & (is_blank(tx.security_id) | is_blank(tx.shares) | is_blank(tx.price))
        add("ERROR", G, "fact_transactions", "security_id/shares/price",
            "Contradiction: trade row missing security, shares or price", miss.sum(), trade.sum())
        extra = cash & ~(is_blank(tx.security_id) & is_blank(tx.shares) & is_blank(tx.price))
        add("ERROR", G, "fact_transactions", "security_id/shares/price",
            "Contradiction: cash row has security, shares or price", extra.sum(), cash.sum(),
            note="Blank security/shares/price on cash rows is structure, not missing data")

        sh, pr, amt = num(tx.shares), num(tx.price), num(tx.amount)
        bs = typ.isin({"Buy", "Sell"})
        neg = bs & (sh <= 0)
        add("ERROR", G, "fact_transactions", "shares", "Sign: Buy/Sell with zero or negative shares",
            neg.sum(), (bs & sh.notna()).sum(), ex(typ[neg] + " " + tx.shares[neg]))
        ok = bs & sh.notna() & pr.notna() & amt.notna()
        bad = ok & ((sh.abs() * pr - amt).abs() > 0.01)
        add("ERROR", G, "fact_transactions", "amount", "Recompute: Buy/Sell amount != |shares| x price",
            bad.sum(), ok.sum())
        dv = (typ == "Dividend") & sh.notna() & pr.notna() & amt.notna()
        whole = dv & ((sh.abs() * pr - amt).abs() <= 0.01)
        add("ERROR", G, "fact_transactions", "amount",
            "Plausibility: Dividend amount equals the full position value (shares x price)",
            whole.sum(), dv.sum(), ex(tx.amount[whole]),
            "A dividend is a small yield on the position, not the position's value")

    if "fact_fees" in T:
        fee = T["fact_fees"]
        a, b, p = num(fee.aum_basis), num(fee.bps_charged), num(fee.amount)
        ok = a.notna() & b.notna() & p.notna()
        bad = ok & ((a * b / 10000 / 12 - p).abs() > 0.01)
        add("ERROR", G, "fact_fees", "amount", "Recompute: amount != aum_basis x bps / 10000 / 12",
            bad.sum(), ok.sum())

    if "fact_portfolio_snapshot" in T:
        sn = T["fact_portfolio_snapshot"]
        sd, y, m = parse_date(sn.snapshot_date), num(sn.year), num(sn.month)
        ok = sd.notna() & y.notna() & m.notna()
        bad = ok & ((sd.dt.year != y) | (sd.dt.month != m))
        add("ERROR", G, "fact_portfolio_snapshot", "year/month",
            "Contradiction: year/month disagree with snapshot_date", bad.sum(), ok.sum())
        r, bm, al = num(sn.return_ytd), num(sn.benchmark_return_ytd), num(sn.active_alpha_ytd)
        ok = r.notna() & bm.notna() & al.notna()
        bad = ok & ((r - bm - al).abs() > 1e-5)
        add("ERROR", G, "fact_portfolio_snapshot", "active_alpha_ytd",
            "Recompute: alpha != return_ytd - benchmark_return_ytd", bad.sum(), ok.sum(),
            note=f"{(~ok).sum()} rows not checkable because a value did not parse")

    if "dim_date" in T:
        dt = T["dim_date"]
        dd = parse_date(dt.date)
        ok = dd.notna()
        d = dd[ok]
        x = dt[ok]
        bad = ((d.dt.year != num(x.year)) | (d.dt.month != num(x.month))
               | (d.dt.quarter != num(x.quarter)) | (d.dt.day_name() != x.day_of_week.str.strip())
               | (d.dt.month_name() != x.month_name.str.strip())
               | (d.dt.isocalendar().week.astype(int) != num(x.week_of_year))
               | (d.dt.is_month_end.astype(int) != num(x.is_month_end))
               | (d.dt.is_quarter_end.astype(int) != num(x.is_quarter_end))
               | (d.dt.is_year_end.astype(int) != num(x.is_year_end)))
        add("ERROR", G, "dim_date", "(calendar)", "Contradiction: calendar columns disagree with date",
            bad.sum(), ok.sum())
        wk = (d.dt.dayofweek >= 5) & (x.is_trading_day.str.strip() == "1")
        add("ERROR", G, "dim_date", "is_trading_day", "Contradiction: weekend marked as trading day",
            wk.sum(), ok.sum())

    if "dim_security" in T:
        sec = T["dim_security"]
        flag = sec.is_etf.str.strip()
        etf, stock = flag == "True", flag == "False"
        note_s = "ETFs span sectors, so blank sector on ETFs is structure"
        note_e = "Individual securities have no expense ratio, so blank there is structure"
        add("ERROR", G, "dim_security", "sector", "Contradiction: non-ETF with blank sector",
            (stock & is_blank(sec.sector)).sum(), stock.sum(), note=note_s)
        add("ERROR", G, "dim_security", "sector", "Contradiction: ETF with a sector",
            (etf & ~is_blank(sec.sector)).sum(), etf.sum(), note=note_s)
        add("ERROR", G, "dim_security", "expense_ratio_bps", "Contradiction: ETF with blank expense ratio",
            (etf & is_blank(sec.expense_ratio_bps)).sum(), etf.sum(), note=note_e)
        add("ERROR", G, "dim_security", "expense_ratio_bps",
            "Contradiction: non-ETF with an expense ratio",
            (stock & ~is_blank(sec.expense_ratio_bps)).sum(), stock.sum(), note=note_e)


# =====================================================================
# GROUP 3 - referential integrity
# =====================================================================
def check_referential(T):
    G = "3 Referential integrity"
    for ft, fc, dtab, dc in FOREIGN_KEYS:
        if not have(T, ft, dtab):
            continue
        f, d = T[ft][fc], T[dtab][dc]
        nb = f[~is_blank(f)]
        add("INFO", G, ft, fc, f"Null key -> {dtab}.{dc}", len(f) - len(nb), len(f),
            note="Blank FK: check whether it is structural")
        raw_miss = ~nb.isin(set(d))
        add("ERROR", G, ft, fc, f"Join breaks on raw text -> {dtab}.{dc}", raw_miss.sum(), len(nb),
            ex(nb[raw_miss].unique()), "Raw text does not match the dimension key exactly")
        orphan = ~norm_key(nb).isin(set(norm_key(d)))
        add("ERROR", G, ft, fc, f"Orphans: no matching {dtab}.{dc} (after normalizing)",
            orphan.sum(), len(nb), ex(nb[orphan].unique()))


# =====================================================================
# GROUP 4 - cross-table business rules
# =====================================================================
def check_cross_table(T):
    G = "4 Cross-table"
    if "dim_client" in T:
        cli = T["dim_client"]
        cli_adv = lookup(cli, "client_id", "advisor_id")
        cli_since = lookup(cli, "client_id", "client_since")
        for ft, dc in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date"),
                       ("fact_transactions", "txn_date")]:
            if ft not in T:
                continue
            f = T[ft]
            key = norm_key(f.client_id)
            adv = key.map(cli_adv)
            ok = adv.notna() & ~is_blank(adv.fillna("")) & ~is_blank(f.advisor_id)
            bad = ok & (norm_key(adv.fillna("")) != norm_key(f.advisor_id))
            add("WARN", G, ft, "advisor_id", "Fact advisor != client's advisor in dim_client",
                bad.sum(), ok.sum())
            since = key.map(cli_since).fillna("").str.strip()
            ok = (since != "") & ~is_blank(f[dc])
            if ft == "fact_transactions":                   # daily data: compare the day
                early = ok & (f[dc].str.strip() < since)
            else:                                           # monthly data dated the 1st
                early = ok & (f[dc].str.strip().str[:7] < since.str[:7])
            add("WARN", G, ft, dc, "Activity dated before client_since", early.sum(), ok.sum())

        if "fact_portfolio_snapshot" in T:
            sn = T["fact_portfolio_snapshot"]
            acct = norm_key(sn.client_id).map(lookup(cli, "client_id", "primary_account_type"))
            ok = acct.notna() & ~is_blank(acct.fillna(""))
            bad = ok & (acct.fillna("").str.strip() != sn.account_type.str.strip())
            add("WARN", G, "fact_portfolio_snapshot", "account_type",
                "account_type != client's primary_account_type", bad.sum(), ok.sum())

            # does each risk profile map to exactly one snapshot benchmark?
            per_client = sn.groupby(norm_key(sn.client_id)).benchmark_id.agg(
                lambda s: "|".join(sorted(set(s.str.strip()))))
            c = cli.assign(bench=norm_key(cli.client_id).map(per_client),
                           rp=cli.risk_profile.str.strip())
            c = c[c.bench.notna() & (c.rp != "")]
            mapping = c.groupby("rp").bench.agg(lambda s: "/".join(sorted(set(s))))
            add("WARN", G, "dim_client", "risk_profile",
                "Risk profile maps to more than one snapshot benchmark",
                mapping.str.contains("[/|]").sum(), len(mapping),
                "; ".join(f"{k} -> {v}" for k, v in mapping.items()),
                "If each profile has one benchmark, the benchmark can confirm or recover a profile")

        used = set()
        for ft in ("fact_fees", "fact_portfolio_snapshot", "fact_transactions"):
            if ft in T:
                used |= set(norm_key(T[ft].client_id))
        idle = ~norm_key(cli.client_id).isin(used)
        add("INFO", G, "dim_client", "client_id", "Client has no fees, snapshots or transactions",
            idle.sum(), len(cli), ex(cli.client_id[idle]))

    if have(T, "fact_fees", "fact_portfolio_snapshot"):
        fee, sn = T["fact_fees"], T["fact_portfolio_snapshot"]
        aum = sn.assign(_k=norm_key(sn.client_id) + "|" + sn.snapshot_date.str.strip()) \
                .drop_duplicates("_k").set_index("_k").aum
        a = (norm_key(fee.client_id) + "|" + fee.fee_date.str.strip()).map(aum)
        ok = a.notna() & num(a.fillna("")).notna() & num(fee.aum_basis).notna()
        bad = ok & ((num(fee.aum_basis) - num(a.fillna(""))).abs() > 0.01)
        add("ERROR", G, "fact_fees", "aum_basis", "aum_basis != snapshot aum (same client, month)",
            bad.sum(), ok.sum(), note=f"{(~ok).sum()} fee rows had no usable matching snapshot")

    if have(T, "fact_transactions", "dim_date"):
        tx = T["fact_transactions"]
        trading = tx.txn_date.str.strip().map(lookup(T["dim_date"], "date", "is_trading_day"))
        trades = tx.txn_type.str.strip().isin({"Buy", "Sell"})
        ok = trades & trading.notna()
        off = ok & (trading.fillna("").str.strip() == "0")
        add("WARN", G, "fact_transactions", "txn_date", "Buy/Sell dated on a non-trading day",
            off.sum(), ok.sum(), ex(tx.txn_date[off].unique()))

    if "fact_transactions" in T:
        tx = T["fact_transactions"]
        t = tx[tx.txn_type.str.strip().isin({"Buy", "Sell"})].copy()
        t["q"] = num(t.shares).abs() * t.txn_type.str.strip().map({"Buy": 1, "Sell": -1})
        t["sid"] = norm_key(t.security_id)
        t = t.sort_values(["client_id", "sid", "txn_date", "txn_id"])
        t["pos"] = t.groupby(["client_id", "sid"]).q.cumsum()
        sells = t.txn_type.str.strip() == "Sell"
        add("INFO", G, "fact_transactions", "shares", "Sell leaves a negative running position",
            (sells & (t.pos < -1e-6)).sum(), sells.sum(),
            note="Data has no opening positions, so this cannot prove an error on its own")


# =====================================================================
# Main
# =====================================================================
def run_checks(T, prof):
    check_generic_columns(T, prof)
    check_configured_columns(T)
    check_single_table(T)
    check_referential(T)
    check_cross_table(T)
    dq = pd.DataFrame(FINDINGS)
    rank = {"ERROR": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    dq = dq.assign(_r=dq.severity.map(rank)).sort_values(["_r", "group", "table"]).drop(columns="_r")
    out = REPORTS / "dq_summary_raw.csv"
    dq.to_csv(out, index=False)
    print(f"Saved {out}  ({len(dq)} checks run)\n")
    print(dq.severity.value_counts().reindex(list(rank)).fillna(0).astype(int).to_string())
    print("\nFindings (PASS rows hidden):")
    print(dq[dq.severity != "PASS"][["severity", "group", "table", "column", "check", "rows_failed"]]
          .to_string(index=False))


def main():
    files = [Path(p) for p in sys.argv[1:]] or sorted(RAW.glob("*.csv"))
    rows, T = [], {}
    for f in files:
        df = read_table(f)
        T[f.stem] = df
        for col in df.columns:
            rows.append(profile_column(f.stem, col, df[col]))
        print(f"profiled {f.name:32} {df.shape[0]:>8,} rows x {df.shape[1]} cols")
    prof = pd.DataFrame(rows)
    out = REPORTS / "profile_raw.csv"
    prof.to_csv(out, index=False)
    print(f"Saved {out}  ({len(prof)} columns profiled)")
    pd.set_option("display.width", 250, "display.max_columns", 20,
                  "display.max_rows", 300, "display.max_colwidth", 70)
    run_checks(T, prof)


if __name__ == "__main__":
    main()
