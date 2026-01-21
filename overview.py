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

# --- Base ---
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

# Full universe shown in selector (includes base)
ALL_COMPANIES = {BASE_COMPANY: BASE_TICKER, **COMPETITORS}

# --- Data Fetch ---
@st.cache_data(ttl=60 * 30)
def fetch_close_prices(tickers: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
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

    # MultiIndex when multiple tickers
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

def compute_start_end_metrics(close_wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for company in close_wide.columns:
        s = close_wide[company].dropna()
        if s.empty:
            rows.append({"Company": company, "Start Close": None, "End Close": None, "Diff (RM)": None, "% Diff": None})
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
    dfm["_sort"] = dfm["% Diff"].fillna(-10**18)
    dfm = dfm.sort_values("_sort", ascending=False).drop(columns=["_sort"])
    return dfm

def main():
    st.title("📈 Stock Overview — LBS Bina as Base (Always Selected)")

    # --- Filters row: start/end ---
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Start Date", value=date(2020, 1, 1), key="overview_start")
    with c2:
        end_date = st.date_input("End Date", value=date.today(), key="overview_end")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # --- Company selector (next line) ---
    # Initialize session state default selection
    if "company_selection" not in st.session_state:
        st.session_state.company_selection = [BASE_COMPANY]

    selected_companies = st.multiselect(
        "Select companies (LBS Bina is always included)",
        options=list(ALL_COMPANIES.keys()),
        default=st.session_state.company_selection,
        key="company_selector",
    )

    # Enforce LBS always selected
    if BASE_COMPANY not in selected_companies:
        selected_companies = [BASE_COMPANY] + selected_companies
        st.session_state.company_selector = selected_companies

    # Persist selection
    st.session_state.company_selection = selected_companies

    # Button
    get_data = st.button("Get Data", type="primary")

    if not get_data:
        st.info("Choose dates + companies, then click **Get Data**.")
        return

    # Build tickers list
    tickers = [ALL_COMPANIES[name] for name in selected_companies]

    with st.spinner("Fetching closing prices..."):
        close_wide = fetch_close_prices(tickers, start_date, end_date)

    if close_wide.empty:
        st.error("No data returned. Try again or shorten the date range.")
        return

    # Rename ticker columns -> company names
    ticker_to_company = {v: k for k, v in ALL_COMPANIES.items()}
    close_wide = close_wide.rename(columns=ticker_to_company)

    # Ensure LBS exists in output
    if BASE_COMPANY not in close_wide.columns:
        st.error("LBS Bina data did not return from Yahoo for this period. Try a shorter range.")
        return

    # --- Metrics ---
    st.subheader("📌 Start vs End Performance")
    metrics = compute_start_end_metrics(close_wide)

    pretty = metrics.copy()
    pretty["Start Close"] = pretty["Start Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["End Close"] = pretty["End Close"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["Diff (RM)"] = pretty["Diff (RM)"].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "—")
    pretty["% Diff"] = pretty["% Diff"].map(lambda x: f"{x:,.2f}%" if pd.notna(x) else "—")

    st.dataframe(pretty, use_container_width=True, hide_index=True)

    # --- Chart ---
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


