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
def fetch_close_prices(tickers, start_dt, end_dt):
    start = pd.to_datetime(start_dt)
    end = pd.to_datetime(end_dt) + pd.Timedelta(days=1)

    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        progress=False,
        threads=True,
    )

    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]]
        close.columns = [tickers[0]]

    close.index = pd.to_datetime(close.index)
    return close

# --- App ---
def main():
    st.title("📈 LBS Bina vs Competitors – Closing Price Comparison")

    # --- Filters (MAIN PAGE) ---
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        start_date = st.date_input("Start Date", value=date(2020, 1, 1))
    with col2:
        end_date = st.date_input("End Date", value=date.today())
    with col3:
        selected_competitors = st.multiselect(
            "Select Competitors",
            options=list(COMPETITORS.keys()),
            default=["S P Setia", "Sime Darby Property", "Eco World"],
        )

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    if not selected_competitors:
        st.warning("Select at least one competitor.")
        return

    # --- Fetch Data ---
    tickers = [BASE_TICKER] + [COMPETITORS[c] for c in selected_competitors]

    with st.spinner("Fetching stock prices..."):
        df_close = fetch_close_prices(tickers, start_date, end_date)

    if df_close.empty:
        st.error("No data returned. Try adjusting date range.")
        return

    # Rename tickers → company names
    rename_map = {BASE_TICKER: BASE_COMPANY}
    rename_map.update({v: k for k, v in COMPETITORS.items()})
    df_close = df_close.rename(columns=rename_map)

    # Long format for Plotly
    df_long = (
        df_close.reset_index()
        .melt(id_vars="Date", var_name="Company", value_name="Close")
        .dropna()
    )

    # --- Chart ---
    fig = px.line(
        df_long,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price Comparison (LBS Bina as Baseline)",
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Closing Price (MYR)",
        legend_title="Company",
        margin=dict(l=10, r=10, t=60, b=10),
    )

    fig.update_xaxes(rangeslider_visible=True)

    st.plotly_chart(fig, use_container_width=True)


