"""Final Trades data layer (MIS3060 Week 14).

2025 CNBC Halftime Report "Final Trades" picks + daily prices -> long-term returns on $1,000 per
mention vs SPY, a holding-period curve, and a "follow the picks" portfolio over time.
"""
from pathlib import Path
import os
import pandas as pd

DATA_DIR = Path(os.environ.get("FT_DATA_DIR", Path(__file__).parent / "data"))
TRADES_FILE = "final_trades_2025.csv"     # instructor-provided: episode_date, guest, ticker, company
SNAPSHOT_FILE = "prices_snapshot.csv"     # built by build_market_snapshot.py: date, ticker, close
BENCH = "SPY"
STAKE = 1_000.0
PRICE_START = "2024-12-31"                # prices are needed from just before the first 2025 episode

# Holding periods in trading days (about 21 trading days per month)
HORIZONS = {
    "3 months (63 trading days)": 63,
    "6 months (126 trading days)": 126,
    "12 months (252 trading days)": 252,
    "To latest close": None,
}
CURVE_DAYS = (63, 126, 189, 252)          # 3, 6, 9 and 12 months


def load_trades(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    t = pd.read_csv(Path(data_dir) / TRADES_FILE, parse_dates=["episode_date"])
    t["ticker"] = t["ticker"].str.strip().str.upper()
    t["mention_id"] = range(1, len(t) + 1)
    return t


def load_snapshot(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    p = pd.read_csv(Path(data_dir) / SNAPSHOT_FILE, parse_dates=["date"])
    return p[["date", "ticker", "close"]]


def download_prices(tickers, start, end) -> pd.DataFrame:
    """Live adjusted closes from Yahoo Finance via yfinance, in long format. Raises on failure."""
    import logging
    import yfinance as yf
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)      # silence per-ticker error spam
    tickers = sorted(set(tickers))
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
    long = close.reset_index().melt(id_vars="Date", var_name="ticker", value_name="close").dropna()
    long = long.rename(columns={"Date": "date"})
    if long.empty:
        raise RuntimeError("yfinance returned no data")
    return long


def get_prices(tickers, start, end, live: bool = False, data_dir: Path = DATA_DIR):
    """Try live data if asked; fall back to the committed snapshot. Returns (prices, source).
    Live is used only if every ticker that is in the snapshot also came back live."""
    snap = load_snapshot(data_dir)
    snap = snap[snap["ticker"].isin(set(tickers))]
    if live:
        try:
            live_prices = download_prices(tickers, start, end)
            if set(snap["ticker"]) <= set(live_prices["ticker"]):
                return live_prices, "live (Yahoo Finance)"
        except Exception:
            pass
    return snap, "snapshot CSV"


def price_table(prices: pd.DataFrame) -> pd.DataFrame:
    """Prices pivoted wide: one row per trading day, one column per ticker."""
    return prices.pivot_table(index="date", columns="ticker", values="close").sort_index()


def mention_returns(trades: pd.DataFrame, prices: pd.DataFrame, horizon_days) -> pd.DataFrame:
    """TODO (ICE 14 Task 3, with Claude): one row per mention with mention_id, episode_date, guest, ticker,
    company, entry_date, exit_date, trading_days, return, spy_return, excess, pnl ($1,000 stake) and beat_spy.
    Entry = close on the episode date or the next trading day; exit = horizon_days trading days later,
    or the latest close when horizon_days is None. SPY over the same two dates is the benchmark.
    Skip mentions whose holding period has not been reached yet or whose prices are missing."""
    columns = ["mention_id", "episode_date", "guest", "ticker", "company", "entry_date", "exit_date",
               "trading_days", "return", "spy_return", "excess", "pnl", "beat_spy"]
    table = price_table(prices)               # rows = trading days, columns = tickers
    days = table.index                        # the list of trading days, oldest first
    if BENCH not in table.columns:
        raise ValueError(f"{BENCH} prices are needed as the benchmark")

    rows = []
    for _, m in trades.iterrows():
        if m["ticker"] not in table.columns:  # no prices at all for this ticker
            continue

        # Buying day: the first trading day on or after the episode date.
        entry_pos = days.searchsorted(m["episode_date"])
        if entry_pos >= len(days):            # episode is after the last price we have
            continue

        # Selling day: horizon_days rows later, or the last row when horizon_days is None.
        exit_pos = len(days) - 1 if horizon_days is None else entry_pos + horizon_days
        if exit_pos >= len(days):             # that day hasn't happened yet
            continue

        entry_date, exit_date = days[entry_pos], days[exit_pos]
        buy, sell = table.at[entry_date, m["ticker"]], table.at[exit_date, m["ticker"]]
        spy_buy, spy_sell = table.at[entry_date, BENCH], table.at[exit_date, BENCH]
        if pd.isna([buy, sell, spy_buy, spy_sell]).any():   # a price is missing on one of the two days
            continue

        ret = sell / buy - 1
        spy_ret = spy_sell / spy_buy - 1
        rows.append({
            "mention_id": m["mention_id"], "episode_date": m["episode_date"], "guest": m["guest"],
            "ticker": m["ticker"], "company": m["company"],
            "entry_date": entry_date, "exit_date": exit_date, "trading_days": exit_pos - entry_pos,
            "return": ret, "spy_return": spy_ret, "excess": ret - spy_ret,
            "pnl": STAKE * ret, "beat_spy": ret > spy_ret,
        })
    return pd.DataFrame(rows, columns=columns)


def summary(r: pd.DataFrame) -> dict:
    """TODO (Task 3): dictionary with mentions, avg_return, avg_spy_return, avg_excess,
    hit_rate (share that beat SPY) and pnl (sum). Handle an empty table."""
    if r.empty:                               # nothing to average: report 0 mentions, NaN averages
        nan = float("nan")
        return {"mentions": 0, "avg_return": nan, "avg_spy_return": nan,
                "avg_excess": nan, "hit_rate": nan, "pnl": 0.0}
    return {
        "mentions": len(r),
        "avg_return": r["return"].mean(),
        "avg_spy_return": r["spy_return"].mean(),
        "avg_excess": r["excess"].mean(),
        "hit_rate": r["beat_spy"].mean(),      # True counts as 1, False as 0, so the mean is the share
        "pnl": r["pnl"].sum(),
    }


def holding_curve(trades: pd.DataFrame, prices: pd.DataFrame, days=CURVE_DAYS) -> pd.DataFrame:
    """TODO (Task 4): average return, SPY return, excess and hit rate after each holding period in
    `days` (3, 6, 9, 12 months), using the SAME mentions at every point: only those that have reached the
    longest period. One row per period with months, trading_days and the summary() values."""
    # Step 1: find the mentions that have been held for the LONGEST period (e.g. 252 days).
    longest = mention_returns(trades, prices, max(days))
    same_trades = trades[trades["mention_id"].isin(longest["mention_id"])]

    # Step 2: measure exactly those mentions at every checkpoint.
    rows = []
    for d in days:
        r = mention_returns(same_trades, prices, d)
        rows.append({"months": round(d / 21), "trading_days": d, **summary(r)})   # ** unpacks the dict
    return pd.DataFrame(rows)


def portfolio_curve(trades: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """TODO (Task 4): 'follow the picks'. $1,000 invested in every mention at its entry close and never
    sold, vs the same dollars put into SPY on the same dates. One row per trading day from the first
    entry: date, invested, picks_value, spy_value. An entry needs a real price that day; a ticker that
    stops trading later is carried at its last price."""
    # Entry day and entry price for every mention. A 0-day holding period means "buy and sell the same
    # day", so mention_returns() finds the entry day and drops mentions with no real price on that day.
    entries = mention_returns(trades, prices, 0)
    columns = ["date", "invested", "picks_value", "spy_value"]
    if entries.empty:
        return pd.DataFrame(columns=columns)

    table = price_table(prices)
    carried = table.ffill()                   # a missing price is replaced by the last known price
    days = table.index

    invested = pd.Series(0.0, index=days)
    picks_value = pd.Series(0.0, index=days)
    spy_value = pd.Series(0.0, index=days)
    for _, e in entries.iterrows():
        held = days >= e["entry_date"]        # True on the entry day and every day after
        shares = STAKE / table.at[e["entry_date"], e["ticker"]]      # how many shares $1,000 buys
        spy_shares = STAKE / table.at[e["entry_date"], BENCH]
        invested[held] += STAKE
        picks_value[held] += shares * carried.loc[held, e["ticker"]]
        spy_value[held] += spy_shares * carried.loc[held, BENCH]

    out = pd.DataFrame({"invested": invested, "picks_value": picks_value, "spy_value": spy_value})
    out = out[out.index >= entries["entry_date"].min()]     # start on the first entry day
    return out.rename_axis("date").reset_index()[columns]
