# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta
from streamlit_plotly_events import plotly_events

def main():
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

    CACHE_VERSION = 7
    MIN_PRICE = 0.05
    MAX_PRICE = 20.0

    @st.cache_data(ttl="12h")
    def fetch_prices(ticker, start, end):
        try:
            df = yf.download(
                ticker, start=start, end=end + timedelta(days=1),
                progress=False, auto_adjust=True, repair=True
            )
            if df.empty:
                return pd.DataFrame()
            df = df[["Close"]].reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            df = df[df["Close"].between(MIN_PRICE, MAX_PRICE)].dropna()
            return df[["Date", "Close"]]
        except:
            return pd.DataFrame()

    def make_chart(df):
        fig = px.line(
            df, x="Date", y="Close", color="Company",
            title="Closing Price Comparison (MYR)",
            height=600, template="plotly_dark"
        )
        fig.update_traces(line_width=2.2, hovertemplate="%{y:.3f} MYR")
        fig.update_layout(
            hovermode="x unified",
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            margin=dict(l=20, r=20, t=60, b=20),
            legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center")
        )
        fig.update_xaxes(title="Date", gridcolor="rgba(255,255,255,0.1)")
        fig.update_yaxes(
            title="Close (MYR)", tickformat=".3f",
            gridcolor="rgba(255,255,255,0.1)",
            range=[0, None]
        )
        return fig

    # Session state keys unique to this tab
    if "ov_df" not in st.session_state:
        st.session_state.ov_df = pd.DataFrame()
    if "ov_loaded" not in st.session_state:
        st.session_state.ov_loaded = False
    if "ov_picks" not in st.session_state:
        st.session_state.ov_picks = []

    st.title("📊 Overview – LBS Bina & Peers Price Comparison")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start", date(2020,1,1), key="ov_start")
    with col2:
        end = st.date_input("End", date.today(), key="ov_end")

    selected = st.multiselect(
        "Select companies",
        ALL_COMPANIES,
        default=[BASE_COMPANY],
        key="ov_companies"
    )

    if st.button("Generate Chart", type="primary"):
        if not selected:
            st.error("Select at least one company")
            return
        if start >= end:
            st.error("Start date must be before end date")
            return

        with st.spinner("Loading prices..."):
            dfs = []
            for company in selected:
                ticker = BASE_TICKER if company == BASE_COMPANY else COMPETITORS.get(company)
                if ticker:
                    df = fetch_prices(ticker, start, end)
                    if not df.empty:
                        df["Company"] = company
                        dfs.append(df)

            if not dfs:
                st.error("No data returned from Yahoo Finance")
                return

            df_all = pd.concat(dfs, ignore_index=True)
            df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

            minp = df_all["Close"].min()
            maxp = df_all["Close"].max()
            st.caption(f"Prices loaded: {minp:.3f} – {maxp:.3f} MYR  |  {len(df_all):,} rows")

            st.session_state.ov_df = df_all
            st.session_state.ov_loaded = True
            st.session_state.ov_picks = []

    if st.session_state.ov_loaded and not st.session_state.ov_df.empty:
        df = st.session_state.ov_df
        companies = sorted(df["Company"].unique())

        st.subheader("Closing Prices")

        fig = make_chart(df)

        clicked = plotly_events(
            fig,
            click_event=True,
            key="ov_plotly_click",
            override_height=600
        )

        if clicked:
            c = clicked[0]
            curve = c.get("curveNumber")
            point = c.get("pointIndex")
            if curve is not None and point is not None and curve < len(companies):
                comp = companies[curve]
                df_comp = df[df["Company"] == comp].reset_index(drop=True)
                if point < len(df_comp):
                    row = df_comp.iloc[point]
                    pick = {
                        "Company": comp,
                        "Date": row["Date"],
                        "Close": float(row["Close"])
                    }
                    st.session_state.ov_picks.append(pick)
                    st.session_state.ov_picks = st.session_state.ov_picks[-2:]

        picks = st.session_state.ov_picks

        c1, c2, c3 = st.columns([1,1,0.6])
        with c1:
            st.markdown("**Pick #1**")
            if len(picks) >= 1:
                p = picks[0]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()}  •  **{p['Close']:.3f}**")
            else:
                st.caption("Click point on chart")

        with c2:
            st.markdown("**Pick #2**")
            if len(picks) >= 2:
                p = picks[1]
                st.caption(p["Company"])
                st.write(f"{p['Date'].date()}  •  **{p['Close']:.3f}**")
            else:
                st.caption("Click second point")

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
                st.markdown("### Change")
                st.write(f"**Δ**: {delta:+.3f}")
                st.write(f"**%**: {pct:+.2f}%")
                st.write(f"**Days**: {days}")
            else:
                st.info("Pick two points on same line for % change")

    else:
        st.info("Select companies and dates, then click **Generate Chart**")

    st.caption("Yahoo Finance data • MYR • Informational only")

if __name__ == "__main__":
    main()
