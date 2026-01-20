# overview.py
# Streamlit: Overview Dashboard
# - Closing Price comparison (click 2 points -> show Δ + %)
# - Revenue vs PATMI (from financials.py)
# - Sales placeholder

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from streamlit_plotly_events import plotly_events

# -------------------------
# OPTIONAL: your financials helpers
# -------------------------
try:
    from financials import get_revenue_data, get_patmi_data
    FINANCIALS_OK = True
except Exception:
    FINANCIALS_OK = False
    get_revenue_data = None
    get_patmi_data = None


# -------------------------
# Config
# -------------------------
BASE_COMPANY_NAME = "LBS Bina"
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

ALL_COMPANIES = [BASE_COMPANY_NAME] + list(COMPETITORS.keys())


# -------------------------
# Data fetch
# -------------------------
@st.cache_data(show_spinner=False)
def fetch_history(ticker: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start_dt, end=end_dt)

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()

    if "Datetime" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    # 🔥 NORMALISE BURSA PRICES
    # If prices look like 300–1000+, convert to RM
    if df["Close"].max() > 20:   # RM stocks never trade >20 normally
        df["Close"] = df["Close"] / 1000

    df = df.dropna(subset=["Date", "Close"])
    return df



def _ticker_for_company(company: str) -> str:
    return BASE_TICKER if company == BASE_COMPANY_NAME else COMPETITORS[company]


# -------------------------
# Closing Price chart + 2-point pick
# -------------------------
def closing_price_chart_with_picks(df_all: pd.DataFrame):
    st.subheader("Closing Price Comparison")

    if df_all is None or df_all.empty:
        st.warning("No data returned for the selected period / companies.")
        return

    df_all = df_all.copy()
    df_all["Date"] = pd.to_datetime(df_all["Date"], errors="coerce")
    df_all["Close"] = pd.to_numeric(df_all["Close"], errors="coerce")
    df_all = df_all.dropna(subset=["Date", "Close", "Company"])

    # Stable order so curveNumber mapping is consistent
    company_order = sorted(df_all["Company"].unique().tolist())
    df_all["Company"] = pd.Categorical(df_all["Company"], categories=company_order, ordered=True)
    df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

    if "picked_points_close" not in st.session_state:
        st.session_state.picked_points_close = []

    # Build chart (match your screenshot style)
    fig = px.line(
        df_all,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price",
    )
    fig.update_traces(mode="lines")
    fig.update_layout(
        hovermode="x unified",
        height=500,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="Company",
    )
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Close", tickformat=".4f")

    clicked = plotly_events(
        fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="close_price_plotly_events",
        override_height=500,
    )

    if clicked:
        c = clicked[0]
        curve = c.get("curveNumber")
        point_index = c.get("pointIndex")

        if curve is not None and point_index is not None:
            companies_in_plot = list(df_all["Company"].cat.categories)

            if 0 <= curve < len(companies_in_plot):
                company = companies_in_plot[curve]
                df_comp = df_all[df_all["Company"] == company].reset_index(drop=True)

                if 0 <= point_index < len(df_comp):
                    row = df_comp.loc[point_index]
                    picked = {
                        "Company": company,
                        "Date": pd.to_datetime(row["Date"]),
                        "Close": float(row["Close"]),
                    }
                    st.session_state.picked_points_close.append(picked)
                    st.session_state.picked_points_close = st.session_state.picked_points_close[-2:]

    picks = st.session_state.picked_points_close
    a, b, c = st.columns([1.2, 1.2, 0.7])

    with a:
        st.write("**Pick #1**")
        if len(picks) >= 1:
            p1 = picks[0]
            st.caption(p1["Company"])
            st.write(f"{p1['Date'].date()} • **{p1['Close']:.4f}**")
        else:
            st.caption("Click a point")

    with b:
        st.write("**Pick #2**")
        if len(picks) >= 2:
            p2 = picks[1]
            st.caption(p2["Company"])
            st.write(f"{p2['Date'].date()} • **{p2['Close']:.4f}**")
        else:
            st.caption("Click a second point")

    with c:
        if st.button("Reset picks", key="reset_close_picks"):
            st.session_state.picked_points_close = []
            st.rerun()

    if len(picks) == 2:
        p1, p2 = picks
        diff = p2["Close"] - p1["Close"]
        pct = (diff / p1["Close"]) * 100 if p1["Close"] else 0.0
        days = int((p2["Date"] - p1["Date"]).days)

        st.markdown("### Difference")
        st.write(f"**Δ Close:** {diff:+.4f}")
        st.write(f"**% Change:** {pct:+.2f}%")
        st.write(f"**Days between:** {days} day(s)")

        if p1["Company"] != p2["Company"]:
            st.warning("Pick both points on the same company line for a clean A→B move.")


# -------------------------
# Revenue vs PATMI chart
# -------------------------
def revenue_patmi_chart(selected_companies, start_dt, end_dt):
    st.subheader("💰 Revenue vs PATMI Comparison")

    if not FINANCIALS_OK:
        st.info("financials.py not available / not implemented. Skipping Revenue vs PATMI.")
        return

    rev_df = get_revenue_data(selected_companies, start_dt, end_dt)
    patmi_df = get_patmi_data(selected_companies, start_dt, end_dt)

    if rev_df is None or patmi_df is None or rev_df.empty or patmi_df.empty:
        st.warning("No Revenue or PATMI data available for the selected period.")
        return

    combined = rev_df.merge(patmi_df, on="Company", how="inner").copy()
    if combined.empty:
        st.warning("Revenue and PATMI couldn't be matched (Company keys mismatch).")
        return

    combined["Revenue_M"] = (combined["Revenue"] / 1_000).round(2)
    combined["PATMI_M"] = (combined["PATMI"] / 1_000).round(2)

    fig = go.Figure(
        data=[
            go.Bar(
                name="Revenue",
                x=combined["Company"],
                y=combined["Revenue"],
                text=combined["Revenue_M"].astype(str) + "M",
                textposition="outside",
            ),
            go.Bar(
                name="PATMI",
                x=combined["Company"],
                y=combined["PATMI"],
                text=combined["PATMI_M"].astype(str) + "M",
                textposition="outside",
            ),
        ]
    )

    fig.update_layout(
        barmode="group",
        title=f"Revenue vs PATMI ({start_dt} → {end_dt})",
        xaxis_title="Company",
        yaxis_title="Amount (RM)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=520,
        margin=dict(l=10, r=10, t=60, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------------
# Main
# -------------------------
def main():
    st.title("📊 Overview Dashboard")

    # Persistent state (prevents reset on click)
    if "overview_generated" not in st.session_state:
        st.session_state.overview_generated = False
    if "overview_df_all" not in st.session_state:
        st.session_state.overview_df_all = pd.DataFrame()
    if "overview_selected_companies" not in st.session_state:
        st.session_state.overview_selected_companies = [BASE_COMPANY_NAME]
    if "overview_start_dt" not in st.session_state:
        st.session_state.overview_start_dt = date(2020, 1, 1)
    if "overview_end_dt" not in st.session_state:
        st.session_state.overview_end_dt = date.today()

    start_dt = st.date_input("Start date", value=st.session_state.overview_start_dt, key="overview_start")
    end_dt = st.date_input("End date", value=st.session_state.overview_end_dt, key="overview_end")

    selected_companies = st.multiselect(
        "Select companies",
        options=ALL_COMPANIES,
        default=st.session_state.overview_selected_companies,
        key="overview_companies",
    )

    st.session_state.overview_start_dt = start_dt
    st.session_state.overview_end_dt = end_dt
    st.session_state.overview_selected_companies = selected_companies

    if st.button("Generate Overview", type="primary"):
        if not selected_companies:
            st.warning("Pick at least one company.")
            st.session_state.overview_generated = False
            st.session_state.overview_df_all = pd.DataFrame()
            st.rerun()

        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            st.session_state.overview_generated = False
            st.session_state.overview_df_all = pd.DataFrame()
            st.rerun()

        dfs = []
        with st.spinner("Fetching price data..."):
            for comp in selected_companies:
                ticker = _ticker_for_company(comp)
                df = fetch_history(ticker, start_dt, end_dt + pd.Timedelta(days=1))
                if df.empty:
                    continue
                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.warning("No stock data fetched. Check tickers/date range.")
            st.session_state.overview_generated = False
            st.session_state.overview_df_all = pd.DataFrame()
        else:
            df_all = pd.concat(dfs, ignore_index=True)
            st.session_state.overview_df_all = df_all
            st.session_state.overview_generated = True
            st.session_state.picked_points_close = []  # reset picks each generate

        st.rerun()

    if st.session_state.overview_generated and not st.session_state.overview_df_all.empty:
        df_all = st.session_state.overview_df_all.copy()

        closing_price_chart_with_picks(df_all)
        revenue_patmi_chart(selected_companies, start_dt, end_dt)

        st.subheader("🎯 Sales Target vs Actual (Placeholder)")
        st.info("This requires additional data (annual reports / sales target dataset).")
    else:
        st.caption("Select companies + dates, then click **Generate Overview**.")




