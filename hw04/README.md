# HW4: Cleaning the Wildcat Capital Data

Audit, clean and validate the eight-table Wildcat Capital warehouse extract without inventing data, and prove each fix worked.

## Structure

```
hw04/
├── README.md                 this file
├── decision_log.md           Part B: 22 decisions, written before the cleaning code
├── scripts/
│   ├── 00_check.py           setup: confirms row/column counts of the 8 raw files
│   ├── 01_profile.py         Part A: generic profiler + 473 checks in 4 groups
│   ├── 02_clean.py           Part C: cleaning program (D1–D11), asserted step by step
│   └── 03_validate.py        Part D: RI function, rules, reconciliations, IQR, scorecard
├── data/
│   ├── raw/                  the 8 source CSVs (read-only; not pushed, see .gitignore)
│   ├── clean/                8 clean CSVs + README_clean.md
│   └── audit/                cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv               Part A: one row per column
    ├── dq_summary_raw.csv            Part A: every check, tagged ERROR / WARN / INFO / PASS
    ├── data_quality_scorecard.csv    Part D: one row per table per stage (raw / clean)
    ├── validation_details.csv        Part D: every RI, rule and reconciliation result
    ├── iqr_outliers.csv              Part D: IQR fences and counts
    ├── iqr_outlier_rows.csv          Part D: the flagged rows
    ├── ri_orphans.csv                Part D: every orphan key found
    └── cleaning_report.md            Part E: report for the portfolio committee
```

## How to run

Requires Python 3 and pandas (`pip install pandas`). Put the 8 Wildcat Capital CSVs in `data/raw/`, then run from the `hw04` folder, in order:

```
python scripts/00_check.py      # expect 8 x OK
python scripts/01_profile.py    # writes reports/profile_raw.csv, dq_summary_raw.csv
python scripts/02_clean.py      # writes data/clean/ and data/audit/; stops if any check fails
python scripts/03_validate.py   # writes the scorecard and validation reports
```

Every file is read as text (`dtype=str, keep_default_na=False`) and each column is converted on purpose. `02_clean.py` never writes to `data/raw/`.

## Results in one line each

- **Audit:** 473 checks found 9 ERROR, 10 WARN and 10 INFO findings.
- **Cleaning:** 225 rows quarantined (25 duplicate clients, 200 orphan transactions), 198,331 values corrected and logged, 6 flag columns added. Raw = clean + quarantined is proven for all 8 tables.
- **Validation:** all 13 relationships match 100% after cleaning (`fact_transactions` was 81.95% raw). The plausibility rules still fail on the flagged defects in the clean stage, by design.

## Process

Each script was drafted with Claude, run and debugged in VS Code, and reviewed by Claude Code before it was committed.

## What Claude Code flagged, and what I did

### Review 1: `01_profile.py` (Part A)

| Flagged | What I did |
|---|---|
| Crashes if an extra CSV is in `data/raw` (KeyError on the primary-key lookup) | Config-driven checks now run only for tables that are present; generic checks run on any table |
| Duplicate dimension keys would crash Group 4 (`set_index().map()`) | Added a `lookup()` helper that tolerates duplicates (they are reported by the key checks) |
| `.notna()` never sees blank cells, because blanks are `""` with `keep_default_na=False` | All comparisons now test for `""` explicitly |
| Denominators inconsistent: unparseable rows counted as passes in one check and failures in another | Each check now counts only rows it could actually evaluate |
| Whitespace issues double-counted; header-only, empty and BOM files crash | Each value counted once; guarded zero rows; `encoding="utf-8-sig"`; tested on all three edge cases |
| **The amount = shares × price check passed Dividends**, hiding that every dividend equals the whole position value | Limited the recompute to Buy/Sell and added a dividend plausibility check. **This exposed a real defect in all 53,864 dividends** (decision log D8) |
| Returns below −100% should be ERROR, above +100% only WARN | Split into two checks with a note about mixed % units |
| Missing checks: natural keys (`date`, `ticker`), `dim_date` flags and weekends, reverse ETF contradictions, `client_since` range, code lists for sector and benchmark asset class, Sells beyond holdings | Added all of them. Sells beyond holdings is INFO only: the data has no opening positions |
| Reconcile Advisory Fee transactions to `fact_fees`, compare `initial_aum` to the first snapshot | **Not done:** fee debits and monthly fee charges are on different bases with no linking key, so a one-to-one rule would be guesswork (decision log L22) |

### Review 2: `02_clean.py` (Part C)

| Flagged | What I did |
|---|---|
| D4 "per-state totals" compared the result with itself, so it could never fail | Before-counts now computed from the raw column (coded + spelled-out, counted separately) |
| D1 "no fact row references a copy" re-tested its own filter | Replaced with an independent check after removal: every fee and snapshot client still exists |
| Asserts disappear under `python -O` | `check()` now raises `RuntimeError`; confirmed it still runs under `-O` |
| No foreign-key check on the final tables | Added a proof that all 13 relationships match 100% on the clean output |
| Final proof checked counts, not contents | Added: clean and quarantined keys don't overlap and together equal the raw keys; added columns are exactly the 6 flags and hold only 0/1; **every changed cell is in `value_changes.csv` and every other cell equals raw** |
| D2 did not check "exactly one twin, with the lower `txn_id`" | Both now asserted |
| D7 relied on a generic mapping instead of the log's evidence | Asserts every blank client is on benchmark 3 and benchmark 3's 757 known clients are all Balanced |
| D6 alpha check ran before rounding | Re-checked on the written text |
| D8–D11 printed no before/after | Added before/after output to each; D8 now also asserts every dividend is flagged and amounts are unchanged |
| Old quarantine files not cleared; CRLF line endings on Windows | Script **warns** about stale quarantine files instead of deleting them; writes LF endings like the raw files |

Earlier, while testing `02_clean.py`, its own checks stopped the run three times. Each time the decision log was refined:
- 2 of the 25 duplicate clients had an *extra* letter, not a missing one ("Pacen"/"Pace"), so copies are now identified as the record with no activity.
- Later steps affect fewer rows once the 225 quarantined rows are gone (e.g. D3 197,044 rather than 197,175).
- A "1170.15%" return becomes a +1,170% return after D6, so D9 flags 977 rows rather than 976.

### Review 3: `03_validate.py` (Part D)

| Flagged | What I did |
|---|---|
| **The clean stage scored 100% on every metric even though D8–D11 defects remain** | Added plausibility rules for each flagged defect. They fail in both stages, so clean `fact_transactions` now shows 94.21% rule pass instead of a misleading 100% |
| R4 tested the D7 fill against the evidence that produced it | R4 now tests only profiles stated in the source, not imputed ones |
| Key uniqueness counted both members of a duplicate pair | Uses `keep="first"`, so only the repeat counts |
| `dim_advisor` business key was its primary key | Changed to first name + last name + region |
| Reconciliations mixed into rule pass | Separate `pct_reconciliation_pass` column; row weighting documented in the script header |
| Clean scored over more columns (the flags) than raw | Scorecard now uses only the original raw columns in both stages |
| Negative Buys counted twice (sign rule + amount rule) | Amount rule uses `|shares|` |
| IQR sentence hard-coded "all" and claimed a reconciliation found the dividend defect | Sentence built from this run's counts; the claim now refers to the D8 rule, which this script does run |
| IQR gave counts but no row flags; transaction types mixed in one distribution | Writes `iqr_outlier_rows.csv`; transaction fences are computed per `txn_type` |
| Missing bounds: `client_since`, `year`; `bps_charged` ceiling 200 vs 100 in the decision log | Added; ceiling set to 100 to match decision log L17 |
| RI function should report whether the dimension key is unique; orphan rows were discarded | Returns `dim_key_unique`; orphans saved to `ri_orphans.csv` |
