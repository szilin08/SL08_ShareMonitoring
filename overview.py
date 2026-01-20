# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date, timedelta
from streamlit_plotly_events import plotly_events

BASE_COMPANY = "LBS Bina"
BASE_TICKER = "5789.KL"

def fetch_prices(ticker, start, end):
    df = yf.download(
        ticker,
        start=start,
        end=end + timedelta(days=1),
        progress=False
    )

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    df = df[["Date", "Close"]]   # 🔴 ONLY THESE TWO
    df["Date"] = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    return df.dropna()

def main():
    st.title("📈 LBS Bina – Closing Price")

    start_dt = st.date_input("Start date", date(2020, 1, 1))
    end_dt = st.date_input("End date", date.today())

    if "picks" not in st.session_state:
        st.session_state.picks = []

    if st.button("Generate"):
        df = fetch_prices(BASE_TICKER, start_dt, end_dt)

        if df.empty:
            st.error("No data returned.")
            return

        # 🔍 DEBUG — YOU SHOULD SEE ~0.30–0.80
        st.caption(
            f"Close range: {df['Close'].min():.3f} – {df['Close'].max():.3f}"
        )

        fig = px.line(
            df,
            x="Date",
            y="Close",
            title="Closing Price (MYR)",
            template="plotly_dark"
        )

        fig.update_traces(
            line=dict(width=2.5, color="#7fc8ff")
        )

        fig.update_layout(
            hovermode="x unified",
            height=600,
            margin=dict(l=40, r=20, t=60, b=40),
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
        )

        fig.update_yaxes(
            title="MYR",
            tickformat=".3f",
            zeroline=False
        )

        clicked = plotly_events(
            fig,
            click_event=True,
            key="price_click",
            override_height=600
        )

        if clicked:
            x = pd.to_datetime(clicked[0]["x"])
            row = df.iloc[(df["Date"] - x).abs().argsort()[:1]]

            st.session_state.picks.append({
                "Date": row["Date"].iloc[0],
                "Close": row["Close"].iloc[0]
            })
            st.session_state.picks = st.session_state.picks[-2:]

        st.plotly_chart(fig, use_container_width=True)

        # ───── Picks ─────
        p = st.session_state.picks
        c1, c2, c3 = st.columns([1, 1, 0.6])

        with c1:
            st.write("**Pick #1**")
            if len(p) >= 1:
                st.write(f"{p[0]['Date'].date()} • {p[0]['Close']:.3f}")

        with c2:
            st.write("**Pick #2**")
            if len(p) >= 2:
                st.write(f"{p[1]['Date'].date()} • {p[1]['Close']:.3f}")

        with c3:
            if st.button("Reset"):
                st.session_state.picks = []
                st.rerun()

        if len(p) == 2:
            diff = p[1]["Close"] - p[0]["Close"]
            pct = diff / p[0]["Close"] * 100
            days = (p[1]["Date"] - p[0]["Date"]).days

            st.markdown("### Difference")
            st.write(f"Δ Close: **{diff:+.3f} MYR**")
            st.write(f"% Change: **{pct:+.2f}%**")
            st.write(f"Days: **{days}**")

if __name__ == "__main__":
    main()
