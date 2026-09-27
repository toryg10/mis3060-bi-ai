"""
HW03 - Specification B: Executive Events Pipeline (SEC 8-K Item 5.02)

Collects executive departure and appointment events from SEC 8-K filings
(Item 5.02, "Departure of Directors or Certain Officers; Election of
Directors; Appointment of Certain Officers ...") filed in the past 12 months
for five companies. For every qualifying filing the full 8-K filing text is
downloaded, stripped of HTML, and searched for executive events. Each event
(one person departing and/or being appointed) becomes its own row in
hw03/executive_events.csv.

Uses requests for all HTTP calls and BeautifulSoup to strip HTML.
"""

import csv
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
USER_AGENT = "MIS3060 Villanova tgauth01@villanova.edu"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 0.2          # seconds between SEC requests (< 10 req/sec)
LOOKBACK_DAYS = 365          # "past 12 months"
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/"
OUTPUT_CSV = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]


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
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for tag in soup.find_all(CELL_TAGS):
        tag.insert_before(" ")
        tag.insert_after(" ")
    text = soup.get_text()
    text = text.replace("\xa0", " ").replace("​", "")
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ---------------------------------------------------------------------------
# Step 1: find 8-K filings with Item 5.02 filed in the past 12 months
# ---------------------------------------------------------------------------
def _matching_filings(block, cutoff):
    """Return 8-K / Item 5.02 filings on or after `cutoff` from one block of
    the submissions JSON (the 'recent' block or an older overflow file)."""
    out = []
    for i, form in enumerate(block.get("form", [])):
        items = block["items"][i] or ""
        filing_date = block["filingDate"][i]
        if (form == "8-K" and "5.02" in [s.strip() for s in items.split(",")]
                and filing_date >= cutoff):
            out.append({
                "accession": block["accessionNumber"][i],
                "filing_date": filing_date,
                "primary_doc": block["primaryDocument"][i],
            })
    return out


def get_executive_filings(cik, cutoff):
    """Return all Form 8-K filings whose items include 5.02 and whose
    filingDate is on or after `cutoff` (YYYY-MM-DD), newest first."""
    data = sec_get(SUBMISSIONS_URL.format(cik=cik)).json()
    recent = data["filings"]["recent"]
    results = _matching_filings(recent, cutoff)

    # 'recent' holds only the latest ~1,000 filings of ALL form types.
    # Frequent filers (e.g. JPM) can exceed that within 12 months, so also
    # read any older overflow files that still overlap the lookback window.
    oldest_recent = min(recent["filingDate"]) if recent["filingDate"] else ""
    if oldest_recent and oldest_recent >= cutoff:
        for extra in data["filings"].get("files", []):
            if extra.get("filingTo", "") >= cutoff:
                block = sec_get(SUBMISSIONS_FILE_URL.format(name=extra["name"])).json()
                results.extend(_matching_filings(block, cutoff))

    # De-duplicate and sort newest first.
    unique = {f["accession"]: f for f in results}
    return sorted(unique.values(), key=lambda f: f["filing_date"], reverse=True)


# ---------------------------------------------------------------------------
# Step 2: download the full 8-K filing text and strip HTML
# ---------------------------------------------------------------------------
def _archive_base(cik, accession):
    return ARCHIVE_BASE.format(cik_int=int(cik), acc_nodash=accession.replace("-", ""))


def download_filing_text(cik, filing):
    """Download the complete submission text file for a filing and return
    (form_8k_text, exhibit_99_text) as plain text. Falls back to the primary
    document if the complete submission file cannot be parsed."""
    accession = filing["accession"]
    base = _archive_base(cik, accession)
    raw = sec_get(base + f"{accession}.txt").text

    main_parts, exhibit_parts = [], []
    for doc in re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw, re.S | re.I):
        type_match = re.search(r"<TYPE>\s*([^\s<]+)", doc, re.I)
        text_match = re.search(r"<TEXT>(.*?)</TEXT>", doc, re.S | re.I)
        if not type_match or not text_match:
            continue
        doc_type = type_match.group(1).upper()
        body = text_match.group(1)
        if doc_type == "8-K":
            main_parts.append(html_to_text(body))
        elif doc_type.startswith("EX-99"):
            exhibit_parts.append(html_to_text(body))

    if not main_parts:  # fallback: primary 8-K document
        main_parts.append(html_to_text(sec_get(base + filing["primary_doc"]).text))
    return "\n".join(main_parts), "\n".join(exhibit_parts)


# ---------------------------------------------------------------------------
# Step 3: isolate the Item 5.02 section and split it into sentences
# ---------------------------------------------------------------------------
ITEM_HEADING = re.compile(r"(?im)^\s*item\s*(\d{1,2}\.\d{2})")
SECTION_END = re.compile(r"(?im)^\s*signatures?\b")
ITEM_502_TITLE = re.compile(
    r"^[\s.:\-]*(?:\([a-f]\)\s*)*departure of directors.*?(?:officers?|arrangements?[^.\n]*)\.?\s*$",
    re.I | re.M)


def extract_item_502(text):
    """Return the text of the Item 5.02 section (heading removed). If the
    heading cannot be found, returns the whole text before the signatures."""
    headings = list(ITEM_HEADING.finditer(text))
    best = ""
    for idx, h in enumerate(headings):
        if h.group(1) != "5.02":
            continue
        start = h.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        sig = SECTION_END.search(text, start, end)
        section = text[start: sig.start() if sig else end]
        if len(section) > len(best):
            best = section
    if not best:
        sig = SECTION_END.search(text)
        best = text[: sig.start()] if sig else text
    # Drop the long statutory item title line.
    best = ITEM_502_TITLE.sub("", best, count=1)
    return best.strip()


ABBREVIATIONS = {"mr", "ms", "mrs", "dr", "messrs", "jr", "sr", "inc", "corp",
                 "co", "no", "st", "vs", "u.s", "u.s.a", "n.a", "l.l.c", "ltd"}


def split_sentences(text):
    """Split text into sentences without breaking on 'Mr.', 'Inc.', initials."""
    sentences = []
    for line in text.split("\n"):
        start = 0
        for m in re.finditer(r"[.!?]\s+(?=[A-Z\"(])", line):
            before = line[start:m.start()]
            last_word = re.split(r"\s+", before.strip())[-1] if before.strip() else ""
            lw = last_word.lower().rstrip(".")
            if lw in ABBREVIATIONS or re.fullmatch(r"[A-Z]", last_word):
                continue  # abbreviation or middle initial, not a sentence end
            sentences.append(line[start:m.start() + 1].strip())
            start = m.end()
        tail = line[start:].strip()
        if tail:
            sentences.append(tail)
    return [s for s in sentences if s]


# ---------------------------------------------------------------------------
# Step 4: find people's names in a sentence
# ---------------------------------------------------------------------------
HONORIFICS = {"Mr.", "Ms.", "Mrs.", "Dr.", "Mr", "Ms", "Mrs", "Dr"}
NAME_SUFFIXES = {"Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV"}
CORPORATE_SUFFIXES = {"Inc", "Inc.", "Corp", "Corp.", "Corporation", "Company",
                      "Co", "Co.", "LLC", "LLP", "L.P.", "Ltd", "Ltd.", "Group",
                      "Holdings", "Bank", "Partners", "Capital", "University",
                      "&", "Foundation", "Fund", "Trust", "Associates"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
NON_NAME_WORDS = set(MONTHS) | {
    # document / legal vocabulary
    "Item", "Items", "Form", "Exhibit", "Exhibits", "Section", "Securities",
    "Exchange", "Commission", "Act", "Rule", "Regulation", "Report", "Proxy",
    "Statement", "Statements", "Signature", "Signatures", "Date", "Dated",
    "Name", "Title", "Description", "Cover", "Page", "Interactive", "Data",
    "File", "Press", "Release", "Forward", "Looking", "Certain", "Departure",
    "Departures", "Election", "Elections", "Appointment", "Appointments",
    "Arrangements", "Compensatory", "Results", "Condition", "Other", "Events",
    "Additional", "Information", "Retirement", "Resignation", "Agreement",
    "Letter", "Offer", "Plan", "Award", "Awards", "Stock", "Restricted",
    "Units", "Unit", "Performance", "Shares", "Share", "Cash", "Incentive",
    "Bonus", "Base", "Salary", "Annual", "Meeting", "Fiscal", "Year", "Quarter",
    "Equity", "Omnibus", "Long", "Term", "Deferred", "Severance", "Change",
    "Control", "Transition", "Consulting", "Employment", "Amended", "Restated",
    # governance / titles
    "Company", "Corporation", "Board", "Directors", "Director", "Committee",
    "Compensation", "Human", "Resources", "Talent", "Nominating", "Governance",
    "Audit", "Risk", "Chief", "Executive", "Officer", "Officers", "President",
    "Vice", "Senior", "Financial", "Operating", "Accounting", "Legal",
    "Technology", "Information", "People", "General", "Counsel", "Chair",
    "Chairman", "Chairwoman", "Chairperson", "Treasurer", "Secretary",
    "Controller", "Principal", "Corporate", "Group", "Global", "Interim",
    "Acting", "Lead", "Independent", "Head", "Deputy", "Assistant", "Managing",
    "Emeritus", "Advisor", "Adviser", "Member", "Members", "Operations",
    # sentence starters / function words
    "The", "This", "That", "These", "Those", "On", "In", "As", "At", "By",
    "For", "From", "Following", "Effective", "Upon", "Prior", "After",
    "Before", "During", "Pursuant", "Under", "With", "Messrs", "He", "She",
    "His", "Her", "They", "Their", "There", "It", "Its", "Our", "We", "If",
    "Each", "Such", "Any", "All", "No", "Not", "And", "Of", "To", "Also",
    "Accordingly", "Additionally", "Further", "Furthermore", "In addition",
    "Both", "Neither", "Mr", "Ms", "Mrs", "Dr", "A", "An",
    # companies, places, business units
    "Apple", "Microsoft", "NVIDIA", "Nvidia", "JPMorgan", "Chase", "Walmart",
    "Sam's", "Club", "Inc", "Corp", "LLC", "Ltd", "Bank", "Holdings", "Firm",
    "America", "American", "United", "States", "Americas", "International",
    "Cloud", "Services", "Retail", "Stores", "Store", "Marketing", "Sales",
    "Worldwide", "Strategy", "Commercial", "Consumer", "Investment", "Asset",
    "Wealth", "Management", "Markets", "Community", "Business", "Banking",
    "Division", "Segment", "Department", "New", "York", "Delaware",
    "Washington", "California", "Arkansas", "Cupertino", "Redmond", "Santa",
    "Clara", "Bentonville", "University", "School", "College", "Institute",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
}

# Words that mark a document or legal term ("Non-Competition Agreements",
# "Retention Award Letter"); any phrase containing one is never a name.
DOCUMENT_WORDS = {
    "Agreement", "Agreements", "Amendment", "Amendments", "Arrangement",
    "Arrangements", "Plan", "Plans", "Policy", "Policies", "Program",
    "Programs", "Letter", "Letters", "Award", "Awards", "Contract", "Contracts",
    "Covenant", "Covenants", "Waiver", "Release", "Guidelines", "Terms",
    "Schedule", "Addendum", "Memorandum", "Non", "Competition", "Solicitation",
    "Disparagement", "Confidentiality", "Indemnification", "Retention",
    "Separation", "Clawback", "Recoupment", "Notice",
}
NON_NAME_WORDS |= DOCUMENT_WORDS

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*\.?|&")


def _clean_token(tok):
    """Remove possessive endings: "Maestri's" -> "Maestri", "Combs'" -> "Combs"."""
    return re.sub(r"'s?$", "", tok)


def _is_initial(tok):
    return re.fullmatch(r"[A-Z]\.", tok) is not None


def _is_non_name(core):
    """True if a word (or any hyphenated part of it, or its singular form)
    is a known non-name word such as a title, month, or document term."""
    parts = [core] + core.split("-")
    return any(p in NON_NAME_WORDS or (p.endswith("s") and p[:-1] in NON_NAME_WORDS)
               for p in parts)


def _is_name_word(tok):
    core = _clean_token(tok).rstrip(".")
    return (len(core) >= 2 and core[0].isupper() and any(c.islower() for c in core)
            and not _is_non_name(core))


def find_names(sentence):
    """Return a list of name mentions in a sentence as dicts
    {text, start, end, honorific, surname_only}."""
    tokens = list(WORD_RE.finditer(sentence))
    mentions = []
    i = 0
    while i < len(tokens):
        honorific = False
        if tokens[i].group() in HONORIFICS:
            honorific = True
            i += 1
            if i >= len(tokens):
                break
        run = []
        j = i
        while j < len(tokens):
            tok = tokens[j].group()
            if run:
                gap = sentence[tokens[j - 1].end():tokens[j].start()]
                prev = tokens[j - 1].group()
                if tok in NAME_SUFFIXES and gap in (" ", ", "):
                    run.append(tokens[j])
                    j += 1
                    break
                # a comma, other punctuation, or a word ending in "." (other
                # than an initial) ends the name
                if gap != " " or (prev.endswith(".") and not _is_initial(prev)):
                    break
                if prev.endswith("'s") or prev.endswith("'"):
                    break  # possessive ends the name
            if _is_initial(tok) or _is_name_word(tok):
                run.append(tokens[j])
                j += 1
            else:
                break

        full_words = [t for t in run if not _is_initial(t.group())
                      and t.group() not in NAME_SUFFIXES]
        next_tok = tokens[j].group() if j < len(tokens) else ""
        next_core = _clean_token(next_tok).rstrip(".")
        followed_by_company = (next_tok in CORPORATE_SUFFIXES
                               or next_core in DOCUMENT_WORDS)
        if run and not followed_by_company:
            text = " ".join(_clean_token(t.group()) for t in run)
            text = re.sub(r"(?<![A-Z])\.$", "", text).strip()  # sentence period
            if 2 <= len(full_words) <= 4:
                mentions.append({"text": text, "start": run[0].start(),
                                 "end": run[-1].end(), "honorific": honorific,
                                 "surname_only": False})
            elif len(full_words) == 1 and len(run) == 1 and honorific:
                mentions.append({"text": text, "start": run[0].start(),
                                 "end": run[-1].end(), "honorific": True,
                                 "surname_only": True})
        i = j if j > i else i + 1
    return mentions


def _name_words(name):
    """Name words without initials or suffixes: "Todd A. Combs" -> ["Todd", "Combs"]."""
    return [w for w in name.split() if not _is_initial(w) and w not in NAME_SUFFIXES]


def _is_piece_of(short, long):
    """True if `short` is a shorter piece of `long`, e.g. "Nora Johnson" of
    "Suzanne Nora Johnson" or "Todd Combs" of "Todd A. Combs"."""
    if short == long:
        return False
    a, b = _name_words(short), _name_words(long)
    if not a or len(a) > len(b):
        return False
    contiguous = any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))
    return contiguous and (len(a) < len(b) or len(short.split()) < len(long.split()))


def _longest_containing(name, names):
    """Return the longest name in `names` that `name` is a piece of (or name)."""
    best = name
    for other in names:
        if _is_piece_of(best, other):
            best = other
    return best


def _surname(full_name):
    parts = [p for p in full_name.split() if p not in NAME_SUFFIXES]
    return parts[-1] if parts else full_name


# ---------------------------------------------------------------------------
# Step 5: classify departure / appointment language
# ---------------------------------------------------------------------------
DEPARTURE_RE = re.compile(
    r"\b(?:resign(?:s|ed|ing|ation)?"
    r"|retir(?:e|es|ed|ing|ement)(?!\s+(?:plans?|savings|benefits?|income|accounts?|programs?))"
    r"|step(?:s|ped|ping)? down"
    r"|depart(?:s|ed|ing|ure)"
    r"|leav(?:e|es|ing) (?:the|its|our) (?:Company|Corporation|Firm|Board)"
    r"|not (?:to )?(?:stand|seek|be nominated) for re-?election"
    r"|declined? to stand for re-?election"
    r"|terminat(?:e|ed|ion) (?:of )?(?:his|her|their)? ?(?:employment|service)"
    r"|separat(?:e|ed|ion) from"
    r"|cease(?:d|s)? to (?:serve|be)"
    r"|no longer (?:serve|serving|be)"
    r"|(?:be |been )?succeeded by|replaced by)\b",
    re.I)

APPOINTMENT_RE = re.compile(
    r"\b(?:appoint(?:s|ed|ing|ment)?"
    r"|(?<!re-)(?<!re)elect(?:s|ed|ion)?"
    r"|named"
    r"|promot(?:e|es|ed|ion)"
    r"|hired"
    r"|will (?:become|succeed|assume)"
    r"|to succeed|succeed(?:s|ing)?"
    r"|has been (?:selected|chosen)"
    r"|assum(?:e|es|ed|ing) the (?:role|position|title))\b",
    re.I)

# Phrases that contain an appointment word but are NOT an appointment.
APPOINTMENT_NOISE = [
    r"\belect(?:s|ed)? (?:not )?to (?=retire|resign|step|leave|stand|terminate|not)",
    r"until (?:his|her|their|a|the) successors? (?:is|are|has been|have been) "
    r"(?:duly )?(?:appointed|elected|named|chosen|qualified)[^.;]*",
    r"until the (?:appointment|election) of (?:his|her|their|a) successors?",
    r"(?:search|process) (?:for|to (?:identify|find)) (?:a|his|her|their) (?:new |permanent )?successors?",
    r"named executive officers?",
    r"election of directors",
]
# Past-tense biography sentences ("previously served as ...").
BIO_RE = re.compile(r"\b(?:previously|formerly|prior to joining|from \d{4} (?:to|until|through)"
                    r"|between \d{4} and \d{4})\b", re.I)


def classify(fragment, sentence):
    """Return a set of event categories ('departure', 'appointment') found in
    a text fragment. `sentence` is used to recognize biography sentences."""
    found = set()
    if DEPARTURE_RE.search(fragment):
        found.add("departure")
    cleaned = fragment
    for pattern in APPOINTMENT_NOISE:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    is_bio = BIO_RE.search(sentence) and "effective" not in sentence.lower()
    if APPOINTMENT_RE.search(cleaned) and not is_bio:
        found.add("appointment")
    return found


# ---------------------------------------------------------------------------
# Step 6: titles and effective dates
# ---------------------------------------------------------------------------
TITLE_START = (r"(?:Co-)?(?:Executive|Senior|Vice|Chief|President|General|Principal"
               r"|Corporate|Group|Global|Interim|Acting|Lead|Independent|Deputy"
               r"|Assistant|Managing|Chair(?:man|woman|person)?|Director|Treasurer"
               r"|Secretary|Controller|Head|CEO|CFO|COO|CTO|CAO|CIO|CLO|CHRO)")
TITLE_CONT = r"(?!(?:" + "|".join(MONTHS) + r"|Effective)\b)(?:[A-Z][A-Za-z&'\-]*|of|and|the|for|&)"
TITLE_RE = re.compile(rf"\b{TITLE_START}\b(?:(?:[ ]+|,[ ]+(?={TITLE_START}\b)){TITLE_CONT})*")
TITLE_KEY = re.compile(r"\b(?:Chief|President|Officer|Director|Chair\w*|Treasurer|Secretary"
                       r"|Controller|Counsel|Head|CEO|CFO|COO|CTO|CAO|CIO|CLO|CHRO)\b")
COMPANY_NAMES = r"(?:Apple|Microsoft|NVIDIA|Nvidia|JPMorgan|Walmart)"


def _clean_title(title):
    title = re.sub(rf"\s+of\s+(?:the\s+)?(?:Company|Corporation|Firm|{COMPANY_NAMES}\b.*)$",
                   "", title)
    while True:
        new = re.sub(r"(?:\s+(?:of|and|the|for|&)|,)\s*$", "", title)
        if new == title:
            break
        title = new
    return title.strip()


def find_titles(text):
    """Return [(start, end, title)] for job titles in text."""
    out = []
    for m in TITLE_RE.finditer(text):
        raw = m.group()
        if not TITLE_KEY.search(raw) or "Committee" in raw:
            continue
        title = _clean_title(raw)
        if title.startswith("Board") or title in ("Directors",):
            title = "Director"
        if TITLE_KEY.search(title):
            out.append((m.start(), m.start() + len(title), title))
    return out


BOARD_SEAT_RE = re.compile(
    r"\b(?:to|from|on|of) (?:the|its|our|\w+'s) Board(?: of Directors)?\b"
    r"|\bas an? (?:independent |non-employee )?(?:director|member of the Board)\b"
    r"|\bre-?election\b", re.I)
LOWERCASE_TITLE_RE = re.compile(r"\bprincipal (financial|accounting|executive|operating) officer\b", re.I)

DATE_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s+(\d{4})\b")
EFFECTIVE_DATE_RE = re.compile(r"\beffective\b[^;]{0,90}?" + DATE_RE.pattern, re.I)
IMMEDIATE_RE = re.compile(r"\beffective (?:immediately|as of the date hereof|upon (?:such|the) date)\b"
                          r"|\bwith immediate effect\b", re.I)


def _iso(month, day, year):
    try:
        return datetime.strptime(f"{month} {day} {year}", "%B %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return NOT_FOUND


def report_date(full_text, filing_date):
    """The 8-K cover's 'Date of Report (Date of earliest event reported)'."""
    m = re.search(r"Date of Report.{0,120}?" + DATE_RE.pattern, full_text, re.S | re.I)
    if not m:
        m = re.search(DATE_RE.pattern + r".{0,40}?\(?Date of (?:Report|earliest)",
                      full_text[:3000], re.S | re.I)
    if m:
        groups = [g for g in m.groups() if g]
        return _iso(*groups[-3:])
    return filing_date


def find_effective_date(sentences, event_date):
    """Pick the effective date from the sentences describing one person."""
    for s in sentences:                          # 1) "effective March 31, 2026"
        m = EFFECTIVE_DATE_RE.search(s)
        if m:
            return _iso(*m.groups()[-3:])
    for s in sentences:                          # 2) "effective immediately"
        if IMMEDIATE_RE.search(s):
            return event_date
    for s in sentences:                          # 3) any explicit date
        m = DATE_RE.search(s)
        if m:
            return _iso(*m.groups())
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Step 7: turn an Item 5.02 section into one event per person
# ---------------------------------------------------------------------------
def extract_events(section_text, event_date):
    """Return a list of dicts {event_type, person_name, title, effective_date}
    — one per person who departs and/or is appointed."""
    sentences = split_sentences(section_text)
    parsed = [(s, find_names(s)) for s in sentences]

    # Full names in the section, used to resolve "Mr. Maestri" -> "Luca Maestri".
    full_names = []
    for _, mentions in parsed:
        for m in mentions:
            if not m["surname_only"] and m["text"] not in full_names:
                full_names.append(m["text"])

    canonical = {name: _longest_containing(name, full_names) for name in full_names}
    full_names = [n for n in full_names if canonical[n] == n]

    def resolve(mention):
        if not mention["surname_only"]:
            return canonical.get(mention["text"], mention["text"])
        for name in full_names:
            if _surname(name) == mention["text"]:
                return name
        return mention["text"]

    people = {}          # name -> {"cats": set, "sents": [...], "titles": [...]}
    order = []
    last_person = None

    def person(name):
        if name not in people:
            people[name] = {"cats": set(), "sents": [], "event_sents": [],
                            "dep_titles": [], "app_titles": [], "any_titles": []}
            order.append(name)
        return people[name]

    for sentence, mentions in parsed:
        # Mask names so they are not read as part of a title.
        masked = list(sentence)
        for m in mentions:
            masked[m["start"]:m["end"]] = "#" * (m["end"] - m["start"])
        masked = "".join(masked)
        titles = find_titles(masked)

        if not mentions:
            # Pronoun sentence ("He will retire ..."): attribute to last person.
            cats = classify(sentence, sentence)
            if cats and last_person:
                p = person(last_person)
                p["cats"] |= cats
                p["sents"].append(sentence)
                p["event_sents"].append(sentence)
            elif last_person:
                person(last_person)["sents"].append(sentence)
            continue

        prev_cats = set()
        for k, m in enumerate(mentions):
            name = resolve(m)
            before_start = mentions[k - 1]["end"] if k > 0 else 0
            after_end = mentions[k + 1]["start"] if k + 1 < len(mentions) else len(sentence)
            before = sentence[before_start:m["start"]]
            after = sentence[m["end"]:after_end]

            if k == 0:
                cats = classify(before + " " + after, sentence)
            elif re.search(r"(?:succeeded|replaced) by\s*$", before, re.I):
                cats = {"appointment"} | classify(after, sentence)
            elif re.fullmatch(r"\s*(?:,\s*)?(?:and\s*)?", before):
                cats = prev_cats | classify(after, sentence)   # "A and B were appointed"
            else:
                cats = classify(after, sentence)
            # "B was named CFO" where the only verb is in the next gap is handled
            # above; if two people are listed, pass categories back to the first.
            prev_cats = cats

            p = person(name)
            p["sents"].append(sentence)
            if cats:
                p["cats"] |= cats
                p["event_sents"].append(sentence)
            last_person = name

            # Titles near this mention.
            lo, hi = before_start if k == 0 else m["start"], after_end
            nearby = [t for t in titles if t[0] >= lo and t[1] <= hi]
            as_titles = [t for t in nearby
                         if re.search(r"\bas (?:the |its |our |a |an |interim |acting )?"
                                      r"(?:(?:Company|Corporation|Firm|" + COMPANY_NAMES +
                                      r")'s )?$", masked[:t[0]])]
            appositive = [t for t in nearby
                          if re.fullmatch(r",\s*(?:the |our |its )?(?:(?:Company|Corporation|" +
                                          COMPANY_NAMES + r")'s )?",
                                          masked[m["end"]:t[0]])]
            preceding = [t for t in nearby if 0 <= m["start"] - t[1] <= 2]
            if "appointment" in cats:
                p["app_titles"] += [t[2] for t in as_titles]
            if "departure" in cats:
                p["dep_titles"] += [t[2] for t in appositive + preceding]
                p["dep_titles"] += [t[2] for t in as_titles if "appointment" not in cats]
            p["any_titles"] += [t[2] for t in as_titles + appositive + preceding + nearby]

            # Board seats described in lowercase ("elected to the Board").
            if cats and BOARD_SEAT_RE.search(before + after) and not nearby:
                key = "app_titles" if "appointment" in cats else "dep_titles"
                p[key].append("Director")
            lower = LOWERCASE_TITLE_RE.search(after)
            if cats and lower and not nearby:
                p["any_titles"].append(f"Principal {lower.group(1).title()} Officer")

        # If a later person in the sentence carried the verb (e.g.
        # "Jane Doe and John Smith were appointed ..."), share it backwards.
        for k in range(len(mentions) - 2, -1, -1):
            gap = sentence[mentions[k]["end"]:mentions[k + 1]["start"]]
            a, b = resolve(mentions[k]), resolve(mentions[k + 1])
            if (a != b and re.fullmatch(r"\s*(?:,\s*)?(?:and\s*)?", gap)
                    and not people[a]["cats"] and people[b]["cats"]):
                people[a]["cats"] |= people[b]["cats"]
                people[a]["event_sents"].append(sentence)

    events = []
    for name in order:
        p = people[name]
        if not p["cats"]:
            continue
        if p["cats"] == {"departure", "appointment"}:
            event_type = "both"
        else:
            event_type = next(iter(p["cats"]))

        def first(lst):
            return lst[0] if lst else None

        dep, app, anyt = first(p["dep_titles"]), first(p["app_titles"]), first(p["any_titles"])
        if event_type == "both" and dep and app and dep != app:
            title = f"{dep} -> {app}"
        elif event_type == "departure":
            title = dep or anyt or app
        elif event_type == "appointment":
            title = app or anyt or dep
        else:
            title = app or dep or anyt
        events.append({
            "event_type": event_type,
            "person_name": name,
            "title": title or NOT_FOUND,
            "effective_date": find_effective_date(p["event_sents"] + p["sents"], event_date),
        })
    return events


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_company(co, cutoff):
    rows = []
    ticker, cik = co["ticker"], co["cik"]
    try:
        filings = get_executive_filings(cik, cutoff)
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"WARNING: {ticker}: could not load submissions from SEC ({e}); skipping company.")
        return None   # None = SEC unreachable (different from "no events")

    if not filings:
        print(f"{ticker}: No executive events in past 12 months")
        return rows

    for f in filings:
        try:
            main_text, exhibit_text = download_filing_text(cik, f)
        except (requests.RequestException, ValueError, OSError) as e:
            print(f"WARNING: {ticker} {f['filing_date']} ({f['accession']}): "
                  f"could not download filing ({e}); skipping.")
            continue

        event_date = report_date(main_text, f["filing_date"])
        events = extract_events(extract_item_502(main_text), event_date)
        if not events and exhibit_text:
            # Some 8-Ks put the details in the attached press release.
            events = extract_events(exhibit_text, event_date)
        if not events:
            print(f"WARNING: {ticker} {f['filing_date']} ({f['accession']}): Item 5.02 "
                  f"filing with no departure/appointment identified "
                  f"(e.g. compensation-only); no rows added.")
            continue

        for ev in events:
            row = {"company": co["company"], "ticker": ticker, "cik": cik,
                   "filing_date": f["filing_date"], **ev}
            shown_date = (ev["effective_date"] if ev["effective_date"] != NOT_FOUND
                          else f["filing_date"])
            print(f"{ticker} | {shown_date} | {ev['event_type']} | "
                  f"{ev['person_name']} | {ev['title']}")
            rows.append(row)

    if not rows:
        print(f"{ticker}: No executive events in past 12 months")
    return rows


def main():
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    all_rows = []
    failed = 0
    for co in COMPANIES:
        rows = process_company(co, cutoff)
        if rows is None:
            failed += 1
        else:
            all_rows.extend(rows)

    if failed == len(COMPANIES):
        print(f"\nERROR: SEC could not be reached for any company; "
              f"{OUTPUT_CSV.name} was left unchanged.")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nSaved {len(all_rows)} executive events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
