# pages/cash_flow.py
import streamlit as st
import pandas as pd
import yfinance as yf

companies = {
    "LBS Bina": "5789.KL",
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

# Define row order
row_order = [
    "Operating Cash Flow",
    "Investing Cash Flow",
    "Financing Cash Flow",
    "End Cash Position",
    "Capital Expenditure",
    "Issuance of Capital Stock",
    "Issuance of Debt",
    "Repayment of Debt",
    "Repurchase of Capital Stock",
    "Free Cash Flow"
]

def fetch_cash_flow(ticker_code):
    """Fetch cash flow data from yfinance and format in thousands"""
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_cashflow  # rows: items, columns: dates
    df = df.fillna(0)

    # Convert numeric columns to thousands
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col] / 1000

    # Format columns as date strings
    df.columns = pd.to_datetime(df.columns).strftime('%m/%d/%Y')
    return df

def main():
    st.title("📊 Company Cash Flow – Quarterly (Numbers in Thousands)")

    selected_companies = st.multiselect(
        "Select companies to view",
        list(companies.keys()),
        default=["LBS Bina"],
        key="cash_flow_multiselect"
    )

    if st.button("Fetch Cash Flow"):
        for company in selected_companies:
            try:
                df = fetch_cash_flow(companies[company])

                # Reorder rows according to row_order
                df = df.reindex(row_order)

                st.subheader(f"📄 {company} Cash Flow")
                st.dataframe(
                    df.style
                    .set_table_styles([{
                        'selector': 'thead',
                        'props': [('background-color', '#1e1e1e'), ('color', 'white')]
                    }, {
                        'selector': 'tbody',
                        'props': [('background-color', '#121212'), ('color', 'white')]
                    }])
                    .format("{:,.0f}")
                )

                # Download CSV
                csv = df.to_csv().encode('utf-8')
                st.download_button(
                    f"Download {company} Cash Flow CSV",
                    csv,
                    file_name=f"{company.replace(' ', '_')}_cash_flow.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Failed to fetch {company}: {e}")
