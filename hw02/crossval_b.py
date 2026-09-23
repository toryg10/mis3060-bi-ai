# Cross-validation Prompt B: count Buy transactions by subtraction
import pandas as pd

df = pd.read_csv("02_Data/Raw/fact_transactions.csv")

total_rows = len(df)
other_types = ["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]
other_count = df["txn_type"].isin(other_types).sum()
buy_count = total_rows - other_count

print(f"Total rows:             {total_rows:,}")
print(f"Non-Buy rows:           {other_count:,}")
print(f"Prompt B - Buy count (subtraction): {buy_count:,}")