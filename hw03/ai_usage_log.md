# HW03 AI Usage Log

## Prompt 1 — Specification A (earnings pipeline)

Sent in a new Claude Cowork session. This is the full text of Specification A from `specifications.md`, with one line added at the end.

> ## Specification A — Earnings Pipeline (Item 2.02)
>
> Create a Python script named `hw03/hw03_earnings.py` that collects quarterly earnings information from SEC 8-K filings for the following five companies:
>
> - Apple Inc. (AAPL), CIK: 0000320193
> - Microsoft Corporation (MSFT), CIK: 0000789019
> - NVIDIA Corporation (NVDA), CIK: 0001045810
> - JPMorgan Chase & Co. (JPM), CIK: 0000019617
> - Walmart Inc. (WMT), CIK: 0000104169
>
> Set the SEC EDGAR User-Agent header to `"MIS3060 Villanova tgauth01@villanova.edu"` on every HTTP request made by the script.
>
> For each company, query the SEC EDGAR submissions API using:
>
> `https://data.sec.gov/submissions/CIK{cik}.json`
>
> Filter the results to include only Form 8-K filings where the `items` field contains `"2.02"`, which represents Results of Operations and Financial Condition. From these results, select the four most recent qualifying filings for each company, representing approximately one filing per quarter.
>
> For each selected filing, construct the SEC filing index URL and identify the `.htm` exhibit containing the company's earnings press release. Download the earnings press release and remove the HTML formatting so that the filing can be analyzed as plain text.
>
> From the plain text, extract the following information:
>
> - Reporting period, such as `"fourth quarter fiscal 2024"`
> - Quarterly revenue, reported as a number in millions or billions
> - Diluted earnings per share (EPS)
> - Net income
>
> Use pattern matching or regular expressions to identify these values in the text. If any individual field cannot be successfully extracted, store the string `"NOT_FOUND"` for that field rather than leaving the value blank or storing `None`.
>
> As each filing is processed, print the extracted information in the following format:
>
> `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
>
> If an earnings press release exhibit cannot be identified or downloaded for a filing, the script should print a warning and continue processing the remaining filings rather than crashing.
>
> Wait about 0.2 seconds between SEC requests to respect the SEC's rate limit of 10 requests per second and avoid being temporarily blocked.
>
> After all five companies have been processed, save the results to:
>
> `hw03/earnings_history.csv`
>
> The CSV file must contain the following columns:
>
> `company`, `ticker`, `cik`, `filing_date`, `period`, `revenue_reported`, `eps_diluted`, `net_income`
>
> The script should process up to four earnings filings for each of the five companies, resulting in up to 20 rows in the final CSV.
>
> Save the script to hw03/hw03_earnings.py in my connected folder, but don't run it yet.

**Follow-up prompts in the same session:**

1. The first version used Python's built-in `urllib` and `html.parser` instead of the required packages. I asked:
   > Rewrite hw03/hw03_earnings.py to use the requests library for all HTTP calls (with the User-Agent header on every requests.get() call) and BeautifulSoup to strip HTML, since my assignment requires those two packages. Keep everything else the same, and don't run it yet.
2. After the first run, NVIDIA's 2026-02-25 filing was labeled "first quarter fiscal 2027" instead of "fourth quarter fiscal 2026". I asked:
   > In hw03/earnings_history.csv, NVIDIA's 2026-02-25 filing was labeled "first quarter fiscal 2027" but it should be "fourth quarter fiscal 2026". The period regex is probably matching the outlook section instead of the headline. Fix extract_period so it prefers the period in the press release headline/first paragraph and ignores outlook sentences like "For the first quarter of fiscal 2027". Then rerun python hw03/hw03_earnings.py.

## Prompt 2 — Specification B (executive events pipeline)

Sent in a new Claude Cowork session. This is the full text of Specification B from `specifications.md`, with two lines added at the end.

> ## Specification B — Executive Events Pipeline (Item 5.02)
>
> Create a Python script named `hw03/hw03_executives.py` that collects executive departure and appointment events from SEC 8-K filings for the following five companies:
>
> - Apple Inc. (AAPL), CIK: 0000320193
> - Microsoft Corporation (MSFT), CIK: 0000789019
> - NVIDIA Corporation (NVDA), CIK: 0001045810
> - JPMorgan Chase & Co. (JPM), CIK: 0000019617
> - Walmart Inc. (WMT), CIK: 0000104169
>
> Set the SEC EDGAR User-Agent header to `"MIS3060 Villanova tgauth01@villanova.edu"` on every HTTP request made by the script.
>
> For each company, query the SEC EDGAR submissions API and filter the results to include only Form 8-K filings where the `items` field contains `"5.02"`, which relates to the departure or appointment of directors and officers. Only include qualifying filings with a `filingDate` within the past 12 months.
>
> For every matching filing, download the full 8-K filing text and remove the HTML formatting so that the filing can be analyzed as plain text.
>
> From the filing text, extract the following information for each executive event:
>
> - Event type: `"departure"`, `"appointment"`, or `"both"`
> - Person's full name
> - Person's title
> - Effective date of the change
>
> If a single 8-K filing contains multiple executive events, such as one executive departing and another executive being appointed, create a separate row for each event rather than combining them into one row.
>
> As each executive event is processed, print the information in the following format:
>
> `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
>
> If a company has no Item 5.02 filings within the past 12 months, do not treat this as an error. Instead, print:
>
> `[Ticker]: No executive events in past 12 months`
>
> The script should continue processing all remaining companies normally.
>
> Wait about 0.2 seconds between SEC requests to respect the SEC's rate limit of 10 requests per second and avoid being temporarily blocked.
>
> After all five companies have been processed, save the extracted executive events to:
>
> `hw03/executive_events.csv`
>
> The CSV file must contain the following columns:
>
> `company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`
>
> The script must handle companies with zero qualifying executive events without crashing and must create separate rows when a single filing contains multiple executive events.
>
> Use the requests library for all HTTP calls and BeautifulSoup to strip HTML.
>
> Save the script to hw03/hw03_executives.py in my connected folder, but don't run it yet.

**Follow-up prompt in the same session:**

The first run produced 30 rows, 3 of which were bad. I asked:
> The executive_events.csv has 3 bad rows:
> 1. JPM "Combs'" — a possessive of Todd A. Combs, a duplicate
> 2. WMT "Non-Competition Agreements" — not a person's name
> 3. NVDA "Nora Johnson" — duplicate of "Suzanne Nora Johnson"
> Fix the name extraction so possessives like "Combs'" are resolved to the full name, phrases containing words like Agreement/Agreements are never treated as names, and a name that is a shorter piece of another full name in the same filing is merged into it. Then rerun python hw03/hw03_executives.py.

After the fix: 27 rows, all real people.

## Prompt 3 — Timeline

Sent in a new Claude Cowork session. This is the prompt from the assignment, with one line added at the end.

> Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.
> 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies.
>
> Save it as hw03/hw03_timeline.py in my connected folder.

No follow-ups were needed. The script ran on the first try and produced 27 rows.

## Which companies' extractions required iteration

- **NVDA (earnings):** the period regex matched the outlook sentence instead of the headline, so the Q4 FY2026 release was labeled Q1 FY2027. This was fixed with a follow-up prompt. Revenue, EPS and net income were extracted correctly for all 20 rows on the first run, with no `NOT_FOUND` values.
- **JPM, WMT, NVDA (executives):** the name extraction produced a possessive duplicate ("Combs'"), a non-person ("Non-Competition Agreements") and a partial-name duplicate ("Nora Johnson"). All three were fixed with one follow-up prompt.
- **Known remaining issue:** some titles are incomplete. For example, John R. Furner is listed as "Director", but he was named President and CEO (see validation 5B). Two effective dates are `NOT_FOUND`.

## Something the script did that I didn't specify

The first version of the earnings script used Python's built-in libraries (urllib and html.parser) instead of requests and BeautifulSoup, which I hadn't thought to specify. That wasn't what the assignment required, so I asked Claude to rewrite it using those packages, and it worked after the change.
