# HW03 Validation

## 5A — Known-Answer Check: Earnings

Company/quarter checked: Apple, Q3 fiscal 2026 (quarter ended June 2026; 8-K filed 2026-07-30)
Official source: Apple Newsroom press release — (https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/)

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Apple Q3 FY2026 Revenue | $109.4 billion | 109.4 billion | Yes |
| Apple Q3 FY2026 EPS Diluted | $2.02 | 2.02 | Yes |

Both values matched, so no regex fix was needed for this check.


## 5B — Known-Answer Check: Executive Events

Event checked: Walmart (WMT), 8-K filed 2025-11-14 — John R. Furner
CSV row: both | John R. Furner | Director | effective 2026-02-01
Sources: Reuters (https://www.reuters.com/sustainability/boards-policy-regulation/walmart-ceo-doug-mcmillon-retire-names-insider-john-furner-new-ceo-2025-11-14/) and The New York Times (https://www.nytimes.com/2025/11/14/business/walmart-doug-mcmillon-john-furner.html)

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | Partially | Name is correct. News says Furner was named President and CEO of Walmart Inc.; the CSV only captured "Director" (his board seat), so the title extraction missed the main role. |
| Event type (departure/appointment) | Yes | "both" fits: he left his prior role leading Walmart U.S. and was appointed CEO. |
| Effective date | Yes | News confirms February 1, 2026, matching the CSV. |


## 5C — Cross-Validation: Earnings via Yahoo Finance

Company/quarter: Apple, Q3 fiscal 2026 (yfinance quarter ending 2026-06-30)
Code: hw03/yfinance_check.py (yfinance `quarterly_income_stmt`, most recent quarter)

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | 109.4 billion | $109.4 billion | Yes |
| Net Income | 29,789 million | $29.79 billion | Yes |

Both sources agree. The only difference is formatting: the 8-K extraction pulled net income from the financial statement table (in millions), while yfinance reports it in dollars, which rounds to the same $29.79 billion.


## 5D — Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 27 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes (27 rows) | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | Pass |