# pages/balance_sheet.py
import streamlit as st
import pandas as pd
import yfinance as yf

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_COMPANY = "LBS Bina"

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

# Share count rows — unscaled (not RM thousands), no variance shown
ROWS_UNSCALED = {
    "Share Issued",
    "Ordinary Shares Number",
    "Preferred Shares Number",
    "Treasury Shares Number",
}

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_balance_sheet(ticker_code: str) -> pd.DataFrame:
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
        tk = companies.get(comp)
        if not tk:
            continue
        df = fetch_balance_sheet(tk)
        if not df.empty:
            all_dates.update([c for c in df.columns if pd.notna(c)])
    return sorted(all_dates, reverse=True)


def get_all_years(quarters: list) -> list:
    return sorted({q.year for q in quarters}, reverse=True)


# ── BUILD RAW TABLE ───────────────────────────────────────────────────────────
def build_raw_table(selected_companies: list, mode: str, period) -> pd.DataFrame:
    """Pure float DataFrame: index=ROW_ORDER, columns=company names."""
    # Always include LBS Bina as the first column
    ordered = [BASE_COMPANY] + [c for c in selected_companies if c != BASE_COMPANY]

    result = {}
    for comp in ordered:
        tk = companies.get(comp)
        if not tk:
            result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue
        df = fetch_balance_sheet(tk)
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
        else:
            yr_cols = sorted(
                [c for c in df.columns if pd.Timestamp(c).year == int(period)],
                reverse=True,
            )
            if not yr_cols:
                result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            else:
                result[comp] = df[yr_cols[0]].reindex(ROW_ORDER).astype(float)

    return pd.DataFrame(result, index=ROW_ORDER).astype(float)


# ── FORMATTING HELPERS ────────────────────────────────────────────────────────
def fmt_value(row_name: str, val) -> str:
    try:
        v = float(val)
    except Exception:
        return "--"
    if pd.isna(v) or v == 0:
        return "--"
    if v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"


def fmt_variance(diff: float, pct: float) -> str:
    """Return a variance string like '+1,234,567 (+12.3%)' or '(1,234,567) (-12.3%)'."""
    if pd.isna(diff) or pd.isna(pct):
        return ""
    abs_diff = abs(diff)
    abs_pct  = abs(pct)
    sign     = "+" if diff >= 0 else "-"
    return f"{sign}{abs_diff:,.0f}  ({sign}{abs_pct:.1f}%)"


# ── BUILD DISPLAY TABLE WITH VARIANCE ────────────────────────────────────────
def build_display_table(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Returns:
      display_df  — string DataFrame where each non-base company column is
                    replaced by two columns: value + variance vs LBS Bina
      cell_styles — dict mapping (row, col) → css colour string
    """
    base_col = BASE_COMPANY
    has_base = base_col in df_raw.columns

    display_cols = []   # ordered list of final column names
    col_data     = {}   # col_name → list of string values (indexed by ROW_ORDER)
    cell_styles  = {}   # (row_name, col_name) → css

    for comp in df_raw.columns:
        val_col  = comp
        var_col  = f"{comp} vs LBS Bina" if comp != base_col else None

        display_cols.append(val_col)
        col_data[val_col] = {}

        if var_col:
            display_cols.append(var_col)
            col_data[var_col] = {}

        for row in ROW_ORDER:
            raw_val  = df_raw.loc[row, comp]
            val_str  = fmt_value(row, raw_val)
            col_data[val_col][row] = val_str

            if var_col and has_base and row not in ROWS_UNSCALED:
                base_val = df_raw.loc[row, base_col]
                try:
                    v     = float(raw_val)
                    b     = float(base_val)
                    diff  = v - b
                    pct   = (diff / abs(b) * 100) if b != 0 else float("nan")
                    var_str = fmt_variance(diff, pct)
                    col_data[var_col][row] = var_str
                    # colour
                    if not pd.isna(diff) and var_str:
                        colour = "#16a34a" if diff >= 0 else "#dc2626"
                        cell_styles[(row, var_col)] = f"color:{colour};font-size:11px;"
                except Exception:
                    col_data[var_col][row] = ""
            elif var_col:
                col_data[var_col][row] = ""

    display_df = pd.DataFrame(col_data, index=ROW_ORDER)[display_cols]
    return display_df, cell_styles


# ── STREAMLIT PAGE ────────────────────────────────────────────────────────────
def main():
    st.title("📊 Company Balance Sheet – Quarterly")

    st.caption(
        "All monetary items in **RM thousands**. "
        "Share count rows are unscaled. "
        "**LBS Bina is always the base** — variance columns show each peer's difference vs LBS Bina. "
        "For **Year** view, the most recent quarter-end within that year is used. "
        "Negative values shown in brackets. "
        "Data from Yahoo Finance — may be delayed or estimated."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    col_comp, col_mode, col_period = st.columns([3, 1, 2])

    with col_comp:
        selected_companies = st.multiselect(
            "Select companies to compare",
            list(companies.keys()),
            default=["LBS Bina", "Matrix Concepts"],
            key="balance_sheet_multiselect",
        )

    with col_mode:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True,
                             key="bs_view_mode")

    # Always ensure LBS Bina is included
    if BASE_COMPANY not in selected_companies:
        selected_companies = [BASE_COMPANY] + selected_companies

    if len(selected_companies) == 0:
        st.info("Select at least one company to continue.")
        return

    with st.spinner("Loading available periods…"):
        quarters = get_all_quarters(selected_companies)
        years    = get_all_years(quarters)

    with col_period:
        if view_mode == "Quarter":
            if not quarters:
                st.warning("No data found.")
                return
            q_labels  = [q.strftime("%d %b %Y") for q in quarters]
            sel_label = st.selectbox("Select Quarter", q_labels, index=0,
                                     key="bs_quarter_select")
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found.")
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
        df_raw = build_raw_table(selected_companies, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned. Try a different period or company selection.")
        return

    display_df, cell_styles = build_display_table(df_raw)

    # ── Render ────────────────────────────────────────────────────────────────
    st.subheader(f"📄 Balance Sheet Comparison — {period_str}")
    if mode == "year":
        st.caption(f"Showing latest available quarter within {period_str} for each company.")

    # Build Styler
    def apply_styles(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for (row, col), css in cell_styles.items():
            if row in styles.index and col in styles.columns:
                styles.loc[row, col] = css
        return styles

    # Identify variance columns for lighter header treatment
    var_cols = [c for c in display_df.columns if "vs LBS Bina" in c]

    table_styles = [
        {
            "selector": "thead th",
            "props": [
                ("background-color", "#1e1e1e"),
                ("color", "white"),
                ("font-size", "12px"),
                ("white-space", "nowrap"),
                ("padding", "8px 10px"),
            ],
        },
        {
            "selector": "tbody td",
            "props": [
                ("background-color", "#121212"),
                ("color", "white"),
                ("font-size", "13px"),
                ("padding", "6px 10px"),
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
                ("padding", "6px 12px"),
                ("white-space", "nowrap"),
                ("min-width", "240px"),
                ("text-align", "left"),
            ],
        },
    ]

    # Dim the variance column headers slightly
    for vc in var_cols:
        table_styles.append({
            "selector": f'thead th[id="{vc}"]',
            "props": [("color", "#9ca3af"), ("font-style", "italic")],
        })

    styler = (
        display_df.style
        .apply(apply_styles, axis=None)
        .set_table_styles(table_styles)
    )

    st.dataframe(
        styler,
        use_container_width=True,
        height=min(38 * len(ROW_ORDER) + 40, 900),
    )

    # Legend
    st.markdown(
        "<p style='font-size:12px;color:#6b7280;margin-top:6px;'>"
        "<span style='color:#16a34a;font-weight:600;'>+green</span> = higher than LBS Bina &nbsp;·&nbsp; "
        "<span style='color:#dc2626;font-weight:600;'>-red</span> = lower than LBS Bina &nbsp;·&nbsp; "
        "Variance = peer − LBS Bina</p>",
        unsafe_allow_html=True,
    )

    # ── Download (raw values only, no variance cols) ──────────────────────────
    raw_display = pd.DataFrame(
        {comp: {row: fmt_value(row, df_raw.loc[row, comp]) for row in ROW_ORDER}
         for comp in df_raw.columns},
        index=ROW_ORDER,
    )
    csv = raw_display.to_csv().encode("utf-8")
    st.download_button(
        label=f"⬇️ Download CSV — {period_str}",
        data=csv,
        file_name=f"balance_sheet_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
        key="bs_download_btn",
    )
