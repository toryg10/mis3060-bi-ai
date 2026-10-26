# HW4 Decision Log: Wildcat Capital

Written **before** any cleaning code, from the evidence in `reports/dq_summary_raw.csv` (473 checks: 9 ERROR, 10 WARN, 10 INFO) and `reports/profile_raw.csv`. Each entry is the instruction the cleaning script (`02_clean.py`) must follow. Entries 1–11 change data. Entries 12–22 are deliberately **left as is**, either because the "problem" is legitimate structure or because fixing it would mean inventing data.

**Planned order** (each step depends on the one before):
1. Quarantine rows that should not exist (D1, D2), so later steps don't repair rows that are being removed.
2. Fix formats so keys join (D3, D4).
3. Fix values that can be reconciled against other columns or tables (D5, D6, D7).
4. Add flag columns where a value is suspicious but cannot be corrected (D8–D11).

---

## Part 1: Changes to the data

### D1. Duplicate clients with truncated last names
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / whole row (`client_id` 2501–2525) |
| **Evidence** | 25 clients (50 rows in the near-duplicate check) are identical except `last_name`, which is cut short in the copy: `Taylo`/`Taylor` (2501 ↔ 674), `Marti`/`Martin` (2502 ↔ 1795), `Jacobso`/`Jacobson` (2503 ↔ 99). They match the original on first name, age, ZIP, initial AUM, client_since and advisor. Separately, the cross-table check found exactly these 25 clients have **no** fees, snapshots or transactions. |
| **Dimension violated** | Uniqueness |
| **Decision** | **Quarantine** the 25 copies to `data/audit/quarantine_dim_client_duplicates.csv`, with the ID of the original each one duplicates. |
| **Justification** | Each copy is the same person entered twice. Keeping them inflates the client count from 2,500 to 2,525 and would split any client-level KPI. Because no fact row points to a copy, removing them cannot orphan anything. |
| **Risk** | If any were a genuinely different person (for example, a family member with the same first name, age and ZIP), we would lose a real client. That risk is low: an identical initial AUM to the cent plus identical start dates is not plausible for two people. **Verify:** the script asserts that no fact row references a quarantined client. |

### D2. Transactions for clients that do not exist
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `client_id` |
| **Evidence** | 200 rows (`client_id` 2702–3192) have no match in `dim_client`. Each one is identical to an earlier real transaction except `client_id` (400 rows in the near-duplicate check = 200 pairs; in all 200 pairs the real row has the lower `txn_id`). |
| **Dimension violated** | Referential Integrity, Uniqueness |
| **Decision** | **Quarantine** the 200 rows to `data/audit/quarantine_fact_transactions_orphans.csv`, with the `txn_id` of the real twin. |
| **Justification** | They are copies of real transactions with a corrupted client ID. Keeping them would double-count $ volume, and a BI model would show them under a blank client. Reassigning them to the twin's client would create exact duplicates, so removal is correct. |
| **Risk** | If they were real activity for clients missing from `dim_client`, we would understate volume. Their exact match to existing rows makes that very unlikely. |

### D3. Security IDs stored as decimals
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `security_id` |
| **Evidence** | All 197,175 non-blank values are stored as `45.0` instead of `45`. Raw text matches `dim_security` **0%** of the time; after normalizing, **100%** match. |
| **Dimension violated** | Validity (type), Referential Integrity |
| **Decision** | **Convert** to integer text (`45.0` → `45`). |
| **Justification** | Pure formatting: the float came from an earlier export. Without the fix, every trade fails to join to its security in Power BI. |
| **Risk** | None if every value ends in `.0`. **Verify:** assert that no value has a non-zero decimal part before converting, and a 100% match to `dim_security` after. |

### D4. State names spelled out
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `state` |
| **Evidence** | 78 of 2,525 values are full names (Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2); all others are 2-letter codes. |
| **Dimension violated** | Consistency, Validity |
| **Decision** | **Standardize** to the 2-letter USPS code. |
| **Justification** | Mixed formats split a state into two groups in any chart (`PA` and `Pennsylvania`), so PA would be undercounted. |
| **Risk** | Very low; the mapping is unambiguous. **Verify:** every value is in the 50-state + DC list after the fix, and the per-state count equals code + full name before. |

### D5. Buy trades with negative shares
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `shares` |
| **Evidence** | 836 Buy rows have negative shares. All 197,175 trade rows satisfy `amount = |shares| × price`, so the magnitude is correct and only the sign is wrong. Direction is already carried by `txn_type`, and every Sell is positive. |
| **Dimension violated** | Validity (sign rule), Consistency |
| **Decision** | **Convert** to the absolute value. Log every change in `value_changes.csv`. |
| **Justification** | The sign convention in this table is "shares positive, `txn_type` gives direction". A negative Buy would subtract from positions and share totals. |
| **Risk** | If a negative sign actually meant "this was a Sell mislabeled as Buy", we would record the wrong direction. Nothing in the data supports that (the amount is positive in every case), so we treat it as a sign error. |

### D6. Returns stored as percent strings
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `return_ytd` |
| **Evidence** | 300 values are text like `9.28%` and do not parse as numbers. Converting `9.28%` → `0.0928` makes `return_ytd − benchmark_return_ytd = active_alpha_ytd` hold for **all 300** rows (to within 0.00005, the rounding of a 2-decimal percent). Without dividing by 100, **0 of 300** reconcile. |
| **Dimension violated** | Validity (type), Consistency (units) |
| **Decision** | **Convert**: strip `%` and divide by 100. |
| **Justification** | The rest of the column is stored as decimal fractions, and the alpha column independently confirms the correct scale. |
| **Risk** | The 2-decimal precision of the percent strings is lower than the other rows (6 decimals). That loss can't be recovered; it's noted as a limitation. |

### D7. Blank risk profiles
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `risk_profile` |
| **Evidence** | 76 blanks. One belongs to a duplicate client (quarantined in D1). The other 75 all have snapshots benchmarked to `benchmark_id` 3 (60/40 Blend), and among the 2,425 clients with a profile, benchmark 3 is used **only** by Balanced clients (757 of 757). |
| **Dimension violated** | Completeness |
| **Decision** | **Fill** with `Balanced`, and add the flag column `risk_profile_imputed` = 1 for those 75 rows. |
| **Justification** | Benchmark assignment follows the risk profile one-to-one for benchmark 3, so the profile is recovered from evidence, not guessed. The flag keeps the fill visible. (Benchmarks 1 and 8 are each shared by two profiles, so this method would **not** work for them; it happens not to be needed.) |
| **Risk** | If a Balanced benchmark were ever assigned to a non-Balanced client, the fill would be wrong. No such case exists in the 2,425 known clients. |

### D8. Dividends equal to the full position value
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `amount` (Dividend rows) |
| **Evidence** | All 53,864 Dividend rows have `amount = shares × price` exactly, i.e. the whole value of the position. The median dividend ($48.8K) is the same size as the median Buy ($47.9K) and is about 6% of the client's **total** AUM for the month; some exceed it. |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | **Flag**: add `dividend_amount_suspect` = 1. Do not change the amount. |
| **Justification** | Real dividends are a small yield on the position. The correct amount can't be derived because no yield or dividend rate exists anywhere in the data, so changing it would be inventing numbers. The flag lets the BI layer exclude these rows from income reporting. |
| **Risk** | Anyone summing income without filtering the flag overstates dividend income massively. That's stated in `README_clean.md` and the report. |

### D9. Returns above +100%
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `return_ytd`, `active_alpha_ytd` |
| **Evidence** | 976 rows (144 clients) have `return_ytd` > 1. They are **not** a units error: alpha reconciles exactly using the stored values. They coincide with large AUM jumps (client 29: AUM $9.1K → $52.1K in one month, return −32% → +287%), i.e. deposits being counted as investment return. |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | **Flag**: add `return_suspect` = 1. Keep the values. |
| **Justification** | The return isn't flow-adjusted. A true time-weighted return needs daily flows and valuations we don't have, so recomputing it would invent data. |
| **Risk** | Average-return and alpha KPIs are inflated if these rows are included. |

### D10. AUM sitting at exactly $1,000
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `aum`; `fact_fees` / `aum_basis` |
| **Evidence** | 420 snapshots (92 clients) and 386 fee rows have exactly 1000.0, the column minimum. Every other AUM value is near-unique. The returns on those rows run from −99.4% to 0%, consistent with a floor applied to depleted accounts. Fees still reconcile (`amount` = 1000 × bps / 10000 / 12). |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | **Flag**: add `aum_floor_flag` = 1 in both tables. Keep the values. |
| **Justification** | $1,000 looks like a system floor, not a real balance, but the true balance isn't recoverable. |
| **Risk** | Small effect on AUM totals. Larger effect on per-client returns and fees for those 92 clients. |

### D11. Trades dated on non-trading days
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `txn_date` (Buy and Sell) |
| **Evidence** | 40,649 of 143,311 Buy/Sell rows (28%) fall on days `dim_date` marks `is_trading_day` = 0. That matches the share of non-trading days in the calendar, so trade dates look like they were generated without regard to the market calendar. |
| **Dimension violated** | Accuracy / Plausibility, Consistency (with `dim_date`) |
| **Decision** | **Flag**: add `non_trading_day_trade` = 1. Do not move the dates. |
| **Justification** | Moving a trade to the "next trading day" would be an assumption about settlement we can't verify. |
| **Risk** | Daily trading-volume charts will show weekend activity. |

---

## Part 2: Reviewed and left as is

### L12. Sector blank for ETFs; expense ratio blank for individual securities
| Field | Entry |
|---|---|
| **Table / column** | `dim_security` / `sector` (219 blank), `expense_ratio_bps` (281 blank) |
| **Evidence** | Sector is blank for exactly the 219 ETFs and for no individual security. Expense ratio is blank for exactly the 281 non-ETFs and for no ETF. The contradiction checks pass in both directions. |
| **Dimension violated** | None. Legitimate structure. |
| **Decision** | **Leave as is.** |
| **Justification** | An ETF spans many sectors; an individual stock or bond has no expense ratio. Filling these would create false data. |
| **Risk** | A BI user might read blanks as missing. Documented in `README_clean.md`. |

### L13. Blank security, shares and price on cash transactions
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `security_id`, `shares`, `price` |
| **Evidence** | 101,597 blanks in each, and they are exactly the Deposit (35,981), Withdrawal (29,850) and Advisory Fee (35,766) rows. No trade row is missing them, and no cash row has them. |
| **Dimension violated** | None. Legitimate structure. |
| **Decision** | **Leave as is.** In the RI check, the null-key rate is reported separately from orphans. |
| **Justification** | Cash movements don't involve a security. |
| **Risk** | None, provided the RI function doesn't count blanks as orphans. |

### L14. `None` in advisor certifications
| Field | Entry |
|---|---|
| **Table / column** | `dim_advisor` / `certifications` |
| **Evidence** | 6 of 25 advisors have the text `None`. |
| **Dimension violated** | None. Legitimate value. |
| **Decision** | **Leave as is.** |
| **Justification** | It means "no certification", which is a real answer, not missing data. It must stay text: default `read_csv` would have turned it into NaN, which is exactly why the assignment reads everything as `dtype=str`. |
| **Risk** | A BI tool may treat `None` as null. Documented. |

### L15. ZIP codes with leading zeros
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `zip_code` |
| **Evidence** | All 2,525 values have 5 digits; some start with 0 (`03897`, `05601`). |
| **Dimension violated** | None. |
| **Decision** | **Leave as is.** Keep as text. |
| **Justification** | ZIP is an identifier, not a number. Converting to integer would drop the zero (`03897` → `3897`). |
| **Risk** | The BI tool must load it as Text. Documented in `README_clean.md`. |

### L16. Account type `529`
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `primary_account_type`; `fact_portfolio_snapshot` / `account_type` |
| **Evidence** | 523 clients and 26,882 snapshots have the account type `529`, which looks like a number among text values. |
| **Dimension violated** | None. |
| **Decision** | **Leave as is.** |
| **Justification** | A 529 is a real US education-savings account type. |
| **Risk** | None, if the column is typed as Text. |

### L17. Fee rate above 100 bps
| Field | Entry |
|---|---|
| **Table / column** | `fact_fees` / `bps_charged` |
| **Evidence** | 1 row of 122,197 (`fee_id` 68809) at 100.38 bps. Its amount reconciles with the formula. |
| **Dimension violated** | Accuracy / Plausibility (borderline) |
| **Decision** | **Leave as is.** |
| **Justification** | Only 0.38 bps over a soft business ceiling, and internally consistent. Not evidence of an error. |
| **Risk** | Negligible. |

### L18. Several cash flows on the same day
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `amount` |
| **Evidence** | 1,050 rows are identical except `amount` (Deposit 411, Advisory Fee 377, Withdrawal 262), e.g. client 1 deposited both $94,893.52 and $26,587.27 on 2024-09-25. |
| **Dimension violated** | None. |
| **Decision** | **Leave as is.** |
| **Justification** | Different amounts mean different transactions. Two deposits on one day is normal. |
| **Risk** | If some were double entries, we keep both, but nothing distinguishes them as errors. |

### L19. Coincidental repeats on different dates
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `txn_date` (14 rows); `fact_fees` / `fee_date` (2 rows) |
| **Evidence** | Same client, type and amount on different dates (for example, a $306.32 Advisory Fee in 2020 and again in 2022). The 2 fee rows are both $0.71 charged on the $1,000 floor (see D10). |
| **Dimension violated** | None. |
| **Decision** | **Leave as is.** |
| **Justification** | Recurring fees of the same size on different dates are expected. |
| **Risk** | Negligible. |

### L20. Sells larger than the running position
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `shares` |
| **Evidence** | 43,010 of 59,755 Sells would leave a negative position when Buys and Sells are added up in date order. |
| **Dimension violated** | Accuracy (cannot be confirmed) |
| **Decision** | **Leave as is.** Documented as a limitation. |
| **Justification** | The data has no opening positions (holdings before 2020), so a Sell can't be judged against what the client owned. Flagging 72% of Sells would make the flag meaningless. |
| **Risk** | Position-level analysis built from transactions alone will be wrong. Don't build holdings from this table. |

### L21. Securities with the same name
| Field | Entry |
|---|---|
| **Table / column** | `dim_security` / `name` |
| **Evidence** | 3 pairs share a name (`Jones Inc Fund`: 38 and 62). Their tickers, asset classes and benchmarks differ. |
| **Dimension violated** | None. |
| **Decision** | **Leave as is.** |
| **Justification** | Fund families issue several funds under one name. `ticker` is unique, so it's the identifier. |
| **Risk** | Charts by name would merge them; use ticker. |

### L22. Advisory Fee transactions vs. `fact_fees`
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` (Advisory Fee) vs. `fact_fees` |
| **Evidence** | They don't reconcile one to one. Client 1's July 2023 fee debit is $7,130.27, while `fact_fees` holds monthly charges of about $1,700. 33,469 of 35,766 fee debits fall in a month that has a `fact_fees` row; the rest don't. |
| **Dimension violated** | Consistency (unconfirmed) |
| **Decision** | **Leave as is.** Documented as a limitation. |
| **Justification** | The two tables measure different things (a cash debit vs. a calculated charge, possibly batched over several months). There's no key linking them, so a rule would be guesswork. |
| **Risk** | Fee revenue differs depending on which table is used. The report must state that `fact_fees` is the source for fee revenue. |
