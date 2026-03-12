import streamlit as st
import pandas as pd
from financials import companies, fetch_quarterly_financials

def main():

    st.title("📊 Profitability Metrics")

    selected_companies = st.multiselect(
        "Select companies",
        list(companies.keys()),
        default=["LBS Bina"]
    )

    if st.button("Calculate Profitability Metrics"):

        for company in selected_companies:

            df = fetch_quarterly_financials(companies[company])

            if df.empty:
                st.write(f"No financial data for {company}")
                continue

            # Use latest quarter
            latest = df.iloc[:, 0]

            revenue = latest.get("Total Revenue", 0)
            gross_profit = latest.get("Gross Profit", 0)
            operating_expense = latest.get("Operating Expense", 0)
            pretax_income = latest.get("Pretax Income", 0)
            tax_provision = latest.get("Tax Provision", 0)
            net_income = latest.get("Net Income Common Stockholders", 0)
            ebitda = latest.get("EBITDA", 0)
            interest_expense = latest.get("Interest Expense", 0)

            metrics = {}

            if revenue != 0:

                metrics["Gross Margin (%)"] = (gross_profit / revenue) * 100

                metrics["Operating Margin (%)"] = (
                    (gross_profit - operating_expense) / revenue
                ) * 100

                metrics["Profit Before Tax Margin (%)"] = (
                    pretax_income / revenue
                ) * 100

                metrics["Profit After Tax Margin (%)"] = (
                    (pretax_income - tax_provision) / revenue
                ) * 100

                metrics["PATMI Margin (%)"] = (
                    net_income / revenue
                ) * 100

                metrics["EBITDA Margin (%)"] = (
                    ebitda / revenue
                ) * 100

            if pretax_income != 0:

                metrics["Effective Tax Rate (%)"] = (
                    tax_provision / pretax_income
                ) * 100

                metrics["Interest Coverage Ratio (x)"] = (
                    interest_expense / pretax_income
                )

            metrics_df = pd.DataFrame(
                list(metrics.items()),
                columns=["Metric", company]
            )

            st.subheader(company)

            st.dataframe(
                metrics_df.style.format({company: "{:.2f}"})
            )
