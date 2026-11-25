"""Quick first look at the Final Trades data (MIS3060 ICE 14).

Run from the ice14 folder:  python explore.py
"""
from market import load_trades, load_snapshot

trades = load_trades()      # one row per Final Trades mention
prices = load_snapshot()    # one row per ticker per trading day

print("=== Final Trades (2025) ===")
print("Number of mentions:          ", len(trades))
print("Number of different tickers: ", trades["ticker"].nunique())
print("Number of different analysts:", trades["guest"].nunique())
print("First episode date:          ", trades["episode_date"].min().date())
print("Last episode date:           ", trades["episode_date"].max().date())

print()
print("=== Price snapshot ===")
print("First price date:            ", prices["date"].min().date())
print("Last price date:             ", prices["date"].max().date())

print()
print("=== 5 most-mentioned tickers ===")
print(trades["ticker"].value_counts().head(5).to_string())

print()
print("=== 5 analysts with the most mentions ===")
print(trades["guest"].value_counts().head(5).to_string())
