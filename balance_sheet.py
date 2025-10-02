# pages/balance_sheet.py
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

# Define the exact row order
row_order = [
    "Total Assets",
    "Current Assets",
    "Cash, Cash Equivalents & Short Term Investments",
    "Cash And Cash Equivalents",
    "Cash",
    "Other Short Term Investments",
    "Inventory",
    "Raw Materials",
    "Finished Goods",
    "Prepaid Assets",
    "Restricted Cash",
    "Assets Held for Sale Current",
    "Total non-current assets",
    "Total Liabilities Net Minority Interest",
    "Current Liabilities",
    "Current Provisions",
    "Current Debt And Capital Lease Obligation",
    "Current Debt",
    "Current Capital Lease Obligation",
    "Total Non Current Liabilities Net Minority Interest",
    "Long Term Debt And Capital Lease Obligation",
    "Long Term Debt",
    "Long Term Capital Lease Obligation",
    "Tradeand Other Payables Non Current",
    "Total Equity Gross Minority Interest",
    "Stockholders' Equity",
    "Capital Stock",
    "Preferred Stock",
    "Common Stock",
    "Retained Earnings",
    "Treasury Stock",
    "Other Equity Interest",
    "Minority Interest",
    "Total Capitalization",
    "Preferred Stock Equity",
    "Common Stock Equity",
    "Capital Lease Obligations",
    "Net Tangible Assets",
    "Working Capital",
    "Invested Capital",
    "Tangible Book Value",
    "Total Debt",
    "Net Debt",
    "Share Issued",
    "Ordinary Shares Number",
    "Preferred Shares Number",
    "Treasury Shares Number"
]

def fetch_balance_sheet(ticker_code):
    """Fetch balance sheet data from yfinance and format in thousands"""
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_balance_sheet  # items as rows, dates as columns
    df = df.fillna(0)

    # Convert numeric columns to thousands
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col] / 1000

    # Format columns (dates) as strings
    df.columns = pd.to_datetime(df.columns).strftime('%m/%d/%Y')
    return df

def main():
    st.title("📊 Company Balance Sheet – Quarterly (Numbers in Thousands)")

    selected_companies = st.multiselect(
        "Select companies to view",
        list(companies.keys()),
        default=["LBS Bina"],
        key="balance_sheet_multiselect"
    )

    if st.button("Fetch Balance Sheets"):
        for company in selected_companies:
            try:
                df = fetch_balance_sheet(companies[company])

                # Reorder rows according to row_order
                df = df.reindex(row_order)

                st.subheader(f"📄 {company} Balance Sheet")
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
                    f"Download {company} Balance Sheet CSV",
                    csv,
                    file_name=f"{company.replace(' ', '_')}_balance_sheet.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Failed to fetch {company}: {e}")
