# overview.py
# ───────────────────────────────────────────────────────────────
# Malaysian Property Stocks Closing Price Comparison
# Standalone Streamlit page – do NOT call via overview.main()
# ───────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="Property Stocks Overview", layout="wide")

# ─── Configuration ───────────────────────────────────────────────

BASE_NAME   = "LBS Bina"
BASE_TICKER = "5789.KL"

COMPETITORS = {
    "S P Setia"         : "8664.KL",
    "Sime Darby Property": "5288.KL",
    "Eco World"         : "8206.KL",
    "UEM Sunrise"       : "5148.KL",
    "IOI Properties"    : "5249.KL",
    "Mah Sing"          : "8583.KL",
    "IJM Corporation"   : "3336.KL",
    "Sunway"            : "5211.KL",
    "Gamuda"            : "5398.KL",
    "OSK Holdings"      : "5053.KL",
    "UOA Development"   : "5200.KL",
}

ALL_COMPANIES = [BASE_NAME] + list(COMPETITORS.keys())

CACHE_VERSION = 3               # bump → forces cache refresh
MIN_PRICE     = 0.05
MAX_PRICE     = 20.0            # generous upper bound for Malaysian property stocks

# ─── Helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl="6h", show_spinner=False)
def get_closing_prices(
    ticker: str,
    start: date,
    end: date,
    _version: int = CACHE_VERSION
) -> pd.DataFrame:
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end + timedelta(days=1),
            progress=False,
            auto_adjust=True,
            actions=False
        )
        if df.empty:
            return pd.DataFrame()

        df = df[["Close"]].reset_index()
        df["Date"]  = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna().rename(columns={"Close": "Close"})

        # Filter obviously wrong prices (KLSE property stocks are cheap)
        df = df[df["Close"].between(MIN_PRICE, MAX_PRICE)]

        return df[["Date", "Close"]]

    except Exception:
        return pd.DataFrame()


def create_price_chart(df: pd.DataFrame) -> px.line:
    fig = px.line(
        df,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price Comparison (MYR)",
        height=600,
        template="plotly_dark"
    )

    fig.update_traces(
        mode="lines",
        line_width=2.3,
        hovertemplate="%{y:.3f} MYR<extra></extra>"
    )

    fig.update_layout(
        hovermode="x unified",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(l=30, r=30, t=70, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    fig.update_xaxes(
        title="Date",
        gridcolor="rgba(200,200,200,0.08)",
        zeroline=False
    )

    fig.update_yaxes(
        title="Price (MYR)",
        tickformat=".3f",
        gridcolor="rgba(200,200,200,0.08)",
        zeroline=False,
        range=[0, None],
        rangemode="tozero"
    )

    return fig

# ─── Main UI ─────────────────────────────────────────────────────

st.title("📈 Malaysian Property Stocks — Price Overview")

# Session state
if "df_prices" not in st.session_state:
    st.session_state.df_prices = pd.DataFrame()
if "generated" not in st.session_state:
    st.session_state.generated = False
if "picked_points" not in st.session_state:
    st.session_state.picked_points = []

# Inputs ────────────────────────────────────────────────────────

c1, c2 = st.columns([1,1])

with c1:
    start_date = st.date_input(
        "Start date",
        value=date(2020, 1, 1),
        min_value=date(2015, 1, 1),
        key="start_date"
    )

with c2:
    end_date = st.date_input(
        "End date",
        value=date.today(),
        key="end_date"
    )

companies = st.multiselect(
    "Companies to compare",
    options=ALL_COMPANIES,
    default=[BASE_NAME],
    key="companies"
)

# Generate button
if st.button("Load & Compare Prices", type="primary", use_container_width=True):

    if not companies:
        st.error("Select at least one company.")
        st.stop()

    if start_date >= end_date:
        st.error("Start date must be before end date.")
        st.stop()

    with st.spinner("Downloading prices from Yahoo Finance…"):
        frames = []

        for company in companies:
            ticker = BASE_TICKER if company == BASE_NAME else COMPETITORS[company]
            df = get_closing_prices(ticker, start_date, end_date)
            if not df.empty:
                df["Company"] = company
                frames.append(df)

        if not frames:
            st.error("No valid data returned. Try a different date range or fewer companies.")
            st.session_state.generated = False
            st.session_state.df_prices = pd.DataFrame()
        else:
            combined = pd.concat(frames, ignore_index=True)
            combined = combined[["Date", "Close", "Company"]]
            combined = combined.sort_values(["Company", "Date"]).reset_index(drop=True)

            # Debug line (visible once)
            min_p = combined["Close"].min()
            max_p = combined["Close"].max()
            st.caption(f"Loaded {len(combined):,} data points  •  Price range: {min_p:.3f} – {max_p:.3f} MYR")

            st.session_state.df_prices   = combined
            st.session_state.generated   = True
            st.session_state.picked_points = []   # reset picks

# ─── Chart & Interaction ─────────────────────────────────────────

if st.session_state.generated and not st.session_state.df_prices.empty:

    df = st.session_state.df_prices

    st.subheader("Closing Price Comparison")

    # Keep legend / curve order stable
    company_list = sorted(df["Company"].unique())

    fig = create_price_chart(df)

    from streamlit_plotly_events import plotly_events

    selected_points = plotly_events(
        fig,
        click_event=True,
        key="price_click_events",
        override_height=600
    )

    # Process click
    if selected_points:
        pt = selected_points[0]
        curve = pt.get("curveNumber")
        idx   = pt.get("pointIndex")

        if curve is not None and idx is not None and 0 <= curve < len(company_list):
            comp = company_list[curve]
            df_one = df[df["Company"] == comp].reset_index(drop=True)

            if 0 <= idx < len(df_one):
                row = df_one.iloc[idx]
                pick = {
                    "Company": comp,
                    "Date"   : pd.to_datetime(row["Date"]),
                    "Price"  : float(row["Close"])
                }
                st.session_state.picked_points.append(pick)
                st.session_state.picked_points = st.session_state.picked_points[-2:]

    picks = st.session_state.picked_points

    colA, colB, colC = st.columns([1, 1, 0.6])

    with colA:
        st.markdown("**Point 1**")
        if len(picks) >= 1:
            p = picks[0]
            st.caption(p["Company"])
            st.write(f"{p['Date'].date()} • **{p['Price']:.3f}** MYR")
        else:
            st.caption("← click any point")

    with colB:
        st.markdown("**Point 2**")
        if len(picks) >= 2:
            p = picks[1]
            st.caption(p["Company"])
            st.write(f"{p['Date'].date()} • **{p['Price']:.3f}** MYR")
        else:
            st.caption("← click second point")

    with colC:
        if st.button("Clear picks"):
            st.session_state.picked_points = []
            st.rerun()

    # Show difference
    if len(picks) == 2:
        a, b = picks
        if a["Company"] == b["Company"]:
            change    = b["Price"] - a["Price"]
            pct       = change / a["Price"] * 100 if a["Price"] else 0
            day_count = (b["Date"] - a["Date"]).days

            st.markdown("#### Change between picks")
            st.write(f"**Δ Price**   : {change:+.3f} MYR")
            st.write(f"**% Change**  : {pct:+.2f}%")
            st.write(f"**Days**      : {day_count}")
        else:
            st.info("For % change calculation pick two points on the **same line**.")

else:
    st.info("Choose companies and date range → click **Load & Compare Prices**")

st.caption("• Data: Yahoo Finance  •  Prices in MYR  •  For informational use only")
