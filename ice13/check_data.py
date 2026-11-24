"""Quick check of the Wildcat data layer: prints the 2024 KPIs.

Run from the ice13 folder:  python check_data.py
"""
import wildcat_data as wd

tables = wd.load_tables()
monthly = wd.build_monthly(tables)

# Keep only 2024 (all tiers, all regions)
m2024 = monthly[monthly["year"] == 2024]

print("Wildcat Capital - 2024 (all tiers, all regions)")
print("-----------------------------------------------")
print(f"Ending AUM:          {wd.money(wd.ending_aum(m2024))}")
print(f"Total fees:          {wd.money(wd.total_fees(m2024))}")
print(f"Net flows:           {wd.money(wd.net_flows(m2024))}")
print(f"Effective fee rate:  {wd.effective_fee_rate_bps(m2024):.1f} bps")
print(f"Rows (2024 only):    {len(m2024):,}")
print(f"Rows (full table):   {len(monthly):,}")
