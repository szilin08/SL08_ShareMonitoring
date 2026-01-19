import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from financials import get_revenue_data, get_patmi_data  # <-- make sure you implemented these


# --- Fetch Stock Data ---
def fetch_data(ticker, start, end):
    return yf.Ticker(ticker).history(start=start, end=end)


def main():
    st.title("📊 Overview Dashboard")

    # Base + Competitors
    base_ticker = "5789.KL"
    competitors = {
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

    # Date range
    start = st.date_input("Start date", value=date(2020, 1, 1), key="overview_start")
    end = st.date_input("End date", value=date.today(), key="overview_end")


    # Company selection
    selected_companies = st.multiselect("Select companies", ["LBS Bina"] + list(competitors.keys()))

    if st.button("Generate Overview"):
        dfs = []
        for comp in selected_companies:
            ticker = base_ticker if comp == "LBS Bina" else competitors[comp]
            df = fetch_data(ticker, start, end + pd.Timedelta(days=1))
            df["Company"] = comp
            dfs.append(df)

        if dfs:
            df_all = pd.concat(dfs).reset_index()

            # --- Graph 1: Trading Volume ---
            st.subheader("📈 Trading Volume Comparison")
            fig_vol = px.line(df_all, x="Date", y="Volume", color="Company",
                              title="Trading Volume Over Time")
            st.plotly_chart(fig_vol, use_container_width=True)

            # --- Graph 2: Revenue + PATMI Combined ---
            st.subheader("💰 Revenue vs PATMI Comparison")
            rev_df = get_revenue_data(selected_companies, start, end)
            patmi_df = get_patmi_data(selected_companies, start, end)

            if not rev_df.empty and not patmi_df.empty:
                # Merge Revenue + PATMI into one table
                combined_df = rev_df.merge(patmi_df, on="Company", how="inner")

                # Format numbers to millions for labels
                combined_df["Revenue_M"] = (combined_df["Revenue"] / 1_000).round(2)
                combined_df["PATMI_M"] = (combined_df["PATMI"] / 1_000).round(2)

                fig_combined = go.Figure(data=[
                    go.Bar(
                        name="Revenue",
                        x=combined_df["Company"],
                        y=combined_df["Revenue"],
                        marker_color="steelblue",
                        text=combined_df["Revenue_M"].astype(str) + "M",   # show as millions
                        textposition="outside"
                    ),
                    go.Bar(
                        name="PATMI",
                        x=combined_df["Company"],
                        y=combined_df["PATMI"],
                        marker_color="darkorange",
                        text=combined_df["PATMI_M"].astype(str) + "M",    # show as millions
                        textposition="outside"
                    )
                ])

                fig_combined.update_layout(
                    barmode="group",
                    title=f"Revenue vs PATMI Comparison ({start} → {end})",
                    xaxis_title="Company",
                    yaxis_title="Amount (RM)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig_combined, use_container_width=True)
            else:
                st.warning("No Revenue or PATMI data available for the selected period.")


            # --- Graph 3: Sales Target vs Actual ---
            st.subheader("🎯 Sales Target vs Actual (Placeholder)")
            st.info("This requires additional data (annual reports / sales target dataset).")

            # Example placeholder if you later add CSV
            # sales_df = pd.read_csv("sales_targets.csv")  # Columns: Company, Target, Actual
            # fig_sales = px.bar(sales_df, x="Company", y=["Target", "Actual"], barmode="group")
            # st.plotly_chart(fig_sales, use_container_width=True)
