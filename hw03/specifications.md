# HW03 Specifications

## Specification A — Earnings Pipeline (Item 2.02)

Create a Python script named `hw03/hw03_earnings.py` that collects quarterly earnings information from SEC 8-K filings for the following five companies:

- Apple Inc. (AAPL), CIK: 0000320193
- Microsoft Corporation (MSFT), CIK: 0000789019
- NVIDIA Corporation (NVDA), CIK: 0001045810
- JPMorgan Chase & Co. (JPM), CIK: 0000019617
- Walmart Inc. (WMT), CIK: 0000104169

Set the SEC EDGAR User-Agent header to `"MIS3060 Villanova tgauth01@villanova.edu"` on every HTTP request made by the script.

For each company, query the SEC EDGAR submissions API using:

`https://data.sec.gov/submissions/CIK{cik}.json`

Filter the results to include only Form 8-K filings where the `items` field contains `"2.02"`, which represents Results of Operations and Financial Condition. From these results, select the four most recent qualifying filings for each company, representing approximately one filing per quarter.

For each selected filing, construct the SEC filing index URL and identify the `.htm` exhibit containing the company's earnings press release. Download the earnings press release and remove the HTML formatting so that the filing can be analyzed as plain text.

From the plain text, extract the following information:

- Reporting period, such as `"fourth quarter fiscal 2024"`
- Quarterly revenue, reported as a number in millions or billions
- Diluted earnings per share (EPS)
- Net income

Use pattern matching or regular expressions to identify these values in the text. If any individual field cannot be successfully extracted, store the string `"NOT_FOUND"` for that field rather than leaving the value blank or storing `None`.

As each filing is processed, print the extracted information in the following format:

`[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`

If an earnings press release exhibit cannot be identified or downloaded for a filing, the script should print a warning and continue processing the remaining filings rather than crashing.

Wait about 0.2 seconds between SEC requests to respect the SEC's rate limit of 10 requests per second and avoid being temporarily blocked.

After all five companies have been processed, save the results to:

`hw03/earnings_history.csv`

The CSV file must contain the following columns:

`company`, `ticker`, `cik`, `filing_date`, `period`, `revenue_reported`, `eps_diluted`, `net_income`

The script should process up to four earnings filings for each of the five companies, resulting in up to 20 rows in the final CSV.

---

## Specification B — Executive Events Pipeline (Item 5.02)

Create a Python script named `hw03/hw03_executives.py` that collects executive departure and appointment events from SEC 8-K filings for the following five companies:

- Apple Inc. (AAPL), CIK: 0000320193
- Microsoft Corporation (MSFT), CIK: 0000789019
- NVIDIA Corporation (NVDA), CIK: 0001045810
- JPMorgan Chase & Co. (JPM), CIK: 0000019617
- Walmart Inc. (WMT), CIK: 0000104169

Set the SEC EDGAR User-Agent header to `"MIS3060 Villanova tgauth01@villanova.edu"` on every HTTP request made by the script.

For each company, query the SEC EDGAR submissions API and filter the results to include only Form 8-K filings where the `items` field contains `"5.02"`, which relates to the departure or appointment of directors and officers. Only include qualifying filings with a `filingDate` within the past 12 months.

For every matching filing, download the full 8-K filing text and remove the HTML formatting so that the filing can be analyzed as plain text.

From the filing text, extract the following information for each executive event:

- Event type: `"departure"`, `"appointment"`, or `"both"`
- Person's full name
- Person's title
- Effective date of the change

If a single 8-K filing contains multiple executive events, such as one executive departing and another executive being appointed, create a separate row for each event rather than combining them into one row.

As each executive event is processed, print the information in the following format:

`[Ticker] | [Date] | [Event Type] | [Name] | [Title]`

If a company has no Item 5.02 filings within the past 12 months, do not treat this as an error. Instead, print:

`[Ticker]: No executive events in past 12 months`

The script should continue processing all remaining companies normally.

Wait about 0.2 seconds between SEC requests to respect the SEC's rate limit of 10 requests per second and avoid being temporarily blocked.

After all five companies have been processed, save the extracted executive events to:

`hw03/executive_events.csv`

The CSV file must contain the following columns:

`company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`

The script must handle companies with zero qualifying executive events without crashing and must create separate rows when a single filing contains multiple executive events.