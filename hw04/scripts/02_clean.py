"""
02_clean.py - Part C: clean the eight Wildcat Capital tables.

Follows decision_log.md entry by entry (D1-D11), in the order the log defends:
  1. quarantine rows that should not exist  (D1, D2)
  2. fix formats so keys join               (D3, D4)
  3. repair values that can be reconciled   (D5, D6, D7)
  4. flag what cannot be corrected          (D8-D11)

Every step prints rows affected + a before/after check, then ASSERTS the
after-state. If any fix does not do what the log claims, the script stops.

Reads : data/raw/*.csv              (never modified)
Writes: data/clean/*.csv            same file names, same columns, plus 0/1 flag columns
        data/clean/README_clean.md
        data/audit/cleaning_log.csv, value_changes.csv, quarantine_*.csv
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW, CLEAN, AUDIT = BASE / "data" / "raw", BASE / "data" / "clean", BASE / "data" / "audit"
CLEAN.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

# Row counts each step must affect. If the data says otherwise, stop and re-audit.
# The audit counted fact_transactions on RAW data. D2 runs first and quarantines 200 rows
# (58 Buy, 35 Sell, 38 Dividend, 69 cash), so later transaction steps expect the raw count
# minus what D2 already removed:
#   D3  197,175 - 131 trade rows             = 197,044
#   D5      836 -   1 negative Buy           =     835
#   D8   53,864 -  38 dividends              =  53,826
#   D11  40,649 -  19 off-calendar trades    =  40,630
# Likewise D1 quarantines 25 clients, one of which had a spelled-out state:
#   D4       78 -   1                        =      77
# And D6 converts one percent string ('1170.15%') into a value above 1, so D9 sees one more:
#   D9      976 +   1                        =     977
EXPECTED = {"D1": 25, "D2": 200, "D3": 197044, "D4": 77, "D5": 835, "D6": 300, "D7": 75,
            "D8": 53826, "D9": 977, "D10_snap": 420, "D10_fee": 386, "D11": 40630}

FLAG_COLUMNS = {"dim_client": ["risk_profile_imputed"],
                "fact_fees": ["aum_floor_flag"],
                "fact_portfolio_snapshot": ["return_suspect", "aum_floor_flag"],
                "fact_transactions": ["dividend_amount_suspect", "non_trading_day_trade"]}

# All 13 relationships: (fact, column, dimension, key, blank allowed?)
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_fees", "client_id", "dim_client", "client_id", False),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", False),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_transactions", "client_id", "dim_client", "client_id", False),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_transactions", "security_id", "dim_security", "security_id", True),  # blank on cash rows
    ("fact_fees", "fee_date", "dim_date", "date", False),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", False),
    ("fact_transactions", "txn_date", "dim_date", "date", False),
]

STATE_CODES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI",
    "Wyoming": "WY"}
US_CODES = set(STATE_CODES.values())

# ---------------------------------------------------------------- state
T = {n: pd.read_csv(RAW / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}
RAW_ROWS = {n: len(df) for n, df in T.items()}
RAW_T = {n: df.copy() for n, df in T.items()}          # untouched copy for the final proofs
RAW_COLS = {n: list(df.columns) for n, df in T.items()}
LOG, CHANGES, QUARANTINE, FLAGS = [], [], {}, {}


def num(s):
    return pd.to_numeric(s, errors="coerce")


def step(code, title):
    print(f"\n{'=' * 78}\n{code}  {title}\n{'=' * 78}")


def log(table, code, issue, action, rows, note=""):
    LOG.append({"step": code, "table": table, "issue": issue, "action": action,
                "rows_affected": int(rows), "note": note})
    print(f"   rows affected: {rows:,}")


def check(condition, message):
    """assert with a readable message; stops the script if a fix did not work."""
    if not condition:                       # not a bare assert: `python -O` would strip those
        raise RuntimeError(f"STOPPED: {message}")
    print(f"   OK  {message}")


def record_changes(table, column, old, new):
    """Write every changed cell to value_changes.csv."""
    changed = old != new
    pk = PK[table]
    CHANGES.append(pd.DataFrame({
        "table": table, "key_column": pk, "key": T[table].loc[changed[changed].index, pk],
        "column": column, "old_value": old[changed], "new_value": new[changed]}))
    return int(changed.sum())


def quarantine(table, mask, name, reason, extra=None):
    q = T[table][mask].copy()
    q.insert(0, "quarantine_reason", reason)
    if extra is not None:
        for col, values in extra.items():
            q[col] = values
    QUARANTINE[(table, name)] = q
    T[table] = T[table][~mask].copy()
    return len(q)


def add_flag(table, column, mask, meaning):
    T[table][column] = mask.map({True: "1", False: "0"})
    FLAGS[(table, column)] = (int(mask.sum()), meaning)


# ================================================================ 1. QUARANTINE
step("D1", "dim_client: duplicate clients (last_name altered) -> quarantine")
cli = T["dim_client"]
used = set()
for f in ("fact_fees", "fact_portfolio_snapshot", "fact_transactions"):
    used |= set(T[f].client_id)
match_cols = [c for c in cli.columns if c not in ("client_id", "last_name")]
pairs = cli.merge(cli, on=match_cols, suffixes=("", "_orig"))
pairs = pairs[pairs.client_id != pairs.client_id_orig]
# In each pair the copy is the record nothing points to; the original has activity.
pairs = pairs[~pairs.client_id.isin(used) & pairs.client_id_orig.isin(used)]
print(pairs[["client_id", "last_name", "client_id_orig", "last_name_orig"]].head(3).to_string(index=False))
check(len(pairs) == EXPECTED["D1"] and pairs.client_id.is_unique,
      f"found {EXPECTED['D1']} copies, each matching one active original on every column but last_name")
one_letter = pairs.apply(lambda r: abs(len(r.last_name) - len(r.last_name_orig)) == 1 and
                         (r.last_name_orig.startswith(r.last_name) or r.last_name.startswith(r.last_name_orig)),
                         axis=1)
check(one_letter.all(), "every copy's last_name differs from the original by one letter at the end")
mask = cli.client_id.isin(pairs.client_id)
twin = cli.loc[mask, "client_id"].map(pairs.set_index("client_id").client_id_orig)
before = len(cli)
n = quarantine("dim_client", mask, "duplicates",
               "Duplicate of an existing client; last_name off by one letter, all other fields identical",
               {"duplicate_of_client_id": twin})
check(len(T["dim_client"]) == before - n and T["dim_client"].client_id.is_unique,
      f"dim_client {before:,} -> {len(T['dim_client']):,} rows")
kept = set(T["dim_client"].client_id)
check(all(T[f].client_id.isin(kept).all() for f in ("fact_fees", "fact_portfolio_snapshot"))
      and T["fact_transactions"].client_id.isin(kept | set(RAW_T["fact_transactions"].client_id[
          ~RAW_T["fact_transactions"].client_id.isin(set(RAW_T["dim_client"].client_id))])).all(),
      "after removal, every fee/snapshot client still exists; transactions lose nothing they had")
log("dim_client", "D1", "25 duplicate clients (last_name off by one letter)", "quarantine", n,
    "Matched to originals on every other column; none referenced by any fact table")

step("D2", "fact_transactions: client_id not in dim_client -> quarantine")
tx = T["fact_transactions"]
valid = set(T["dim_client"].client_id)
orphan = ~tx.client_id.isin(valid)
twin_cols = [c for c in tx.columns if c not in ("txn_id", "client_id")]
twins = tx[orphan].merge(tx[~orphan], on=twin_cols, suffixes=("", "_real"))
print(f"   orphans: {orphan.sum():,}  twin matches found: {len(twins):,}")
check(orphan.sum() == EXPECTED["D2"] and len(twins) == orphan.sum() and twins.txn_id.is_unique,
      "every orphan has exactly ONE real twin (identical except client_id)")
check((twins.txn_id_real.astype(int) < twins.txn_id.astype(int)).all(),
      "in every pair the real row has the lower txn_id (the orphan is the later copy)")
twin_id = tx.loc[orphan, "txn_id"].map(twins.set_index("txn_id").txn_id_real)
n = quarantine("fact_transactions", orphan, "orphans",
               "client_id not in dim_client; row is a copy of a real transaction",
               {"copy_of_txn_id": twin_id})
check(T["fact_transactions"].client_id.isin(valid).all(), "every remaining client_id exists in dim_client")
log("fact_transactions", "D2", "200 transactions for non-existent clients", "quarantine", n,
    "Each identical to a real transaction except client_id (twin txn_id kept in quarantine file)")

# ================================================================ 2. FORMATS
step("D3", "fact_transactions.security_id: '45.0' -> '45'")
tx = T["fact_transactions"]
sid = tx.security_id
has = sid != ""
sec_ids = set(T["dim_security"].security_id)
print(f"   before: raw match to dim_security = {sid[has].isin(sec_ids).mean():.1%}  e.g. {sid[has].iloc[0]}")
check(sid[has].str.fullmatch(r"\d+\.0").all(), "every non-blank ID ends in '.0' (no real decimals lost)")
new = sid.where(~has, sid.str.replace(r"\.0$", "", regex=True))
n = record_changes("fact_transactions", "security_id", sid, new)
T["fact_transactions"]["security_id"] = new
after = new[has]
print(f"   after : match to dim_security = {after.isin(sec_ids).mean():.1%}  e.g. {after.iloc[0]}")
check(n == EXPECTED["D3"] and after.isin(sec_ids).all(), "100% of non-blank security_ids now join")
check((new == "").sum() == (~has).sum(), "blank security_ids (cash rows) untouched")
log("fact_transactions", "D3", "security_id stored as decimal text", "convert", n,
    "'45.0' -> '45'; raw join rate 0% -> 100%")

step("D4", "dim_client.state: full names -> 2-letter codes")
st = T["dim_client"].state
full = ~st.isin(US_CODES)
print(f"   before: {full.sum()} full names, e.g. {sorted(st[full].unique())[:4]}")
check(st[full].isin(STATE_CODES.keys()).all(), "every full name has a known code")
new = st.map(lambda v: STATE_CODES.get(v, v))
# expected per-state total = rows already coded + rows spelled out, counted separately
coded = st[~full].value_counts()
spelled = st[full].value_counts().rename(index=STATE_CODES).groupby(level=0).sum()
before_counts = coded.add(spelled, fill_value=0).astype(int)
n = record_changes("dim_client", "state", st, new)
T["dim_client"]["state"] = new
check(n == EXPECTED["D4"] and new.isin(US_CODES).all(), "every state is now a valid 2-letter code")
after_counts = new.value_counts()
check(after_counts.sort_index().equals(before_counts.sort_index()),
      "per-state totals = old code count + old full-name count (nothing lost)")
print(f"   after : PA = {(new == 'PA').sum()} (was {(st == 'PA').sum()} 'PA' + {(st == 'Pennsylvania').sum()} 'Pennsylvania')")
log("dim_client", "D4", "state spelled out", "standardize", n, "Full names mapped to USPS codes")

# ================================================================ 3. RECONCILED REPAIRS
step("D5", "fact_transactions.shares: negative Buy -> positive")
tx = T["fact_transactions"]
sh, pr, amt = num(tx.shares), num(tx.price), num(tx.amount)
neg = (tx.txn_type == "Buy") & (sh < 0)
print(f"   before: {neg.sum()} Buy rows with negative shares, e.g. {tx.shares[neg].iloc[0]}")
check(((sh[neg].abs() * pr[neg] - amt[neg]).abs() <= 0.01).all(),
      "reconcile: amount = |shares| x price on every one, so only the sign is wrong")
new = tx.shares.where(~neg, tx.shares.str.lstrip("-"))
n = record_changes("fact_transactions", "shares", tx.shares, new)
T["fact_transactions"]["shares"] = new
sh2 = num(new)
bs = tx.txn_type.isin(["Buy", "Sell"])
check(n == EXPECTED["D5"] and (sh2[bs] > 0).all(), "every Buy/Sell now has positive shares")
check(((sh2[bs] * pr[bs] - amt[bs]).abs() <= 0.01).all(), "amount = shares x price still holds on all Buy/Sell rows")
log("fact_transactions", "D5", "Buy with negative shares", "convert (absolute value)", n,
    "Verified against amount = |shares| x price; direction comes from txn_type")

step("D6", "fact_portfolio_snapshot.return_ytd: '9.28%' -> 0.0928")
sn = T["fact_portfolio_snapshot"]
r = sn.return_ytd
pct = r.str.endswith("%")
print(f"   before: {pct.sum()} percent strings, e.g. {r[pct].iloc[0]}; parseable = {num(r).notna().mean():.2%}")
val = num(r[pct].str.rstrip("%")) / 100
bm, al = num(sn.benchmark_return_ytd[pct]), num(sn.active_alpha_ytd[pct])
gap = (val - bm - al).abs()
check((gap <= 5e-5 + 1e-9).all(),
      "reconcile: return/100 - benchmark = alpha on every row (within 2-decimal rounding)")
check(((num(r[pct].str.rstrip("%")) - bm - al).abs() > 5e-5).all(),
      "and NOT dividing by 100 fails on every row, so /100 is the right scale")
new = r.copy()
new[pct] = val.round(6).map(lambda v: f"{v:g}" if abs(v) >= 1e-4 else f"{v:.6f}")
n = record_changes("fact_portfolio_snapshot", "return_ytd", r, new)
T["fact_portfolio_snapshot"]["return_ytd"] = new
print(f"   after : e.g. {new[pct].iloc[0]}; parseable = {num(new).notna().mean():.2%}")
check(n == EXPECTED["D6"] and num(new).notna().all(), "every return_ytd is now a decimal number")
stored_gap = (num(new[pct]) - bm - al).abs()
check((stored_gap <= 5e-5 + 1e-9).all(),
      f"re-checked on the written text: alpha still reconciles (max gap {stored_gap.max():.2e})")
log("fact_portfolio_snapshot", "D6", "return_ytd stored as percent text", "convert (/100)", n,
    "Scale confirmed by return - benchmark = alpha")

step("D7", "dim_client.risk_profile: blank -> recover from snapshot benchmark")
cli, sn = T["dim_client"], T["fact_portfolio_snapshot"]
bench = sn.groupby("client_id").benchmark_id.agg(lambda s: "|".join(sorted(set(s))))
known = cli[cli.risk_profile != ""].assign(b=lambda d: d.client_id.map(bench)).dropna(subset=["b"])
profiles_per_bench = known.groupby("b").risk_profile.agg(lambda s: sorted(set(s)))
unique_map = {b: p[0] for b, p in profiles_per_bench.items() if len(p) == 1}
print("   benchmark -> profiles among known clients:",
      "; ".join(f"{b}: {'/'.join(p)}" for b, p in profiles_per_bench.items()))
blank = cli.risk_profile == ""
cand = cli.client_id[blank].map(bench)
fill = cand.map(unique_map)
print(f"   before: {blank.sum()} blank; recoverable from a one-to-one benchmark: {fill.notna().sum()}")
check(fill.notna().all(), "every blank client's benchmark maps to exactly one profile")
check((cand == "3").all(), "every blank client is benchmarked only to benchmark 3")
b3 = known[known.b == "3"]
check(len(b3) >= 100 and set(b3.risk_profile) == {"Balanced"},
      f"benchmark 3 has {len(b3)} known clients, all Balanced (strong evidence, not one client)")
new = cli.risk_profile.copy()
new[blank] = fill
n = record_changes("dim_client", "risk_profile", cli.risk_profile, new)
T["dim_client"]["risk_profile"] = new
add_flag("dim_client", "risk_profile_imputed", blank,
         "risk_profile was blank and was filled from the client's snapshot benchmark")
check(n == EXPECTED["D7"] and (new != "").all(), "no blank risk_profile remains")
check(set(new[blank]) == {"Balanced"}, "all fills are 'Balanced' (benchmark 3 is used only by Balanced)")
log("dim_client", "D7", "blank risk_profile", "fill + flag risk_profile_imputed", n,
    "Benchmark 3 is used only by Balanced clients (757 of 757 known)")

# ================================================================ 4. FLAGS (values kept)
step("D8", "fact_transactions: dividend = full position value -> flag")
tx = T["fact_transactions"]
div = tx.txn_type == "Dividend"
whole = div & ((num(tx.shares) * num(tx.price) - num(tx.amount)).abs() <= 0.01)
print(f"   before: {div.sum():,} dividends, median ${num(tx.amount[div]).median():,.0f} "
      f"(median Buy ${num(tx.amount[tx.txn_type == 'Buy']).median():,.0f}); no flag column")
amount_before = tx.amount.copy()
add_flag("fact_transactions", "dividend_amount_suspect", whole,
         "Dividend amount equals shares x price (the whole position); true dividend unknown")
print(f"   after : dividend_amount_suspect = 1 on {whole.sum():,} rows")
check(whole.sum() == EXPECTED["D8"] and whole.sum() == div.sum(),
      f"all {div.sum():,} dividends flagged (every one equals shares x price)")
check(T["fact_transactions"].amount.equals(amount_before), "amounts unchanged")
log("fact_transactions", "D8", "dividend amount = whole position value", "flag dividend_amount_suspect",
    whole.sum(), "No yield data exists to compute the true dividend")

step("D9", "fact_portfolio_snapshot: return_ytd above +100% -> flag")
sn = T["fact_portfolio_snapshot"]
big = num(sn.return_ytd) > 1
print(f"   before: return_ytd max {num(sn.return_ytd).max():.2f}, rows above 1.0 = {big.sum():,}; no flag column")
add_flag("fact_portfolio_snapshot", "return_suspect", big,
         "return_ytd > 100%; deposits counted as return (not flow-adjusted)")
r, b, a = num(sn.return_ytd[big]), num(sn.benchmark_return_ytd[big]), num(sn.active_alpha_ytd[big])
check(((r - b - a).abs() <= 5e-5 + 1e-9).all(),
      "alpha reconciles on flagged rows (within rounding), so this is not a units error")
print(f"   after : return_suspect = 1 on {(T['fact_portfolio_snapshot'].return_suspect == '1').sum():,} rows; "
      "values (and active_alpha_ytd) unchanged")
check(big.sum() == EXPECTED["D9"], f"{big.sum():,} rows flagged across {sn.client_id[big].nunique()} clients")
log("fact_portfolio_snapshot", "D9", "return_ytd above +100%", "flag return_suspect", big.sum(),
    "Coincides with large deposits; not recomputable without daily flows")

step("D10", "AUM at exactly $1,000 (floor value) -> flag in snapshots and fees")
sn, fee = T["fact_portfolio_snapshot"], T["fact_fees"]
f_s = num(sn.aum) == 1000
f_f = num(fee.aum_basis) == 1000
print(f"   before: aum = 1000.0 on {f_s.sum()} snapshots ({sn.client_id[f_s].nunique()} clients), "
      f"aum_basis = 1000.0 on {f_f.sum()} fee rows; no flag column")
add_flag("fact_portfolio_snapshot", "aum_floor_flag", f_s, "aum is exactly 1000.0, a floor/placeholder")
add_flag("fact_fees", "aum_floor_flag", f_f, "aum_basis is exactly 1000.0, a floor/placeholder")
print(f"   after : aum_floor_flag = 1 on {(T['fact_portfolio_snapshot'].aum_floor_flag == '1').sum()} "
      f"snapshots and {(T['fact_fees'].aum_floor_flag == '1').sum()} fee rows; values unchanged")
check(f_s.sum() == EXPECTED["D10_snap"] and f_f.sum() == EXPECTED["D10_fee"],
      f"{f_s.sum()} snapshots and {f_f.sum()} fee rows flagged")
log("fact_portfolio_snapshot", "D10", "aum = 1000.0 floor", "flag aum_floor_flag", f_s.sum())
log("fact_fees", "D10", "aum_basis = 1000.0 floor", "flag aum_floor_flag", f_f.sum())

step("D11", "fact_transactions: Buy/Sell on a non-trading day -> flag")
tx = T["fact_transactions"]
trading = tx.txn_date.map(T["dim_date"].set_index("date").is_trading_day)
check(trading.notna().all(), "every txn_date exists in dim_date")
bs = tx.txn_type.isin(["Buy", "Sell"])
off = bs & (trading == "0")
print(f"   before: Buy/Sell rows by is_trading_day: {trading[bs].value_counts().to_dict()}; no flag column")
add_flag("fact_transactions", "non_trading_day_trade", off,
         "Buy/Sell dated on a day dim_date marks as non-trading")
print(f"   after : non_trading_day_trade = 1 on {(T['fact_transactions'].non_trading_day_trade == '1').sum():,} rows")
check(off.sum() == EXPECTED["D11"], f"{off.sum():,} trades flagged; dates unchanged")
log("fact_transactions", "D11", "Buy/Sell on non-trading day", "flag non_trading_day_trade", off.sum())

# ================================================================ FINAL PROOFS
step("PROOF", "raw rows = clean rows + quarantined rows, for every table")
for t in TABLES:
    q = sum(len(df) for (tt, _), df in QUARANTINE.items() if tt == t)
    c = len(T[t])
    check(RAW_ROWS[t] == c + q, f"{t:26} raw {RAW_ROWS[t]:>8,} = clean {c:>8,} + quarantined {q:>4,}")
    added = [col for col in T[t].columns if col not in RAW_COLS[t]]
    check(list(T[t].columns[:len(RAW_COLS[t])]) == RAW_COLS[t],
          f"{t:26} same columns, same order (+ flags: {', '.join(added) or 'none'})")
    check(T[t][PK[t]].is_unique, f"{t:26} primary key {PK[t]} unique")

    # keys: clean and quarantined do not overlap, and together are exactly the raw keys
    qkeys = set()
    for (tt, _), df in QUARANTINE.items():
        if tt == t:
            qkeys |= set(df[PK[t]])
    ckeys, rkeys = set(T[t][PK[t]]), set(RAW_T[t][PK[t]])
    check(not (ckeys & qkeys) and (ckeys | qkeys) == rkeys,
          f"{t:26} clean keys + quarantined keys = raw keys, no overlap")

    # added columns are exactly the planned flags, holding only 0/1
    check(added == FLAG_COLUMNS.get(t, []), f"{t:26} added columns are exactly the planned flags")
    for col in added:
        check(T[t][col].isin(["0", "1"]).all(), f"{t:26} {col} holds only 0/1")

step("PROOF", "every changed cell is in value_changes.csv; every other cell equals raw")
changes = pd.concat(CHANGES, ignore_index=True)
for t in TABLES:
    pk = PK[t]
    clean = T[t].set_index(pk)[RAW_COLS[t][1:] if RAW_COLS[t][0] == pk else
                               [c for c in RAW_COLS[t] if c != pk]]
    raw = RAW_T[t].set_index(pk).loc[clean.index, clean.columns]
    diff = clean.ne(raw)
    found = {(k, c) for c in diff.columns for k in diff.index[diff[c]]}
    logged = set(zip(changes.loc[changes.table == t, "key"], changes.loc[changes.table == t, "column"]))
    check(found == logged, f"{t:26} {len(found):>7,} changed cells = {len(logged):>7,} logged changes")

step("PROOF", "referential integrity on the clean tables (all 13 relationships)")
for ft, fc, dt_, dc, blank_ok in RELATIONSHIPS:
    f = T[ft][fc]
    nb = f[f != ""]
    if not blank_ok:
        check(len(nb) == len(f), f"{ft}.{fc}: no blank keys")
    else:
        cash = T[ft].txn_type.isin(["Deposit", "Withdrawal", "Advisory Fee"])
        check(((f == "") == cash).all(), f"{ft}.{fc}: blank exactly on cash rows")
    check(nb.isin(set(T[dt_][dc])).all(), f"{ft}.{fc} -> {dt_}.{dc}: 100% match ({len(nb):,} keys)")

# ================================================================ WRITE
CSV = {"index": False, "lineterminator": "\n"}        # LF endings, like the raw files
for t in TABLES:
    T[t].to_csv(CLEAN / f"{t}.csv", **CSV)
written = set()
for (t, name), q in QUARANTINE.items():
    fname = f"quarantine_{t}_{name}.csv"
    q.to_csv(AUDIT / fname, **CSV)
    written.add(fname)
pd.DataFrame(LOG).to_csv(AUDIT / "cleaning_log.csv", **CSV)
changes.to_csv(AUDIT / "value_changes.csv", **CSV)
stale = sorted(p.name for p in AUDIT.glob("quarantine_*.csv") if p.name not in written)
if stale:   # not deleted automatically: remove by hand after checking
    print(f"\nWARNING: old quarantine files not written by this run: {stale}")


# ---------------------------------------------------------------- README_clean.md
def flag_rows():
    return "\n".join(f"| `{t}` | `{c}` | {n:,} | {m} |" for (t, c), (n, m) in FLAGS.items())


def count_rows():
    out = []
    for t in TABLES:
        q = sum(len(df) for (tt, _), df in QUARANTINE.items() if tt == t)
        out.append(f"| `{t}` | {RAW_ROWS[t]:,} | {len(T[t]):,} | {q:,} |")
    return "\n".join(out)


readme = f"""# Wildcat Capital: clean tables

Produced by `scripts/02_clean.py` from `data/raw/`, following `decision_log.md`.
Raw files were not modified. Every change is in `data/audit/`.

## Row counts

| Table | Raw | Clean | Quarantined |
|---|---:|---:|---:|
{count_rows()}

Quarantined rows are in `data/audit/quarantine_*.csv`, each with a `quarantine_reason` and the ID of the row it duplicates.

## Relationships (star schema)

| From (many) | To (one) | Key |
|---|---|---|
| `fact_fees` | `dim_client` | `client_id` |
| `fact_fees` | `dim_advisor` | `advisor_id` |
| `fact_fees` | `dim_date` | `fee_date` -> `date` |
| `fact_portfolio_snapshot` | `dim_client` | `client_id` |
| `fact_portfolio_snapshot` | `dim_advisor` | `advisor_id` |
| `fact_portfolio_snapshot` | `dim_benchmark` | `benchmark_id` |
| `fact_portfolio_snapshot` | `dim_date` | `snapshot_date` -> `date` |
| `fact_transactions` | `dim_client` | `client_id` |
| `fact_transactions` | `dim_advisor` | `advisor_id` |
| `fact_transactions` | `dim_security` | `security_id` (blank on cash rows by design) |
| `fact_transactions` | `dim_date` | `txn_date` -> `date` |
| `dim_client` | `dim_advisor` | `advisor_id` (snowflake) |
| `dim_security` | `dim_benchmark` | `benchmark_id` (snowflake) |

Join facts to `dim_date` on the `date` column, not `date_id`: the fact tables store dates, not date IDs.

## Column-type settings a BI tool needs

| Set as | Columns | Why |
|---|---|---|
| **Text** | `dim_client.zip_code` | Leading zeros (`03897`) are lost if read as a number |
| **Text** | `primary_account_type`, `account_type` | `529` is an account type, not a number |
| **Text** | `dim_advisor.certifications` | `None` means "no certification", not null |
| **Whole number** | all `*_id` columns, `year`, `month`, `quarter`, `week_of_year`, `age`, `years_experience`, flag columns | |
| **Date** | `date`, `fee_date`, `snapshot_date`, `txn_date`, `client_since` | ISO `YYYY-MM-DD` |
| **Decimal** | `aum`, `aum_basis`, `amount`, `initial_aum`, `price`, `shares`, `bps_charged`, `expense_ratio_bps` | |
| **Decimal (fraction, not %)** | `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` | `0.0928` = 9.28%; format as % in the visual |
| **True/False** | `is_active`, `is_etf` | |
| **0/1** | `dim_date.is_*` flags and every flag column below | |

## Flag columns added (1 = suspicious, value kept)

| Table | Column | Rows = 1 | Meaning |
|---|---|---:|---|
{flag_rows()}

Filter on these flags in reports: for example, exclude `dividend_amount_suspect = 1` from any income figure.

## Blanks that are correct (not missing data)

- `dim_security.sector` is blank for every ETF; `expense_ratio_bps` is blank for every non-ETF.
- `fact_transactions.security_id`, `shares` and `price` are blank on Deposit, Withdrawal and Advisory Fee rows.

## Known limitations (chosen not to fix)

1. **Dividend amounts are not real dividends** (`dividend_amount_suspect`). No yield data exists to correct them, so do not report dividend income from this table.
2. **Returns are not flow-adjusted** (`return_suspect`). Large deposits show up as returns above 100%; `active_alpha_ytd` on those rows is inflated by the same amount. A true time-weighted return needs daily flows and valuations.
3. **AUM floor of $1,000** (`aum_floor_flag`). The true balance of depleted accounts is unknown.
4. **Trades on non-trading days** (`non_trading_day_trade`). Dates were not moved, since the correct settlement date is unknown.
5. **300 returns have 2-decimal precision** (converted from `%` strings), versus 6 decimals elsewhere.
6. **Positions cannot be rebuilt from transactions.** There are no opening holdings before 2020, and most Sells exceed the shares bought in the data.
7. **Advisory Fee transactions do not reconcile to `fact_fees`.** Use `fact_fees` as the source for fee revenue.
8. **Securities can share a name.** Use `ticker`, which is unique.
"""
(CLEAN / "README_clean.md").write_text(readme, encoding="utf-8")

print(f"\n{'=' * 78}\nDONE. Clean tables -> {CLEAN}\n      Audit trail  -> {AUDIT}")
print(f"      {len(LOG)} cleaning steps, {len(changes):,} value changes, "
      f"{sum(len(q) for q in QUARANTINE.values())} rows quarantined, {len(FLAGS)} flag columns")
