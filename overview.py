# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta
import time
from streamlit_plotly_events import plotly_events

# ────────────────────────────────────────────────
# FIX YAHOO BLOCKING / EMPTY DATA (2025-2026 common issue)
# Set a realistic browser User-Agent to bypass blocks
# ────────────────────────────────────────────────
yf.utils.get_user_agent = lambda: (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def main():
    # Config
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

    CACHE_VERSION = 8  # ↑ to force refresh if cache has bad empty data
    MIN_PRICE = 0.01
    MAX_PRICE = 20.0

    # ────────────────────────────────────────────────
    # Fetch function with retry & debug
    # ────────────────────────────────────────────────
    @st.cache_data(ttl="6h", show_spinner=False)
    def fetch_close_series(ticker: str, start: date, end: date, _ver=CACHE_VERSION):
        debug_msg = f"Fetching {ticker} from {start} to {end}"
        st.caption(debug_msg)  # visible in app for troubleshooting

        for attempt in range(3):  # retry up to 3 times
            try:
                tk = yf.Ticker(ticker)
                df = tk.history(
                    start=start,
                    end=end + timedelta(days=1),
                    auto_adjust=True,
                    repair=True
                )

                if df.empty:
                    st.caption(f"DEBUG: Empty for {ticker} (attempt {attempt+1})")
                    time.sleep(1.5)  # backoff
                    continue

                df = df[["Close"]].reset_index()
                df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                df = df[df["Close"].between(MIN_PRICE, MAX_PRICE)].dropna(subset=["Date", "Close"])

                st.caption(f"DEBUG: Success for {ticker} – {len(df)} rows")
                return df[["Date", "Close"]]

            except Exception as e:
                st.caption(f"DEBUG: Error on attempt {attempt+1} for {ticker}: {str(e)}")
                time.sleep(2)

        st.caption(f"DEBUG: Failed after retries for {ticker}")
        return pd.DataFrame()

    def build_chart(df_all: pd.DataFrame) -> px.line:
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
            legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", yanchor="bottom"),
        )
        fig.update_xaxes(title="Date", gridcolor="rgba(255,255,255,0.08)", zeroline=False)
        fig.update_yaxes(
            title="Close (MYR)",
            tickformat=".3f",
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
            range=[0, None]
        )
        return fig

    # Session state (unique keys for this tab)
    if "ov_df_all" not in st.session_state:
        st.session_state.ov_df_all = pd.DataFrame()
    if "ov_generated" not in st.session_state:
        st.session_state.ov_generated = False
    if "ov_picks" not in st.session_state:
        st.session_state.ov_picks = []

    # ────────────────────────────────────────────────
    # UI
    # ────────────────────────────────────────────────
    st.title("📊 Overview – LBS Bina & Competitors Price Comparison")

    col1, col2 = st.columns(2)
    with col1:
        start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="ov_start_dt")
    with col2:
        end_dt = st.date_input("End date", value=date.today(), key="ov_end_dt")

    selected = st.multiselect(
        "Select companies",
        options=ALL_COMPANIES,
        default=[BASE_COMPANY],
        key="ov_selected"
    )

    if st.button("Generate Overview", type="primary", key="ov_generate_btn"):

        if not selected:
            st.error("Please select at least one company.")
            return

        if start_dt >= end_dt:
            st.error("Start date must be before end date.")
            return

        with st.spinner("Fetching prices (with retries)..."):
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
                st.error("No valid data returned from any selected company. Check debug messages above.")
                st.session_state.ov_generated = False
                return

            df_all = pd.concat(dfs, ignore_index=True)
            df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

            min_p = df_all["Close"].min()
            max_p = df_all["Close"].max()
            st.caption(f"Data loaded • Price range: {min_p:.3f} – {max_p:.3f} MYR • {len(df_all):,} rows")

            st.session_state.ov_df_all = df_all
            st.session_state.ov_generated = True
            st.session_state.ov_picks = []  # reset picks

    # Display chart if data ready
    if st.session_state.ov_generated and not st.session_state.ov_df_all.empty:

        df_all = st.session_state.ov_df_all
        companies = sorted(df_all["Company"].unique())

        st.subheader("Closing Price Comparison")

        fig = build_chart(df_all)

        clicked = plotly_events(fig, click_event=True, key="ov_click_ev", override_height=620)

        if clicked:
            c = clicked[0]
            curve_num = c.get("curveNumber")
            point_idx = c.get("pointIndex")
            if curve_num is not None and point_idx is not None and curve_num < len(companies):
                comp = companies[curve_num]
                df_comp = df_all[df_all["Company"] == comp].reset_index(drop=True)
                if point_idx < len(df_comp):
                    row = df_comp.iloc[point_idx]
                    pick = {"Company": comp, "Date": row["Date"], "Close": float(row["Close"])}
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
            if st.button("Reset picks", key="ov_reset_btn"):
                st.session_state.ov_picks = []
                st.rerun()

        if len(picks) == 2:
            p1, p2 = picks
            if p1["Company"] == p2["Company"]:
                diff = p2["Close"] - p1["Close"]
                pct = (diff / p1["Close"] * 100) if p1["Close"] != 0 else 0
                days = (p2["Date"] - p1["Date"]).days
                st.markdown("### Difference")
                st.write(f"**Δ Close**: {diff:+.3f} MYR")
                st.write(f"**% Change**: {pct:+.2f}%")
                st.write(f"**Days between**: {days}")
            else:
                st.info("For % change, pick two points on the **same company** line.")

    else:
        st.info("Select companies and dates, then click **Generate Overview**.")
        st.caption("Tip: If still no data, check debug messages above – likely Yahoo blocking. Try again later or use wider date range.")

    st.caption("Data from Yahoo Finance • Prices in MYR • Not financial advice • User-Agent fix applied")

if __name__ == "__main__":
    main()
