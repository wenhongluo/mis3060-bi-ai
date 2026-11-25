"""Final Trades scorecard (MIS3060 ICE 14): did following CNBC's 2025 "Final Trades" beat the market?

Run from the ice14 folder:  streamlit run app.py
All numbers come from the functions in market.py; this file only shows them.
"""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import market

st.set_page_config(page_title="Final Trades Scorecard", layout="wide")


# ---------- Helpers: number formatting ----------
def money(x: float) -> str:
    """$1,234 for gains and -$1,041 for losses (minus sign before the dollar sign)."""
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def pct(x: float, signed: bool = False) -> str:
    return f"{x:+.1%}" if signed else f"{x:.1%}"


# ---------- Data (cached so it is not reloaded on every click) ----------
@st.cache_data
def load_trades():
    return market.load_trades()


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Loading prices...")     # remember for 6 hours
def load_prices(live: bool, end: str):
    tickers = list(load_trades()["ticker"].unique()) + [market.BENCH]
    return market.get_prices(tickers, market.PRICE_START, end, live=live)


trades = load_trades()

# ---------- Sidebar ----------
st.sidebar.header("Settings")
live = st.sidebar.toggle("Try live prices (Yahoo Finance)", value=False,
                         help="Downloads about 300 tickers, which can take a minute. "
                              "Falls back to the saved snapshot if anything is missing.")
horizon_names = list(market.HORIZONS)
horizon_label = st.sidebar.selectbox("Holding period", horizon_names,
                                     index=horizon_names.index("12 months (252 trading days)"))
horizon_days = market.HORIZONS[horizon_label]
all_analysts = sorted(trades["guest"].unique())
analysts = st.sidebar.multiselect("Analysts to include", all_analysts, default=all_analysts)

# ---------- Title ----------
st.title("Did following CNBC's 2025 Final Trades beat the market?")
st.markdown("Every pick from the *Halftime Report* \"Final Trades\" segment in 2025, "
            "scored as **$1,000 bought at the close** on the episode date and compared "
            "with the same $1,000 in **SPY** over the same dates.")

# Yahoo's end date is not included, so ask for one day past today to include today's close.
end = (date.today() + timedelta(days=1)).isoformat()
prices, source = load_prices(live, end)
if live and source != "live (Yahoo Finance)":
    st.warning("Live download failed or was incomplete, so the saved snapshot is shown instead.")

if not analysts:
    st.warning("No analysts selected. Pick at least one in the sidebar.")
    st.stop()

chosen = trades[trades["guest"].isin(analysts)]
r = market.mention_returns(chosen, prices, horizon_days)
s = market.summary(r)

# Why mentions were skipped: no price on the buying day vs. selling date not reached yet.
can_buy = len(market.mention_returns(chosen, prices, 0))   # 0-day hold = has a buying price
no_price = len(chosen) - can_buy
not_yet = can_buy - s["mentions"]
reasons = []
if no_price:
    reasons.append(f"{no_price} have no price data (mostly companies acquired and delisted)")
if not_yet:
    reasons.append(f"{not_yet} have not reached the {horizon_label.split(' (')[0].replace(' months', '-month')} selling date yet")
skipped = f" — skipped: {'; '.join(reasons)}" if reasons else ""

st.caption(f"Prices: **{source}**, last price date **{prices['date'].max():%b %d, %Y}** · "
           f"**{s['mentions']} of {len(chosen)} mentions included**{skipped}.")

if s["mentions"] == 0:
    st.warning("No mentions match these settings. Try a shorter holding period or more analysts.")
    st.stop()

# ---------- KPI cards ----------
st.subheader(f"Holding period: {horizon_label}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mentions included", f"{s['mentions']:,}", border=True)
c2.metric("Average return", pct(s["avg_return"]),
          delta=f"{pct(s['avg_excess'], signed=True)} vs SPY", border=True,
          help=f"SPY averaged {pct(s['avg_spy_return'])} over the same dates.")
c3.metric("Share that beat SPY", pct(s["hit_rate"]), border=True)
c4.metric("Total P&L", money(s["pnl"]), border=True,
          help=f"$1,000 in each mention: {money(market.STAKE * s['mentions'])} invested in total.")

# ---------- Tabs ----------
BLUE, ORANGE, GREY = "#1f77b4", "#ff7f0e", "#7f7f7f"
PCT = st.column_config.NumberColumn(format="percent")       # show 0.123 as 12.30%
USD = st.column_config.NumberColumn(format="dollar")        # show 1234.5 as $1,234.50

tab1, tab2, tab3, tab4 = st.tabs(["Holding period", "Follow the picks", "Analysts", "Mentions"])

# 1) Holding period: same mentions measured after 3, 6, 9 and 12 months
with tab1:
    hc = market.holding_curve(chosen, prices)
    n_curve = int(hc["mentions"].iloc[0]) if len(hc) else 0
    if n_curve == 0:
        st.warning("None of the selected mentions has been held for 12 months yet.")
    else:
        ahead = int((hc["avg_excess"] > 0).sum())
        gap = hc["avg_excess"].iloc[-1]
        if ahead == len(hc):
            title = f"The picks beat SPY at every holding period ({pct(gap, True)} at 12 months)"
        elif ahead == 0:
            title = f"The picks trailed SPY at every holding period ({pct(gap, True)} at 12 months)"
        else:
            title = f"The picks beat SPY at {ahead} of {len(hc)} holding periods ({pct(gap, True)} at 12 months)"
        long = hc.melt(id_vars="months", value_vars=["avg_return", "avg_spy_return"],
                       var_name="series", value_name="average return")
        long["series"] = long["series"].map({"avg_return": "Picks", "avg_spy_return": "SPY"})
        fig = px.line(long, x="months", y="average return", color="series", markers=True, title=title,
                      color_discrete_map={"Picks": BLUE, "SPY": GREY})
        fig.update_layout(yaxis_tickformat=".0%", xaxis_dtick=3, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(hc, hide_index=True, column_config={
            "avg_return": PCT, "avg_spy_return": PCT, "avg_excess": PCT, "hit_rate": PCT, "pnl": USD})
        st.caption(f"Uses the same **{n_curve}** mentions at every point: only those already held for "
                   f"12 months, so the curve shows the effect of time, not a changing group of picks. "
                   f"(This tab ignores the holding-period setting.)")

# 2) Follow the picks: $1,000 in every mention, never sold, vs the same dollars in SPY
with tab2:
    pc = market.portfolio_curve(chosen, prices)
    if pc.empty:
        st.warning("No mentions with a buying price for these analysts.")
    else:
        last = pc.iloc[-1]
        picks_gain = last["picks_value"] / last["invested"] - 1
        spy_gain = last["spy_value"] / last["invested"] - 1
        k1, k2, k3 = st.columns(3)
        k1.metric("Invested", money(last["invested"]), border=True)
        k2.metric("Picks portfolio", money(last["picks_value"]), delta=pct(picks_gain, True), border=True)
        k3.metric("Same dollars in SPY", money(last["spy_value"]), delta=pct(spy_gain, True), border=True)
        diff = last["picks_value"] - last["spy_value"]
        word = "more" if diff >= 0 else "less"
        title = (f"Following the picks turned {money(last['invested'])} into {money(last['picks_value'])}, "
                 f"{money(abs(diff))} {word} than SPY")
        long = pc.melt(id_vars="date", value_vars=["picks_value", "spy_value", "invested"],
                       var_name="series", value_name="dollars")
        long["series"] = long["series"].map(
            {"picks_value": "Picks portfolio", "spy_value": "Same dollars in SPY", "invested": "Dollars invested"})
        fig = px.line(long, x="date", y="dollars", color="series", title=title,
                      color_discrete_map={"Picks portfolio": BLUE, "Same dollars in SPY": GREY,
                                          "Dollars invested": "#bbbbbb"})
        fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f", legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Buy and hold from each episode to the last price date ({pc['date'].max():%b %d, %Y}). "
                   f"This tab ignores the holding-period setting.")

# 3) Analysts: average excess return vs SPY, one bar per analyst
with tab3:
    per = r.groupby("guest").size()
    max_n = int(per.max())
    min_n = st.slider("Minimum mentions per analyst", 1, max(max_n, 2), min(5, max_n))
    rows = [{"analyst": g, **market.summary(grp)} for g, grp in r.groupby("guest") if len(grp) >= min_n]
    if not rows:
        st.warning(f"No analyst has at least {min_n} mentions with these settings.")
    else:
        by = pd.DataFrame(rows).sort_values("avg_excess")
        beat = int((by["avg_excess"] > 0).sum())
        title = f"{beat} of {len(by)} analysts beat SPY on average ({horizon_label.split(' (')[0]}, {min_n}+ mentions)"
        fig = go.Figure(go.Bar(x=by["avg_excess"], y=by["analyst"], orientation="h",
                               marker_color=[BLUE if v > 0 else ORANGE for v in by["avg_excess"]],
                               text=[pct(v, True) for v in by["avg_excess"]], textposition="outside"))
        fig.update_layout(title=title, xaxis_title="Average excess return vs SPY", xaxis_tickformat=".0%",
                          height=max(300, 32 * len(by) + 120))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(by.sort_values("avg_excess", ascending=False), hide_index=True, column_config={
            "avg_return": PCT, "avg_spy_return": PCT, "avg_excess": PCT, "hit_rate": PCT, "pnl": USD})

# 4) Mentions: distribution, best and worst, and the full table
with tab4:
    share = (r["excess"] > 0).mean()
    med = r["excess"].median()
    fig = px.histogram(r, x="excess", nbins=50, color_discrete_sequence=[BLUE],
                       title=f"{pct(share)} of mentions beat SPY; the typical (median) mention was "
                             f"{pct(med, True)} vs SPY")
    fig.add_vline(x=0, line_dash="dash", line_color="black")
    fig.update_layout(xaxis_title="Excess return vs SPY", xaxis_tickformat=".0%", yaxis_title="Mentions")
    st.plotly_chart(fig, use_container_width=True)

    show = ["episode_date", "guest", "ticker", "company", "entry_date", "exit_date",
            "return", "spy_return", "excess", "pnl"]
    fmt = {"return": PCT, "spy_return": PCT, "excess": PCT, "pnl": USD,
           "episode_date": st.column_config.DateColumn(), "entry_date": st.column_config.DateColumn(),
           "exit_date": st.column_config.DateColumn()}
    left, right = st.columns(2)
    left.markdown("**Best 10 mentions vs SPY**")
    left.dataframe(r.nlargest(10, "excess")[show], hide_index=True, column_config=fmt)
    right.markdown("**Worst 10 mentions vs SPY**")
    right.dataframe(r.nsmallest(10, "excess")[show], hide_index=True, column_config=fmt)

    with st.expander(f"All mentions ({len(r)})"):
        st.dataframe(r, hide_index=True, column_config=fmt)
        st.download_button("Download as CSV", r.to_csv(index=False).encode("utf-8"),
                           file_name="final_trades_mentions.csv", mime="text/csv")

st.info("Educational analysis, not investment advice.")
