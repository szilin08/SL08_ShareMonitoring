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


def variance_parts(diff: float, pct: float) -> tuple[str, bool]:
    """
    Returns (variance_string, is_positive).
    e.g. "+1,234 (+12.3%)" or "(1,234) (-12.3%)"
    """
    if pd.isna(diff) or pd.isna(pct):
        return "", True
    abs_diff = abs(diff)
    abs_pct  = abs(pct)
    is_pos   = diff >= 0
    sign     = "+" if is_pos else "-"
    return f"{sign}{abs_diff:,.0f} ({sign}{abs_pct:.1f}%)", is_pos


# ── BUILD HTML TABLE ──────────────────────────────────────────────────────────
def build_html_table(df_raw: pd.DataFrame) -> str:
    """
    Renders an HTML table where each peer company column shows the value on
    the top line and the coloured variance on a second line — no extra columns.
    """
    base_col = BASE_COMPANY
    has_base = base_col in df_raw.columns
    cols     = list(df_raw.columns)

    # ── styles ────────────────────────────────────────────────────────────────
    css = """
    <style>
    .bs-wrap {
        overflow-x: auto;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .bs-table {
        border-collapse: collapse;
        width: 100%;
        font-size: 13px;
        background: #121212;
        color: #f3f4f6;
    }
    .bs-table thead th {
        background: #1e1e1e;
        color: #f9fafb;
        font-size: 12px;
        font-weight: 600;
        padding: 10px 12px;
        text-align: right;
        white-space: nowrap;
        position: sticky;
        top: 0;
        z-index: 2;
        border-bottom: 1px solid #374151;
    }
    .bs-table thead th.row-label {
        text-align: left;
        min-width: 240px;
        position: sticky;
        left: 0;
        z-index: 3;
        background: #1e1e1e;
    }
    .bs-table tbody td {
        padding: 6px 12px;
        text-align: right;
        white-space: nowrap;
        border-bottom: 1px solid #1f2937;
        font-variant-numeric: tabular-nums;
        vertical-align: top;
        min-width: 140px;
    }
    .bs-table tbody td.row-label {
        text-align: left;
        color: #d1d5db;
        font-size: 12px;
        font-weight: 500;
        position: sticky;
        left: 0;
        background: #121212;
        z-index: 1;
        min-width: 240px;
    }
    .bs-table tbody tr:hover td {
        background: #1e2d40;
    }
    .bs-table tbody tr:hover td.row-label {
        background: #1e2d40;
    }
    .val-main  { display: block; }
    .val-var   { display: block; font-size: 11px; margin-top: 2px; }
    .pos       { color: #16a34a; }
    .neg       { color: #dc2626; }
    .base-col  { color: #f3f4f6; }
    </style>
    """

    # ── header row ────────────────────────────────────────────────────────────
    header_cells = '<th class="row-label">Metric</th>'
    for comp in cols:
        header_cells += f"<th>{comp}</th>"

    # ── body rows ─────────────────────────────────────────────────────────────
    body_rows = ""
    for row in ROW_ORDER:
        cells = f'<td class="row-label">{row}</td>'

        for comp in cols:
            raw_val = df_raw.loc[row, comp]
            val_str = fmt_value(row, raw_val)

            if comp == base_col:
                cells += f'<td><span class="val-main base-col">{val_str}</span></td>'
                continue

            # peer column — compute variance vs base
            var_html = ""
            if has_base and row not in ROWS_UNSCALED and val_str != "--":
                base_val = df_raw.loc[row, base_col]
                try:
                    v    = float(raw_val)
                    b    = float(base_val)
                    diff = v - b
                    pct  = (diff / abs(b) * 100) if b != 0 else float("nan")
                    var_str, is_pos = variance_parts(diff, pct)
                    if var_str:
                        colour_cls = "pos" if is_pos else "neg"
                        var_html   = f'<span class="val-var {colour_cls}">{var_str}</span>'
                except Exception:
                    pass

            cells += f'<td><span class="val-main">{val_str}</span>{var_html}</td>'

        body_rows += f"<tr>{cells}</tr>\n"

    html = f"""
    {css}
    <div class="bs-wrap">
      <table class="bs-table">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{body_rows}</tbody>
      </table>
    </div>
    """
    return html


# ── STREAMLIT PAGE ────────────────────────────────────────────────────────────
def main():
    st.title("📊 Company Balance Sheet – Quarterly")

    st.caption(
        "All monetary items in **RM thousands**. "
        "Share count rows are unscaled. "
        "**LBS Bina is always the base** — variance shown inline below each peer's value. "
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
        view_mode = st.radio(
            "View by", ["Quarter", "Year"], horizontal=True, key="bs_view_mode"
        )

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
            sel_label = st.selectbox(
                "Select Quarter", q_labels, index=0, key="bs_quarter_select"
            )
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found.")
                return
            sel_year   = st.selectbox(
                "Select Year", years, index=0, key="bs_year_select"
            )
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

    # ── Render ────────────────────────────────────────────────────────────────
    st.subheader(f"📄 Balance Sheet Comparison — {period_str}")
    if mode == "year":
        st.caption(
            f"Showing latest available quarter within {period_str} for each company."
        )

    html_table = build_html_table(df_raw)
    st.markdown(html_table, unsafe_allow_html=True)

    # Legend
    st.markdown(
        "<p style='font-size:12px;color:#6b7280;margin-top:10px;'>"
        "<span style='color:#16a34a;font-weight:600;'>+green</span> = higher than LBS Bina &nbsp;·&nbsp; "
        "<span style='color:#dc2626;font-weight:600;'>-red</span> = lower than LBS Bina &nbsp;·&nbsp; "
        "Variance = peer − LBS Bina &nbsp;·&nbsp; shown inline below each value</p>",
        unsafe_allow_html=True,
    )

    # ── Download ──────────────────────────────────────────────────────────────
    raw_display = pd.DataFrame(
        {
            comp: {row: fmt_value(row, df_raw.loc[row, comp]) for row in ROW_ORDER}
            for comp in df_raw.columns
        },
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
