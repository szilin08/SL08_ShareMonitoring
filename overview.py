import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from financials import get_revenue_data, get_patmi_data  # make sure you implemented these


# -----------------------------
# Config
# -----------------------------
BASE_TICKER = "5789.KL"  # LBS Bina
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
ALL_COMPANIES = ["LBS Bina"] + list(COMPETITORS.keys())

PRICE_FIELDS = ["Close", "Adj Close", "Open", "High", "Low"]


# -----------------------------
# Helpers
# -----------------------------
def _resolve_ticker(company: str) -> str:
    return BASE_TICKER if company == "LBS Bina" else COMPETITORS[company]


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_history(ticker: str, start_dt: date, end_dt_inclusive: date) -> pd.DataFrame:
    """
    yfinance end is exclusive, so we add +1 day to include end date.
    Returns a dataframe with Date index (DatetimeIndex) and OHLCV columns.
    """
    end_exclusive = end_dt_inclusive + timedelta(days=1)
    df = yf.Ticker(ticker).history(start=start_dt, end=end_exclusive, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    return df


def sanitize_period(start_dt: date, end_dt: date, label: str) -> tuple[date, date]:
    if start_dt > end_dt:
        st.warning(f"{label}: Start date is after end date — swapping them.")
        return end_dt, start_dt
    return start_dt, end_dt


def summarize_period(hist: pd.DataFrame, price_col: str) -> dict:
    """
    Uses first/last available rows in the fetched range.
    Adds extra metrics: volatility (daily std), max drawdown, CAGR (if possible).
    """
    if hist.empty or price_col not in hist.columns:
        return {
            "start": None, "end": None, "abs": None, "pct": None,
            "vol": None, "mdd": None, "cagr": None,
            "start_date": None, "end_date": None
        }

    s = float(hist[price_col].iloc[0])
    e = float(hist[price_col].iloc[-1])
    start_date = hist.index[0].date()
    end_date = hist.index[-1].date()

    abs_chg = e - s
    pct_chg = (abs_chg / s) * 100 if s != 0 else None

    # Daily returns for stats
    rets = hist[price_col].pct_change().dropna()
    vol = float(rets.std() * (252 ** 0.5) * 100) if len(rets) > 1 else None  # annualized %
    # Max drawdown
    curve = (1 + rets).cumprod()
    peak = curve.cummax()
    dd = (curve / peak) - 1
    mdd = float(dd.min() * 100) if len(dd) else None  # %
    # CAGR
    days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
    years = days / 365.25 if days and days > 0 else None
    cagr = (float((e / s) ** (1 / years) - 1) * 100) if (years and years > 0 and s > 0) else None

    return {
        "start": s, "end": e, "abs": abs_chg, "pct": pct_chg,
        "vol": vol, "mdd": mdd, "cagr": cagr,
        "start_date": start_date, "end_date": end_date
    }


def build_line_df(hist: pd.DataFrame, company: str, period_label: str, price_col: str, normalize: bool) -> pd.DataFrame:
    if hist.empty or price_col not in hist.columns:
        return pd.DataFrame()

    out = hist[[price_col]].copy()
    out = out.reset_index()
    out["Company"] = company
    out["Period"] = period_label

    if normalize:
        base = float(out[price_col].iloc[0])
        out[price_col] = (out[price_col] / base) * 100 if base != 0 else out[price_col]

    return out


# -----------------------------
# App
# -----------------------------
def main():
    st.set_page_config(page_title="Overview Dashboard", layout="wide")
    st.title("📊 Overview Dashboard")

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")

        selected_companies = st.multiselect(
            "Select companies",
            ALL_COMPANIES,
            default=["LBS Bina"],
        )

        st.divider()
        st.subheader("Advanced Price Comparison")

        price_col = st.selectbox("Price field", PRICE_FIELDS, index=0)

        normalize = st.checkbox("Normalize to 100 (performance view)", value=True)
        show_candles = st.checkbox("Show candlestick (single company only)", value=False)

        st.markdown("**Period A**")
        a_start = st.date_input("A: Start", value=date(2022, 1, 1), key="A_start")
        a_end = st.date_input("A: End", value=date(2022, 12, 31), key="A_end")

        st.markdown("**Period B**")
        b_start = st.date_input("B: Start", value=date(2023, 1, 1), key="B_start")
        b_end = st.date_input("B: End", value=date(2023, 12, 31), key="B_end")

        st.divider()
        st.subheader("Financials Range (Revenue / PATMI)")
        fin_start = st.date_input("Financials Start", value=date(2020, 1, 1), key="fin_start")
        fin_end = st.date_input("Financials End", value=date.today(), key="fin_end")

        generate = st.button("Generate Overview", type="primary")

    if not generate:
        st.info("Pick your companies + periods on the left, then click **Generate Overview**.")
        return

    if not selected_companies:
        st.error("Select at least 1 company.")
        return

    # Sanitize periods
    a_start, a_end = sanitize_period(a_start, a_end, "Period A")
    b_start, b_end = sanitize_period(b_start, b_end, "Period B")
    fin_start, fin_end = sanitize_period(fin_start, fin_end, "Financials")

    # -----------------------------
    # 1) Advanced Price Comparison (A vs B)
    # -----------------------------
    st.subheader("📉 Price Comparison (Advanced: Period A vs Period B)")

    rows = []
    line_frames = []

    progress = st.progress(0, text="Fetching price data...")
    total = len(selected_companies)

    for i, comp in enumerate(selected_companies, start=1):
        ticker = _resolve_ticker(comp)

        hist_a = fetch_history(ticker, a_start, a_end)
        hist_b = fetch_history(ticker, b_start, b_end)

        sa = summarize_period(hist_a, price_col)
        sb = summarize_period(hist_b, price_col)

        rows.append({
            "Company": comp,
            "Ticker": ticker,

            "A Start Date": sa["start_date"],
            "A End Date": sa["end_date"],
            "A Start": sa["start"],
            "A End": sa["end"],
            "A Δ (RM)": sa["abs"],
            "A Δ (%)": sa["pct"],
            "A Vol (%)": sa["vol"],
            "A MaxDD (%)": sa["mdd"],
            "A CAGR (%)": sa["cagr"],

            "B Start Date": sb["start_date"],
            "B End Date": sb["end_date"],
            "B Start": sb["start"],
            "B End": sb["end"],
            "B Δ (RM)": sb["abs"],
            "B Δ (%)": sb["pct"],
            "B Vol (%)": sb["vol"],
            "B MaxDD (%)": sb["mdd"],
            "B CAGR (%)": sb["cagr"],

            "Δ(%) B - A": (sb["pct"] - sa["pct"]) if (sb["pct"] is not None and sa["pct"] is not None) else None,
            "CAGR Gap (B - A)": (sb["cagr"] - sa["cagr"]) if (sb["cagr"] is not None and sa["cagr"] is not None) else None,
        })

        line_frames.append(build_line_df(hist_a, comp, "A", price_col, normalize))
        line_frames.append(build_line_df(hist_b, comp, "B", price_col, normalize))

        progress.progress(i / total, text=f"Fetching price data... ({i}/{total})")

    progress.empty()

    summary_df = pd.DataFrame(rows)

    # Scoreboard style: best/worst
    c1, c2, c3 = st.columns([1.2, 1.2, 2.0])
    with c1:
        if summary_df["B Δ (%)"].notna().any():
            best = summary_df.loc[summary_df["B Δ (%)"].idxmax()]
            st.metric("Best in Period B", best["Company"], f"{best['B Δ (%)']:.2f}%")
        else:
            st.metric("Best in Period B", "—", "—")
    with c2:
        if summary_df["B Δ (%)"].notna().any():
            worst = summary_df.loc[summary_df["B Δ (%)"].idxmin()]
            st.metric("Worst in Period B", worst["Company"], f"{worst['B Δ (%)']:.2f}%")
        else:
            st.metric("Worst in Period B", "—", "—")
    with c3:
        st.caption(
            "A = first selected period, B = second selected period. "
            "Vol = annualized volatility (approx). MaxDD = maximum drawdown within the period."
        )

    st.markdown("### Period Change Summary (Value + % + risk metrics)")
    st.dataframe(
        summary_df.style.format({
            "A Start": "{:,.3f}",
            "A End": "{:,.3f}",
            "A Δ (RM)": "{:,.3f}",
            "A Δ (%)": "{:,.2f}",
            "A Vol (%)": "{:,.2f}",
            "A MaxDD (%)": "{:,.2f}",
            "A CAGR (%)": "{:,.2f}",

            "B Start": "{:,.3f}",
            "B End": "{:,.3f}",
            "B Δ (RM)": "{:,.3f}",
            "B Δ (%)": "{:,.2f}",
            "B Vol (%)": "{:,.2f}",
            "B MaxDD (%)": "{:,.2f}",
            "B CAGR (%)": "{:,.2f}",

            "Δ(%) B - A": "{:,.2f}",
            "CAGR Gap (B - A)": "{:,.2f}",
        }),
        use_container_width=True
    )

    # Line chart (A vs B), normalized option
    line_df = pd.concat([x for x in line_frames if not x.empty], ignore_index=True) if line_frames else pd.DataFrame()
    if not line_df.empty:
        y_label = "Index (Start=100)" if normalize else "Price (RM)"
        st.markdown("### Price Performance Lines (A vs B)")
        fig_price = px.line(
            line_df,
            x="Date",
            y=price_col,
            color="Company",
            line_dash="Period",
            title=f"{price_col} Performance — Period A vs Period B",
            labels={price_col: y_label}
        )
        st.plotly_chart(fig_price, use_container_width=True)
    else:
        st.warning("No price data returned for the chosen periods (check dates / tickers).")

    # Optional candlestick (advanced, only meaningful for one company)
    if show_candles:
        if len(selected_companies) != 1:
            st.warning("Candlestick view is only enabled when you select exactly 1 company.")
        else:
            comp = selected_companies[0]
            ticker = _resolve_ticker(comp)
            hist = fetch_history(ticker, min(a_start, b_start), max(a_end, b_end))
            if hist.empty:
                st.warning("No OHLC data for candlestick.")
            else:
                st.markdown("### Candlestick (combined date window)")
                fig_c = go.Figure(
                    data=[go.Candlestick(
                        x=hist.index,
                        open=hist["Open"],
                        high=hist["High"],
                        low=hist["Low"],
                        close=hist["Close"],
                        name=comp
                    )]
                )
                fig_c.update_layout(
                    title=f"{comp} ({ticker}) Candlestick",
                    xaxis_title="Date",
                    yaxis_title="Price (RM)",
                )
                st.plotly_chart(fig_c, use_container_width=True)

    st.divider()

    # -----------------------------
    # 2) Revenue vs PATMI (bar chart)
    # -----------------------------
    st.subheader("💰 Revenue vs PATMI Comparison")

    rev_df = get_revenue_data(selected_companies, fin_start, fin_end)
    patmi_df = get_patmi_data(selected_companies, fin_start, fin_end)

    if rev_df is None:
        rev_df = pd.DataFrame()
    if patmi_df is None:
        patmi_df = pd.DataFrame()

    if not rev_df.empty and not patmi_df.empty:
        combined_df = rev_df.merge(patmi_df, on="Company", how="inner")

        # Expecting Revenue/PATMI in RM '000 based on your prior code. Keep your unit consistent.
        # If your functions already return RM, change divisor to 1_000_000 for "millions".
        combined_df["Revenue_M"] = (combined_df["Revenue"] / 1_000).round(2)
        combined_df["PATMI_M"] = (combined_df["PATMI"] / 1_000).round(2)

        fig_combined = go.Figure(data=[
            go.Bar(
                name="Revenue",
                x=combined_df["Company"],
                y=combined_df["Revenue"],
                text=combined_df["Revenue_M"].astype(str) + "M",
                textposition="outside"
            ),
            go.Bar(
                name="PATMI",
                x=combined_df["Company"],
                y=combined_df["PATMI"],
                text=combined_df["PATMI_M"].astype(str) + "M",
                textposition="outside"
            )
        ])

        fig_combined.update_layout(
            barmode="group",
            title=f"Revenue vs PATMI ({fin_start} → {fin_end})",
            xaxis_title="Company",
            yaxis_title="Amount (RM)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig_combined, use_container_width=True)
    else:
        st.warning("No Revenue or PATMI data available for the selected period.")

    st.divider()

    # -----------------------------
    # 3) Sales Target vs Actual (Placeholder)
    # -----------------------------
    st.subheader("🎯 Sales Target vs Actual (Placeholder)")
    st.info("This requires additional data (annual reports / sales target dataset).")
    # Example:
    # sales_df = pd.read_csv("sales_targets.csv")  # Columns: Company, Target, Actual
    # fig_sales = px.bar(sales_df, x="Company", y=["Target", "Actual"], barmode="group")
    # st.plotly_chart(fig_sales, use_container_width=True)


if __name__ == "__main__":
    main()
