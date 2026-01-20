# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta
import time
from streamlit_plotly_events import plotly_events

# Fix for Yahoo Finance blocking / empty responses (common 2025–2026)
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

    CACHE_VERSION = 10          # Bump this to force cache refresh
    MIN_PRICE_MYR = 0.01
    MAX_PRICE_MYR = 15.0        # Realistic upper bound for these stocks

    # ────────────────────────────────────────────────
    # DATA FETCH WITH DEBUG & SAFEGUARDS
    # ────────────────────────────────────────────────
    @st.cache_data(ttl="6h", show_spinner=False)
    def fetch_close_series(ticker: str, start: date, end: date, _ver=CACHE_VERSION):
        st.caption(f"Fetching {ticker} → {start} to {end}")

        for attempt in range(3):
            try:
                tk = yf.Ticker(ticker)
                df = tk.history(
                    start=start,
                    end=end + timedelta(days=1),
                    auto_adjust=True,
                    repair=False                # avoid scipy dependency if possible
                )

                if df.empty:
                    st.caption(f"Empty response for {ticker} (attempt {attempt+1})")
                    time.sleep(1.5)
                    continue

                # Reset index and select only needed columns
                df = df.reset_index()[["Date", "Close"]]

                # Force numeric & round early
                df["Date"]  = pd.to_datetime(df["Date"]).dt.tz_localize(None)
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce").round(4)

                # Hard clamp to realistic range – this kills the 1000+ bug
                df = df[df["Close"].between(MIN_PRICE_MYR, MAX_PRICE_MYR)]

                df = df.dropna(subset=["Date", "Close"])

                if df.empty:
                    st.caption(f"No valid prices after cleaning for {ticker}")
                else:
                    min_c = df["Close"].min()
                    max_c = df["Close"].max()
                    st.caption(f"Success: {len(df)} rows • Close range: {min_c:.3f} – {max_c:.3f} MYR")

                return df

            except Exception as e:
                st.caption(f"Error attempt {attempt+1} for {ticker}: {str(e)}")
                time.sleep(2)

        st.caption(f"Failed to fetch valid data for {ticker} after 3 attempts")
        return pd.DataFrame()

    def build_chart(df_all: pd.DataFrame):
        if df_all.empty:
            return px.line(title="No Data")

        fig = px.line(
            df_all,
            x="Date",
            y="Close",
            color="Company",
            title="Closing Price Comparison (MYR)",
            height=620,
            template="plotly_dark"
        )

        fig.update_traces(mode="lines", line_width=2.4, hovertemplate="%{y:.3f} MYR<extra></extra>")

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
            tickformat=".3f",
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
            range=[0, None]  # let it auto-scale but start at 0
        )

        return fig

    # ────────────────────────────────────────────────
    # SESSION STATE (tab-safe keys)
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
    st.title("📊 Overview – LBS Bina & Peers Price Comparison")

    col1, col2 = st.columns(2)
    with col1:
        start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="ov_start")
    with col2:
        end_dt = st.date_input("End date", value=date.today(), key="ov_end")

    selected = st.multiselect(
        "Select companies",
        options=ALL_COMPANIES,
        default=[BASE_COMPANY],
        key="ov_companies"
    )

    if st.button("Generate Overview", type="primary"):

        if not selected:
            st.error("Select at least one company.")
            return
        if start_dt >= end_dt:
            st.error("Start date must be earlier than end date.")
            return

        with st.spinner("Fetching share prices..."):
            dfs = []
            for comp in selected:
                ticker = BASE_TICKER if comp == BASE_COMPANY else COMPETITORS.get(comp)
                if not ticker:
                    continue
                df = fetch_close_series(ticker, start_dt, end_dt)
                if not df.empty:
                    df["Company"] = comp
                    dfs.append(df)

            if not dfs:
                st.error("No valid price data returned for the selected companies.")
                return

            df_all = pd.concat(dfs, ignore_index=True)
            df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

            # Final safety check & debug
            if not df_all.empty:
                overall_min = df_all["Close"].min()
                overall_max = df_all["Close"].max()
                st.caption(f"Final loaded data • Overall Close range: {overall_min:.3f} – {overall_max:.3f} MYR • {len(df_all)} rows")

            st.session_state.ov_df_all = df_all
            st.session_state.ov_generated = True
            st.session_state.ov_picks = []

    # ────────────────────────────────────────────────
    # CHART & PICK INTERACTION
    # ────────────────────────────────────────────────
    if st.session_state.ov_generated and not st.session_state.ov_df_all.empty:

        df_all = st.session_state.ov_df_all
        companies = sorted(df_all["Company"].unique())

        st.subheader("Closing Price Comparison")

        fig = build_chart(df_all)

        clicked = plotly_events(
            fig,
            click_event=True,
            key="ov_click_event",
            override_height=620
        )

        if clicked:
            c = clicked[0]
            curve = c.get("curveNumber")
            idx = c.get("pointIndex")
            if curve is not None and idx is not None and curve < len(companies):
                comp = companies[curve]
                df_comp = df_all[df_all["Company"] == comp].reset_index(drop=True)
                if idx < len(df_comp):
                    row = df_comp.iloc[idx]
                    pick = {
                        "Company": comp,
                        "Date": row["Date"],
                        "Close": float(row["Close"])
                    }
                    st.session_state.ov_picks.append(pick)
                    st.session_state.ov_picks = st.session_state.ov_picks[-2:]

        picks = st.session_state.ov_picks

        c1, c2, c3 = st.columns([1, 1, 0.6])

        with c1:
            st.markdown("**Pick #1**")
            if len(picks) >= 1:
                p = picks[0]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
            else:
                st.caption("Click a point on the chart")

        with c2:
            st.markdown("**Pick #2**")
            if len(picks) >= 2:
                p = picks[1]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()} • **{p['Close']:.3f}** MYR")
            else:
                st.caption("Click a second point")

        with c3:
            if st.button("Reset picks"):
                st.session_state.ov_picks = []
                st.rerun()

        if len(picks) == 2:
            p1, p2 = picks
            if p1["Company"] == p2["Company"]:
                delta = p2["Close"] - p1["Close"]
                pct = (delta / p1["Close"] * 100) if p1["Close"] != 0 else 0
                days = (p2["Date"] - p1["Date"]).days
                st.markdown("### Difference")
                st.write(f"**Δ Close**: {delta:+.3f} MYR")
                st.write(f"**% Change**: {pct:+.2f}%")
                st.write(f"**Days**: {days}")
            else:
                st.info("Pick two points on the **same line** for percentage change calculation.")

    else:
        st.info("Select one or more companies and a date range, then click **Generate Overview**.")
        st.caption("Tip: If the chart still looks wrong, look at the debug captions above for price range.")

    st.caption("Data: Yahoo Finance • Prices in MYR • Informational use only")

if __name__ == "__main__":
    main()
