import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import plotly.express as px
from streamlit_plotly_events import plotly_events

st.set_page_config(page_title="Overview", layout="wide")

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

CACHE_VERSION = 1  # bump if you change fetch logic


@st.cache_data(show_spinner=False)
def fetch_close(ticker: str, start_dt: date, end_dt: date, _v: int = CACHE_VERSION) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start_dt, end=end_dt)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    if "Datetime" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df.get("Close"), errors="coerce")
    df = df.dropna(subset=["Date", "Close"])

    return df[["Date", "Close"]]


def main():
    st.title("📊 Overview Dashboard")

    # --- session state ---
    if "df_all" not in st.session_state:
        st.session_state.df_all = pd.DataFrame()
    if "generated" not in st.session_state:
        st.session_state.generated = False
    if "picks" not in st.session_state:
        st.session_state.picks = []  # list of dicts

    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="overview_start")
    end_dt = st.date_input("End date", value=date.today(), key="overview_end")

    selected_companies = st.multiselect(
        "Select companies",
        options=[BASE_NAME] + list(COMPETITORS.keys()),
        default=[BASE_NAME],
        key="overview_companies",
    )

    # --- Fetch button ---
    if st.button("Get Historical Data", type="primary"):
        if not selected_companies:
            st.warning("Pick at least one company.")
            return
        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            return

        dfs = []
        with st.spinner("Fetching..."):
            for comp in selected_companies:
                ticker = BASE_TICKER if comp == BASE_NAME else COMPETITORS[comp]
                df = fetch_close(ticker, start_dt, end_dt + pd.Timedelta(days=1))
                if df.empty:
                    continue
                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.warning("No data returned for that range.")
            st.session_state.generated = False
            st.session_state.df_all = pd.DataFrame()
            st.session_state.picks = []
            return

        df_all = pd.concat(dfs, ignore_index=True)
        df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

        st.session_state.df_all = df_all
        st.session_state.generated = True
        st.session_state.picks = []  # reset picks when refetching

    if not st.session_state.generated or st.session_state.df_all.empty:
        st.caption("Pick companies + dates, then click **Get Historical Data**.")
        return

    df_all = st.session_state.df_all.copy()

    # --- Debug (so you can see if Yahoo is giving 265 vs 0.265) ---
    with st.expander("Debug (if chart looks wrong)"):
        st.write("Close min/max:", float(df_all["Close"].min()), float(df_all["Close"].max()))
        st.dataframe(df_all.head(5), use_container_width=True)

    col1, col2 = st.columns(2)

    # --- Closing Price chart (clickable) ---
    with col1:
        st.subheader("Closing Price Comparison")

        fig_close = px.line(
            df_all,
            x="Date",
            y="Close",
            color="Company",
            title="Closing Price",
        )

        fig_close.update_traces(mode="lines", line=dict(width=2))
        fig_close.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            height=500,
            margin=dict(l=10, r=10, t=50, b=10),
            paper_bgcolor="#0b0f14",
            plot_bgcolor="#0b0f14",
            legend_title_text="Company",
        )
        fig_close.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
        fig_close.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False, tickformat=".4f")

        # IMPORTANT: company order must match trace order
        company_order = list(df_all["Company"].unique())

        clicked = plotly_events(
            fig_close,
            click_event=True,
            select_event=False,
            hover_event=False,
            key="close_clicks",
            override_height=500,
        )

        if clicked:
            c = clicked[0]
            curve = c.get("curveNumber")
            point_index = c.get("pointIndex")

            if curve is not None and point_index is not None and 0 <= curve < len(company_order):
                company = company_order[curve]
                df_comp = df_all[df_all["Company"] == company].reset_index(drop=True)

                if 0 <= point_index < len(df_comp):
                    row = df_comp.loc[point_index]
                    st.session_state.picks.append({
                        "Company": company,
                        "Date": pd.to_datetime(row["Date"]),
                        "Close": float(row["Close"]),
                    })
                    st.session_state.picks = st.session_state.picks[-2:]

        picks = st.session_state.picks
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
            if st.button("Reset picks", key="reset_picks"):
                st.session_state.picks = []
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

    # --- Right column placeholder (keep your layout) ---
    with col2:
        st.subheader(" ")
        st.caption("Add Volume chart here later if you want.")



