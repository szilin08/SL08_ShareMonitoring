# pages/financials.py
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

ROW_SECTIONS = [
    ("Revenue & Profit", [
        "Total Revenue", "Cost Of Revenue", "Gross Profit",
    ]),
    ("Operating Performance", [
        "Operating Expense", "Operating Income",
        "Total Operating Income As Reported", "Total Expenses",
        "Rent Expense Supplemental",
    ]),
    ("Below the Line", [
        "Net Non Operating Interest Income Expense",
        "Interest Income", "Interest Expense", "Net Interest Income",
    ]),
    ("Earnings", [
        "Pretax Income", "Tax Provision", "Tax Rate For Calcs",
        "Net Income Common Stockholders",
        "Diluted NI Available To Com Stockholders",
        "Net Income From Continuing & Discontinued Operation",
        "Net Income From Continuing Operation Net Minority Interest",
        "Normalized Income", "Tax Effect Of Unusual Items",
    ]),
    ("Per Share", [
        "Basic EPS", "Diluted EPS",
        "Basic Average Shares", "Diluted Average Shares",
    ]),
    ("Quality Metrics", [
        "EBIT", "EBITDA", "Normalized EBITDA",
        "Reconciled Cost Of Revenue", "Reconciled Depreciation",
        "Total Unusual Items Excluding Goodwill", "Total Unusual Items",
    ]),
]

ROWS_UNSCALED = {"Basic EPS", "Diluted EPS", "Tax Rate For Calcs"}

ROW_REVENUE = "Total Revenue"
ROW_PATMI   = "Net Income From Continuing Operation Net Minority Interest"

HIGHLIGHT_ROWS = {
    "Total Revenue", "Gross Profit", "Operating Income",
    "Net Income Common Stockholders",
    "Net Income From Continuing Operation Net Minority Interest",
    "EBIT", "EBITDA", "Normalized EBITDA", "Pretax Income",
}

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_quarterly(ticker_code: str) -> pd.DataFrame:
    t  = yf.Ticker(ticker_code)
    df = t.quarterly_financials
    if df is None or df.empty:
        return pd.DataFrame()
    df.columns = pd.to_datetime(df.columns, errors="coerce")
    df = df.reindex(ROW_ORDER)
    df = df.apply(pd.to_numeric, errors="coerce")
    scale = [r for r in df.index if r not in ROWS_UNSCALED]
    df.loc[scale] = df.loc[scale] / 1_000.0
    return df


def all_quarters(comp_list):
    seen = set()
    for c in comp_list:
        tk = companies.get(c)
        if not tk:
            continue
        df = fetch_quarterly(tk)
        if not df.empty:
            seen.update(df.columns.tolist())
    return sorted([q for q in seen if pd.notna(q)], reverse=True)


def all_years(quarters):
    return sorted({q.year for q in quarters}, reverse=True)


# ── BUILD COMPARISON TABLE ─────────────────────────────────────────────────────
def build_table(comp_list, mode, period) -> pd.DataFrame:
    """Returns pure-numeric DataFrame: index=ROW_ORDER, columns=company names."""
    out = {}
    for comp in comp_list:
        tk = companies.get(comp)
        if not tk:
            out[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue
        df = fetch_quarterly(tk)
        if df.empty:
            out[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            continue

        if mode == "quarter":
            target = pd.Timestamp(period)
            col = next((c for c in df.columns if c == target), None)
            if col is None:
                out[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
            else:
                s = df[col].reindex(ROW_ORDER)
                out[comp] = s.astype(float)

        else:  # year
            yr_cols = [c for c in df.columns if c.year == int(period)]
            if not yr_cols:
                out[comp] = pd.Series(float("nan"), index=ROW_ORDER, dtype=float)
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
                out[comp] = pd.Series(vals, dtype=float)

    return pd.DataFrame(out, index=ROW_ORDER).astype(float)


# ── FORMATTING ─────────────────────────────────────────────────────────────────
def fmt(row_name, val) -> str:
    try:
        v = float(val)
    except Exception:
        return "—"
    if pd.isna(v) or v == 0:
        return "—"
    if row_name in ("Basic EPS", "Diluted EPS"):
        return f"{v:.3f}"
    if row_name == "Tax Rate For Calcs":
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"


def to_display(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric DataFrame -> fully string DataFrame (safe for Styler)."""
    result = {}
    for comp in df_raw.columns:
        result[comp] = {row: fmt(row, df_raw.loc[row, comp]) for row in df_raw.index}
    return pd.DataFrame(result, index=df_raw.index)


# ── SECTION TABLE RENDERER ────────────────────────────────────────────────────
def render_section(df_raw: pd.DataFrame, section_rows: list):
    rows = [r for r in section_rows if r in df_raw.index]
    if not rows:
        return

    sub_raw  = df_raw.loc[rows]
    sub_disp = to_display(sub_raw)   # all strings — safe dtype

    def style_col(col):
        out = []
        for row_name in col.index:
            style = ""
            if row_name in HIGHLIGHT_ROWS:
                try:
                    v = float(df_raw.loc[row_name, col.name])
                    if not pd.isna(v):
                        style = "color:#16a34a;font-weight:600" if v > 0 else "color:#dc2626;font-weight:600"
                except Exception:
                    pass
            out.append(style)
        return out

    header_bg   = "#1e293b"
    header_fg   = "#f1f5f9"
    row_odd_bg  = "#ffffff"
    row_even_bg = "#f8fafc"
    row_hover   = "#eff6ff"

    styler = (
        sub_disp.style
        .apply(style_col, axis=0)
        .set_table_styles([
            {"selector": "thead th",
             "props": [("background-color", header_bg), ("color", header_fg),
                       ("font-size", "12px"), ("white-space", "nowrap"),
                       ("padding", "8px 14px"), ("font-weight", "600"),
                       ("border-bottom", "2px solid #3b82f6")]},
            {"selector": "tbody td",
             "props": [("font-size", "13px"), ("padding", "6px 14px"),
                       ("font-variant-numeric", "tabular-nums"),
                       ("text-align", "right")]},
            {"selector": "tbody tr:nth-child(odd)  td",
             "props": [("background-color", row_odd_bg)]},
            {"selector": "tbody tr:nth-child(even) td",
             "props": [("background-color", row_even_bg)]},
            {"selector": "th.row_heading",
             "props": [("font-size", "12px"), ("color", "#374151"),
                       ("font-weight", "500"), ("padding", "6px 14px"),
                       ("white-space", "nowrap"), ("text-align", "left"),
                       ("min-width", "240px")]},
        ])
    )
    st.dataframe(styler, use_container_width=True,
                 height=min(42 * len(rows) + 42, 680))


# ── PAGE ──────────────────────────────────────────────────────────────────────
def main():
    # ── Inline styles
    st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 14px !important;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 11px !important;
        color: #64748b !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 17px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
    }
    .section-pill {
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: #1d4ed8;
        padding: 3px 10px 3px 0;
        margin: 20px 0 6px 0;
        border-left: 3px solid #3b82f6;
        padding-left: 10px;
        background: linear-gradient(90deg, rgba(59,130,246,0.08) 0%, transparent 100%);
        border-radius: 0 4px 4px 0;
        width: 100%;
        box-sizing: border-box;
    }
    .comp-label {
        font-size: 14px;
        font-weight: 700;
        color: #1e293b;
        margin: 14px 0 6px 0;
        padding-bottom: 4px;
        border-bottom: 2px solid #e2e8f0;
    }
    .legend-row {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 6px;
    }
    .legend-pos { color: #16a34a; font-weight: 600; }
    .legend-neg { color: #dc2626; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header
    st.markdown(
        "<h2 style='font-size:26px;font-weight:800;color:#0f172a;margin-bottom:2px;'>"
        "📊 Company Financials</h2>"
        "<p style='color:#64748b;font-size:13px;margin-bottom:24px;'>"
        "Peer comparison · amounts in <b>RM thousands</b> · "
        "EPS &amp; Tax Rate unscaled · data via Yahoo Finance</p>",
        unsafe_allow_html=True,
    )

    # ── Control bar
    c1, c2, c3 = st.columns([3, 1, 2])
    with c1:
        selected = st.multiselect(
            "Companies",
            list(companies.keys()),
            default=["LBS Bina", "Mah Sing", "Matrix Concepts"],
            placeholder="Pick companies to compare…",
        )
    with c2:
        view_mode = st.radio("View by", ["Quarter", "Year"], horizontal=True)

    if not selected:
        st.info("Select at least one company above.")
        return

    with st.spinner("Fetching available periods…"):
        quarters = all_quarters(selected)
        years    = all_years(quarters)

    with c3:
        if view_mode == "Quarter":
            if not quarters:
                st.warning("No quarterly data found.")
                return
            q_labels   = [q.strftime("%d %b %Y") for q in quarters]
            sel_label  = st.selectbox("Quarter (end date)", q_labels, index=0)
            period     = quarters[q_labels.index(sel_label)]
            mode       = "quarter"
            period_str = sel_label
        else:
            if not years:
                st.warning("No annual data found.")
                return
            sel_year   = st.selectbox("Year", years, index=0)
            period     = sel_year
            mode       = "year"
            period_str = str(sel_year)

    # ── Fetch
    go = st.button("🔄  Fetch & Compare", type="primary")
    if not go:
        st.caption("Press **Fetch & Compare** to load the table.")
        return

    with st.spinner(f"Loading {len(selected)} companies for {period_str}…"):
        df_raw = build_table(selected, mode, period)

    if df_raw.empty or df_raw.isna().all().all():
        st.warning("No data returned for this selection. Try another period.")
        return

    # ── Period badge
    st.markdown(
        f"<div style='margin:12px 0 4px;'>"
        f"<span style='background:#1e293b;color:#f1f5f9;font-size:12px;"
        f"font-weight:600;padding:4px 12px;border-radius:20px;'>"
        f"Period: {period_str}</span>"
        f"&nbsp; <span style='color:#64748b;font-size:12px;'>"
        f"{len(selected)} companies selected</span></div>",
        unsafe_allow_html=True,
    )

    # ── Summary metric cards
    SUMMARY = [
        ("Revenue",       ROW_REVENUE,  "RM'000"),
        ("PATMI",         ROW_PATMI,    "RM'000"),
        ("EBITDA",        "EBITDA",     "RM'000"),
        ("Gross Profit",  "Gross Profit","RM'000"),
        ("EBIT",          "EBIT",       "RM'000"),
        ("Operating Inc.","Operating Income","RM'000"),
    ]

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    for comp in selected:
        st.markdown(f"<div class='comp-label'>{comp}</div>", unsafe_allow_html=True)
        cols = st.columns(len(SUMMARY))
        for i, (label, row_key, unit) in enumerate(SUMMARY):
            with cols[i]:
                try:
                    v = float(df_raw.loc[row_key, comp])
                    val_str = f"{v:,.0f}" if not pd.isna(v) and v != 0 else "—"
                except Exception:
                    val_str = "—"
                st.metric(label=f"{label}", value=val_str)

    # ── Full tables
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='legend-row'>"
        "<span class='legend-pos'>■ Green</span> = positive &nbsp;·&nbsp; "
        "<span class='legend-neg'>■ Red</span> = negative (brackets) &nbsp;·&nbsp; "
        "— = no data available</div>",
        unsafe_allow_html=True,
    )

    for section_name, section_rows in ROW_SECTIONS:
        st.markdown(
            f"<div class='section-pill'>{section_name}</div>",
            unsafe_allow_html=True,
        )
        render_section(df_raw, section_rows)

    # ── Download
    st.markdown("---")
    csv_bytes = to_display(df_raw).to_csv().encode("utf-8")
    st.download_button(
        label="⬇️  Download CSV",
        data=csv_bytes,
        file_name=f"financials_{period_str.replace(' ', '_')}.csv",
        mime="text/csv",
    )
