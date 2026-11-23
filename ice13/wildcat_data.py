"""Wildcat Capital data layer for Streamlit apps (MIS3060 Weeks 13-14).

Load the eight Clean star-schema tables once, aggregate them to ONE small monthly
table, and compute every KPI from that table with plain pandas functions.
Balances (AUM) are never added across months; rates are recomputed from sums.
"""
from pathlib import Path
import os
import pandas as pd

DATA_DIR = Path(os.environ.get("WILDCAT_DATA_DIR", Path(__file__).parent / "data" / "wildcat"))


def load_tables(data_dir: Path = DATA_DIR) -> dict:
    """Read the Clean CSVs with explicit types (keys as numbers, dates as dates)."""
    dates = {"fact_portfolio_snapshot": ["snapshot_date"], "fact_fees": ["fee_date"],
             "fact_transactions": ["txn_date"], "dim_client": ["client_since"]}
    names = ["dim_advisor", "dim_client", "fact_portfolio_snapshot", "fact_fees", "fact_transactions"]
    t = {n: pd.read_csv(Path(data_dir) / f"{n}.csv", parse_dates=dates.get(n, []),
                        dtype={"zip_code": str} if n == "dim_client" else None) for n in names}
    t["dim_advisor"]["advisor"] = t["dim_advisor"]["first_name"] + " " + t["dim_advisor"]["last_name"]
    return t


def build_monthly(t: dict) -> pd.DataFrame:
    """One row per month x client tier x advisor (~4,500 rows): everything the app needs."""
    tier = t["dim_client"][["client_id", "client_tier"]]
    keys = ["month", "client_tier", "advisor_id"]

    s = t["fact_portfolio_snapshot"].merge(tier, on="client_id")
    s["month"] = s["snapshot_date"]
    aum = s.groupby(keys).agg(ending_aum=("aum", "sum"), clients=("client_id", "nunique"))

    f = t["fact_fees"].merge(tier, on="client_id")
    f["month"] = f["fee_date"]
    fees = f.groupby(keys).agg(fees=("amount", "sum"), fee_basis=("aum_basis", "sum"))

    x = t["fact_transactions"].merge(tier, on="client_id")
    x = x[x["txn_type"].isin(["Deposit", "Withdrawal"])].copy()
    x["month"] = x["txn_date"].values.astype("datetime64[M]")          # transactions are daily: roll to month start
    x["signed"] = x["amount"].where(x["txn_type"] == "Deposit", -x["amount"])
    flows = x.groupby(keys).agg(net_flows=("signed", "sum"))

    m = aum.join(fees, how="outer").join(flows, how="outer").fillna(0).reset_index()
    m = m.merge(t["dim_advisor"][["advisor_id", "advisor", "region"]], on="advisor_id")
    m["year"] = m["month"].dt.year
    return m


# ---------- KPI functions: always pass an already-filtered frame ----------
def ending_aum(df: pd.DataFrame) -> float:
    """Balance at the LAST month in the frame (semi-additive), not a sum over months."""
    if df.empty:
        return 0.0
    last = df.loc[df["ending_aum"] > 0, "month"].max()
    return float(df.loc[df["month"] == last, "ending_aum"].sum())


def ending_clients(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    last = df.loc[df["ending_aum"] > 0, "month"].max()
    return int(df.loc[df["month"] == last, "clients"].sum())


def total_fees(df: pd.DataFrame) -> float:
    return float(df["fees"].sum())


def net_flows(df: pd.DataFrame) -> float:
    return float(df["net_flows"].sum())


def effective_fee_rate_bps(df: pd.DataFrame) -> float:
    """Annualized fees per dollar of fee basis, recomputed from sums (never averaged)."""
    basis = df["fee_basis"].sum()
    return float(df["fees"].sum() * 12 * 10_000 / basis) if basis else float("nan")


def money(x: float) -> str:
    """$12.73B / $48.7M / $512K."""
    a = abs(x)
    if a >= 1e9:
        return f"${x/1e9:,.2f}B"
    if a >= 1e6:
        return f"${x/1e6:,.1f}M"
    return f"${x/1e3:,.0f}K"
