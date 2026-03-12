import streamlit as st
import yfinance as yf
import pandas as pd

def main():

    st.title("Profitability Metrics")

    ticker_symbol = st.session_state.get("selected_ticker", "LBS.BK")
    ticker = yf.Ticker(ticker_symbol)

    financials = ticker.financials

    if financials.empty:
        st.warning("No financial data available.")
        return

    # Use latest year
    data = financials.iloc[:, 0]

    revenue = data.get("Total Revenue", None)
    gross_profit = data.get("Gross Profit", None)
    operating_income = data.get("Operating Income", None)
    pretax_income = data.get("Pretax Income", None)
    tax_provision = data.get("Tax Provision", None)
    net_income = data.get("Net Income", None)
    interest_expense = data.get("Interest Expense", None)
    ebitda = data.get("EBITDA", None)

    metrics = {}

    if revenue:
        if gross_profit:
            metrics["Gross Margin (%)"] = gross_profit / revenue * 100

        if operating_income:
            metrics["Operating Margin (%)"] = operating_income / revenue * 100

        if pretax_income:
            metrics["Profit Before Tax Margin (%)"] = pretax_income / revenue * 100

        if pretax_income and tax_provision:
            metrics["Profit After Tax Margin (%)"] = (pretax_income - tax_provision) / revenue * 100

        if net_income:
            metrics["PATMI Margin (%)"] = net_income / revenue * 100

        if ebitda:
            metrics["EBITDA Margin (%)"] = ebitda / revenue * 100

    if pretax_income and tax_provision:
        metrics["Effective Tax Rate (%)"] = tax_provision / pretax_income * 100

    if pretax_income and interest_expense:
        metrics["Interest Coverage Ratio (x)"] = pretax_income / interest_expense

    metrics_df = pd.DataFrame(
        list(metrics.items()),
        columns=["Metric", "Value"]
    )

    st.dataframe(metrics_df.style.format({"Value": "{:.2f}"}))
