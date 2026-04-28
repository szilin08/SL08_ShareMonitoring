# pages/financials.py
import streamlit as st
import pandas as pd
import yfinance as yf

# -------------------------
# CONFIG
# -------------------------
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
ROW_PATMI   = "Net Income From Continuing Operation Net Minority Interest"

ROWS_UNSCALED = {"Basic EPS", "Diluted EPS", "Tax Rate For Calcs"}

# -------------------------
# DATA FETCHING
# -------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_quarterly_financials(ticker_code: str) -> pd.DataFrame:
    t = yf.Ticker(ticker_code)
    df = t.quarterly_financials
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
        df = fetch_quarterly_financials(ticker)
        if not df.empty:
            all_dates.update([c for c in df.columns if pd.notna(c)])
    return sorted(all_dates, reverse=True)


def get_all_years(quarters: list) -> list:
    return sorted({q.year for q in quarters}, reverse=True)


# -------------------------
# BUILD RAW TABLE
# -------------------------
def build_comparison_table(selected_companies: list, mode: str, period) -> pd.DataFrame:
    # Always put LBS Bina first
    ordered = [BASE_COMPANY] + [c for c in selected_companies if c != BASE_COMPANY]

    result = {}
    for comp in ordered:
        ticker = companies.get(comp)
        if not ticker:
            result[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue

        df = fetch_quarterly_financials(ticker)
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

        else:  # year — sum money rows, average unscaled rows
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
                    if row_vals.empty:
                        vals[row] = float("nan")
                    elif row in ROWS_UNSCALED:
                        vals[row] = float(row_vals.mean())
                    else:
                        vals[row] = float(row_vals.sum())
                result[comp] = pd.Series(vals, dtype=float)

    return pd.DataFrame(result, index=ROW_ORDER).astype(float)


# -------------------------
# FORMATTING HELPERS
# -------------------------
def fmt_cell(row_name: str, val) -> str:
    try:
        v = float(val)
    except Exception:
        return "--"
    if pd.isna(v) or v == 0:
        return "--"
    if row_name in ("Basic EPS", "Diluted EPS"):
        return f"{v:.2f}"
    if row_name == "Tax Rate For Calcs":
        return f"{v:.6f}".rstrip("0").rstrip(".")
    if v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"


def fmt_variance(diff: float, pct: float) -> str:
    if pd.isna(diff) or pd.isna(pct):
        return ""
    sign = "+" if diff >= 0 else "-"
    return f"{sign}{abs(diff):,.0f}  ({sign}{abs(pct):.1f}%)"


# -------------------------
# BUILD DISPLAY TABLE WITH VARIANCE
# -------------------------
def build_display_table(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Returns:
      display_df  — string DataFrame; each peer company gets a value col +
                    a 'vs LBS Bina' variance col inserted right after it.
      cell_styles — dict (row, col) → css string for variance colouring.
    """
    base_col = BASE_COMPANY
    has_base = base_col in df_raw.columns

    display_cols = []
    col_data     = {}
    cell_styles  = {}

    for comp in df_raw.columns:
        val_col = comp
        var_col = f"{comp} vs LBS Bina" if comp != base_col else None

        display_cols.append(val_col)
        col_data[val_col] = {}

        if var_col:
            display_cols.append(var_col)
            col_data[var_col] = {}

        for row in ROW_ORDER:
            raw_val = df_raw.loc[row, comp]
            val_str = fmt_cell(row, raw_val)
            col_data[val_col][row] = val_str

            if var_col and has_base and row not in ROWS_UNSCALED:
                base_val = df_raw.loc[row, base_col]
                try:
                    v    = float(raw_val)
                    b    = float(base_val)
                    diff = v - b
                    pct  = (diff / abs(b) * 100) if b != 0 else float("nan")
                    var_str = fmt_variance(diff, pct)
                    col_data[var_col][row] = var_str
                    if not pd.isna(diff) and var_str:
                        colour = "#16a34a" if diff >= 0 else "#dc2626"
                        cell_styles[(row, var_col)] = f"color:{colour};font-size:11px;"
                except Exception:
                    col_data[var_col][row] = ""
            elif var_col:
                col_data[var_col][row] = ""

    display_df = pd.DataFrame(col_data, index=ROW_ORDER)[display_cols]
    return display_df, cell_styles


# -------------------------
# METRICS HELPERS (used by other pages)
# -------------------------
def get_revenue_data(company_list, start=None, end=None) -> pd.DataFrame:
    records = []
    start = pd.to_datetime(start) if start is not None else None
    end   = pd.to_datetime(end)   if end   is not None else None
    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "Revenue": 0.0}); continue
        df = fetch_quarterly_financials(ticker)
        if df.empty or ROW_REVENUE not in df.index:
            records.append({"Company": comp, "Revenue": 0.0}); continue
        row = pd.to_numeric(df.loc[ROW_REVENUE], errors="coerce")
        row.index = pd.to_datetime(row.index, errors="coerce")
        if start is not None and end is not None:
            row = row.loc[(row.index >= start) & (row.index <= end)]
        records.append({"Company": comp, "Revenue": float(row.dropna().sum()) if not row.dropna().empty else 0.0})
    return pd.DataFrame(records)


def get_patmi_data(company_list, start=None, end=None) -> pd.DataFrame:
    records = []
    start = pd.to_datetime(start) if start is not None else None
    end   = pd.to_datetime(end)   if end   is not None else None
    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            records.append({"Company": comp, "PATMI": 0.0}); continue
        df = fetch_quarterly_financials(ticker)
        if df.empty or ROW_PATMI not in df.index:
            records.append({"Company": comp, "PATMI": 0.0}); continue
        row = pd.to_numeric(df.loc[ROW_PATMI], errors="coerce")
        row.index = pd.to_datetime(row.index, errors="coerce")
        if start is not None and end is not None:
            row = row.loc[(row.index >= start) & (row.index <= end)]
        records.append({"Company": comp, "PATMI": float(row.dropna().sum()) if not row.dropna().empty else 0.0})
    return pd.DataFrame(records)


# -------------------------
# STREAMLIT PAGE
# -------------------------
def main():
    st.title("📊 Company Financials – Quarterly / Yearly")

    st.caption(
        "Most financial line items are shown in **thousands (RM'000)**. "
        "**Basic/Diluted EPS** and **Tax Rate For Calcs** are shown **unscaled**. "
        "**LBS Bina is always the base** — variance columns show each peer's difference vs LBS Bina. "
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
            key="fin_multiselect",
        )

    with col_mode:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True,
                             key="fin_view_mode")

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
                st.warning("No data found for selected companies.")
                return
            q_labels  = [q.strftime("%d %b %Y") for q in quarters]
            sel_label = st.selectbox("Select Quarter", q_labels, index=0,
                                     key="fin_quarter_select")
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found for selected companies.")
                return
            sel_year   = st.selectbox("Select Year", years, index=0,
                                      key="fin_year_select")
            period     = sel_year
            mode       = "year"
            period_str = str(sel_year)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    if not st.button("Fetch Financials", type="primary", key="fin_fetch_btn"):
        st.caption("Press **Fetch Financials** to load the comparison table.")
        return

    with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
        df_raw = build_comparison_table(selected_companies, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned. Try a different period or company selection.")
        return

    display_df, cell_styles = build_display_table(df_raw)

    # ── Render ────────────────────────────────────────────────────────────────
    st.subheader(f"📄 Financial Comparison — {period_str}")

    def apply_styles(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for (row, col), css in cell_styles.items():
            if row in styles.index and col in styles.columns:
                styles.loc[row, col] = css
        return styles

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
                ("min-width", "260px"),
                ("text-align", "left"),
            ],
        },
    ]

    # Dim variance column headers
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
        {comp: {row: fmt_cell(row, df_raw.loc[row, comp]) for row in ROW_ORDER}
         for comp in df_raw.columns},
        index=ROW_ORDER,
    )
    csv = raw_display.to_csv().encode("utf-8")
    st.download_button(
        label=f"⬇️ Download CSV — {period_str}",
        data=csv,
        file_name=f"financials_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
        key="fin_download_btn",
    )
