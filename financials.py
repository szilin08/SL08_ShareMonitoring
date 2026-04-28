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
    """
    Returns DataFrame: index=ROW_ORDER, columns=quarter Timestamps.
    Money rows scaled to thousands. EPS/TaxRate unscaled.
    """
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
    """Return all unique quarter-end dates across selected companies, newest first."""
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
# BUILD TABLE
# rows = ROW_ORDER, columns = company names
# -------------------------
def build_comparison_table(selected_companies: list, mode: str, period) -> pd.DataFrame:
    """
    mode = 'quarter' → period is a Timestamp
    mode = 'year'    → period is an int year (sums quarters in that year)
    Returns pure float DataFrame: index=ROW_ORDER, columns=company names.
    """
    result = {}
    for comp in selected_companies:
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
# DISPLAY FORMATTING
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


def to_display(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Convert float DataFrame → all-string DataFrame for safe Styler use."""
    out = {}
    for comp in df_raw.columns:
        out[comp] = {row: fmt_cell(row, df_raw.loc[row, comp]) for row in df_raw.index}
    return pd.DataFrame(out, index=df_raw.index)


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
    st.title("📊 Company Financials – Quarterly")

    st.caption(
        "Most financial line items are shown in **thousands (RM'000)**. "
        "**Basic/Diluted EPS** and **Tax Rate For Calcs** are shown **unscaled**. "
        "Negative values shown in brackets. "
        "Data sourced from Yahoo Finance — may be delayed or estimated."
    )

    # ── Company & period selection ────────────────────────────────────────────
    col_comp, col_mode, col_period = st.columns([3, 1, 2])

    with col_comp:
        selected_companies = st.multiselect(
            "Select companies to compare",
            list(companies.keys()),
            default=["LBS Bina"],
        )

    with col_mode:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True)

    if not selected_companies:
        st.info("Select at least one company to continue.")
        return

    # Discover available periods from the selected companies
    with st.spinner("Loading available periods…"):
        quarters = get_all_quarters(selected_companies)
        years    = get_all_years(quarters)

    with col_period:
        if view_mode == "Quarter":
            if not quarters:
                st.warning("No data found for selected companies.")
                return
            q_labels   = [q.strftime("%d %b %Y") for q in quarters]
            sel_label  = st.selectbox("Select Quarter", q_labels, index=0)
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No data found for selected companies.")
                return
            sel_year   = st.selectbox("Select Year", years, index=0)
            period     = sel_year
            mode       = "year"
            period_str = str(sel_year)

    # ── Fetch button ──────────────────────────────────────────────────────────
    if not st.button("Fetch Financials", type="primary"):
        st.caption("Press **Fetch Financials** to load the comparison table.")
        return

    # ── Build table ───────────────────────────────────────────────────────────
    with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
        df_raw = build_comparison_table(selected_companies, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned. Try a different period or company selection.")
        return

    df_display = to_display(df_raw)

    # ── Render table ──────────────────────────────────────────────────────────
    st.subheader(f"📄 Financial Comparison — {period_str}")

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
        file_name=f"financials_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
    )
