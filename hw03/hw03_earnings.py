"""
HW03 - Specification A: Earnings Pipeline (SEC 8-K Item 2.02)

Collects quarterly earnings information from SEC 8-K filings (Item 2.02,
"Results of Operations and Financial Condition") for five companies,
extracts reporting period, revenue, diluted EPS and net income from each
earnings press release exhibit, and saves the results to
hw03/earnings_history.csv.

Uses requests for all HTTP calls and BeautifulSoup to strip HTML.
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
USER_AGENT = "MIS3060 Villanova tgauth01@villanova.edu"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 0.2          # seconds between SEC requests (< 10 req/sec)
FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/"
OUTPUT_CSV = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "period",
               "revenue_reported", "eps_diluted", "net_income"]


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
def sec_get(url):
    """GET a URL from SEC with the required User-Agent, pausing first to
    respect the SEC rate limit. Returns the requests.Response object."""
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# HTML -> plain text
# ---------------------------------------------------------------------------
BLOCK_TAGS = ["p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4",
              "h5", "h6", "table", "section", "title"]
CELL_TAGS = ["td", "th"]
SKIP_TAGS = ["script", "style", "head", "ix:header"]


def html_to_text(html):
    """Strip HTML tags/formatting with BeautifulSoup and return normalized
    plain text (one line per paragraph / table row)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    # Keep paragraph / table-row boundaries as newlines and table cells apart.
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for tag in soup.find_all(CELL_TAGS):
        tag.insert_before(" ")
        tag.insert_after(" ")
    text = soup.get_text()
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = text.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ---------------------------------------------------------------------------
# Step 1: find qualifying 8-K Item 2.02 filings
# ---------------------------------------------------------------------------
def get_earnings_filings(cik, limit=FILINGS_PER_COMPANY):
    """Return the most recent Form 8-K filings whose items include 2.02."""
    data = sec_get(SUBMISSIONS_URL.format(cik=cik)).json()
    recent = data["filings"]["recent"]
    results = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i] or ""
        if form == "8-K" and "2.02" in items.split(","):
            results.append({
                "accession": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "primary_doc": recent["primaryDocument"][i],
            })
    # The submissions API lists filings newest first, but sort to be safe.
    results.sort(key=lambda f: f["filing_date"], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Step 2: locate the earnings press release exhibit in the filing index
# ---------------------------------------------------------------------------
def filing_index_url(cik, accession):
    base = ARCHIVE_BASE.format(cik_int=int(cik),
                               acc_nodash=accession.replace("-", ""))
    return base + f"{accession}-index.htm"


def find_press_release_url(cik, accession):
    """Parse the filing index page and return the URL of the .htm exhibit
    most likely to be the earnings press release (usually EX-99.1).
    Returns None if no suitable exhibit is found."""
    index_html = sec_get(filing_index_url(cik, accession)).text
    soup = BeautifulSoup(index_html, "html.parser")
    candidates = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        description = cells[1].get_text(" ", strip=True).lower()
        link = cells[2].find("a", href=True)
        doc_type = cells[3].get_text(" ", strip=True).upper()
        if link is None:
            continue
        href = link["href"].replace("/ix?doc=", "")
        if not href.lower().endswith((".htm", ".html")):
            continue
        filename = href.rsplit("/", 1)[-1].lower()

        score = 0
        if doc_type.startswith("EX-99"):
            score += 10
            if doc_type in ("EX-99.1", "EX-99.01", "EX-99"):
                score += 5
        elif re.search(r"ex[-_]?99", filename):
            score += 8
        else:
            continue  # not an exhibit 99 document
        if re.search(r"press release|earnings|results", description):
            score += 3
        candidates.append((score, "https://www.sec.gov" + href
                           if href.startswith("/") else href))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Step 3: extract fields with regular expressions
# ---------------------------------------------------------------------------
NUM = r"(\d[\d,]*(?:\.\d+)?)"
ORDINALS = {"1": "first", "2": "second", "3": "third", "4": "fourth"}


def _clean_num(s):
    return s.rstrip(".,")


def _full_year(yy):
    return yy if len(yy) == 4 else "20" + yy


# Sentences that describe guidance for a FUTURE quarter, e.g.
# "For the first quarter of fiscal 2027, NVIDIA expects revenue to be ..."
OUTLOOK_SENTENCE = re.compile(
    r"^\s*for the (?:first|second|third|fourth)[- ]quarter,? of fiscal\b"
    r"|\b(?:outlook|expects?|expected to|guidance|anticipates?|forecasts?|looking ahead)\b",
    re.I)
# Section headings that start the forward-looking part of a release.
OUTLOOK_HEADING = re.compile(
    r"^(?:business |financial |fiscal \d{4} |full[- ]year )?(?:outlook|guidance)\b.{0,40}$", re.I)

# Patterns that name a specific fiscal/calendar quarter, in priority order.
PERIOD_PATTERNS = [
    # "fourth quarter fiscal 2024", "second quarter of fiscal year 2025",
    # "Fourth Quarter and Fiscal 2026" (NVIDIA headline style)
    (r"\b(first|second|third|fourth)[- ]quarter,? (?:and |of )?fiscal (?:year )?(\d{4})\b",
     lambda m: f"{m.group(1).lower()} quarter fiscal {m.group(2)}"),
    # "fiscal 2025 fourth quarter"
    (r"\bfiscal (?:year )?(\d{4}),? (first|second|third|fourth)[- ]quarter\b",
     lambda m: f"{m.group(2).lower()} quarter fiscal {m.group(1)}"),
    # "Q2 FY26", "Q4 fiscal 2025"
    (r"\bQ([1-4]) (?:FY ?|fiscal (?:year )?)(\d{2,4})\b",
     lambda m: f"{ORDINALS[m.group(1)]} quarter fiscal {_full_year(m.group(2))}"),
    # "second-quarter 2025", "fourth quarter of 2024" (calendar year)
    (r"\b(first|second|third|fourth)[- ]quarter,? (?:of )?(\d{4})\b",
     lambda m: f"{m.group(1).lower()} quarter {m.group(2)}"),
    # "2Q25"
    (r"\b([1-4])Q(\d{2})\b",
     lambda m: f"{ORDINALS[m.group(1)]} quarter {_full_year(m.group(2))}"),
]
# Last resort: "quarter ended June 30, 2025"
QUARTER_ENDED = re.compile(r"\bquarter ended ([A-Z][a-z]+ \d{1,2}, \d{4})")


def _sentences(text):
    """Split plain text into sentences (one release line may hold several)."""
    out = []
    for line in text.split("\n"):
        out.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line) if s.strip())
    return out


def _drop_outlook(text):
    """Remove the Outlook section and any forward-looking guidance sentences."""
    kept_lines = []
    for line in text.split("\n"):
        if OUTLOOK_HEADING.match(line.strip()):
            break  # everything after an "Outlook" heading is guidance
        kept_lines.append(line)
    return "\n".join(
        " ".join(s for s in _sentences(line) if not OUTLOOK_SENTENCE.search(s))
        for line in kept_lines)


def _headline_region(text, max_lines=15, para_len=150):
    """The headline block plus the first full paragraph of the release."""
    lines = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        lines.append(line)
        if len(line) >= para_len or len(lines) >= max_lines:
            break
    return "\n".join(lines)


def extract_period(text):
    """Return the quarter the release reports on, preferring the headline and
    first paragraph and ignoring outlook sentences about future quarters."""
    reported = _drop_outlook(text)
    regions = (_headline_region(reported), reported[:5000], reported)
    for region in regions:
        for pattern, fmt in PERIOD_PATTERNS:
            m = re.search(pattern, region, re.I)
            if m:
                return fmt(m)
    for region in regions:
        m = QUARTER_ENDED.search(region)
        if m:
            return f"quarter ended {m.group(1)}"
    return NOT_FOUND


def extract_revenue(text):
    # Narrative form: "... revenue of $94.9 billion", "Revenue was $65.6 billion"
    narrative = [
        r"(?:quarterly|total|consolidated|record|reported|net) (?:net )?revenues?"
        r"(?: was| were| of| reached| totaled)?[^$\n]{0,80}?\$\s?" + NUM + r"\s*(billion|million)",
        r"\brevenues?(?: was| were| of| reached| totaled)?[^$\n]{0,80}?\$\s?" + NUM + r"\s*(billion|million)",
        r"\b(?:total )?net sales(?: was| were| of)?[^$\n]{0,60}?\$\s?" + NUM + r"\s*(billion|million)",
    ]
    for pattern in narrative:
        m = re.search(pattern, text, re.I)
        if m:
            return f"{_clean_num(m.group(1))} {m.group(2).lower()}"
    # Financial statement table (amounts in millions): "Total net sales $ 94,930"
    m = re.search(r"\btotal (?:net )?(?:revenues?|sales)\s*\$?\s*(\d[\d,]{2,})\b", text, re.I)
    if m:
        return f"{m.group(1)} million"
    return NOT_FOUND


def extract_eps(text):
    patterns = [
        r"(?<!non-)(?<!non-GAAP )diluted earnings per (?:common )?share[^$\n]{0,60}?\$\s?(\d+\.\d{2})",
        r"(?<!non-)(?<!non-GAAP )earnings per diluted (?:common )?share[^$\n]{0,60}?\$\s?(\d+\.\d{2})",
        r"(?<!non-)\bGAAP (?:diluted )?EPS[^$\n]{0,40}?\$\s?(\d+\.\d{2})",
        r"\bdiluted EPS[^$\n]{0,40}?\$\s?(\d+\.\d{2})",
        # JPM style: "net income of $14.2 billion, or $5.07 per share"
        r"net income of \$\s?[\d.,]+ (?:billion|million),? or \$\s?(\d+\.\d{2}) per (?:diluted )?share",
        r"\$\s?(\d+\.\d{2}) per diluted share",
        # Table row: "Diluted $ 1.64 $ 1.46"
        r"\bdiluted\s*\$\s*(\d+\.\d{2})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1)
    return NOT_FOUND


def extract_net_income(text):
    narrative = [
        r"\bnet income(?: attributable to [A-Za-z.,& ]{1,40}?)?"
        r"(?: was| were| of| totaled| reached)[^$\n]{0,40}?\$\s?" + NUM + r"\s*(billion|million)",
        r"\bnet income[^$\n]{0,60}?\$\s?" + NUM + r"\s*(billion|million)",
    ]
    for pattern in narrative:
        m = re.search(pattern, text, re.I)
        if m:
            return f"{_clean_num(m.group(1))} {m.group(2).lower()}"
    # Financial statement table (amounts in millions): "Net income $ 14,736"
    table = [
        r"\bnet income attributable to [A-Za-z.,& ]{1,40}?\s*\$\s*(\d[\d,]{2,})\b",
        r"\bnet income\s*\$\s*(\d[\d,]{2,})\b",
    ]
    for pattern in table:
        m = re.search(pattern, text, re.I)
        if m:
            return f"{m.group(1)} million"
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def _fmt(value):
    return value if value == NOT_FOUND else f"${value}"


def process_company(co):
    rows = []
    ticker, cik = co["ticker"], co["cik"]
    try:
        filings = get_earnings_filings(cik)
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"WARNING: {ticker}: could not load submissions from SEC ({e}); skipping company.")
        return rows

    if not filings:
        print(f"WARNING: {ticker}: no 8-K Item 2.02 filings found.")
        return rows

    for f in filings:
        row = {
            "company": co["company"], "ticker": ticker, "cik": cik,
            "filing_date": f["filing_date"], "period": NOT_FOUND,
            "revenue_reported": NOT_FOUND, "eps_diluted": NOT_FOUND,
            "net_income": NOT_FOUND,
        }
        try:
            url = find_press_release_url(cik, f["accession"])
            if url is None:
                print(f"WARNING: {ticker} {f['filing_date']} ({f['accession']}): "
                      f"no earnings press release exhibit found; skipping.")
                rows.append(row)
                continue
            text = html_to_text(sec_get(url).text)
        except (requests.RequestException, ValueError, OSError) as e:
            print(f"WARNING: {ticker} {f['filing_date']} ({f['accession']}): "
                  f"could not download press release ({e}); skipping.")
            rows.append(row)
            continue

        row["period"] = extract_period(text)
        row["revenue_reported"] = extract_revenue(text)
        row["eps_diluted"] = extract_eps(text)
        row["net_income"] = extract_net_income(text)

        print(f"{ticker} | {row['period']} | Revenue: {_fmt(row['revenue_reported'])} | "
              f"EPS: {_fmt(row['eps_diluted'])} | Net Income: {_fmt(row['net_income'])}")
        rows.append(row)
    return rows


def main():
    all_rows = []
    for co in COMPANIES:
        all_rows.extend(process_company(co))

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nSaved {len(all_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
