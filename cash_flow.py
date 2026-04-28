# pages/cash_flow.py
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
    "Operating Cash Flow",
    "Investing Cash Flow",
    "Financing Cash Flow",
    "End Cash Position",
    "Capital Expenditure",
    "Issuance of Capital Stock",
    "Issuance of Debt",
    "Repayment of Debt",
    "Repurchase of Capital Stock",
    "Free Cash Flow",
]

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_cash_flow(ticker_code: str) -> pd.DataFrame:
    """Returns DataFrame: index=ROW_ORDER, columns=quarter Timestamps, scaled to thousands."""
    ticker = yf.Ticker(ticker_code)
    df = ticker.quarterly_cashflow
    if df is None or df.empty:
        return pd.DataFrame(index=ROW_ORDER)
    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        df.columns = pd.to_datetime([str(c) for c in df.columns], errors="coerce")
    df = df.reindex(ROW_ORDER)
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df / 1000.0
    return df


def get_all_quarters(selected_companies: list) -> list:
    all_dates = set()
    for comp in selected_companies:
        tk = companies.get(comp)
        if not tk:
            continue
        df = fetch_cash_flow(tk)
        if not df.empty:
            all_dates.update([c for c in df.columns if pd.notna(c)])
    return sorted(all_dates, reverse=True)


def get_all_years(quarters: list) -> list:
    return sorted({q.year for q in quarters}, reverse=True)


# ── BUILD RAW TABLE ───────────────────────────────────────────────────────────
def build_raw_table(selected_companies: list, mode: str, period) -> pd.DataFrame:
    """Pure float DataFrame: index=ROW_ORDER, columns=company names (LBS Bina first)."""
    ordered = [BASE_COMPANY] + [c for c in selected_companies if c != BASE_COMPANY]

    result = {}
    for comp in ordered:
        tk = companies.get(comp)
        if not tk:
            result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue
        df = fetch_cash_flow(tk)
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
        else:  # year — sum quarters (cash flow is a flow, so summing is correct)
            yr_cols = [c for c in df.columns if pd.Timestamp(c).year == int(period)]
            if not yr_cols:
                result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            else:
                sub = df[yr_cols]
                vals = {}
                for row in ROW_ORDER:
                    if row not in sub.index:
                        vals[row] = float("nan")
                        continue
                    row_vals = pd.to_numeric(sub.loc[row], errors="coerce").dropna()
                    vals[row] = float(row_vals.sum()) if not row_vals.empty else float("nan")
                result[comp] = pd.Series(vals, dtype=float)

    return pd.DataFrame(result, index=ROW_ORDER).astype(float)


# ── FORMATTING HELPERS ────────────────────────────────────────────────────────
def fmt_value(val) -> str:
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
    if pd.isna(diff) or pd.isna(pct):
        return ""
    sign = "+" if diff >= 0 else "-"
    return f"{sign}{abs(diff):,.0f}  ({sign}{abs(pct):.1f}%)"


# ── BUILD DISPLAY TABLE WITH VARIANCE ────────────────────────────────────────
def build_display_table(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Returns display_df (strings) with value + variance columns for each peer,
    and cell_styles dict for colouring.
    """
    has_base  = BASE_COMPANY in df_raw.columns
    display_cols = []
    col_data     = {}
    cell_styles  = {}

    for comp in df_raw.columns:
        val_col = comp
        var_col = f"{comp} vs LBS Bina" if comp != BASE_COMPANY else None

        display_cols.append(val_col)
        col_data[val_col] = {}
        if var_col:
            display_cols.append(var_col)
            col_data[var_col] = {}

        for row in ROW_ORDER:
            raw_val = df_raw.loc[row, comp]
            col_data[val_col][row] = fmt_value(raw_val)

            if var_col and has_base:
                base_val = df_raw.loc[row, BASE_COMPANY]
                try:
                    v    = float(raw_val)
                    b    = float(base_val)
                    diff = v - b
                    pct  = (diff / abs(b) * 100) if b != 0 else float("nan")
                    var_str = fmt_variance(diff, pct)
                    col_data[var_col][row] = var_str
                    if var_str:
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
    st.title("📊 Company Cash Flow – Quarterly")

    st.caption(
        "All items shown in **RM thousands**. "
        "**LBS Bina is always the base** — variance columns show each peer's difference vs LBS Bina. "
        "For **Year** view, quarters are summed (cash flow is a period flow). "
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
            key="cash_flow_multiselect",
        )

    with col_mode:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True,
                             key="cf_view_mode")

    # Always ensure LBS Bina is included
    if BASE_COMPANY not in selected_companies:
        selected_companies = [BASE_COMPANY] + selected_companies

    if not selected_companies:
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
                                     key="cf_quarter_select")
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found.")
                return
            sel_year   = st.selectbox("Select Year", years, index=0,
                                      key="cf_year_select")
            period     = sel_year
            mode       = "year"
            period_str = str(sel_year)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    if not st.button("Fetch Cash Flow", type="primary", key="cf_fetch_btn"):
        st.caption("Press **Fetch Cash Flow** to load the comparison table.")
        return

    with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
        df_raw = build_raw_table(selected_companies, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned. Try a different period or company selection.")
        return

    display_df, cell_styles = build_display_table(df_raw)

    # ── Render ────────────────────────────────────────────────────────────────
    st.subheader(f"📄 Cash Flow Comparison — {period_str}")

    def apply_styles(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for (row, col), css in cell_styles.items():
            if row in styles.index and col in styles.columns:
                styles.loc[row, col] = css
        return styles

    st.dataframe(
        display_df.style
        .apply(apply_styles, axis=None)
        .set_table_styles([
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
                    ("min-width", "200px"),
                    ("text-align", "left"),
                ],
            },
        ]),
        use_container_width=True,
        height=min(38 * len(ROW_ORDER) + 40, 600),
    )

    st.markdown(
        "<p style='font-size:12px;color:#6b7280;margin-top:6px;'>"
        "<span style='color:#16a34a;font-weight:600;'>+green</span> = higher than LBS Bina &nbsp;·&nbsp; "
        "<span style='color:#dc2626;font-weight:600;'>-red</span> = lower than LBS Bina &nbsp;·&nbsp; "
        "Variance = peer − LBS Bina</p>",
        unsafe_allow_html=True,
    )

    # ── Download (clean values only, no variance cols) ────────────────────────
    raw_display = pd.DataFrame(
        {comp: {row: fmt_value(df_raw.loc[row, comp]) for row in ROW_ORDER}
         for comp in df_raw.columns},
        index=ROW_ORDER,
    )
    csv = raw_display.to_csv().encode("utf-8")
    st.download_button(
        label=f"⬇️ Download CSV — {period_str}",
        data=csv,
        file_name=f"cash_flow_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
        key="cf_download_btn",
    )
