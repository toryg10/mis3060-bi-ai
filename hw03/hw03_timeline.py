"""
HW03 - Corporate Events Timeline

Joins the executive events (8-K Item 5.02) collected by hw03_executives.py
with the earnings filings (8-K Item 2.02) collected by hw03_earnings.py.

For every executive event, the script finds the earnings filing for the same
company whose filing_date is closest to the event's filing_date, then:

  * days_to_nearest_earnings - absolute number of days between the two
                               filing dates
  * event_timing             - 'same week'       if within 7 days (either side)
                               'before earnings' if the event was filed earlier
                               'after earnings'  if the event was filed later

The combined table (all columns from both source tables, plus the two new
columns) is saved to hw03/corporate_events_timeline.csv, and a per-company
summary plus overall before/after counts are printed to the console.

Inputs : hw03/earnings_history.csv, hw03/executive_events.csv
Output : hw03/corporate_events_timeline.csv
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HW_DIR = Path(__file__).resolve().parent
EARNINGS_CSV = HW_DIR / "earnings_history.csv"
EVENTS_CSV = HW_DIR / "executive_events.csv"
OUTPUT_CSV = HW_DIR / "corporate_events_timeline.csv"

SAME_WEEK_DAYS = 7            # "within 7 days" of an earnings filing
BEFORE = "before earnings"
AFTER = "after earnings"
SAME_WEEK = "same week"

# Columns that are specific to each source table (company/ticker/cik are shared)
EVENT_COLS = ["event_type", "person_name", "title", "effective_date"]
EARNINGS_COLS = ["period", "revenue_reported", "eps_diluted", "net_income"]


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_data():
    """Read both CSVs as text (keeps CIK leading zeros and 'NOT_FOUND' values)
    and parse only the filing_date columns as real dates."""
    earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
    events = pd.read_csv(EVENTS_CSV, dtype=str)

    earnings["filing_date"] = pd.to_datetime(earnings["filing_date"], errors="coerce")
    events["filing_date"] = pd.to_datetime(events["filing_date"], errors="coerce")

    bad_earn = earnings["filing_date"].isna().sum()
    bad_evt = events["filing_date"].isna().sum()
    if bad_earn:
        print(f"WARNING: dropping {bad_earn} earnings row(s) with an unreadable filing_date")
        earnings = earnings.dropna(subset=["filing_date"])
    if bad_evt:
        print(f"WARNING: {bad_evt} executive event(s) have an unreadable filing_date")

    return earnings, events


# ---------------------------------------------------------------------------
# Timing logic
# ---------------------------------------------------------------------------
def classify_timing(signed_days):
    """signed_days = event filing_date - earnings filing_date (negative = before)."""
    if abs(signed_days) <= SAME_WEEK_DAYS:
        return SAME_WEEK
    return BEFORE if signed_days < 0 else AFTER


def find_nearest_earnings(event_row, earnings):
    """Return (earnings_row, signed_days) for the closest earnings filing of
    the same company, or (None, None) if there is none. On an exact tie the
    earlier earnings filing is used so the result is deterministic."""
    company_earnings = earnings[earnings["ticker"] == event_row["ticker"]]
    if company_earnings.empty or pd.isna(event_row["filing_date"]):
        return None, None

    signed = (event_row["filing_date"] - company_earnings["filing_date"]).dt.days
    # Sort by distance, then by earnings date so ties resolve to the earlier filing
    order = (
        pd.DataFrame({"abs_days": signed.abs(), "date": company_earnings["filing_date"]})
        .sort_values(["abs_days", "date"])
    )
    best_idx = order.index[0]
    return company_earnings.loc[best_idx], int(signed.loc[best_idx])


def build_timeline(earnings, events):
    """Pair every executive event with its nearest earnings filing."""
    rows = []
    for _, evt in events.iterrows():
        nearest, signed_days = find_nearest_earnings(evt, earnings)

        row = {
            "company": evt["company"],
            "ticker": evt["ticker"],
            "cik": evt["cik"],
            "event_filing_date": evt["filing_date"].date() if pd.notna(evt["filing_date"]) else None,
        }
        for col in EVENT_COLS:
            row[col] = evt[col]

        if nearest is None:
            print(f"WARNING: no earnings filings found for {evt['ticker']} "
                  f"({evt['person_name']}) - timing left blank")
            row["earnings_filing_date"] = None
            for col in EARNINGS_COLS:
                row[col] = None
            row["days_to_nearest_earnings"] = None
            row["event_timing"] = None
        else:
            row["earnings_filing_date"] = nearest["filing_date"].date()
            for col in EARNINGS_COLS:
                row[col] = nearest[col]
            row["days_to_nearest_earnings"] = abs(signed_days)
            row["event_timing"] = classify_timing(signed_days)
            row["_signed_days"] = signed_days   # used only for the printed summary

        rows.append(row)

    timeline = pd.DataFrame(rows)
    timeline["days_to_nearest_earnings"] = timeline["days_to_nearest_earnings"].astype("Int64")
    return timeline.sort_values(["ticker", "event_filing_date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_company_summary(timeline, earnings):
    print("=" * 78)
    print("EXECUTIVE EVENTS RELATIVE TO THE NEAREST EARNINGS ANNOUNCEMENT")
    print("=" * 78)

    # Keep the company order used in the source data
    companies = earnings.drop_duplicates("ticker")[["ticker", "company"]]
    extra = timeline[~timeline["ticker"].isin(companies["ticker"])].drop_duplicates("ticker")
    companies = pd.concat([companies, extra[["ticker", "company"]]])

    for _, co in companies.iterrows():
        co_events = timeline[timeline["ticker"] == co["ticker"]]
        print(f"\n{co['company']} ({co['ticker']}) - {len(co_events)} event(s)")
        if co_events.empty:
            print("  No executive events in the events table.")
            continue
        for _, e in co_events.iterrows():
            if pd.isna(e["event_timing"]):
                print(f"  {e['event_filing_date']} | {e['event_type']:<11} | "
                      f"{e['person_name']} ({e['title']}) -> no earnings filing to compare")
                continue
            direction = "before" if e["_signed_days"] < 0 else "after"
            if e["_signed_days"] == 0:
                direction = "on the same day as"
            detail = (f"{e['days_to_nearest_earnings']} days {direction}"
                      if e["_signed_days"] != 0 else direction)
            print(f"  {e['event_filing_date']} | {e['event_type']:<11} | "
                  f"{e['person_name']} ({e['title']})")
            print(f"      -> {e['event_timing'].upper()}: {detail} the "
                  f"{e['earnings_filing_date']} earnings filing ({e['period']})")


def print_final_counts(timeline):
    counts = timeline["event_timing"].value_counts()
    n_before = int(counts.get(BEFORE, 0))
    n_after = int(counts.get(AFTER, 0))
    n_same = int(counts.get(SAME_WEEK, 0))
    n_none = int(timeline["event_timing"].isna().sum())

    print("\n" + "=" * 78)
    print(f"FINAL COUNT - all {timeline['ticker'].nunique()} companies, "
          f"{len(timeline)} executive events")
    print("=" * 78)
    print(f"  Before an earnings announcement : {n_before}")
    print(f"  After an earnings announcement  : {n_after}")
    print(f"  Same week (within {SAME_WEEK_DAYS} days)      : {n_same}")
    if n_same:
        same = timeline[timeline["event_timing"] == SAME_WEEK]
        sb = int((same["_signed_days"] < 0).sum())
        sa = int((same["_signed_days"] > 0).sum())
        s0 = int((same["_signed_days"] == 0).sum())
        print(f"      (of these: {sb} just before, {sa} just after, {s0} same day)")
    if n_none:
        print(f"  No earnings filing to compare   : {n_none}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    earnings, events = load_data()
    print(f"Loaded {len(earnings)} earnings filings and {len(events)} executive events.\n")

    timeline = build_timeline(earnings, events)

    output_cols = (
        ["company", "ticker", "cik", "event_filing_date"] + EVENT_COLS
        + ["earnings_filing_date"] + EARNINGS_COLS
        + ["days_to_nearest_earnings", "event_timing"]
    )
    timeline[output_cols].to_csv(OUTPUT_CSV, index=False)

    print_company_summary(timeline, earnings)
    print_final_counts(timeline)
    print(f"\nSaved {len(timeline)} rows to {OUTPUT_CSV.relative_to(HW_DIR.parent)}")


if __name__ == "__main__":
    main()
