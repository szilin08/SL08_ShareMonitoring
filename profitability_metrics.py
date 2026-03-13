import streamlit as st
import pandas as pd
import yfinance as yf
from financials import companies, fetch_quarterly_financials


# ----------------------------------------------------
# PROFITABILITY METRICS
# ----------------------------------------------------
def calculate_profitability(df):

    metrics = pd.DataFrame(index=[
        "Gross Margin (%)",
        "Operating Margin (%)",
        "Profit Before Tax Margin (%)",
        "Profit After Tax Margin (%)",
        "PATMI Margin (%)",
        "EBITDA Margin (%)",
        "Effective Tax Rate (%)",
        "Interest Coverage Ratio (x)"
    ], columns=df.columns)

    for col in df.columns:

        revenue = df.loc["Total Revenue", col]
        gross_profit = df.loc["Gross Profit", col]
        operating_expense = df.loc["Operating Expense", col]
        pretax_income = df.loc["Pretax Income", col]
        tax_provision = df.loc["Tax Provision", col]
        net_income = df.loc["Net Income Common Stockholders", col]
        ebitda = df.loc["EBITDA", col]
        interest_expense = df.loc["Interest Expense", col]

        if revenue != 0 and pd.notna(revenue):

            metrics.loc["Gross Margin (%)", col] = (gross_profit / revenue) * 100

            metrics.loc["Operating Margin (%)", col] = (
                (gross_profit - operating_expense) / revenue
            ) * 100

            metrics.loc["Profit Before Tax Margin (%)", col] = (
                pretax_income / revenue
            ) * 100

            metrics.loc["Profit After Tax Margin (%)", col] = (
                (pretax_income - tax_provision) / revenue
            ) * 100

            metrics.loc["PATMI Margin (%)", col] = (
                net_income / revenue
            ) * 100

            metrics.loc["EBITDA Margin (%)", col] = (
                ebitda / revenue
            ) * 100

        if pretax_income != 0 and pd.notna(pretax_income):

            metrics.loc["Effective Tax Rate (%)", col] = (
                tax_provision / pretax_income
            ) * 100

            metrics.loc["Interest Coverage Ratio (x)", col] = (
                interest_expense / pretax_income
            )

    return metrics


# ----------------------------------------------------
# LIQUIDITY METRICS
# ----------------------------------------------------
def calculate_liquidity(ticker_symbol):

    ticker = yf.Ticker(ticker_symbol)
    bs = ticker.quarterly_balance_sheet

    if bs is None or bs.empty:
        return pd.DataFrame()

    metrics = pd.DataFrame(index=[
        "Quick Ratio (x)",
        "Current Ratio (x)"
    ], columns=bs.columns)

    for col in bs.columns:

        current_assets = bs.loc["Current Assets", col] if "Current Assets" in bs.index else None
        inventory = bs.loc["Inventory", col] if "Inventory" in bs.index else 0
        current_liabilities = bs.loc["Current Liabilities", col] if "Current Liabilities" in bs.index else None

        if current_assets is not None and current_liabilities not in [None, 0]:

            metrics.loc["Quick Ratio (x)", col] = (
                (current_assets - inventory) / current_liabilities
            )

            metrics.loc["Current Ratio (x)", col] = (
                current_assets / current_liabilities
            )

    return metrics


# ----------------------------------------------------
# STREAMLIT PAGE
# ----------------------------------------------------
def main():

    st.title("📊 Financial Ratios")

    selected_companies = st.multiselect(
        "Select companies",
        list(companies.keys()),
        default=["LBS Bina"]
    )

    if st.button("Calculate Metrics"):

        for company in selected_companies:

            ticker_symbol = companies[company]

            # --------------------------------
            # PROFITABILITY SECTION
            # --------------------------------

            df = fetch_quarterly_financials(ticker_symbol)

            if df.empty:
                st.write("No financial data available.")
                continue

            profitability_df = calculate_profitability(df)

            profitability_df.columns = pd.to_datetime(
                profitability_df.columns
            ).strftime("%m/%d/%Y")

            st.subheader(f"{company} — Profitability Metrics")

            st.dataframe(
                profitability_df.style.format("{:.2f}"),
                use_container_width=True
            )

            # --------------------------------
            # LIQUIDITY SECTION
            # --------------------------------

            liquidity_df = calculate_liquidity(ticker_symbol)

            if not liquidity_df.empty:

                liquidity_df.columns = pd.to_datetime(
                    liquidity_df.columns
                ).strftime("%m/%d/%Y")

                st.subheader(f"{company} — Liquidity Metrics")

                st.dataframe(
                    liquidity_df.style.format("{:.2f}"),
                    use_container_width=True
                )
