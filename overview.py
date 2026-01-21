# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import plotly.express as px

# --- Yahoo Finance User-Agent Fix ---
try:
    yf.utils.get_user_agent = lambda: (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
except Exception:
    pass

st.set_page_config(page_title="Overview – Competitor Monitoring", layout="wide")

# --- Base Company ---
BASE_COMPANY = "LBS Bina"
BASE_TICKER = "5789.KL"

# --- Competitors ---
COMPETITORS = {
    "S P Setia": "8664.KL",
    "Sime Darby Property": "5288.KL",
    "Eco World": "8206.KL",
    "UEM Sunrise": "5148.KL",
    "IOI Properties": "5249.KL",
    "Mah Sing": "8583.KL",
    "IJM Corporation": "3336.KL",
    "Sunway": "5211.KL",
    "Gamuda": "5398.KL",
    "OSK Holdings": "5053.KL",
    "UOA Development": "5200.KL",
}

# --- Data Fetch ---
@st.cache_data(ttl=60 * 30)
def fetch_close_prices(tickers: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    """
    Returns wide dataframe:
      index = Date (datetime)
      columns = tickers
      values = Close
    """
    start = pd.to_datetime(start_dt)
    end_exclusive = pd.to_datetime(end_dt) + pd.Timedelta(days=1)

    data = yf.download(
        tickers=tickers,
        start=start,
        end=end_exclusive,
        progress=False,
        threads=True,
        group_by="column",
        auto_adjust=False,
    )

    if data is None or data.empty:
        return pd.DataFrame()

    # MultiIndex if multiple tickers
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            return pd.DataFrame()
        close = data["Close"].copy()
    else:
        # single ticker case
        if "Close" not in data.columns:
            return pd.DataFrame()
        close = data[["Close"]].copy()
        close.columns = [tickers[0]]

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    return close


def compute_start_end_metrics(close_wide: pd.DataFrame) -> pd.DataFrame:
    """
    For each company column:
      start_close = first non-null
      end_close   = last non-null
      diff        = end - start
      pct_diff    = diff / start
    """
    rows = []
    for company in close_wide.columns:
        s = close_wide[company].dropna()
        if s.empty:
            rows.append({
                "Company": company,
                "Start Close": None,
                "End Close": None,
                "Diff (RM)": None,
                "% Diff": None
            })
            continue

        start_close = float(s.iloc[0])
        end_close = float(s.iloc[-1])
        diff = end_close - start_close
        pct = (diff / start_close) * 100 if start_close != 0 else None

        rows.append({
            "Company": company,
            "Start Close": start_close,
            "End Close": end_close,
            "Diff (RM)": diff,
            "% Diff": pct
        })

    dfm = pd.DataFrame(rows)

    # sort by % diff desc, keep NaNs at bottom
    dfm["_sort"] = dfm["% Diff"].fillna(-10**18)
    dfm = dfm.sort_values("_sort", ascending=False).drop(columns=["_sort"])

    return dfm


def main():
    st.title("📈 LBS Bina vs Competitors — Closing Price Comparison")

    # --- Filters layout (main page) ---
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start Date", value=date(2020, 1, 1), key="overview_start")
    with c2:
        end_date = st.date_input("End Date", value=date.today(), key="overview_end")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    st.markdown("**Base (always included):** `LBS Bina (5789.KL)`")

    selected_competitors = st.multiselect(
        "Select Competitors (LBS is always included)",
        options=list(COMPETITORS.keys()),
        default=["S P Setia", "Sime Darby Property", "Eco World"],
        key="overview_competitors",
    )

    if not selected_competitors:
        st.warning("Select at least one competitor.")
        return

    # --- Build ticker list (LBS ALWAYS FIRST) ---
    tickers = [BASE_TICKER] + [COMPETITORS[c] for c in selected_competitors]

    with st.spinner("Fetching stock prices..."):
        close_wide = fetch_close_prices(tickers, start_date, end_date)

    if close_wide.empty:
        st.error("No data returned (Yahoo sometimes blocks). Try a shorter date range.")
        return

    # --- Rename tickers -> names ---
    rename_map = {BASE_TICKER: BASE_COMPANY}
    rename_map.update({v: k for k, v in COMPETITORS.items()})
    close_wide = close_wide.rename(columns=rename_map)

    # Ensure LBS column exists (otherwise show a loud error)
    if BASE_COMPANY not in close_wide.columns:
        st.error(
            "LBS Bina data didn't come back from Yahoo Finance for the selected range.\n\n"
            "Try:\n"
            "- shorter date range\n"
            "- run again\n"
            "- or check ticker `5789.KL` availability"
        )
        st.dataframe(close_wide.head())
        return

    # --- Metrics table ---
    st.subheader("📌 Start vs End Performance (Selected Range)")
    metrics = compute_start_end_metrics(close_wide)

    # Pretty formatting for display
    show = metrics.copy()
    show["Start Close"] = show["Start Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    show["End Close"] = show["End Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    show["Diff (RM)"] = show["Diff (RM)"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    show["% Diff"] = show["% Diff"].map(lambda x: f"{x:,.2f}%" if pd.notna(x) else "—")

    st.dataframe(show, use_container_width=True, hide_index=True)

    # --- Chart data (long form) ---
    df_long = (
        close_wide.reset_index()
        .rename(columns={"index": "Date"})
        .melt(id_vars="Date", var_name="Company", value_name="Close")
        .dropna()
    )

    # --- Chart ---
    st.subheader("📉 Closing Price Comparison")
    fig = px.line(
        df_long,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price (LBS Bina always included)",
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Closing Price (MYR)",
        legend_title="Company",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(rangeslider_visible=True)

    st.plotly_chart(fig, use_container_width=True)


