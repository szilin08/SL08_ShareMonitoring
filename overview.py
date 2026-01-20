# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta
import time
from streamlit_plotly_events import plotly_events

# Fix for Yahoo Finance blocking / empty responses
yf.utils.get_user_agent = lambda: (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

def main():
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

    CACHE_VERSION = 10          # bump to force cache refresh
    MIN_PRICE_MYR = 0.01
    MAX_PRICE_MYR = 15.0        # realistic cap for these counters

    st.set_page_config(page_title="Overview", layout="wide")
    st.title("📊 Overview – LBS Bina & Peers Price Comparison")

    # ────────────────────────────────────────────────
    # DATA FETCH (clean Date+Close only)
    # ────────────────────────────────────────────────
    @st.cache_data(ttl=6*60*60, show_spinner=False)
    def fetch_close_series(ticker: str, start: date, end: date, _ver: int = CACHE_VERSION) -> pd.DataFrame:
        for attempt in range(3):
            try:
                tk = yf.Ticker(ticker)
                df = tk.history(
                    start=start,
                    end=end + timedelta(days=1),
                    auto_adjust=True,
                    repair=False
                )

                if df is None or df.empty:
                    time.sleep(1.2)
                    continue

                df = df.reset_index()

                # normalize date col
                if "Datetime" in df.columns and "Date" not in df.columns:
                    df = df.rename(columns={"Datetime": "Date"})

                if "Date" not in df.columns or "Close" not in df.columns:
                    time.sleep(1.2)
                    continue

                df = df[["Date", "Close"]].copy()
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                # remove tz if exists
                try:
                    df["Date"] = df["Date"].dt.tz_localize(None)
                except Exception:
                    pass

                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

                df = df.dropna(subset=["Date", "Close"])

                # clamp to kill Yahoo KL 1000x nonsense
                df = df[df["Close"].between(MIN_PRICE_MYR, MAX_PRICE_MYR)]

                df = df.sort_values("Date").reset_index(drop=True)

                return df

            except Exception:
                time.sleep(1.5)

        return pd.DataFrame()

    def build_chart(df_all: pd.DataFrame):
        fig = px.line(
            df_all,
            x="Date",
            y="Close",
            color="Company",
            title="Closing Price Comparison (MYR)",
            height=620,
            template="plotly_dark",
        )

        fig.update_traces(
            mode="lines",
            line_width=2.4,
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.4f} MYR<extra></extra>",
        )

        fig.update_layout(
            hovermode="x unified",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            margin=dict(l=30, r=30, t=80, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        )

        fig.update_xaxes(title="Date", gridcolor="rgba(255,255,255,0.08)", zeroline=False)
        fig.update_yaxes(
            title="Close (MYR)",
            tickformat=".4f",
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
        )
        return fig

    # ────────────────────────────────────────────────
    # SESSION STATE
    # ────────────────────────────────────────────────
    if "ov_df_all" not in st.session_state:
        st.session_state.ov_df_all = pd.DataFrame()
    if "ov_generated" not in st.session_state:
        st.session_state.ov_generated = False
    if "ov_picks" not in st.session_state:
        st.session_state.ov_picks = []

    # ────────────────────────────────────────────────
    # UI
    # ────────────────────────────────────────────────
    a, b = st.columns(2)
    with a:
        start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="ov_start")
    with b:
        end_dt = st.date_input("End date", value=date.today(), key="ov_end")

    selected = st.multiselect(
        "Select companies",
        options=ALL_COMPANIES,
        default=[BASE_COMPANY],
        key="ov_companies"
    )

    if st.button("Generate Overview", type="primary", key="ov_generate"):
        if not selected:
            st.error("Select at least one company.")
            return
        if start_dt >= end_dt:
            st.error("Start date must be earlier than end date.")
            return

        dfs = []
        with st.spinner("Fetching share prices..."):
            for comp in selected:
                ticker = BASE_TICKER if comp == BASE_COMPANY else COMPETITORS.get(comp)
                if not ticker:
                    continue

                df = fetch_close_series(ticker, start_dt, end_dt)
                if df.empty:
                    continue

                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.error("No valid price data returned for the selected companies.")
            st.session_state.ov_generated = False
            st.session_state.ov_df_all = pd.DataFrame()
            st.session_state.ov_picks = []
            return

        df_all = pd.concat(dfs, ignore_index=True)
        df_all = df_all[["Date", "Close", "Company"]].copy()
        df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

        st.session_state.ov_df_all = df_all
        st.session_state.ov_generated = True
        st.session_state.ov_picks = []  # reset picks

    # ────────────────────────────────────────────────
    # CHART & PICKING (FIXED)
    # ────────────────────────────────────────────────
    if st.session_state.ov_generated and not st.session_state.ov_df_all.empty:
        df_all = st.session_state.ov_df_all.copy()

        # IMPORTANT: use the same company order the chart will use
        company_order = list(df_all["Company"].unique())

        st.subheader("Closing Price Comparison")

        fig = build_chart(df_all)

        # Optional: show picked vertical markers
        for p in st.session_state.ov_picks:
            try:
                fig.add_vline(x=p["Date"], line_width=1, line_dash="dot")
            except Exception:
                pass

        clicked = plotly_events(
            fig,
            click_event=True,
            select_event=False,
            hover_event=False,
            key="ov_click_event",
            override_height=620
        )

        # ✅ FIX: Use clicked x/y directly. NO pointIndex->iloc mapping.
        if clicked:
            e = clicked[0]
            x = e.get("x")
            y = e.get("y")
            curve = e.get("curveNumber")

            if x is not None and y is not None:
                comp = company_order[curve] if (curve is not None and curve < len(company_order)) else "Unknown"

                pick = {
                    "Company": comp,
                    "Date": pd.to_datetime(x).tz_localize(None),
                    "Close": float(y)
                }
                st.session_state.ov_picks.append(pick)
                st.session_state.ov_picks = st.session_state.ov_picks[-2:]
                st.rerun()

        picks = st.session_state.ov_picks

        c1, c2, c3 = st.columns([1, 1, 0.6])

        with c1:
            st.markdown("**Pick #1**")
            if len(picks) >= 1:
                p = picks[0]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()} • **{p['Close']:.4f}** MYR")
            else:
                st.caption("Click a point on the chart")

        with c2:
            st.markdown("**Pick #2**")
            if len(picks) >= 2:
                p = picks[1]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()} • **{p['Close']:.4f}** MYR")
            else:
                st.caption("Click a second point")

        with c3:
            if st.button("Reset picks", key="ov_reset"):
                st.session_state.ov_picks = []
                st.rerun()

        if len(picks) == 2:
            p1, p2 = picks
            if p1["Company"] == p2["Company"]:
                delta = p2["Close"] - p1["Close"]
                pct = (delta / p1["Close"] * 100) if p1["Close"] != 0 else 0
                days = (p2["Date"] - p1["Date"]).days

                st.markdown("### Difference")
                st.write(f"**Δ Close**: {delta:+.4f} MYR")
                st.write(f"**% Change**: {pct:+.2f}%")
                st.write(f"**Days**: {days}")
            else:
                st.info("Pick two points on the **same line** for percentage change calculation.")

    else:
        st.info("Select one or more companies and a date range, then click **Generate Overview**.")

    st.caption("Data: Yahoo Finance • Prices in MYR • Informational use only")


if __name__ == "__main__":
    main()
