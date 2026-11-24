"""Wildcat Capital — KPI Overview (Streamlit dashboard page).

HOW STREAMLIT WORKS: every time you click something on the page (including a
sidebar filter), Streamlit runs this whole file again from top to bottom. That is
why the data loading below is cached: so the CSVs are not re-read on every click.

HOW TO RUN (in a terminal, from the ice13 folder):
    .venv\\Scripts\\python.exe -m streamlit run app.py
Your browser opens at http://localhost:8501. Press Ctrl + C in the terminal to stop.
"""

# Load the Streamlit library. "st" is a short nickname, so st.title(...) means
# "the title function inside Streamlit".
import streamlit as st

# Load pandas, the table library. We use it below only to put the chart data
# into a small table. "pd" is its usual nickname.
import pandas as pd

# Load Plotly Express, a library that draws interactive charts (you can hover,
# zoom and download them). "px" is its usual nickname.
import plotly.express as px

# Load our own data layer (wildcat_data.py). All KPI math lives there.
# "wd" is its nickname, so wd.money(...) means "money() inside wildcat_data.py".
import wildcat_data as wd

# st.set_page_config: sets up the browser page. It must be the FIRST Streamlit command.
#   page_title = the text on the browser tab
#   layout="wide" = use the full width of the screen instead of a narrow middle column
st.set_page_config(page_title="Wildcat Capital", layout="wide")

# st.title: shows the big heading at the top of the page.
st.title("Wildcat Capital — KPI Overview")


# @st.cache_data (the line starting with @ is a "decorator"; it adds a behavior
# to the function right below it): Streamlit REMEMBERS what this function returns.
#   - First run: it reads the CSVs and builds the monthly table (takes a few seconds).
#   - Every later rerun (every click): it hands back the saved table instantly,
#     without opening the CSV files again.
@st.cache_data
def get_monthly():
    """Read the CSVs and build the monthly table ONCE; later reruns reuse the result."""
    return wd.build_monthly(wd.load_tables())


# A small helper that compares two KPI values that wildcat_data.py already calculated.
# It does not recalculate any KPI; it only says how much the selected year changed
# vs the year before.
def pct_change(current, previous, previous_year):
    """Percent change vs the prior year, as text like '+19.6% vs 2023'."""
    # If there is no prior-year value (first year in the data, or zero), we cannot
    # divide by it, so return None (Python's "nothing"); the card then simply shows
    # no change line instead of crashing.
    if previous is None or previous == 0:
        return None
    # abs() = absolute value (drops the minus sign). It keeps the direction of the
    # change correct even if last year's value was negative (possible for net flows).
    change = (current - previous) / abs(previous) * 100
    # f"..." builds text with a value inside {}.
    #   :+.1f = always show a + or - sign, one decimal place (e.g. +19.6)
    return f"{change:+.1f}% vs {previous_year}"


def describe(selected, all_options):
    """Text for the caption: 'All', 'None selected', or the list of choices."""
    if not selected:  # an empty list counts as "not selected"
        return "None selected"
    if set(selected) == set(all_options):
        return "All"
    # ", ".join(...) glues a list of words into one text: ["HNW", "UHNW"] -> "HNW, UHNW"
    return ", ".join(selected)


# Get the monthly table (from the cache after the first run).
monthly = get_monthly()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

# The choices for each filter come from the data itself, so they stay correct
# if the data changes. sorted() puts them in order.
year_options = sorted(monthly["year"].unique())
# Tiers in business order (smallest to largest clients) instead of alphabetical.
tier_options = [t for t in ["Retail", "HNW", "UHNW"] if t in set(monthly["client_tier"])]
region_options = sorted(monthly["region"].unique())

# st.sidebar.header: a heading in the left sidebar. Anything written as
# st.sidebar.<something> appears in the sidebar instead of the main page.
st.sidebar.header("Filters")

# st.sidebar.selectbox: a drop-down where you pick exactly ONE option.
#   index = which option is selected at the start; len(...) - 1 = the last one,
#   i.e. the latest year.
selected_year = st.sidebar.selectbox("Year", year_options, index=len(year_options) - 1)

# st.sidebar.multiselect: a box where you can pick SEVERAL options (or none).
#   default = what is selected at the start; here, every option.
selected_tiers = st.sidebar.multiselect("Client tier", tier_options, default=tier_options)
selected_regions = st.sidebar.multiselect("Region", region_options, default=region_options)

# st.caption: small grey text. It lists the active filters right under the title,
# so anyone looking at a screenshot knows exactly what they are seeing.
st.caption(
    f"Filters — Year: {selected_year}  ·  "
    f"Client tier: {describe(selected_tiers, tier_options)}  ·  "
    f"Region: {describe(selected_regions, region_options)}"
)

# ---------------------------------------------------------------------------
# Apply the filters — in ONE place. Everything below uses "filtered".
# ---------------------------------------------------------------------------
# .isin(list) asks each row "is your tier one of the selected tiers?" (True/False).
# The & means BOTH must be true: right tier AND right region.
# Year is NOT filtered here, because the trend chart needs all years.
filtered = monthly[monthly["client_tier"].isin(selected_tiers) & monthly["region"].isin(selected_regions)]

# If the selection leaves no data (e.g. no tier picked), say so politely and stop.
# st.warning: a yellow message box. st.stop(): ends this run of the file right here,
# so nothing below runs (no crash, no misleading $0 cards).
if filtered.empty:
    st.warning("No data for this selection. Pick at least one client tier and one region in the sidebar.")
    st.stop()

# From the filtered data, take the selected year and the year before it.
this_year = filtered[filtered["year"] == selected_year]
prior_year = selected_year - 1
last_year = filtered[filtered["year"] == prior_year]

if this_year.empty:
    st.warning(f"No data for {selected_year} with these filters. Try another year, tier or region.")
    st.stop()

# Is there a prior year to compare with? (No for the first year in the data.)
has_prior = not last_year.empty

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

# Call the KPI functions from wildcat_data.py. "x if condition else y" means
# "use x when the condition is true, otherwise y"; here: no prior year -> None.
aum_now = wd.ending_aum(this_year)
aum_before = wd.ending_aum(last_year) if has_prior else None
fees_now = wd.total_fees(this_year)
fees_before = wd.total_fees(last_year) if has_prior else None
flows_now = wd.net_flows(this_year)
flows_before = wd.net_flows(last_year) if has_prior else None
rate_now = wd.effective_fee_rate_bps(this_year)

# st.subheader: a smaller heading, so readers know which year the cards show.
st.subheader(str(selected_year))
if not has_prior:
    st.caption(f"No {prior_year} data, so no % change is shown.")

# st.columns(4): splits the page into 4 equal columns side by side and gives back
# one handle per column. Whatever we put in col1 appears in the first column, etc.
col1, col2, col3, col4 = st.columns(4)

# .metric(label, value, delta): draws one KPI card.
#   label = small text on top ("Ending AUM")
#   value = the big number; wd.money() turns 12729572078.86 into "$12.73B"
#   delta = the small line under the number ("+19.6% vs 2023"). Streamlit colors it
#           green with an up arrow if it starts with "+", red with a down arrow if "-".
#           None = no line at all.
#   border=True draws a box around the card.
col1.metric("Ending AUM", wd.money(aum_now), pct_change(aum_now, aum_before, prior_year), border=True)
col2.metric("Total Fees", wd.money(fees_now), pct_change(fees_now, fees_before, prior_year), border=True)
col3.metric("Net Flows", wd.money(flows_now), pct_change(flows_now, flows_before, prior_year), border=True)

# The fourth card has no delta, so nothing appears under the number.
#   :.1f = round to one decimal place, then we add the text " bps".
col4.metric("Effective Fee Rate", f"{rate_now:.1f} bps", border=True)


# ---------------------------------------------------------------------------
# Charts, organized in three tabs. All of them use the filtered data.
# ---------------------------------------------------------------------------

# st.tabs: creates clickable tabs. It gives back one handle per tab; anything
# written inside "with <tab>:" appears only on that tab.
tab_trend, tab_tiers, tab_advisors = st.tabs(["Trend", "Fees by tier", "Top advisors"])

# Colors used in the bar charts.
HIGHLIGHT = "#118DFF"  # blue: the top bar
OTHER = "#C8C8C8"      # grey: every other bar

# ===========================================================================
# Tab 1 — Trend: Ending AUM by month, all years, for the selected tiers and regions
# ===========================================================================
# "with tab_trend:" = everything indented under this line is drawn on the Trend tab.
with tab_trend:

    # Get the list of months in the filtered data, oldest first.
    #   .unique() = each month only once; sorted() = put them in date order.
    months = sorted(filtered["month"].unique())

    # For EACH month, keep only that month's rows and give them to wd.ending_aum().
    # Because the rows all come from one month, ending_aum() adds AUM across tiers and
    # advisors for that month only. Months are never added together.
    # The [ ... for m in months] pattern is a "list comprehension": a one-line loop
    # that builds a list with one result per month.
    aum_by_month = [wd.ending_aum(filtered[filtered["month"] == m]) for m in months]

    # pd.DataFrame: put the two lists side by side into a small table,
    # one row per month (60 rows for 2020-2024).
    chart_data = pd.DataFrame({"month": months, "ending_aum": aum_by_month})

    # Plot AUM in billions so the axis reads $0B, $5B, $10B (clearer than 10,000,000,000).
    # This only changes the units for the axis; the AUM itself came from wd.ending_aum().
    chart_data["aum_billions"] = chart_data["ending_aum"] / 1e9

    # The exact dollar text for the hover box, made by our money() function ("$12.73B").
    chart_data["aum_label"] = [wd.money(v) for v in chart_data["ending_aum"]]

    # px.line: draws a line chart from a table.
    #   x = column for the horizontal axis, y = column for the vertical axis
    #   markers=True puts a dot on each month, so there is a point to hover over
    #   custom_data = extra columns that the hover box can show
    fig = px.line(
        chart_data,
        x="month",
        y="aum_billions",
        markers=True,
        custom_data=["aum_label"],
        title="Ending AUM by Month",
    )

    # What appears when you hover over a point:
    #   %{x|%b %Y} = the month, written like "Dec 2024"
    #   %{customdata[0]} = our "$12.73B" label
    #   <extra></extra> removes the extra grey box Plotly adds by default
    fig.update_traces(hovertemplate="%{x|%b %Y}<br>Ending AUM: %{customdata[0]}<extra></extra>")

    # Y-axis settings:
    #   rangemode="tozero" makes the axis start at 0 (so changes are not exaggerated)
    #   tickprefix / ticksuffix put "$" before and "B" after each number ($10B)
    #   title_text = the label beside the axis
    fig.update_yaxes(rangemode="tozero", tickprefix="$", ticksuffix="B",
                     title_text="Ending AUM (USD billions)")

    # X-axis label (just "Month" instead of the column name "month").
    fig.update_xaxes(title_text="Month")

    # st.plotly_chart: shows a Plotly chart on the page, interactive.
    #   width="stretch" makes it as wide as the page.
    st.plotly_chart(fig, width="stretch")


# ===========================================================================
# Tab 2 — Fees by tier (selected year)
# ===========================================================================
with tab_tiers:
    # For each selected tier, give that tier's rows to wd.total_fees().
    # (We reuse the KPI function; nothing is recalculated here.)
    tiers_in_year = [t for t in tier_options if t in set(this_year["client_tier"])]
    tier_fees = pd.DataFrame({
        "client_tier": tiers_in_year,
        "fees": [wd.total_fees(this_year[this_year["client_tier"] == t]) for t in tiers_in_year],
    })

    # Sort smallest to largest. Plotly draws the FIRST row at the BOTTOM of a
    # horizontal bar chart, so the largest ends up on top.
    tier_fees = tier_fees.sort_values("fees")

    # The top tier is the last row after sorting. .iloc[-1] = "the last row".
    top_tier = tier_fees["client_tier"].iloc[-1]

    # One color per bar: blue for the top tier, grey for the rest.
    tier_colors = [HIGHLIGHT if t == top_tier else OTHER for t in tier_fees["client_tier"]]

    # Dollar text for the hover box and the bar labels ("$22.4M").
    tier_fees["fees_label"] = [wd.money(v) for v in tier_fees["fees"]]

    # px.bar with orientation="h" draws HORIZONTAL bars:
    #   x = the length of each bar (fees), y = the category (tier).
    #   text = the label written at the end of each bar.
    # The title is built from the data, so it is always true for the current filters.
    fig_tiers = px.bar(
        tier_fees,
        x="fees",
        y="client_tier",
        orientation="h",
        text="fees_label",
        custom_data=["fees_label"],
        title=f"{top_tier} generates the most fees in {selected_year}",
    )
    # marker_color = bar colors (our list); showlegend=False = no legend.
    fig_tiers.update_traces(
        marker_color=tier_colors,
        showlegend=False,
        hovertemplate="%{y}<br>Fees: %{customdata[0]}<extra></extra>",
    )
    # tickformat="~s" writes axis numbers short (20M = 20 million); tickprefix adds "$".
    fig_tiers.update_xaxes(title_text="Total fees", tickprefix="$", tickformat="~s")
    fig_tiers.update_yaxes(title_text="Client tier")
    st.plotly_chart(fig_tiers, width="stretch")


# ===========================================================================
# Tab 3 — Top 10 advisors by fees (selected year)
# ===========================================================================
with tab_advisors:
    # Build one row per advisor, using the KPI functions on that advisor's rows:
    #   wd.total_fees()            = the advisor's total fees
    #   wd.effective_fee_rate_bps() = fees x 12 x 10,000 / fee basis, from sums
    #     (the same formula as in wildcat_data.py, because it IS that function).
    advisor_rows = []
    # .groupby("advisor_id") splits the table into one piece per advisor.
    # "for advisor_id, rows in ..." walks through the pieces one at a time.
    for advisor_id, rows in this_year.groupby("advisor_id"):
        advisor_rows.append({
            "Advisor": rows["advisor"].iloc[0],   # each advisor has one name...
            "Region": rows["region"].iloc[0],     # ...and one region
            "Fees": wd.total_fees(rows),
            "Fee rate (bps)": wd.effective_fee_rate_bps(rows),
        })
    advisors = pd.DataFrame(advisor_rows)

    # Keep the 10 advisors with the most fees, largest first.
    top10 = advisors.sort_values("Fees", ascending=False).head(10).reset_index(drop=True)

    # --- Bar chart (largest on top, same color rule as the tier chart) ---
    chart10 = top10.sort_values("Fees")  # smallest first -> largest drawn on top
    chart10["fees_label"] = [wd.money(v) for v in chart10["Fees"]]
    top_advisor = top10["Advisor"].iloc[0]
    fig_adv = px.bar(
        chart10,
        x="Fees",
        y="Advisor",
        orientation="h",
        text="fees_label",
        custom_data=["fees_label", "Region"],
        title=f"{top_advisor} leads advisors in fees in {selected_year}",
    )
    fig_adv.update_traces(
        marker_color=[HIGHLIGHT if a == top_advisor else OTHER for a in chart10["Advisor"]],
        showlegend=False,
        hovertemplate="%{y} (%{customdata[1]})<br>Fees: %{customdata[0]}<extra></extra>",
    )
    fig_adv.update_xaxes(title_text="Total fees", tickprefix="$", tickformat="~s")
    fig_adv.update_yaxes(title_text="")
    st.plotly_chart(fig_adv, width="stretch")

    # --- Table ---
    # st.dataframe: shows a table you can sort (click a column header) and scroll.
    #   hide_index=True hides the 0, 1, 2 ... row numbers.
    #   column_config tells Streamlit how to DISPLAY each column; the numbers
    #   underneath stay as plain numbers (so sorting still works correctly).
    #   st.column_config.NumberColumn(format=...):
    #     "dollar"   -> shows 2153421.87 as $2,153,421.87
    #     "%.1f bps" -> one decimal place, then " bps" (e.g. 64.9 bps)
    st.dataframe(
        top10,
        hide_index=True,
        column_config={
            "Fees": st.column_config.NumberColumn("Fees", format="dollar"),
            "Fee rate (bps)": st.column_config.NumberColumn("Fee rate (bps)", format="%.1f bps"),
        },
    )

    # st.download_button: a button that downloads a file when clicked.
    #   data = the file contents; .to_csv(index=False) turns the table into CSV text
    #          (plain numbers, no $ signs, so Excel can do math with them)
    #   file_name = the name the file gets in your Downloads folder
    #   mime = tells the browser what kind of file it is ("text/csv" = a CSV file)
    st.download_button(
        label="Download table as CSV",
        data=top10.to_csv(index=False),
        file_name=f"wildcat_top_advisors_{selected_year}.csv",
        mime="text/csv",
    )
