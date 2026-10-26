# Wildcat Capital Data Cleaning Report
**To:** Portfolio Committee  **Re:** Data warehouse extract, 8 tables, 2020–2024

## Executive summary

We audited all eight tables in the data warehouse extract (555,401 rows) with 473 automated checks. They found 9 errors, 10 warnings and 10 items worth noting. We removed 225 rows that should not exist, corrected 198,331 values where other data proved the right answer, and marked 6 kinds of suspicious values with flag columns instead of guessing at a fix. The original files were not changed, and every change is logged.

**What this means for the committee:**

- **The data now joins correctly.** Before cleaning, 0% of trades linked to their security and 200 transactions belonged to clients who do not exist. After cleaning, all 13 table relationships match 100%.
- **Client counts are now right.** The client table held 25 duplicate clients. It now has 2,500 unique clients, not 2,525.
- **Do not report dividend income from this data.** Every one of the 53,826 dividend rows records the full value of the position instead of the dividend paid. Together they total **$3.45 billion**. They are flagged, but they cannot be corrected because the extract contains no dividend rates.
- **Treat returns above 100% with caution.** 977 monthly snapshots show year-to-date returns above +100% because large deposits were counted as investment gains.

## Cleaning summary

| Step | Problem | Action | Rows |
|---|---|---|---:|
| D1 | Duplicate clients (last name off by one letter, e.g. "Taylo" / "Taylor") | Quarantined | 25 |
| D2 | Transactions for client IDs that do not exist (copies of real trades) | Quarantined | 200 |
| D3 | Security IDs stored as `45.0` instead of `45`, so no trade linked to its security | Converted | 197,044 |
| D4 | States spelled out ("Pennsylvania" alongside "PA") | Standardized | 77 |
| D5 | Buy trades with negative shares | Sign corrected | 835 |
| D6 | Returns stored as text such as "9.28%" | Converted to 0.0928 | 300 |
| D7 | Blank client risk profiles | Filled ("Balanced") and flagged | 75 |
| D8 | Dividend equals the whole position value | Flagged | 53,826 |
| D9 | Year-to-date return above +100% | Flagged | 977 |
| D10 | Account value at exactly $1,000 (a system floor) | Flagged | 420 snapshots, 386 fees |
| D11 | Buys and Sells dated on non-trading days | Flagged | 40,630 |

**Data quality scorecard, before and after cleaning (%)**

| Table | Measure | Raw | Clean |
|---|---|---:|---:|
| `fact_transactions` | Referential match | 81.95 | 100.00 |
| `fact_transactions` | Type validity | 91.73 | 100.00 |
| `fact_transactions` | Key uniqueness | 99.93 | 100.00 |
| `fact_transactions` | Rule pass | 94.15 | 94.21 |
| `dim_client` | Completeness | 99.79 | 100.00 |
| `dim_client` | Key uniqueness | 99.01 | 100.00 |
| `dim_client` | Rule pass | 99.56 | 100.00 |
| `fact_portfolio_snapshot` | Type validity | 99.98 | 100.00 |
| `fact_portfolio_snapshot` | Rule pass | 99.90 | 99.90 |

The rule pass for transactions stays at about 94% on purpose. The flagged dividend and calendar problems still fail their checks after cleaning, because flagging a value is not the same as fixing it. The scorecard shows this instead of hiding it.

## Key judgment calls

**1. Filling 75 blank risk profiles with "Balanced."**
*Why:* We did not guess. Every one of these clients is measured against the 60/40 Blend benchmark, and among the 2,425 clients whose profile is on record, that benchmark is used only by Balanced clients (757 of 757). The filled rows carry a flag (`risk_profile_imputed`), so they can be told apart from profiles the client stated.
*Risk:* If a non-Balanced client were ever placed on the 60/40 benchmark, the fill would be wrong. No such case exists among the clients on record.

**2. Flagging the dividends rather than correcting them.**
*Why:* All 53,826 dividend amounts equal shares × price, the value of the entire holding. A real dividend is a small yield on that value. The data has no yield or dividend rate, so any "corrected" amount would be invented.
*Risk:* Anyone who adds up dividends without filtering out the flag (`dividend_amount_suspect`) will overstate income by about $3.45 billion.

**3. Removing 25 duplicate clients, and confirming which record was the copy.**
*Why:* Each pair matches on every field except the last name, including the starting balance to the cent. Our first rule assumed the copy always had the shorter name. The cleaning script's own checks stopped the run when two copies turned out to have an extra letter instead ("Pacen" / "Pace"). We changed the rule to mark as the copy the record with no activity; in all 25 pairs the original has fees, snapshots and trades.
*Risk:* If any pair were two different people, we would lose a real client. Identical balances to the cent make that very unlikely, and the removed rows are kept in a quarantine file.

**4. Converting "9.28%" to 0.0928, and proving the scale.**
*Why:* The rest of the column is stored as fractions. Dividing by 100 makes return − benchmark = alpha hold on all 300 rows. Not dividing makes it hold on none.
*Risk:* These 300 values have only 2 decimal places of precision, against 6 elsewhere.

## Limitations (known and not fixed)

1. **Dividend income is unusable** until the source system supplies actual dividend payments.
2. **Returns are not flow-adjusted.** Large deposits appear as returns above 100%, and the alpha on those rows is inflated by the same amount. A proper time-weighted return needs daily cash flows and valuations.
3. **Holdings cannot be rebuilt from transactions.** There are no opening positions before 2020, and most Sells exceed the shares bought within the data.
4. **About 28% of Buys and Sells fall on market holidays or weekends.** The dates were left as they are because the true trade dates are unknown.
5. **Fee debits in the transaction table do not match the fee table.** Use `fact_fees` as the source for fee revenue.
6. **92 accounts show a $1,000 floor value**, so their true balances are unknown.

---
*Sources: `data/audit/cleaning_log.csv`, `reports/data_quality_scorecard.csv`, `reports/dq_summary_raw.csv`, `decision_log.md`.*

AI-assisted report — reviewed for factual accuracy on 10/26/2026 by Tory Gauthier.
