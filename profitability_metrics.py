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

        revenue = df.loc["Total Revenue", col] if "Total Revenue" in df.index else None
        gross_profit = df.loc["Gross Profit", col] if "Gross Profit" in df.index else None
        operating_expense = df.loc["Operating Expense", col] if "Operating Expense" in df.index else None
        pretax_income = df.loc["Pretax Income", col] if "Pretax Income" in df.index else None
        tax_provision = df.loc["Tax Provision", col] if "Tax Provision" in df.index else None
        net_income = df.loc["Net Income Common Stockholders", col] if "Net Income Common Stockholders" in df.index else None
        ebitda = df.loc["EBITDA", col] if "EBITDA" in df.index else None
        interest_expense = df.loc["Interest Expense", col] if "Interest Expense" in df.index else None

        if pd.notna(revenue) and revenue != 0:

            if pd.notna(gross_profit):
                metrics.loc["Gross Margin (%)", col] = (gross_profit / revenue) * 100

            if pd.notna(gross_profit) and pd.notna(operating_expense):
                metrics.loc["Operating Margin (%)", col] = (
                    (gross_profit - operating_expense) / revenue
                ) * 100

            if pd.notna(pretax_income):
                metrics.loc["Profit Before Tax Margin (%)", col] = (
                    pretax_income / revenue
                ) * 100

            if pd.notna(pretax_income) and pd.notna(tax_provision):
                metrics.loc["Profit After Tax Margin (%)", col] = (
                    (pretax_income - tax_provision) / revenue
                ) * 100

            if pd.notna(net_income):
                metrics.loc["PATMI Margin (%)", col] = (
                    net_income / revenue
                ) * 100

            if pd.notna(ebitda):
                metrics.loc["EBITDA Margin (%)", col] = (
                    ebitda / revenue
                ) * 100

        if pd.notna(pretax_income) and pretax_income != 0:

            if pd.notna(tax_provision):
                metrics.loc["Effective Tax Rate (%)", col] = (
                    tax_provision / pretax_income
                ) * 100

            if pd.notna(interest_expense):
                metrics.loc["Interest Coverage Ratio (x)", col] = (
                    interest_expense / pretax_income
                )

    return metrics


# ----------------------------------------------------
# LIQUIDITY METRICS
# ----------------------------------------------------
def calculate_liquidity(bs):

    metrics = pd.DataFrame(index=[
        "Quick Ratio (x)",
        "Current Ratio (x)"
    ], columns=bs.columns)

    for col in bs.columns:

        current_assets = bs.loc["Current Assets", col] if "Current Assets" in bs.index else None
        inventory = bs.loc["Inventory", col] if "Inventory" in bs.index else 0
        current_liabilities = bs.loc["Current Liabilities", col] if "Current Liabilities" in bs.index else None

        if pd.notna(current_assets) and pd.notna(current_liabilities) and current_liabilities != 0:

            metrics.loc["Quick Ratio (x)", col] = (
                (current_assets - inventory) / current_liabilities
            )

            metrics.loc["Current Ratio (x)", col] = (
                current_assets / current_liabilities
            )

    return metrics


# ----------------------------------------------------
# RETURN METRICS
# ----------------------------------------------------
def calculate_return(df, bs):

    metrics = pd.DataFrame(index=[
        "Return on Equity (%)",
        "Return on Assets (%)"
    ], columns=bs.columns)

    for col in bs.columns:

        net_income = df.loc["Net Income Common Stockholders", col] if "Net Income Common Stockholders" in df.index and col in df.columns else None
        total_equity = bs.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in bs.index else None
        total_assets = bs.loc["Total Assets", col] if "Total Assets" in bs.index else None

        if pd.notna(net_income) and pd.notna(total_equity) and total_equity != 0:
            metrics.loc["Return on Equity (%)", col] = (
                net_income / total_equity
            ) * 100

        if pd.notna(net_income) and pd.notna(total_assets) and total_assets != 0:
            metrics.loc["Return on Assets (%)", col] = (
                net_income / total_assets
            ) * 100

    return metrics


# ----------------------------------------------------
# SOLVENCY METRICS
# ----------------------------------------------------
def calculate_solvency(bs):

    metrics = pd.DataFrame(index=[
        "Debt to Equity Attributable to Owners of the Parent (x)",
        "Debt to Equity (x)",
        "Net Debt to Equity Attributable to Owners of the Parent (x)",
        "Net Debt to Equity (x)"
    ], columns=bs.columns)

    for col in bs.columns:

        total_debt = bs.loc["Total Debt", col] if "Total Debt" in bs.index else None
        common_stock_equity = bs.loc["Common Stock Equity", col] if "Common Stock Equity" in bs.index else None
        total_equity = bs.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in bs.index else None
        net_debt = bs.loc["Net Debt", col] if "Net Debt" in bs.index else None

        if pd.notna(total_debt) and pd.notna(common_stock_equity) and common_stock_equity != 0:
            metrics.loc["Debt to Equity Attributable to Owners of the Parent (x)", col] = (
                total_debt / common_stock_equity
            )

        if pd.notna(total_debt) and pd.notna(total_equity) and total_equity != 0:
            metrics.loc["Debt to Equity (x)", col] = (
                total_debt / total_equity
            )

        if pd.notna(net_debt) and pd.notna(common_stock_equity) and common_stock_equity != 0:
            metrics.loc["Net Debt to Equity Attributable to Owners of the Parent (x)", col] = (
                net_debt / common_stock_equity
            )

        if pd.notna(net_debt) and pd.notna(total_equity) and total_equity != 0:
            metrics.loc["Net Debt to Equity (x)", col] = (
                net_debt / total_equity
            )

    return metrics


# ----------------------------------------------------
# HELPER
# ----------------------------------------------------
def format_columns_as_dates(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    df.columns = pd.to_datetime(df.columns).strftime("%m/%d/%Y")
    return df


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

            # Financials
            df = fetch_quarterly_financials(ticker_symbol)

            if df.empty:
                st.warning(f"No financial data available for {company}.")
                continue

            # Balance Sheet
            ticker = yf.Ticker(ticker_symbol)
            bs = ticker.quarterly_balance_sheet

            if bs is None or bs.empty:
                st.warning(f"No balance sheet data available for {company}.")
                continue

            st.header(company)

            # --------------------------------
            # PROFITABILITY
            # --------------------------------
            profitability_df = calculate_profitability(df)
            profitability_df = format_columns_as_dates(profitability_df)

            st.subheader("Profitability Metrics")
            st.dataframe(
                profitability_df.style.format("{:.2f}"),
                use_container_width=True
            )

            # --------------------------------
            # LIQUIDITY
            # --------------------------------
            liquidity_df = calculate_liquidity(bs)
            liquidity_df = format_columns_as_dates(liquidity_df)

            st.subheader("Liquidity Metrics")
            st.dataframe(
                liquidity_df.style.format("{:.2f}"),
                use_container_width=True
            )

            # --------------------------------
            # RETURN
            # --------------------------------
            return_df = calculate_return(df, bs)
            return_df = format_columns_as_dates(return_df)

            st.subheader("Return Metrics")
            st.dataframe(
                return_df.style.format("{:.2f}"),
                use_container_width=True
            )

            # --------------------------------
            # SOLVENCY
            # --------------------------------
            solvency_df = calculate_solvency(bs)
            solvency_df = format_columns_as_dates(solvency_df)

            st.subheader("Solvency Metrics")
            st.dataframe(
                solvency_df.style.format("{:.2f}"),
                use_container_width=True
            )


if __name__ == "__main__":
    main()
