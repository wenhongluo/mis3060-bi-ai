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
    raise NotImplementedError


def summary(r: pd.DataFrame) -> dict:
    """TODO (Task 3): dictionary with mentions, avg_return, avg_spy_return, avg_excess,
    hit_rate (share that beat SPY) and pnl (sum). Handle an empty table."""
    raise NotImplementedError


def holding_curve(trades: pd.DataFrame, prices: pd.DataFrame, days=CURVE_DAYS) -> pd.DataFrame:
    """TODO (Task 4): average return, SPY return, excess and hit rate after each holding period in
    `days` (3, 6, 9, 12 months), using the SAME mentions at every point: only those that have reached the
    longest period. One row per period with months, trading_days and the summary() values."""
    raise NotImplementedError


def portfolio_curve(trades: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """TODO (Task 4): 'follow the picks'. $1,000 invested in every mention at its entry close and never
    sold, vs the same dollars put into SPY on the same dates. One row per trading day from the first
    entry: date, invested, picks_value, spy_value. An entry needs a real price that day; a ticker that
    stops trading later is carried at its last price."""
    raise NotImplementedError
