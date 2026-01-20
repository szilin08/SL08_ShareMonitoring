# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Property Stocks Overview", layout="wide")

# ────────────────────────────────────────────────
# Constants & Configuration
# ────────────────────────────────────────────────

BASE_NAME = "LBS Bina"
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

ALL_COMPANIES = [BASE_NAME] + list(COMPETITORS.keys())

CACHE_VERSION = 2  # ↑ when you change fetch logic or want to force refresh

# Reasonable price range for Malaysian property & construction stocks
MIN_PRICE = 0.05
MAX_PRICE = 15.0

# ────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────

def ticker_for(company: str) -> str:
    return BASE_TICKER if company == BASE_NAME else COMPETITORS.get(company, None)

@st.cache_data(show_spinner=False, ttl=3600 * 6)  # 6 hours
def fetch_close_series(
    ticker: str,
    start_dt: date,
    end_dt: date,
    _cache_version: int = CACHE_VERSION
) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(start=start_dt, end=end_dt + timedelta(days=1))
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        if "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})

        if "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame()

        out = df[["Date", "Close"]].copy()
        out["Date"] = pd.to_datetime(out["Date"]).dt.tz_localize(None)
        out["Close"] = pd.to_numeric(out["Close"], errors="coerce")

        # Filter invalid / extreme values
        out = out[out["Close"].between(MIN_PRICE, MAX_PRICE)]
        out = out.dropna(subset=["Date", "Close"])

        return out[["Date", "Close"]]

    except Exception:
        return pd.DataFrame()


def build_chart(df_all: pd.DataFrame) -> px.line:
    fig = px.line(
        df_all,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price Comparison (MYR)",
        height=580,
        template="plotly_dark"
    )

    fig.update_traces(mode="lines", line_width=2.2, hovertemplate="%{y:.3f} MYR<extra></extra>")

    fig.update_layout(
        hovermode="x unified",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )

    fig.update_xaxes(
        title="Date",
        gridcolor="rgba(255,255,255,0.06)",
        zeroline=False,
        showgrid=True
    )

    fig.update_yaxes(
        title="Closing Price (MYR)",
        tickformat=".3f",
        gridcolor="rgba(255,255,255,0.06)",
        zeroline=False,
        range=[0, None],           # start from 0, auto max
        rangemode="tozero"
    )

    return fig

# ────────────────────────────────────────────────
# Main App
# ────────────────────────────────────────────────

st.title("📊 Malaysian Property Stocks — Price Comparison")

# Persistent session state
if "ov_df_all" not in st.session_state:
    st.session_state.ov_df_all = pd.DataFrame()
if "ov_generated" not in st.session_state:
    st.session_state.ov_generated = False
if "ov_picks" not in st.session_state:
    st.session_state.ov_picks = []

# ── Inputs ───────────────────────────────────────

col1, col2 = st.columns([1, 1])

with col1:
    start_dt = st.date_input(
        "Start date",
        value=date(2020, 1, 1),
        min_value=date(2010, 1, 1),
        key="ov_start"
    )

with col2:
    end_dt = st.date_input(
        "End date",
        value=date.today(),
        key="ov_end"
    )

selected_companies = st.multiselect(
    "Select companies to compare",
    options=ALL_COMPANIES,
    default=[BASE_NAME],
    key="ov_companies"
)

# ── Generate Button ──────────────────────────────

if st.button("Generate Overview", type="primary", use_container_width=True):

    if not selected_companies:
        st.error("Please select at least one company.")
        st.stop()

    if start_dt >= end_dt:
        st.error("Start date must be before end date.")
        st.stop()

    with st.spinner("Fetching historical prices..."):
        dfs = []
        for comp in selected_companies:
            ticker = ticker_for(comp)
            if not ticker:
                continue
            df = fetch_close_series(ticker, start_dt, end_dt)
            if not df.empty:
                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.error("No valid price data returned for the selected companies and date range.")
            st.session_state.ov_generated = False
            st.session_state.ov_df_all = pd.DataFrame()
            st.session_state.ov_picks = []
        else:
            df_all = pd.concat(dfs, ignore_index=True)
            df_all = df_all[["Date", "Close", "Company"]].copy()
            df_all["Close"] = pd.to_numeric(df_all["Close"], errors="coerce").round(4)
            df_all = df_all.dropna(subset=["Date", "Close", "Company"])
            df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

            # Quick debug info
            if not df_all.empty:
                price_min = df_all["Close"].min()
                price_max = df_all["Close"].max()
                st.caption(f"Loaded {len(df_all):,} rows | Price range: {price_min:.3f} – {price_max:.3f} MYR")

            st.session_state.ov_df_all = df_all
            st.session_state.ov_generated = True
            st.session_state.ov_picks = []   # reset picks on new data

# ── Display Chart & Interaction ──────────────────

if st.session_state.ov_generated and not st.session_state.ov_df_all.empty:

    df_all = st.session_state.ov_df_all

    st.subheader("Closing Price Comparison")

    company_order = sorted(df_all["Company"].unique())  # consistent order

    fig = build_chart(df_all)

    from streamlit_plotly_events import plotly_events

    clicked_points = plotly_events(
        fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="ov_price_clicks",
        override_height=580
    )

    # Handle clicks
    if clicked_points:
        c = clicked_points[0]
        curve_num = c.get("curveNumber")
        point_idx = c.get("pointIndex")

        if curve_num is not None and point_idx is not None:
            comp = company_order[curve_num]
            df_comp = df_all[df_all["Company"] == comp].reset_index(drop=True)

            if 0 <= point_idx < len(df_comp):
                row = df_comp.iloc[point_idx]
                pick = {
                    "Company": comp,
                    "Date": pd.to_datetime(row["Date"]),
                    "Close": float(row["Close"])
                }
                st.session_state.ov_picks.append(pick)
                st.session_state.ov_picks = st.session_state.ov_picks[-2:]  # keep last 2

    # Show picked points
    picks = st.session_state.ov_picks

    c1, c2, c3 = st.columns([1, 1, 0.6])

    with c1:
        st.markdown("**Pick #1**")
        if len(picks) >= 1:
            p = picks[0]
            st.caption(p["Company"])
            st.write(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
        else:
            st.caption("Click any point on the chart")

    with c2:
        st.markdown("**Pick #2**")
        if len(picks) >= 2:
            p = picks[1]
            st.caption(p["Company"])
            st.write(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
        else:
            st.caption("Click a second point")

    with c3:
        if st.button("Reset picks", key="ov_reset_picks"):
            st.session_state.ov_picks = []
            st.rerun()

    # Show difference if two points picked
    if len(picks) == 2:
        p1, p2 = picks
        if p1["Company"] == p2["Company"]:
            diff = p2["Close"] - p1["Close"]
            pct = (diff / p1["Close"] * 100) if p1["Close"] != 0 else 0
            days = (p2["Date"] - p1["Date"]).days

            st.markdown("### Price Change")
            st.write(f"**Change:** {diff:+.3f} MYR")
            st.write(f"**% Change:** {pct:+.2f}%")
            st.write(f"**Period:** {days} day{'s' if days != 1 else ''}")
        else:
            st.info("Tip: For percentage change calculation, pick two points on the **same company** line.")

else:
    st.info("Select companies and date range, then click **Generate Overview** to load the chart.")

st.caption("Data from Yahoo Finance • Prices in MYR • Not investment advice")
