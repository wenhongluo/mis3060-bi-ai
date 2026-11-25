"""Check mention_returns() and summary() (MIS3060 ICE 14, Task 3).

Run from the ice14 folder:  python check_returns.py
"""
import pandas as pd
from market import (load_trades, load_snapshot, mention_returns, summary, HORIZONS,
                    holding_curve, portfolio_curve)

# The two mentions to show in detail at 126 trading days. Change these to any (ticker, episode date).
EXAMPLES = [("UBER", "2025-01-03"), ("GS", "2025-12-31")]

trades = load_trades()
prices = load_snapshot()          # the saved prices, including SPY

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

print(f"Total mentions: {len(trades)}\n")
for label, days in HORIZONS.items():          # 63, 126, 252 and None ("To latest close")
    r = mention_returns(trades, prices, days)
    s = summary(r)
    print(f"=== {label} ===")
    print(f"  mentions used:  {s['mentions']}   skipped: {len(trades) - s['mentions']}")
    print(f"  avg return:     {s['avg_return']:.2%}")
    print(f"  avg SPY return: {s['avg_spy_return']:.2%}")
    print(f"  avg excess:     {s['avg_excess']:.2%}")
    print(f"  hit rate:       {s['hit_rate']:.1%}  (share of mentions that beat SPY)")
    print(f"  total P&L:      ${s['pnl']:,.0f}  on ${1_000 * s['mentions']:,.0f} invested\n")

print("=== 126-day rows for the example mentions ===")
r126 = mention_returns(trades, prices, 126)
for ticker, date in EXAMPLES:
    row = r126[(r126["ticker"] == ticker) & (r126["episode_date"] == pd.Timestamp(date))]
    if row.empty:
        print(f"{ticker} {date}: no row (skipped, or no such mention)\n")
    else:
        print(row.T.to_string(header=False), "\n")     # .T shows one field per line

print("=== summary() on an empty table ===")
print(summary(r126.iloc[0:0]))

print("\n=== Holding curve (same mentions at every point) ===")
hc = holding_curve(trades, prices)
shown = hc.copy()
for col in ["avg_return", "avg_spy_return", "avg_excess", "hit_rate"]:
    shown[col] = shown[col].map("{:.2%}".format)        # show as percentages
shown["pnl"] = shown["pnl"].map("${:,.0f}".format)
print(shown.to_string(index=False))

print("\n=== Portfolio curve: first and last day ===")
pc = portfolio_curve(trades, prices)
print(pc.iloc[[0, -1]].to_string(index=False, float_format="{:,.2f}".format))
