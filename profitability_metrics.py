import streamlit as st
import pandas as pd
from financials import companies, fetch_quarterly_financials


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


def main():

    st.title("📊 Profitability Metrics")

    selected_companies = st.multiselect(
        "Select companies",
        list(companies.keys()),
        default=["LBS Bina"]
    )

    if st.button("Calculate Metrics"):

        for company in selected_companies:

            df = fetch_quarterly_financials(companies[company])

            if df.empty:
                st.write("No data available.")
                continue

            metrics_df = calculate_profitability(df)

            # format columns like financial table
            metrics_df.columns = pd.to_datetime(metrics_df.columns).strftime("%m/%d/%Y")

            st.subheader(f"{company} Profitability Metrics")

            st.dataframe(
                metrics_df.style.format("{:.2f}")
            )
