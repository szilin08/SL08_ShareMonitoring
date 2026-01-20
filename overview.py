import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date
from streamlit_plotly_events import plotly_events

BASE = {"name": "LBS Bina", "ticker": "5789.KL"}

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
ALL = [BASE["name"]] + list(COMPETITORS.keys())

CACHE_VERSION = 10  # bump to force Streamlit cache refresh


@st.cache_data(show_spinner=False)
def fetch_close(ticker: str, start_dt: date, end_dt: date, _v: int = CACHE_VERSION) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start_dt, end=end_dt)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    if "Datetime" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).copy()

    # ✅ Fix Yahoo KL scaling (axis issue)
    mx = float(df["Close"].max())
    if mx > 50:        # e.g. 265, 759, 1400
        df["Close"] = df["Close"] / 1000.0
    elif mx > 20:      # rare fallback
        df["Close"] = df["Close"] / 100.0

    return df[["Date", "Close"]]


def ticker_for(company: str) -> str:
    return BASE["ticker"] if company == BASE["name"] else COMPETITORS[company]


def main():
    st.title("📊 Overview Dashboard")

    # --- state so clicks don’t reset everything ---
    if "df_all" not in st.session_state:
        st.session_state.df_all = pd.DataFrame()
    if "generated" not in st.session_state:
        st.session_state.generated = False
    if "picks" not in st.session_state:
        st.session_state.picks = []

    # Inputs
    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="overview_start")
    end_dt = st.date_input("End date", value=date.today(), key="overview_end")
    selected = st.multiselect("Select companies", options=ALL, default=[BASE["name"]], key="overview_companies")

    # Fetch button
    if st.button("Generate Overview", type="primary"):
        if not selected:
            st.warning("Pick at least one company.")
            st.session_state.generated = False
            st.session_state.df_all = pd.DataFrame()
            st.session_state.picks = []
            st.stop()

        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            st.session_state.generated = False
            st.session_state.df_all = pd.DataFrame()
            st.session_state.picks = []
            st.stop()

        dfs = []
        with st.spinner("Fetching..."):
            for comp in selected:
                df = fetch_close(ticker_for(comp), start_dt, end_dt + pd.Timedelta(days=1))
                if df.empty:
                    continue
                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.warning("No data returned for that range.")
            st.session_state.generated = False
            st.session_state.df_all = pd.DataFrame()
            st.session_state.picks = []
            st.stop()

        # EXACTLY like your old approach: concat + reset_index
        df_all = pd.concat(dfs, ignore_index=True)
        # stable order for click mapping
        company_order = [BASE["name"]] + [c for c in selected if c != BASE["name"]]
        leftovers = [c for c in df_all["Company"].unique() if c not in company_order]
        company_order += sorted(leftovers)

        df_all["Company"] = pd.Categorical(df_all["Company"], categories=company_order, ordered=True)
        df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

        st.session_state.df_all = df_all
        st.session_state.generated = True
        st.session_state.picks = []  # reset picks each time you fetch
        st.rerun()

    if not st.session_state.generated or st.session_state.df_all.empty:
        st.caption("Pick companies + dates, then click **Generate Overview**.")
        return

    df_all = st.session_state.df_all.copy()

    # --- Side by Side Charts (like your old code) ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Closing Price Comparison")

        # SAME as your fig_close block (keep it)
        fig_close = px.line(
            df_all,
            x="Date",
            y="Close",
            color="Company",
            title="Closing Price",
            width=800,
            height=500,
        )

        # Make it dark like you want (optional but matches your reference)
        fig_close.update_traces(mode="lines", line=dict(width=2))
        fig_close.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            paper_bgcolor="#0b0f14",
            plot_bgcolor="#0b0f14",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        fig_close.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
        fig_close.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False, tickformat=".4f")

        # IMPORTANT: use plotly_events instead of st.plotly_chart so clicks work
        clicked = plotly_events(
            fig_close,
            click_event=True,
            select_event=False,
            hover_event=False,
            key="close_clicks",
            override_height=500,
        )

        # Store picks
        if clicked:
            c = clicked[0]
            curve = c.get("curveNumber")
            point_index = c.get("pointIndex")

            companies = list(df_all["Company"].cat.categories)

            if curve is not None and point_index is not None and 0 <= curve < len(companies):
                company = companies[curve]
                df_comp = df_all[df_all["Company"] == company].reset_index(drop=True)

                if 0 <= point_index < len(df_comp):
                    row = df_comp.loc[point_index]
                    st.session_state.picks.append(
                        {
                            "Company": company,
                            "Date": pd.to_datetime(row["Date"]),
                            "Close": float(row["Close"]),
                        }
                    )
                    st.session_state.picks = st.session_state.picks[-2:]

        # Picks UI under chart
        picks = st.session_state.picks
        p1c, p2c, rc = st.columns([1.2, 1.2, 0.7])

        with p1c:
            st.write("**Pick #1**")
            if len(picks) >= 1:
                p1 = picks[0]
                st.caption(p1["Company"])
                st.write(f"{p1['Date'].date()} • **{p1['Close']:.4f}**")
            else:
                st.caption("Click a point")

        with p2c:
            st.write("**Pick #2**")
            if len(picks) >= 2:
                p2 = picks[1]
                st.caption(p2["Company"])
                st.write(f"{p2['Date'].date()} • **{p2['Close']:.4f}**")
            else:
                st.caption("Click a second point")

        with rc:
            if st.button("Reset picks", key="reset_picks"):
                st.session_state.picks = []
                st.rerun()

        # Variance
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
                st.warning("Click 2 points on the same company line if you want a clean variance.")

    with col2:
        # keep empty / placeholder (so layout matches your old side-by-side)
        st.subheader(" ")
        st.caption("Add Volume / other chart here if you want.")


