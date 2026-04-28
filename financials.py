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
ROW_PATMI = "Net Income From Continuing Operation Net Minority Interest"

ROWS_UNSCALED = {
    "Basic EPS",
    "Diluted EPS",
    "Tax Rate For Calcs",
}

# Row groupings for visual separation
ROW_GROUPS = {
    "Income Statement": [
        "Total Revenue", "Cost Of Revenue", "Gross Profit",
        "Operating Expense", "Operating Income",
    ],
    "Below Operating": [
        "Net Non Operating Interest Income Expense", "Pretax Income",
        "Tax Provision", "Net Income Common Stockholders",
        "Diluted NI Available To Com Stockholders",
    ],
    "Per Share": [
        "Basic EPS", "Diluted EPS",
        "Basic Average Shares", "Diluted Average Shares",
    ],
    "Other Metrics": [
        "Total Operating Income As Reported", "Rent Expense Supplemental",
        "Total Expenses", "Net Income From Continuing & Discontinued Operation",
        "Normalized Income", "Interest Income", "Interest Expense",
        "Net Interest Income", "EBIT", "EBITDA",
        "Reconciled Cost Of Revenue", "Reconciled Depreciation",
        "Net Income From Continuing Operation Net Minority Interest",
        "Total Unusual Items Excluding Goodwill", "Total Unusual Items",
        "Normalized EBITDA", "Tax Rate For Calcs", "Tax Effect Of Unusual Items",
    ],
}

# -------------------------
# DATA FETCHING
# -------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_quarterly_financials(ticker_code: str) -> pd.DataFrame:
    t = yf.Ticker(ticker_code)
    df = t.quarterly_financials

    if df is None or df.empty:
        return pd.DataFrame(columns=pd.to_datetime([]))

    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        df.columns = pd.to_datetime([str(c) for c in df.columns], errors="coerce")

    df = df.reindex(ROW_ORDER)
    df = df.apply(pd.to_numeric, errors="coerce")

    scale_rows = [r for r in df.index if r not in ROWS_UNSCALED]
    df.loc[scale_rows] = df.loc[scale_rows] / 1000.0

    return df


def get_available_quarters(company_list: list) -> list[str]:
    """Collect all unique quarters across selected companies, sorted descending."""
    all_dates = set()
    for comp in company_list:
        ticker = companies.get(comp)
        if not ticker:
            continue
        df = fetch_quarterly_financials(ticker)
        if not df.empty:
            for col in df.columns:
                try:
                    all_dates.add(pd.to_datetime(col))
                except Exception:
                    pass
    sorted_dates = sorted(all_dates, reverse=True)
    return sorted_dates


def get_available_years(quarters: list) -> list[int]:
    return sorted({q.year for q in quarters}, reverse=True)


# -------------------------
# BUILD COMPARISON TABLE
# (rows = financial items, columns = companies)
# -------------------------
def build_comparison_table(
    selected_companies: list,
    mode: str,          # "quarter" | "year"
    period,             # Timestamp (quarter) | int (year)
    row_filter: list | None = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame:
      rows    = financial items (ROW_ORDER or subset)
      columns = company names
      values  = numbers in thousands (or unscaled for EPS/Tax)
    """
    rows = row_filter if row_filter else ROW_ORDER
    result = pd.DataFrame(index=rows)

    for comp in selected_companies:
        ticker = companies.get(comp)
        if not ticker:
            result[comp] = pd.NA
            continue

        df = fetch_quarterly_financials(ticker)
        if df.empty:
            result[comp] = pd.NA
            continue

        if mode == "quarter":
            # Find the closest matching column
            target = pd.to_datetime(period)
            matched = None
            for col in df.columns:
                try:
                    if pd.to_datetime(col) == target:
                        matched = col
                        break
                except Exception:
                    pass
            if matched is None:
                result[comp] = pd.NA
            else:
                result[comp] = df[matched].reindex(rows)

        elif mode == "year":
            year = int(period)
            year_cols = [c for c in df.columns if pd.to_datetime(c).year == year]
            if not year_cols:
                result[comp] = pd.NA
            else:
                subset = df[year_cols]
                # Sum money rows; average ratio rows
                series_list = []
                for row in rows:
                    if row not in df.index:
                        series_list.append(pd.NA)
                        continue
                    vals = pd.to_numeric(subset.loc[row], errors="coerce").dropna()
                    if vals.empty:
                        series_list.append(pd.NA)
                    elif row in ROWS_UNSCALED:
                        series_list.append(vals.mean())
                    else:
                        series_list.append(vals.sum())
                result[comp] = series_list

    return result


# -------------------------
# DISPLAY FORMATTING
# -------------------------
def fmt_cell(row_name: str, x):
    if pd.isna(x):
        return "—"
    try:
        val = float(x)
    except Exception:
        return str(x)

    if val == 0:
        return "—"

    if row_name in ("Basic EPS", "Diluted EPS"):
        return f"{val:.2f}"
    if row_name == "Tax Rate For Calcs":
        return f"{val:.6f}".rstrip("0").rstrip(".")

    # Money rows in thousands
    if val < 0:
        return f"({abs(val):,.0f})"
    return f"{val:,.0f}"


def style_comparison_table(df_display: pd.DataFrame, df_raw: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply conditional styling: highlight negatives in red, positives in green for key rows."""
    highlight_rows = {
        "Total Revenue", "Gross Profit", "Operating Income",
        "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest",
        "EBIT", "EBITDA",
    }

    def color_cell(val, row_name, raw_val):
        if val == "—":
            return "color: var(--color-text-secondary, #888)"
        if row_name in highlight_rows:
            try:
                v = float(raw_val)
                if v < 0:
                    return "color: #c0392b; font-weight: 500"
                elif v > 0:
                    return "color: #27ae60; font-weight: 500"
            except Exception:
                pass
        return ""

    styles = pd.DataFrame("", index=df_display.index, columns=df_display.columns)
    for row in df_display.index:
        for col in df_display.columns:
            raw = df_raw.loc[row, col] if (row in df_raw.index and col in df_raw.columns) else pd.NA
            styles.loc[row, col] = color_cell(df_display.loc[row, col], row, raw)

    return df_display.style.apply(lambda _: styles, axis=None)


# -------------------------
# STREAMLIT PAGE
# -------------------------
def main():
    st.title("📊 Company Financials – Comparison View")

    st.caption(
        "Money rows shown in **RM thousands**. "
        "**Basic/Diluted EPS** and **Tax Rate For Calcs** are unscaled. "
        "Negative values shown in brackets. "
        "Data from Yahoo Finance (yfinance) — may be delayed or estimated."
    )

    # ── Company selection ────────────────────────────────────────────────────
    selected_companies = st.multiselect(
        "Select companies to compare",
        list(companies.keys()),
        default=["LBS Bina", "Mah Sing", "Matrix Concepts"],
        help="Each company becomes a column in the table.",
    )

    if not selected_companies:
        st.info("Select at least one company to begin.")
        return

    # ── Period mode ──────────────────────────────────────────────────────────
    col_mode, col_period = st.columns([1, 2])

    with col_mode:
        view_mode = st.radio(
            "View by",
            ["Single Quarter", "Full Year"],
            horizontal=False,
            help="Single Quarter shows one quarter's snapshot. Full Year sums the quarters for that year.",
        )

    # Fetch available periods
    with st.spinner("Loading available periods…"):
        available_quarters = get_available_quarters(selected_companies)
        available_years = get_available_years(available_quarters)

    with col_period:
        if view_mode == "Single Quarter":
            quarter_labels = [q.strftime("%b %Y (Q%m)") if q.month in (3, 6, 9, 12)
                              else q.strftime("%d %b %Y") for q in available_quarters]
            # Nicer labels: use quarter-end month names
            quarter_labels = [q.strftime("%m/%d/%Y") for q in available_quarters]
            selected_q_label = st.selectbox(
                "Select Quarter",
                quarter_labels,
                index=0,
                help="Quarter-end date",
            )
            selected_period = available_quarters[quarter_labels.index(selected_q_label)]
            mode = "quarter"
            period_display = selected_q_label

        else:  # Full Year
            if not available_years:
                st.warning("No yearly data found for selected companies.")
                return
            selected_year = st.selectbox(
                "Select Year",
                available_years,
                index=0,
            )
            selected_period = selected_year
            mode = "year"
            period_display = str(selected_year)

    # ── Row / section filter ─────────────────────────────────────────────────
    with st.expander("🔍 Filter rows", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            show_groups = st.multiselect(
                "Show sections",
                list(ROW_GROUPS.keys()),
                default=list(ROW_GROUPS.keys()),
            )
        with col_b:
            search_term = st.text_input("Search row name", placeholder="e.g. EBITDA")

    # Build filtered row list
    filtered_rows = []
    for grp in show_groups:
        filtered_rows.extend(ROW_GROUPS.get(grp, []))
    if search_term.strip():
        filtered_rows = [r for r in filtered_rows if search_term.strip().lower() in r.lower()]
    if not filtered_rows:
        st.warning("No rows match the current filter.")
        return

    # ── Fetch & build table ──────────────────────────────────────────────────
    if st.button("🔄 Fetch & Compare", type="primary"):
        with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
            df_raw = build_comparison_table(selected_companies, mode, selected_period, filtered_rows)

        if df_raw.empty or df_raw.isna().all().all():
            st.warning("No data returned. Try a different period or company.")
            return

        # ── Display by section ────────────────────────────────────────────
        st.markdown(f"### Period: `{period_display}`  ·  {len(selected_companies)} companies")
        st.markdown(f"*Amounts in RM thousands unless noted.*")

        # Format display copy
        df_display = df_raw.copy()
        for row in df_display.index:
            df_display.loc[row] = df_display.loc[row].apply(
                lambda x: fmt_cell(row, x)
            )

        for grp in show_groups:
            grp_rows = [r for r in ROW_GROUPS.get(grp, []) if r in filtered_rows and r in df_display.index]
            if not grp_rows:
                continue

            st.markdown(f"#### {grp}")

            grp_display = df_display.loc[grp_rows]
            grp_raw = df_raw.loc[grp_rows]

            styler = style_comparison_table(grp_display, grp_raw)

            st.dataframe(
                styler,
                use_container_width=True,
                height=min(40 * len(grp_rows) + 38, 600),
            )

        # ── Quick metrics strip ───────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Quick metrics snapshot")

        metric_rows = {
            "Revenue (RM'000)": ROW_REVENUE,
            "PATMI (RM'000)": ROW_PATMI,
            "EBITDA (RM'000)": "EBITDA",
            "Gross Profit (RM'000)": "Gross Profit",
        }

        cols = st.columns(len(selected_companies))
        for i, comp in enumerate(selected_companies):
            with cols[i]:
                st.markdown(f"**{comp}**")
                for label, row_key in metric_rows.items():
                    val = df_raw.loc[row_key, comp] if row_key in df_raw.index else pd.NA
                    try:
                        v = float(val)
                        formatted = f"{v:,.0f}" if abs(v) >= 1 else "—"
                        delta_color = "normal" if v >= 0 else "inverse"
                    except Exception:
                        formatted = "—"
                    st.metric(label=label.split(" (")[0], value=formatted)

        # ── Download ──────────────────────────────────────────────────────
        st.markdown("---")
        csv_data = df_raw.to_csv()
        st.download_button(
            label="⬇️ Download comparison CSV",
            data=csv_data,
            file_name=f"comparison_{period_display.replace('/', '-')}.csv",
            mime="text/csv",
        )

    else:
        st.info("👆 Press **Fetch & Compare** to load the data.")

        # Show a preview of what will appear
        if selected_companies:
            preview_cols = ["Metric"] + selected_companies
            st.markdown("*Preview: table will show financial rows vs selected companies.*")
            preview_data = {
                "Metric": ["Total Revenue", "Gross Profit", "EBITDA", "Net Income", "Basic EPS"],
            }
            for c in selected_companies:
                preview_data[c] = ["…"] * 5
            st.dataframe(pd.DataFrame(preview_data).set_index("Metric"), use_container_width=True)
