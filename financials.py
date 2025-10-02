# pages/financials.py
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

# Define the exact order of financial items
ROW_ORDER = [
    "Total Revenue",
    "Cost Of Revenue",
    "Gross Profit",
    "Operating Expense",
    "Operating Income",
    "Net Non Operating Interest Income Expense",
    "Pretax Income",
    "Tax Provision",
    "Net Income Common Stockholders",
    "Diluted NI Available To Com Stockholders",
    "Basic EPS",
    "Diluted EPS",
    "Basic Average Shares",
    "Diluted Average Shares",
    "Total Operating Income As Reported",
    "Rent Expense Supplemental",
    "Total Expenses",
    "Net Income From Continuing & Discontinued Operation",
    "Normalized Income",
    "Interest Income",
    "Interest Expense",
    "Net Interest Income",
    "EBIT",
    "EBITDA",
    "Reconciled Cost Of Revenue",
    "Reconciled Depreciation",
    "Net Income From Continuing Operation Net Minority Interest",
    "Total Unusual Items Excluding Goodwill",
    "Total Unusual Items",
    "Normalized EBITDA",
    "Tax Rate For Calcs",
    "Tax Effect Of Unusual Items"
]

ROW_REVENUE = "Total Revenue"
ROW_PATMI = "Net Income From Continuing Operation Net Minority Interest"

def fetch_quarterly_financials(ticker_code):
    """
    Fetch quarterly financials and return a DataFrame:
    - rows = financial items
    - columns = quarter end dates (DatetimeIndex)
    - numeric values (converted to thousands)
    """
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_financials  # items as rows, dates as columns
    if df is None or df.empty:
        # return empty frame with expected index for safety
        empty = pd.DataFrame(columns=pd.to_datetime([]))
        empty = empty.reindex(ROW_ORDER)
        return empty

    # fill missing with NaN (keep numeric type)
    df = df.fillna(0)

    # Convert numeric columns to thousands
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col] / 1000.0

    # Keep columns as actual datetimes for filtering later
    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        # fallback: try parsing each column
        df.columns = pd.to_datetime([str(c) for c in df.columns], errors='coerce')

    # Reorder rows according to ROW_ORDER (this may introduce NaNs for missing rows)
    df = df.reindex(ROW_ORDER)

    return df

def _format_for_display(df):
    """
    Return a copy of df formatted for display:
    - column labels as 'MM/DD/YYYY'
    - replace exact zeros with '--'
    - format numbers with thousands separators (no decimals)
    """
    if df is None or df.empty:
        return df

    display_df = df.copy()

    # Convert columns to strings for display
    try:
        display_df.columns = display_df.columns.strftime('%m/%d/%Y')
    except Exception:
        display_df.columns = [str(c) for c in display_df.columns]

    # Replace exact zeros with '--' for clarity
    display_df = display_df.replace(0, '--')

    # Attempt to format numeric cells nicely: convert numeric cols to int and format
    for col in display_df.columns:
        # If column values are numeric, format them
        try:
            if pd.api.types.is_numeric_dtype(display_df[col]):
                display_df[col] = display_df[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else x)
        except Exception:
            # skip formatting if anything goes wrong
            pass

    return display_df

def main():
    st.title("📊 Company Financials – Quarterly (Numbers in Thousands)")

    selected_companies = st.multiselect(
        "Select companies to view",
        list(companies.keys()),
        default=["LBS Bina"]
    )

    if st.button("Fetch Financials"):
        for company in selected_companies:
            try:
                df = fetch_quarterly_financials(companies[company])

                # Prepare a display-friendly copy
                display_df = _format_for_display(df)

                # --- Style the table for dark theme ---
                st.subheader(f"📄 {company} Financial Table")
                if display_df is None or display_df.empty:
                    st.write("No financials available.")
                else:
                    st.dataframe(
                        display_df.style
                        .set_table_styles([
                            {'selector': 'thead',
                                'props': [('background-color', '#1e1e1e'), ('color', 'white')]},
                            {'selector': 'tbody',
                                'props': [('background-color', '#121212'), ('color', 'white')]}
                        ])
                    )

                    # --- Download CSV per company (raw numeric df) ---
                    csv = df.to_csv()
                    st.download_button(
                        f"Download {company} CSV",
                        csv,
                        file_name=f"{company.replace(' ', '_')}_financials.csv",
                        mime="text/csv"
                    )

            except Exception as e:
                st.error(f"Failed to fetch {company}: {e}")

def get_revenue_data(company_list, start=None, end=None):
    """
    Return DataFrame with columns: Company, Revenue (sum of quarters in [start,end]).
    start/end may be datetime.date, datetime.datetime, or pandas Timestamp.
    """
    records = []
    if start is not None:
        start = pd.to_datetime(start)
    if end is not None:
        end = pd.to_datetime(end)

    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "Revenue": 0})
            continue

        df = fetch_quarterly_financials(ticker)
        if ROW_REVENUE not in df.index:
            records.append({"Company": comp, "Revenue": 0})
            continue

        row = df.loc[ROW_REVENUE]

        # Ensure index is DatetimeIndex (should be) and values numeric
        try:
            idx = pd.DatetimeIndex(row.index)
        except Exception:
            idx = pd.to_datetime(row.index, errors='coerce')

        row.index = idx
        row = pd.to_numeric(row, errors='coerce')  # convert any weird strings to NaN

        if start is not None and end is not None:
            mask = (row.index >= start) & (row.index <= end)
            row = row.loc[mask]

        revenue_sum = float(row.dropna().sum()) if not row.dropna().empty else 0.0
        records.append({"Company": comp, "Revenue": revenue_sum})

    return pd.DataFrame(records)

def get_patmi_data(company_list, start=None, end=None):
    """
    Return DataFrame with columns: Company, PATMI (sum of quarters in [start,end]).
    """
    records = []
    if start is not None:
        start = pd.to_datetime(start)
    if end is not None:
        end = pd.to_datetime(end)

    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "PATMI": 0})
            continue

        df = fetch_quarterly_financials(ticker)
        if ROW_PATMI not in df.index:
            records.append({"Company": comp, "PATMI": 0})
            continue

        row = df.loc[ROW_PATMI]

        # Ensure index is DatetimeIndex and values numeric
        try:
            idx = pd.DatetimeIndex(row.index)
        except Exception:
            idx = pd.to_datetime(row.index, errors='coerce')

        row.index = idx
        row = pd.to_numeric(row, errors='coerce')

        if start is not None and end is not None:
            mask = (row.index >= start) & (row.index <= end)
            row = row.loc[mask]

        patmi_sum = float(row.dropna().sum()) if not row.dropna().empty else 0.0
        records.append({"Company": comp, "PATMI": patmi_sum})

    return pd.DataFrame(records)
