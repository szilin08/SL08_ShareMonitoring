# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import plotly.express as px

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Overview – Competitor Monitoring", layout="wide")

BASE_COMPANY = "LBS Bina"
BASE_TICKER = "5789.KL"

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

ALL_COMPANIES = {BASE_COMPANY: BASE_TICKER, **COMPETITORS}

# Yahoo Finance user-agent workaround (helps reduce empty/blocked responses)
try:
    yf.utils.get_user_agent = lambda: (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
except Exception:
    pass


# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_close_prices(tickers: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    """
    Returns a wide dataframe:
      index = DatetimeIndex
      columns = tickers
      values = Close
    end_dt is inclusive in UI; yfinance end is exclusive => +1 day
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

    # MultiIndex (field, ticker) when multiple tickers; otherwise flat columns
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            return pd.DataFrame()
        close = data["Close"].copy()
    else:
        if "Close" not in data.columns:
            return pd.DataFrame()
        close = data[["Close"]].copy()
        close.columns = [tickers[0]]

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    return close


def compute_perf_table(close_wide: pd.DataFrame) -> pd.DataFrame:
    """
    Start vs End + Peak for each company in the selected period.
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
                "% Diff": None,
                "Peak Close": None,
                "Peak Date": None,
            })
            continue

        start_close = float(s.iloc[0])
        end_close = float(s.iloc[-1])
        diff = end_close - start_close
        pct = (diff / start_close) * 100 if start_close != 0 else None

        peak_close = float(s.max())
        peak_dt = s.idxmax()
        peak_date = peak_dt.date() if hasattr(peak_dt, "date") else peak_dt

        rows.append({
            "Company": company,
            "Start Close": start_close,
            "End Close": end_close,
            "Diff (RM)": diff,
            "% Diff": pct,
            "Peak Close": peak_close,
            "Peak Date": peak_date,
        })

    df = pd.DataFrame(rows)

    # Sort by % diff desc (NaNs at bottom)
    df["_sort"] = df["% Diff"].fillna(-10**18)
    df = df.sort_values("_sort", ascending=False).drop(columns="_sort")

    return df


def enforce_base_selected(selected: list[str]) -> list[str]:
    """
    Ensures LBS is always present and is always first.
    """
    cleaned = [x for x in selected if x != BASE_COMPANY]
    return [BASE_COMPANY] + cleaned


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────
def main():
    st.title("📈 Stock Overview — LBS Bina (Always Selected)")

    # Start & End on same line
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start Date", value=date(2020, 1, 1), key="overview_start")
    with c2:
        end_date = st.date_input("End Date", value=date.today(), key="overview_end")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Companies on next line (LBS always included + locked)
    if "company_selector" not in st.session_state:
        st.session_state.company_selector = [BASE_COMPANY]

    selected_companies = st.multiselect(
        "Select Companies (LBS Bina is always included)",
        options=list(ALL_COMPANIES.keys()),
        default=st.session_state.company_selector,
        key="company_selector",
    )

    selected_companies = enforce_base_selected(selected_companies)
    st.session_state.company_selector = selected_companies  # force it in the widget state

    # Button to fetch
    get_data = st.button("Get Data", type="primary")

    if not get_data:
        st.info("Select dates + companies, then click **Get Data**.")
        return

    # Build ticker list
    tickers = [ALL_COMPANIES[name] for name in selected_companies]

    with st.spinner("Fetching closing prices..."):
        close_wide = fetch_close_prices(tickers, start_date, end_date)

    if close_wide.empty:
        st.error("No data returned. Try again, or shorten the date range.")
        return

    # Rename ticker columns -> company names
    ticker_to_company = {v: k for k, v in ALL_COMPANIES.items()}
    close_wide = close_wide.rename(columns=ticker_to_company)

    # Make sure LBS is actually present (sometimes yfinance fails one ticker)
    if BASE_COMPANY not in close_wide.columns:
        st.error("LBS Bina data did not return from Yahoo Finance for this period. Try a shorter range.")
        return

    # Keep column order as user-selected (LBS first)
    ordered_cols = [c for c in selected_companies if c in close_wide.columns]
    close_wide = close_wide[ordered_cols]

    # ── Metrics table
    st.subheader("📌 Start vs End Performance (with Peak)")
    metrics = compute_perf_table(close_wide)

    pretty = metrics.copy()
    pretty["Start Close"] = pretty["Start Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["End Close"] = pretty["End Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["Diff (RM)"] = pretty["Diff (RM)"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["% Diff"] = pretty["% Diff"].map(lambda x: f"{x:,.2f}%" if pd.notna(x) else "—")
    pretty["Peak Close"] = pretty["Peak Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["Peak Date"] = pretty["Peak Date"].map(lambda x: str(x) if pd.notna(x) else "—")

    st.dataframe(pretty, use_container_width=True, hide_index=True)

    # ── Chart
    st.subheader("📉 Closing Price Comparison")

    df_long = (
        close_wide.reset_index()
        .rename(columns={"index": "Date"})
        .melt(id_vars="Date", var_name="Company", value_name="Close")
        .dropna()
    )

    fig = px.line(
        df_long,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price Comparison",
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Closing Price (MYR)",
        legend_title="Company",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(rangeslider_visible=True)

    st.plotly_chart(fig, use_container_width=True)

