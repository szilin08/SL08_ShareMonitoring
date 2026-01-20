# dividend.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date

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

def _ticker_for_company(company: str) -> str | None:
    if company == BASE_COMPANY_NAME:
        return BASE_TICKER
    return COMPETITORS.get(company)

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_dividends(ticker: str) -> pd.DataFrame:
    """
    Yahoo Finance dividends via yfinance.
    Returns DataFrame with columns: Date, Dividend
    """
    t = yf.Ticker(ticker)
    s = t.dividends  # pandas Series indexed by date
    if s is None or len(s) == 0:
        return pd.DataFrame(columns=["Date", "Dividend"])

    df = s.reset_index()
    df.columns = ["Date", "Dividend"]
    df["Date"] = pd.to_datetime(df["Date"])
    df["Dividend"] = pd.to_numeric(df["Dividend"], errors="coerce")
    df = df.dropna(subset=["Dividend"]).sort_values("Date")
    return df

def build_dividend_dataset(selected_companies: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    rows = []
    for comp in selected_companies:
        ticker = _ticker_for_company(comp)
        if not ticker:
            continue

        df = fetch_dividends(ticker)
        if df.empty:
            continue

        df = df.copy()
        df["Company"] = comp
        df["Ticker"] = ticker
        rows.append(df)

    if not rows:
        return pd.DataFrame(columns=["Date", "Dividend", "Company", "Ticker"])

    all_df = pd.concat(rows, ignore_index=True)
    all_df["DateOnly"] = all_df["Date"].dt.date
    all_df = all_df[(all_df["DateOnly"] >= start_dt) & (all_df["DateOnly"] <= end_dt)].copy()
    all_df = all_df.drop(columns=["DateOnly"])
    all_df = all_df.sort_values(["Company", "Date"])
    return all_df

def annual_dividend_with_growth(df: pd.DataFrame) -> pd.DataFrame:
    """
    Columns: Company, Ticker, Year, AnnualDividend, YoY_Growth (decimal, e.g. 0.12 = 12%)
    """
    if df.empty:
        return pd.DataFrame(columns=["Company", "Ticker", "Year", "AnnualDividend", "YoY_Growth"])

    annual = (
        df.assign(Year=df["Date"].dt.year)
          .groupby(["Company", "Ticker", "Year"], as_index=False)["Dividend"]
          .sum()
          .rename(columns={"Dividend": "AnnualDividend"})
          .sort_values(["Company", "Year"])
    )
    annual["YoY_Growth"] = annual.groupby("Company")["AnnualDividend"].pct_change()
    return annual

def main():
    st.title("💸 Dividend Dashboard")

    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="div_start")
    end_dt = st.date_input("End date", value=date.today(), key="div_end")

    company_options = [BASE_COMPANY_NAME] + list(COMPETITORS.keys())
    selected_companies = st.multiselect(
        "Select companies",
        company_options,
        default=[BASE_COMPANY_NAME],
        key="div_companies",
    )

    if st.button("Generate Dividends", key="div_generate"):
        if not selected_companies:
            st.warning("Select at least 1 company.")
            return
        if start_dt > end_dt:
            st.error("Start date cannot be after end date.")
            return

        with st.spinner("Fetching dividend data from Yahoo Finance..."):
            df = build_dividend_dataset(selected_companies, start_dt, end_dt)

        if df.empty:
            st.warning("No dividend events found for this period (Yahoo Finance may have no data).")
            return

        # --- Summary totals ---
        st.subheader("📌 Total Dividends in Period")
        totals = (
            df.groupby("Company", as_index=False)["Dividend"]
              .sum()
              .rename(columns={"Dividend": "Total Dividend"})
              .sort_values("Total Dividend", ascending=False)
        )
        st.dataframe(totals.style.format({"Total Dividend": "{:.4f}"}), use_container_width=True)

        # --- Timeline chart ---
        st.subheader("📈 Dividend Payout Timeline")
        fig = px.scatter(
            df,
            x="Date",
            y="Dividend",
            color="Company",
            title=f"Dividend Events ({start_dt} → {end_dt})",
        )
        fig.update_traces(marker=dict(size=10), mode="markers")
        fig.update_layout(xaxis_title="Date", yaxis_title="Dividend (per share)")
        st.plotly_chart(fig, use_container_width=True)

        # --- Annual dividends line chart with YoY growth in hover ---
        annual = annual_dividend_with_growth(df)

        st.subheader("📊 Annual Dividends (YoY Growth in Hover)")
        ann_fig = px.line(
            annual,
            x="Year",
            y="AnnualDividend",
            color="Company",
            markers=True,
            title="Annual Dividend per Share",
            custom_data=["YoY_Growth"],
        )

        # Custom hover: show YoY% nicely, handle N/A (first year)
        ann_fig.update_traces(
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "Year: %{x}<br>"
                "Annual Dividend: %{y:.4f}<br>"
                "YoY Growth: %{customdata[0]:+.1%}<br>"
                "<extra></extra>"
            )
        )

        ann_fig.update_layout(xaxis_title="Year", yaxis_title="Annual Dividend (per share)")
        st.plotly_chart(ann_fig, use_container_width=True)

        st.caption("Tip: First year per company will show YoY as blank/NaN since there’s no prior year to compare.")

        # --- Table of events ---
        st.subheader("🧾 Dividend Event Table")
        table_df = df.copy()
        table_df["Date"] = table_df["Date"].dt.date
        st.dataframe(
            table_df.rename(columns={"Dividend": "Dividend (per share)"}).style.format({"Dividend (per share)": "{:.4f}"}),
            use_container_width=True,
        )

        st.caption("Note: Data source is Yahoo Finance via yfinance. Some KL tickers may have missing dividend history.")

if __name__ == "__main__":
    main()
