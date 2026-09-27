import yfinance as yf

aapl = yf.Ticker("AAPL")
income = aapl.quarterly_income_stmt

latest = income.columns[0]  # most recent quarter
revenue = income.loc["Total Revenue", latest]
net_income = income.loc["Net Income", latest]

print(f"Quarter ending: {latest.date()}")
print(f"Revenue:    ${revenue / 1e9:.1f} billion")
print(f"Net Income: ${net_income / 1e9:.2f} billion")