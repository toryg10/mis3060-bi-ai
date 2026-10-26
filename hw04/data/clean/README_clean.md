# Wildcat Capital: clean tables

Produced by `scripts/02_clean.py` from `data/raw/`, following `decision_log.md`.
Raw files were not modified. Every change is in `data/audit/`.

## Row counts

| Table | Raw | Clean | Quarantined |
|---|---:|---:|---:|
| `dim_advisor` | 25 | 25 | 0 |
| `dim_benchmark` | 8 | 8 | 0 |
| `dim_client` | 2,525 | 2,500 | 25 |
| `dim_date` | 1,827 | 1,827 | 0 |
| `dim_security` | 500 | 500 | 0 |
| `fact_fees` | 122,197 | 122,197 | 0 |
| `fact_portfolio_snapshot` | 129,547 | 129,547 | 0 |
| `fact_transactions` | 298,772 | 298,572 | 200 |

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
| `dim_client` | `risk_profile_imputed` | 75 | risk_profile was blank and was filled from the client's snapshot benchmark |
| `fact_transactions` | `dividend_amount_suspect` | 53,826 | Dividend amount equals shares x price (the whole position); true dividend unknown |
| `fact_portfolio_snapshot` | `return_suspect` | 977 | return_ytd > 100%; deposits counted as return (not flow-adjusted) |
| `fact_portfolio_snapshot` | `aum_floor_flag` | 420 | aum is exactly 1000.0, a floor/placeholder |
| `fact_fees` | `aum_floor_flag` | 386 | aum_basis is exactly 1000.0, a floor/placeholder |
| `fact_transactions` | `non_trading_day_trade` | 40,630 | Buy/Sell dated on a day dim_date marks as non-trading |

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
