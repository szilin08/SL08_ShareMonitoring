# pages/financials.py
import streamlit as st
import pandas as pd
import yfinance as yf

# -------------------------
# CONFIG
# -------------------------
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

# Exact order of financial items (rows)
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
    "Tax Effect Of Unusual Items",
]

ROW_REVENUE = "Total Revenue"
ROW_PATMI = "Net Income From Continuing Operation Net Minority Interest"

# Rows that should NOT be scaled to thousands (ratios / per-share)
ROWS_UNSCALED = {
    "Basic EPS",
    "Diluted EPS",
    "Tax Rate For Calcs",
}

# -------------------------
# DATA FETCHING
# -------------------------
def fetch_quarterly_financials(ticker_code: str) -> pd.DataFrame:
    """
    Returns a DataFrame:
      - index: financial items (ROW_ORDER)
      - columns: quarter end dates (Timestamp)
      - values:
          * most items scaled to thousands
          * EPS + Tax Rate NOT scaled
    """
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_financials  # rows=items, cols=dates

    if df is None or df.empty:
        empty = pd.DataFrame(columns=pd.to_datetime([]))
        return empty.reindex(ROW_ORDER)

    # Ensure datetime columns (quarter end)
    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        df.columns = pd.to_datetime([str(c) for c in df.columns], errors="coerce")

    # Reindex to our preferred row order (keeps missing rows as NaN)
    df = df.reindex(ROW_ORDER)

    # Coerce everything numeric where possible
    df = df.apply(pd.to_numeric, errors="coerce")

    # Scale only non-EPS/non-rate rows
    scale_rows = [r for r in df.index if r not in ROWS_UNSCALED]
    df.loc[scale_rows] = df.loc[scale_rows] / 1000.0

    return df

# -------------------------
# DISPLAY FORMATTING
# -------------------------
def _detect_tax_rate_is_fraction(series: pd.Series) -> bool:
    """
    Heuristic: If typical values are between 0 and 1, treat as fraction (0.24).
    If typical values are > 1, treat as already percent (24).
    """
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return True  # default safe assumption: fraction
    typical = vals.abs().median()
    return typical <= 1.0

def format_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    Display rules:
      - columns shown as MM/DD/YYYY
      - exact 0 shown as '--'
      - money rows (thousands): comma, 0 decimals
      - EPS: 2 decimals
      - Tax Rate: % with 1 decimal (auto detects 0.24 vs 24)
    """
    if df is None or df.empty:
        return df

    display_df = df.copy()

    # Convert column labels to strings
    try:
        display_df.columns = pd.to_datetime(display_df.columns).strftime("%m/%d/%Y")
    except Exception:
        display_df.columns = [str(c) for c in display_df.columns]

    # Replace exact zeros with --
    display_df = display_df.replace(0, "--")

    # Detect how tax rate is represented (fraction vs percent)
    tax_is_fraction = True
    if "Tax Rate For Calcs" in df.index:
        tax_is_fraction = _detect_tax_rate_is_fraction(df.loc["Tax Rate For Calcs"])

    def fmt_cell(row_name: str, x):
        if x == "--" or pd.isna(x):
            return x
        try:
            val = float(x)
        except Exception:
            return x

        if row_name in ("Basic EPS", "Diluted EPS"):
            return f"{val:.2f}"

        if row_name == "Tax Rate For Calcs":
            pct = val * 100.0 if tax_is_fraction else val
            return f"{pct:.1f}%"

        # default money-ish rows in thousands
        return f"{val:,.0f}"

    for r in display_df.index:
        display_df.loc[r] = display_df.loc[r].apply(lambda x: fmt_cell(r, x))

    return display_df

# -------------------------
# METRICS HELPERS
# -------------------------
def get_revenue_data(company_list, start=None, end=None) -> pd.DataFrame:
    """
    Return DataFrame with columns: Company, Revenue (sum of quarters in [start,end]).
    Revenue is in thousands (because scaling is applied).
    """
    records = []
    start = pd.to_datetime(start) if start is not None else None
    end = pd.to_datetime(end) if end is not None else None

    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "Revenue": 0.0})
            continue

        df = fetch_quarterly_financials(ticker)
        if df.empty or ROW_REVENUE not in df.index:
            records.append({"Company": comp, "Revenue": 0.0})
            continue

        row = pd.to_numeric(df.loc[ROW_REVENUE], errors="coerce")
        row.index = pd.to_datetime(row.index, errors="coerce")

        if start is not None and end is not None:
            row = row.loc[(row.index >= start) & (row.index <= end)]

        revenue_sum = float(row.dropna().sum()) if not row.dropna().empty else 0.0
        records.append({"Company": comp, "Revenue": revenue_sum})

    return pd.DataFrame(records)

def get_patmi_data(company_list, start=None, end=None) -> pd.DataFrame:
    """
    Return DataFrame with columns: Company, PATMI (sum of quarters in [start,end]).
    PATMI is in thousands (because scaling is applied).
    """
    records = []
    start = pd.to_datetime(start) if start is not None else None
    end = pd.to_datetime(end) if end is not None else None

    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "PATMI": 0.0})
            continue

        df = fetch_quarterly_financials(ticker)
        if df.empty or ROW_PATMI not in df.index:
            records.append({"Company": comp, "PATMI": 0.0})
            continue

        row = pd.to_numeric(df.loc[ROW_PATMI], errors="coerce")
        row.index = pd.to_datetime(row.index, errors="coerce")

        if start is not None and end is not None:
            row = row.loc[(row.index >= start) & (row.index <= end)]

        patmi_sum = float(row.dropna().sum()) if not row.dropna().empty else 0.0
        records.append({"Company": comp, "PATMI": patmi_sum})

    return pd.DataFrame(records)

# -------------------------
# STREAMLIT PAGE
# -------------------------
def main():
    st.title("📊 Company Financials – Quarterly")

    st.caption(
        "Disclaimer: Most financial line items are shown in **thousands**. "
        "**Basic/Diluted EPS** and **Tax Rate** are shown **unscaled**. "
        "Data is sourced from Yahoo Finance (yfinance) and may be delayed, estimated, or incomplete. "
        "Use audited statements for official reporting."
    )

    selected_companies = st.multiselect(
        "Select companies to view",
        list(companies.keys()),
        default=["LBS Bina"],
    )

    if st.button("Fetch Financials"):
        for company in selected_companies:
            try:
                df = fetch_quarterly_financials(companies[company])
                display_df = format_for_display(df)

                st.subheader(f"📄 {company} Financial Table")

                if display_df is None or display_df.empty:
                    st.write("No financials available.")
                    continue

                st.dataframe(
                    display_df.style.set_table_styles(
                        [
                            {
                                "selector": "thead",
                                "props": [
                                    ("background-color", "#1e1e1e"),
                                    ("color", "white"),
                                ],
                            },
                            {
                                "selector": "tbody",
                                "props": [
                                    ("background-color", "#121212"),
                                    ("color", "white"),
                                ],
                            },
                        ]
                    ),
                    use_container_width=True,
                )

                csv = df.to_csv()
                st.download_button(
                    label=f"Download {company} CSV",
                    data=csv,
                    file_name=f"{company.replace(' ', '_')}_financials.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.error(f"Failed to fetch {company}: {e}")


