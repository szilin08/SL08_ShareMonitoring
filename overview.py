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

    # ✅ Fix Yahoo KL scaling (this is your axis problem)
    # If max close is hundreds/thousands, it’s sen*1000.
    mx = float(df["Close"].max())
    if mx > 50:        # e.g. 265, 759, 1400
        df["Close"] = df["Close"] / 1000.0
    elif mx > 20:      # rare fallback
        df["Close"] = df["Close"] / 100.0

    return df[["Date", "Close"]]


def ticker_for(company: str) -> str:
    if company == BASE["name"]:
        return BASE["ticker"]
    return COMPETITORS[company]


def main():
    st.title("📊 Overview Dashboard")

    # state (so clicks don’t reset)
    if "df_all" not in st.session_state:
        st.session_state.df_all = pd.DataFrame()
    if "generated" not in st.session_state:
        st.session_state.generated = False
    if "picks" not in st.session_state:
        st.session_state.picks = []

    start_dt = st.date_input("Start date", value=date(2020, 1, 1))
    end_dt = st.date_input("End date", value=date.today())

    selected = st.multiselect("Select companies", options=ALL, default=[BASE["name"]])

    if st.button("Generate Overview", type="primary"):
        if not selected:
            st.warning("Pick at least one company.")
            return
        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            return

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
            return

        df_all = pd.concat(dfs, ignore_index=True)
        order = sorted(df_all["Company"].unique().tolist())
        df_all["Company"] = pd.Categorical(df_all["Company"], categories=order, ordered=True)
        df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

        st.session_state.df_all = df_all
        st.session_state.generated = True
        st.session_state.picks = []
        st.rerun()

    if not st.session_state.generated or st.session_state.df_all.empty:
        st.caption("Pick companies + dates, then click **Generate Overview**.")
        return

    df_all = st.session_state.df_all.copy()

    st.subheader("Closing Price Comparison")

    fig = px.line(df_all, x="Date", y="Close", color="Company", title="Closing Price")
    fig.update_traces(mode="lines", line=dict(width=2))
    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#0b0f14",
        plot_bgcolor="#0b0f14",
        legend_title_text="Company",
    )
    fig.update_xaxes(title_text="Date", gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    fig.update_yaxes(title_text="Close (RM)", tickformat=".4f", gridcolor="rgba(255,255,255,0.08)", zeroline=False)

    clicked = plotly_events(fig, click_event=True, select_event=False, hover_event=False,
                            key="close_clicks", override_height=520)

    if clicked:
        c = clicked[0]
        curve = c.get("curveNumber")
        point_index = c.get("pointIndex")
        companies = list(df_all["Company"].cat.categories)

        if curve is not None and point_index is not None and 0 <= curve < len(companies):
            comp = companies[curve]
            df_comp = df_all[df_all["Company"] == comp].reset_index(drop=True)

            if 0 <= point_index < len(df_comp):
                row = df_comp.loc[point_index]
                st.session_state.picks.append({
                    "Company": comp,
                    "Date": pd.to_datetime(row["Date"]),
                    "Close": float(row["Close"]),
                })
                st.session_state.picks = st.session_state.picks[-2:]

    picks = st.session_state.picks
    c1, c2, c3 = st.columns([1.2, 1.2, 0.7])

    with c1:
        st.write("**Pick #1**")
        if len(picks) >= 1:
            p1 = picks[0]
            st.caption(p1["Company"])
            st.write(f"{p1['Date'].date()} • **{p1['Close']:.4f}**")
        else:
            st.caption("Click a point")

    with c2:
        st.write("**Pick #2**")
        if len(picks) >= 2:
            p2 = picks[1]
            st.caption(p2["Company"])
            st.write(f"{p2['Date'].date()} • **{p2['Close']:.4f}**")
        else:
            st.caption("Click second point")

    with c3:
        if st.button("Reset picks"):
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


