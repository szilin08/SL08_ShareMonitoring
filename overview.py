# overview.py
"""
Malaysian Property Stocks - Closing Price Comparison
Standalone Streamlit page for LBS Bina and competitors
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Property Stocks Comparison", layout="wide")

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────

BASE_COMPANY = "LBS Bina"
BASE_TICKER  = "5789.KL"

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

ALL_COMPANIES = [BASE_COMPANY] + list(COMPETITORS.keys())

CACHE_VERSION = 4           # increase this number to force cache refresh
MIN_PRICE_MYR = 0.05
MAX_PRICE_MYR = 20.0

# ────────────────────────────────────────────────
# DATA FETCHING
# ────────────────────────────────────────────────

@st.cache_data(ttl="12h", show_spinner=False)
def download_prices(
    ticker: str,
    start: date,
    end: date,
    version: int = CACHE_VERSION
) -> pd.DataFrame:
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end + timedelta(days=1),
            progress=False,
            auto_adjust=True,
            actions=False,
            repair=True
        )

        if df.empty:
            return pd.DataFrame()

        df = df[["Close"]].reset_index(names="Date")
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

        # Remove nonsense prices (Malaysian property stocks rarely go above ~10–15 MYR)
        df = df[df["Close"].between(MIN_PRICE_MYR, MAX_PRICE_MYR)]
        df = df.dropna(subset=["Date", "Close"])

        return df[["Date", "Close"]]

    except Exception:
        return pd.DataFrame()


def build_figure(df: pd.DataFrame) -> px.line:
    fig = px.line(
        df,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price Comparison – Malaysian Property Stocks (MYR)",
        height=620,
        template="plotly_dark"
    )

    fig.update_traces(
        mode="lines+markers",
        line=dict(width=2.4),
        marker=dict(size=4, opacity=0.6),
        hovertemplate="%{y:.3f} MYR<extra></extra>"
    )

    fig.update_layout(
        hovermode="x unified",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(l=40, r=40, t=90, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0.3)",
            bordercolor="rgba(255,255,255,0.15)",
            borderwidth=1
        ),
        font=dict(size=13)
    )

    fig.update_xaxes(
        title="Date",
        gridcolor="rgba(180,180,180,0.08)",
        zeroline=False
    )

    fig.update_yaxes(
        title="Closing Price (MYR)",
        tickformat=".3f",
        gridcolor="rgba(180,180,180,0.08)",
        zeroline=False,
        range=[0, None],
        rangemode="tozero"
    )

    return fig

# ────────────────────────────────────────────────
# SESSION STATE
# ────────────────────────────────────────────────

if "price_data" not in st.session_state:
    st.session_state.price_data = pd.DataFrame()
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "selected_points" not in st.session_state:
    st.session_state.selected_points = []

# ────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────

st.title("🏠 Malaysian Property Developers – Share Price Comparison")

col_start, col_end = st.columns(2)

with col_start:
    start_date = st.date_input(
        "Start date",
        value=date(2020, 1, 1),
        min_value=date(2015, 1, 1),
        key="start"
    )

with col_end:
    end_date = st.date_input(
        "End date",
        value=date.today(),
        key="end"
    )

selected = st.multiselect(
    "Select companies",
    options=ALL_COMPANIES,
    default=[BASE_COMPANY],
    key="companies"
)

if st.button("Generate Price Comparison", type="primary", use_container_width=True):

    if not selected:
        st.error("Please select at least one company.")
    elif start_date >= end_date:
        st.error("Start date must be before end date.")
    else:
        with st.spinner("Fetching data from Yahoo Finance..."):
            frames = []

            for name in selected:
                ticker = BASE_TICKER if name == BASE_COMPANY else COMPETITORS[name]
                df = download_prices(ticker, start_date, end_date)
                if not df.empty:
                    df["Company"] = name
                    frames.append(df)

            if not frames:
                st.error("No valid price data could be retrieved.")
                st.session_state.data_loaded = False
            else:
                all_data = pd.concat(frames, ignore_index=True)
                all_data = all_data.sort_values(["Company", "Date"]).reset_index(drop=True)

                # Show quick validation
                if not all_data.empty:
                    pmin = all_data["Close"].min()
                    pmax = all_data["Close"].max()
                    st.caption(f"Loaded {len(all_data):,} rows • Prices: {pmin:.3f} – {pmax:.3f} MYR")

                st.session_state.price_data = all_data
                st.session_state.data_loaded = True
                st.session_state.selected_points = []  # reset picks

# ────────────────────────────────────────────────
# CHART + INTERACTION
# ────────────────────────────────────────────────

if st.session_state.data_loaded and not st.session_state.price_data.empty:

    df = st.session_state.price_data

    st.subheader("Closing Prices")

    companies_sorted = sorted(df["Company"].unique())

    fig = build_figure(df)

    from streamlit_plotly_events import plotly_events

    clicks = plotly_events(
        fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="price_click",
        override_height=620
    )

    if clicks:
        click = clicks[0]
        curve_number = click.get("curveNumber")
        point_number = click.get("pointIndex")

        if curve_number is not None and point_number is not None:
            company = companies_sorted[curve_number]
            df_single = df[df["Company"] == company].reset_index(drop=True)

            if 0 <= point_number < len(df_single):
                row = df_single.iloc[point_number]
                point_data = {
                    "Company": company,
                    "Date": pd.to_datetime(row["Date"]),
                    "Close": float(row["Close"])
                }
                st.session_state.selected_points.append(point_data)
                st.session_state.selected_points = st.session_state.selected_points[-2:]

    picks = st.session_state.selected_points

    c1, c2, c3 = st.columns([1, 1, 0.6])

    with c1:
        st.markdown("**Pick #1**")
        if len(picks) >= 1:
            p = picks[0]
            st.caption(p["Company"])
            st.markdown(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
        else:
            st.caption("Click a point on the chart")

    with c2:
        st.markdown("**Pick #2**")
        if len(picks) >= 2:
            p = picks[1]
            st.caption(p["Company"])
            st.markdown(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
        else:
            st.caption("Click a second point")

    with c3:
        if st.button("Reset picks"):
            st.session_state.selected_points = []
            st.rerun()

    if len(picks) == 2:
        p1, p2 = picks
        st.markdown("### Difference")
        if p1["Company"] == p2["Company"]:
            delta = p2["Close"] - p1["Close"]
            pct_change = (delta / p1["Close"] * 100) if p1["Close"] != 0 else 0
            days_diff = (p2["Date"] - p1["Date"]).days

            st.write(f"**Price change**: {delta:+.3f} MYR")
            st.write(f"**Percentage change**: {pct_change:+.2f}%")
            st.write(f"**Days between**: {days_diff}")
        else:
            st.info("Select two points on the **same company** to calculate percentage change.")

else:
    st.info("Select companies and date range, then click **Generate Price Comparison**.")

st.caption("Data source: Yahoo Finance • Prices in MYR • Educational use only • Not financial advice")
