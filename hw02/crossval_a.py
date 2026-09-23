# Cross-validation Prompt A: count Buy transactions by filtering directly
import pandas as pd

df = pd.read_csv("02_Data/Raw/fact_transactions.csv")

buy_count = (df["txn_type"] == "Buy").sum()
print(f"Prompt A - Buy count (direct filter): {buy_count:,}")