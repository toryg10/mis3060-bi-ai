# HW2 Validation

## 1C: Errors and Fixes

The script first failed with a "file not found" error because it looked for data/raw/fact_transactions.csv, but my data is stored in 02_Data/Raw. I used Claude Cowork to update the file path in the script and step 1 of my specification, and it then ran without errors.

## 2A: Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | Shape check in step 14 passed |
| Null count — `security_id` | 101,597 | 101,597 | Yes | Same count as `shares` and `price` nulls |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | Yes | pandas 3.0 labels text columns `str` instead of `object`; both mean the dates are stored as text, not a date type |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | Yes | One-cent rounding difference; the true median falls between the two values |
| Skewness of `amount` | 1.15 | 1.15 | Yes | Right-skewed |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | All 836 are Buy; min −499.63 |
| Profile file created | Yes | Yes | Yes | hw02/hw02_profile.txt |
| Chart files created (3) | Yes | Yes | Yes | hist_amount.png, box_amount_by_type.png, scatter_shares_amount.png |
## 2B: Explain the Code and Output

**1. Did Claude's predicted outputs (Prompt 1) match my actual terminal output?**

Mostly yes, but Claude gave very few exact values. It said it couldn't predict most numbers without seeing the data, even though the prompt asked it to list each expected value. What it did predict correctly: the shape (298772, 9) and the shape-check message, that `shares` and `price` would have missing values, a date range from early January 2020 to late December 2024, 0 duplicate `txn_id` values, mean greater than median with a right skew, shares–amount being one of the strongest correlations, NaN min/max for transaction types with no shares, and the chart descriptions and file paths.

Discrepancies:

- **Negative shares:** Claude predicted negative shares would be Sells recorded with a minus sign. In my output, Sell has 0 negative values and all 836 negatives are Buy transactions.
- **`txn_date` type:** Claude predicted `object`, but my output shows `str`. My venv uses pandas 3.0, which labels text columns `str`; it still means the dates are stored as text.
- **`security_id` type:** Claude implied the ID columns would be integers, but `security_id` is `float64` because it contains nulls, and pandas can't store missing values in an int64 column.
- **Nulls:** Claude only predicted nulls in `shares` and "probably" `price`. It did not predict that `security_id`, `shares`, and `price` would all have exactly 101,597 nulls.
- **Column names:** Claude miscounted the column names it could see in the code and didn't know the client, advisor, and security column names.

**2. What did Claude flag as unexpected or worth investigating (Prompt 2)?**

- **836 Buy transactions with negative shares:** the most important issue. Because `amount` is always positive (minimum $13.33), `amount` does not equal shares × price for these rows, which suggests a sign or data-entry error.
- **Dividend amounts look unrealistic:** Dividends average $64,077, higher than Buys, when a real dividend is usually a few percent of a position per year. They appear to be calculated like full trades.
- **Advisory Fees are very skewed:** the mean is $7,375 but the median is only $859, so a few very large fees should be checked for errors such as a misplaced decimal.
- **`amount` has no sign:** the direction of money comes from `txn_type`, so a signed amount or direction column is needed before calculating net flows.
- **Gaps in client IDs:** there are 2,700 unique clients but IDs go up to 3,192, so about 490 IDs never appear.
- **Last date is 2024-12-30, not 12-31:** December 2024 should be checked to make sure the data wasn't cut off.
- **Nulls are only probably structural:** it recommended confirming with a crosstab of missing `shares` by `txn_type`.

Claude's Prompt 2 answer also corrected its Prompt 1 guess: once it saw the real output, it said only Buys have negative shares and Sells are all positive. This shows why predicting the output before running the script is useful — the prediction was wrong, and comparing it to the real output caught that.

**3. Did Claude mention the 101,597 nulls in `security_id`? What explanation did it give?**

Yes. Claude pointed out that `security_id`, `shares`, and `price` each have 101,597 nulls, and that this equals the combined count of Deposits, Advisory Fees, and Withdrawals (35,981 + 35,766 + 29,850 = 101,597). These are cash transactions that don't involve a security, so the nulls are intentional (structural), not a data quality problem. It still recommended confirming this with a crosstab.

**4. Did Claude flag `txn_date` as a concern? Why does that matter for a time-series analysis?**

Yes. Claude said that `str` means the dates are still stored as text and should be converted with `pd.to_datetime` before doing any date work. This matters for time-series analysis because Python treats text dates as plain strings, not points in time. You can't subtract two strings to get the number of days between transactions, grouping by month or year requires pulling pieces out of the text, and sorting only works correctly by luck because the format is YYYY-MM-DD. Any trend or time-based calculation would either fail with an error or give wrong results until the column is converted to a real date type.

**5. Do my three charts match Claude's explanation? Any differences?**

- **Histogram (`hist_amount.png`):** Matches. It has 60 bins, a red dashed line at the mean ($54,075.17), and an orange line at the median ($41,220.49). The long tail to the right, with the median left of the mean, matches Claude's explanation of the 1.15 right skew. The tall bar near $0 is mostly the small Advisory Fees.
- **Box plot (`box_amount_by_type.png`):** Matches. There is one box per `txn_type` in the step 11 order. Buy, Sell, and Dividend look nearly identical, Deposit and Withdrawal stop around $100K, and the Advisory Fee box is squeezed near $0 with a long trail of outliers, matching the $859 median versus $7,375 mean. Claude warned a box could come out blank if `amount` had missing values, but `amount` has 0 nulls, so all six boxes appear.
- **Scatter (`scatter_shares_amount.png`):** Mostly matches. Only Buy, Sell, and Dividend appear, because the other types have no shares, as Claude said. The upward triangle shape shows amount rising with shares (0.65 correlation). One difference from Claude's Prompt 1 explanation: it expected negative shares to be Sells, but the points on the left side of the chart are orange, meaning Buys, and their amounts are still positive. Also, the Dividend points are hard to see because the Sell points are drawn on top of them.

**6. Paste one follow-up question you asked Claude, and Claude's answer.**

**Question:** Why would a Buy transaction have negative shares but still have a positive amount? What are the possible business explanations, and how would I figure out which one is correct?



**Claude's answer:**
It's almost certainly one of these three: a sign error, a reversal of an earlier Buy, or a Sell that was labeled as a Buy. The checks below tell you which.

*Possible explanations*

- **Sign-convention error (most likely).** Some systems record quantity from the cash side, where buying means cash goes out, so the shares are negative. `amount` is stored as a positive size. It's still a normal Buy; only the sign of `shares` is wrong.
- **Reversal or correction.** A mistaken Buy gets cancelled by posting the same trade again with negative shares. If that's the case, each one should match an earlier Buy for the same client and security, with the same number of shares, around the same date. Keeping both rows double-counts the trade.
- **Mislabeled Sell.** The shares really left the account, and the `txn_type` is wrong. This changes cash flow direction, holdings and every total by type.
- **Corporate action posted as a Buy** (a reverse split, spin-off or similar adjustment). This is less likely. The price would usually look odd, such as $0 or a round adjustment value.
- **Errors planted on purpose.** 836 ÷ 83,556 = 1.00% of Buys. A number that exact rarely happens naturally. It suggests the course dataset added these rows as a data-quality test, and your job is to catch and handle them.

*How to tell which one is right*

Run these one at a time. Each one rules explanations in or out.

```python
neg = df[(df["txn_type"] == "Buy") & (df["shares"] < 0)]

# A. Does amount equal |shares| x price?  If yes -> the sign flipped after amount was calculated (points to #1)
print((neg["amount"] - neg["shares"].abs() * neg["price"]).abs().describe())

# B. Do the sizes look like normal Buys, just mirrored?  (points to #1 or #5)
print(neg["shares"].abs().describe())
print(df.loc[(df["txn_type"] == "Buy") & (df["shares"] > 0), "shares"].describe())

# C. Is there a matching original Buy?  Many matches -> #2
pos = df[(df["txn_type"] == "Buy") & (df["shares"] > 0)].copy()
neg_key = neg.assign(abs_shares=neg["shares"].abs())
matches = neg_key.merge(pos, left_on=["client_id", "security_id", "abs_shares"],
                        right_on=["client_id", "security_id", "shares"], suffixes=("_neg", "_orig"))
print(f"Negative Buys with a matching positive Buy: {matches['txn_id_neg'].nunique()} of {len(neg)}")

# D. Are they concentrated anywhere?  Clustered -> one system or person; spread evenly -> random or planted (#5)
print(neg["advisor_id"].value_counts().head())
print(pd.to_datetime(neg["txn_date"]).dt.year.value_counts().sort_index())
```

For #3, check whether the client held that security before the date of the negative Buy, meaning they have an earlier positive Buy of it. A "sell" of shares they never owned can't be real.

*How to read the results*

| What you see | Most likely explanation | What to do |
|---|---|---|
| A ≈ 0, B matches normal Buys, C finds few matches, D is spread evenly | Sign error or planted errors | Use absolute shares and note the fix |
| C matches most of them | Reversals | Remove each reversal and its original Buy |
| Clients held the security beforehand | Mislabeled Sells | Change the type to Sell (confirm first) |
| A ≠ 0 | Something else is going on | Look at 10–20 rows by hand |

Whatever you find, check the spec or data dictionary first, and ask the instructor if it doesn't say. The data can show which explanation is most likely, but only the data owner can confirm it. In your write-up, give the count, the explanation you settled on and why, and what you did with the rows. Fix them in a cleaned copy, never in 02_Data/Raw.

## 2C: Business Check & Cross-Validation

### Business-Reasonableness Questions

**1. `security_id`, `shares`, and `price` are all null in exactly 101,597 rows. Which three transaction types would you expect to have no security, and why? Do the counts add up to 101,597?**

The three transaction types that should have no security are Deposit, Withdrawal, and Advisory Fee. These transactions only involve cash moving into or out of the account and do not involve buying, selling, or receiving income from a specific investment. Therefore, they would not need a `security_id`, `shares`, or `price`.

The counts for these three transaction types add up to 101,597 (Deposit 35,981 + Advisory Fee 35,766 + Withdrawal 29,850 = 101,597), which matches the number of rows with null values. This shows that the missing values are intentional and are not a data quality issue.

**2. There are 83,556 Buy transactions and 59,755 Sell transactions. What does it mean for a wealth management firm to have significantly more Buys than Sells over a five-year period?**

Having significantly more Buy transactions than Sell transactions suggests that clients were generally adding to their investments rather than selling them off over the five-year period. This could mean that the firm was experiencing growth, with clients investing new money or building their portfolios. Overall, the difference suggests more investment activity was focused on purchasing securities than liquidating them.

**3. The `txn_date` column is stored as a string rather than a date. If Claude Cowork generated code to compute the average number of days between transactions, what would go wrong if the dates remained as strings?**

If `txn_date` remained a string, Python would treat the dates as text instead of actual dates. This means it could not properly subtract one date from another to calculate the number of days between transactions. The column would first need to be converted to a date format before calculating the average number of days.

**4. Wildcat Capital has 2,700 clients served by 25 advisors. Is that ratio (roughly 108 clients per advisor) plausible for a registered investment advisory firm?**

Yes, 108 clients per advisor is a reasonable ratio for a registered investment advisory firm. Industry research shows that financial advisors manage about 173 clients on average, while other research estimates a typical range of about 65 to 277 clients per advisor. Wildcat Capital's 108 clients per advisor falls comfortably within this range. This suggests that the firm's client-to-advisor ratio is realistic and could allow advisors to provide more personal attention than firms with much larger client loads.

**Sources:**
- [SmartAsset – Average Number of Clients Per Financial Advisor](https://smartasset.com/advisor-resources/average-number-of-clients-per-financial-advisor) (~173 clients per advisor, based on 2026 IAA and FINRA data)
- [SmartAsset – How Many Clients Does a Financial Advisor Have?](https://smartasset.com/advisor-resources/how-many-clients-does-a-financial-advisor-have) (Kitces research: typical range of 65–277 clients)
- [Financial Planning – How Many Clients Should an RIA Have](https://www.financial-planning.com/news/how-many-clients-should-an-ria-have) (Ensemble Practice survey: ~164 clients per relationship manager)

**5. 836 `Buy` transactions have negative `shares` values (as low as −499.63), while every other transaction type has only positive share values. What are two plausible business explanations for a negative share count on a Buy transaction, and what would you do next to determine which explanation is more likely?**

One possible explanation is that the negative shares represent a correction or reversal of a previous Buy transaction that was entered incorrectly. Another possibility is that the negative values come from a data entry or system error, where a Buy was accidentally recorded with a negative number of shares.

To determine which explanation is more likely, I would look more closely at those 836 transactions and check for matching transactions involving the same client, security, number of shares, and similar dates. If matching positive transactions exist, that would support the correction or reversal explanation. If there is no clear pattern, I would investigate the source data or transaction records to see if the negative values were entered incorrectly.

### Cross-Validation: Count of Buy Transactions

**Prompt A:** "Write Python to count rows in fact_transactions.csv where txn_type equals exactly 'Buy'."

**Prompt B:** "Write Python to count the total rows in fact_transactions.csv, then subtract the count of rows where txn_type is Sell, Deposit, Withdrawal, Dividend, or Advisory Fee."

**6. What did each script return?**

- Prompt A (direct filter): 83,556
- Prompt B (subtraction): total rows 298,772 − non-Buy rows 215,216 = 83,556
- Known-answer benchmark: 83,556

**7. Do the results agree? If not, which one is wrong and why?**

Yes, both methods returned 83,556 Buy transactions, which also matches the known-answer benchmark. This confirms that both methods produced the same result.

**8. Why is it useful to verify a count using subtraction rather than direct filtering?**

Using subtraction is useful because it provides a second way to check that the direct count is correct. If there were unexpected values in `txn_type`, such as a typo like `"buy"` or a blank value, the two methods might give different answers. This would help identify a possible problem in the data.