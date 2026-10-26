import pandas as pd
from pathlib import Path

RAW = Path(__file__).parent.parent / "data" / "raw"
expected = {
    "dim_advisor.csv": (25, 7), "dim_client.csv": (2525, 14),
    "dim_date.csv": (1827, 12), "dim_security.csv": (500, 8),
    "dim_benchmark.csv": (8, 4), "fact_fees.csv": (122197, 8),
    "fact_portfolio_snapshot.csv": (129547, 13),
    "fact_transactions.csv": (298772, 9),
}
for name, shape in expected.items():
    df = pd.read_csv(RAW / name, dtype=str, keep_default_na=False)
    status = "OK" if df.shape == shape else "MISMATCH"
    print(f"{status:8} {name:32} got {df.shape}, expected {shape}")