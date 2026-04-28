# pages/balance_sheet.py
import streamlit as st
import pandas as pd
import yfinance as yf

# ── CONFIG ────────────────────────────────────────────────────────────────────
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
    "Matrix Concepts": "5236.KL",
    "Lagenda Properties": "7179.KL",
}

ROW_ORDER = [
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
    "Treasury Shares Number",
]

# Rows that are share counts — keep unscaled (not in RM thousands)
ROWS_UNSCALED = {
    "Share Issued",
    "Ordinary Shares Number",
    "Preferred Shares Number",
    "Treasury Shares Number",
}

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_balance_sheet(ticker_code: str) -> pd.DataFrame:
    """
    Returns DataFrame: index=ROW_ORDER, columns=quarter Timestamps.
    Money rows scaled to thousands. Share count rows unscaled.
    """
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_balance_sheet
    if df is None or df.empty:
        return pd.DataFrame(index=ROW_ORDER)
    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        df.columns = pd.to_datetime([str(c) for c in df.columns], errors="coerce")
    df = df.reindex(ROW_ORDER)
    df = df.apply(pd.to_numeric, errors="coerce")
    scale_rows = [r for r in df.index if r not in ROWS_UNSCALED]
    df.loc[scale_rows] = df.loc[scale_rows] / 1000.0
    return df


def get_all_quarters(selected_companies: list) -> list:
    all_dates = set()
    for comp in selected_companies:
        ticker = companies.get(comp)
        if not ticker:
            continue
        df = fetch_balance_sheet(ticker)
        if not df.empty:
            all_dates.update([c for c in df.columns if pd.notna(c)])
    return sorted(all_dates, reverse=True)


def get_all_years(quarters: list) -> list:
    return sorted({q.year for q in quarters}, reverse=True)


# ── BUILD COMPARISON TABLE ────────────────────────────────────────────────────
def build_comparison_table(selected_companies: list, mode: str, period) -> pd.DataFrame:
    """
    Returns pure float DataFrame: index=ROW_ORDER, columns=company names.
    mode='quarter' → period is a Timestamp
    mode='year'    → period is an int (takes the most recent quarter in that year,
                     since balance sheet is a point-in-time snapshot, not a sum)
    """
    result = {}
    for comp in selected_companies:
        ticker = companies.get(comp)
        if not ticker:
            result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue
        df = fetch_balance_sheet(ticker)
        if df.empty:
            result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue

        if mode == "quarter":
            target = pd.Timestamp(period)
            col = next((c for c in df.columns if pd.Timestamp(c) == target), None)
            if col is None:
                result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            else:
                result[comp] = df[col].reindex(ROW_ORDER).astype(float)

        else:  # year — use the latest quarter in that year (balance sheet = snapshot)
            yr_cols = sorted(
                [c for c in df.columns if pd.Timestamp(c).year == int(period)],
                reverse=True,
            )
            if not yr_cols:
                result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            else:
                result[comp] = df[yr_cols[0]].reindex(ROW_ORDER).astype(float)

    return pd.DataFrame(result, index=ROW_ORDER).astype(float)


# ── FORMATTING ────────────────────────────────────────────────────────────────
def fmt_cell(row_name: str, val) -> str:
    try:
        v = float(val)
    except Exception:
        return "--"
    if pd.isna(v) or v == 0:
        return "--"
    if row_name in ROWS_UNSCALED:
        return f"{v:,.0f}"
    if v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"


def to_display(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Convert float DataFrame → all-string DataFrame for safe Styler use."""
    out = {}
    for comp in df_raw.columns:
        out[comp] = {row: fmt_cell(row, df_raw.loc[row, comp]) for row in df_raw.index}
    return pd.DataFrame(out, index=df_raw.index)


# ── STREAMLIT PAGE ────────────────────────────────────────────────────────────
def main():
    st.title("📊 Company Balance Sheet – Quarterly")

    st.caption(
        "All monetary items are shown in **RM thousands**. "
        "Share count rows (Share Issued, Ordinary/Preferred/Treasury Shares) are unscaled. "
        "For **Year** view, the most recent quarter-end in that year is used "
        "(balance sheet is a point-in-time snapshot, not a sum). "
        "Negative values shown in brackets. "
        "Data sourced from Yahoo Finance — may be delayed or estimated."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    col_comp, col_mode, col_period = st.columns([3, 1, 2])

    with col_comp:
        selected_companies = st.multiselect(
            "Select companies to compare",
            list(companies.keys()),
            default=["LBS Bina"],
            key="balance_sheet_multiselect",
        )

    with col_mode:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True,
                             key="bs_view_mode")

    if not selected_companies:
        st.info("Select at least one company to continue.")
        return

    with st.spinner("Loading available periods…"):
        quarters = get_all_quarters(selected_companies)
        years    = get_all_years(quarters)

    with col_period:
        if view_mode == "Quarter":
            if not quarters:
                st.warning("No data found for selected companies.")
                return
            q_labels  = [q.strftime("%d %b %Y") for q in quarters]
            sel_label = st.selectbox("Select Quarter", q_labels, index=0,
                                     key="bs_quarter_select")
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found for selected companies.")
                return
            sel_year   = st.selectbox("Select Year", years, index=0,
                                      key="bs_year_select")
            period     = sel_year
            mode       = "year"
            period_str = str(sel_year)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    if not st.button("Fetch Balance Sheet", type="primary", key="bs_fetch_btn"):
        st.caption("Press **Fetch Balance Sheet** to load the comparison table.")
        return

    with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
        df_raw = build_comparison_table(selected_companies, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned. Try a different period or company selection.")
        return

    df_display = to_display(df_raw)

    # ── Render ────────────────────────────────────────────────────────────────
    st.subheader(f"📄 Balance Sheet Comparison — {period_str}")

    if mode == "year":
        st.caption(f"Showing latest available quarter within {period_str} for each company.")

    st.dataframe(
        df_display.style.set_table_styles([
            {
                "selector": "thead th",
                "props": [
                    ("background-color", "#1e1e1e"),
                    ("color", "white"),
                    ("font-size", "13px"),
                    ("white-space", "nowrap"),
                    ("padding", "8px 14px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("background-color", "#121212"),
                    ("color", "white"),
                    ("font-size", "13px"),
                    ("padding", "6px 14px"),
                    ("text-align", "right"),
                    ("font-variant-numeric", "tabular-nums"),
                ],
            },
            {
                "selector": "tbody tr:hover td",
                "props": [("background-color", "#1e2d40")],
            },
            {
                "selector": "th.row_heading",
                "props": [
                    ("background-color", "#121212"),
                    ("color", "#d1d5db"),
                    ("font-size", "12px"),
                    ("font-weight", "500"),
                    ("padding", "6px 14px"),
                    ("white-space", "nowrap"),
                    ("min-width", "260px"),
                    ("text-align", "left"),
                ],
            },
        ]),
        use_container_width=True,
        height=min(38 * len(ROW_ORDER) + 40, 900),
    )

    # ── Download ──────────────────────────────────────────────────────────────
    csv = df_display.to_csv().encode("utf-8")
    st.download_button(
        label=f"⬇️ Download CSV — {period_str}",
        data=csv,
        file_name=f"balance_sheet_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
        key="bs_download_btn",
    )
