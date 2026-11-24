"""Wildcat Capital data layer for the MIS3060 Streamlit dashboard.

What this file does:
  1. load_tables()       reads the Wildcat CSV files from data/wildcat
  2. build_monthly()     squeezes them into ONE small monthly table
  3. the KPI functions   each turn a (filtered) monthly table into one number
  4. money()             formats a number as $12.73B / $48.7M / $512K

The app should only import this file. It should never read the CSVs itself.
"""
from pathlib import Path

import pandas as pd

# The data folder is found relative to THIS file (ice13/data/wildcat),
# so the code works on any computer. No C:\Users\... paths.
DATA_DIR = Path(__file__).resolve().parent / "data" / "wildcat"


# ---------------------------------------------------------------------------
# 1. Load the raw tables
# ---------------------------------------------------------------------------
def load_tables(data_dir=DATA_DIR):
    """Read the five CSVs the dashboard needs and return them in a dictionary.

    Date columns are read as real dates (not text) so we can group by month.
    """
    data_dir = Path(data_dir)
    tables = {
        "dim_advisor": pd.read_csv(data_dir / "dim_advisor.csv"),
        "dim_client": pd.read_csv(data_dir / "dim_client.csv",
                                  parse_dates=["client_since"],
                                  dtype={"zip_code": str}),  # keep leading zeros
        "fact_portfolio_snapshot": pd.read_csv(data_dir / "fact_portfolio_snapshot.csv",
                                               parse_dates=["snapshot_date"]),
        "fact_fees": pd.read_csv(data_dir / "fact_fees.csv",
                                 parse_dates=["fee_date"]),
        "fact_transactions": pd.read_csv(data_dir / "fact_transactions.csv",
                                         parse_dates=["txn_date"]),
    }
    return tables


def _to_month(dates):
    """Turn any date into the first day of its month (e.g. 2023-04-17 -> 2023-04-01)."""
    return dates.dt.to_period("M").dt.to_timestamp()


# ---------------------------------------------------------------------------
# 2. Build the one monthly table
# ---------------------------------------------------------------------------
def build_monthly(tables):
    """Return one row per month x client tier x advisor.

    Columns: month, year, client_tier, advisor_id, advisor, region,
             ending_aum, clients, fees, fee_basis, net_flows
    """
    keys = ["month", "client_tier", "advisor_id"]

    # Each client's tier lives in dim_client; we attach it to every fact table.
    tier = tables["dim_client"][["client_id", "client_tier"]]

    # --- AUM (a balance): total AUM and number of clients in each month ---
    snap = tables["fact_portfolio_snapshot"].merge(tier, on="client_id")
    snap["month"] = _to_month(snap["snapshot_date"])
    aum = snap.groupby(keys).agg(
        ending_aum=("aum", "sum"),          # adding across clients in ONE month is fine
        clients=("client_id", "nunique"),
    )

    # --- Fees: dollars charged and the AUM they were charged on ---
    fee = tables["fact_fees"].merge(tier, on="client_id")
    fee["month"] = _to_month(fee["fee_date"])
    fees = fee.groupby(keys).agg(
        fees=("amount", "sum"),
        fee_basis=("aum_basis", "sum"),
    )

    # --- Net flows: deposits count +, withdrawals count -, everything else ignored ---
    txn = tables["fact_transactions"].merge(tier, on="client_id")
    txn = txn[txn["txn_type"].isin(["Deposit", "Withdrawal"])].copy()
    txn["month"] = _to_month(txn["txn_date"])  # daily dates -> month, same format as above
    txn["signed_amount"] = txn["amount"].where(txn["txn_type"] == "Deposit", -txn["amount"])
    flows = txn.groupby(keys).agg(net_flows=("signed_amount", "sum"))

    # --- Put the three pieces side by side; a missing piece means 0 ---
    monthly = aum.join(fees, how="outer").join(flows, how="outer").fillna(0).reset_index()
    monthly["clients"] = monthly["clients"].astype(int)

    # --- Add advisor name and region from dim_advisor ---
    adv = tables["dim_advisor"].copy()
    adv["advisor"] = adv["first_name"] + " " + adv["last_name"]
    monthly = monthly.merge(adv[["advisor_id", "advisor", "region"]], on="advisor_id", how="left")

    monthly["year"] = monthly["month"].dt.year

    columns = ["month", "year", "client_tier", "advisor_id", "advisor", "region",
               "ending_aum", "clients", "fees", "fee_basis", "net_flows"]
    return monthly[columns].sort_values(keys).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. KPI functions: pass in an ALREADY-FILTERED monthly table, get one number
# ---------------------------------------------------------------------------
def ending_aum(df):
    """AUM in the LAST month that has AUM. Balances are never added across months."""
    with_aum = df[df["ending_aum"] > 0]
    if with_aum.empty:
        return 0.0
    last_month = with_aum["month"].max()
    return float(with_aum.loc[with_aum["month"] == last_month, "ending_aum"].sum())


def total_fees(df):
    """Sum of all fee dollars in the table."""
    return float(df["fees"].sum())


def net_flows(df):
    """Deposits minus withdrawals over every month in the table."""
    return float(df["net_flows"].sum())


def effective_fee_rate_bps(df):
    """Annualized fee rate in basis points, recomputed from sums (never an average of rates)."""
    basis = df["fee_basis"].sum()
    if basis == 0:
        return float("nan")  # no fee basis -> rate is undefined
    return float(df["fees"].sum() * 12 * 10_000 / basis)


# ---------------------------------------------------------------------------
# 4. Formatting helper
# ---------------------------------------------------------------------------
def money(x):
    """Format dollars as $12.73B, $48.7M or $512K."""
    size = abs(x)
    if size >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if size >= 1e6:
        return f"${x / 1e6:,.1f}M"
    return f"${x / 1e3:,.0f}K"
