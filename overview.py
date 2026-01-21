# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import plotly.express as px

# --- Yahoo Finance user-agent workaround (helps reduce empty/blocked responses) ---
try:
    yf.utils.get_user_agent = lambda: (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
except Exception:
    pass

st.set_page_config(page_title="Overview – Competitor Monitoring", layout="wide")

# --- Competitors list ---
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

# --- Data fetch ---
@st.cache_data(ttl=60 * 30, show_spinner=False)  # cache for 30 mins
def fetch_close_prices(tickers: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    """
    Returns a wide dataframe: index=Date, columns=ticker, values=Close
    end_dt is inclusive in UI, but yfinance end is exclusive, so add 1 day.
    """
    start = pd.to_datetime(start_dt)
    end_exclusive = pd.to_datetime(end_dt) + pd.Timedelta(days=1)

    # Use yf.download for multi-ticker (faster + more stable)
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end_exclusive,
        progress=False,
        auto_adjust=False,
        group_by="column",
        threads=True,
    )

    if data is None or data.empty:
        return pd.DataFrame()

    # If multiple tickers -> columns are MultiIndex (field, ticker)
    # If single ticker -> columns are single-level
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = [tickers[0]]

    close.index = pd.to_datetime(close.index).date
    close = close.sort_index()
    return close

def normalize_base_100(close_wide: pd.DataFrame) -> pd.DataFrame:
    """Normalize each series so first valid value = 100."""
    norm = close_wide.copy()
    for c in norm.columns:
        first_valid = norm[c].dropna().iloc[0] if not norm[c].dropna().empty else None
        if first_valid and first_valid != 0:
            norm[c] = (norm[c] / first_valid) * 100
    return norm

def main():
    st.title("📈 Overview – Competitor Closing Price Comparison")

    # --- Sidebar controls ---
    with st.sidebar:
        st.header("Filters")

        start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="overview_start")
        end_dt = st.date_input("End date", value=date.today(), key="overview_end")

        if start_dt > end_dt:
            st.error("Start date must be before end date.")
            st.stop()

        selected = st.multiselect(
            "Select competitors",
            options=list(COMPETITORS.keys()),
            default=["S P Setia", "Sime Darby Property", "Eco World"],
        )

        normalize = st.toggle("Normalize (Base = 100)", value=True, help="Makes different price levels comparable.")
        show_range = st.checkbox("Show range slider", value=True)

        run = st.button("Get Data", use_container_width=True)

    if not run:
        st.info("Pick competitors + dates, then click **Get Data**.")
        return

    if not selected:
        st.warning("Select at least 1 competitor.")
        return

    tickers = [COMPETITORS[name] for name in selected]

    with st.spinner("Fetching prices..."):
        close_wide = fetch_close_prices(tickers, start_dt, end_dt)

    if close_wide.empty:
        st.error("No data returned. Try a shorter range, or different tickers.")
        return

    # Map ticker -> company name for display
    ticker_to_name = {v: k for k, v in COMPETITORS.items()}

    close_wide = close_wide.rename(columns=ticker_to_name)

    if normalize:
        plot_wide = normalize_base_100(close_wide)
        y_label = "Indexed Close (Base = 100)"
        title = "Closing Price Comparison (Normalized)"
    else:
        plot_wide = close_wide
        y_label = "Close (MYR)"
        title = "Closing Price Comparison"

    # Convert to long for plotly express
    df_long = (
        plot_wide.reset_index(names="Date")
        .melt(id_vars="Date", var_name="Company", value_name="Close")
        .dropna()
    )

    fig = px.line(
        df_long,
        x="Date",
        y="Close",
        color="Company",
        title=title,
    )
    fig.update_layout(
        yaxis_title=y_label,
        xaxis_title="Date",
        legend_title="Company",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    if show_range:
        fig.update_xaxes(rangeslider_visible=True)

    st.plotly_chart(fig, use_container_width=True)



