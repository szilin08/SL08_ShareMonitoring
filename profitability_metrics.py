# pages/financial_ratios.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from financials import companies, fetch_quarterly_financials

# ─────────────────────────────────────────────────────────────
# CACHED DATA FETCHERS
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_info(ticker_code: str) -> dict:
    try:
        return yf.Ticker(ticker_code).info or {}
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_quarterly_cashflow(ticker_code: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker_code).quarterly_cashflow
        if df is None or df.empty:
            return pd.DataFrame()
        df.columns = pd.to_datetime(df.columns, errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_balance_sheet_raw(ticker_code: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker_code).quarterly_balance_sheet
        if df is None or df.empty:
            return pd.DataFrame()
        df.columns = pd.to_datetime(df.columns, errors="coerce")
        df = df.apply(pd.to_numeric, errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────────
# COLOURS
# ─────────────────────────────────────────────────────────────
LBS_COLOR   = "#58a6ff"
PEER_COLORS = ["#f0883e","#3fb950","#bc8cff","#ff7b72","#ffa657","#79c0ff","#56d364","#d2a8ff"]

def company_color(comp: str, comp_list: list) -> str:
    if comp == "LBS Bina":
        return LBS_COLOR
    peers = [c for c in comp_list if c != "LBS Bina"]
    return PEER_COLORS[(peers.index(comp) if comp in peers else 0) % len(PEER_COLORS)]

# ─────────────────────────────────────────────────────────────
# CHART LAYOUT BASE
# ─────────────────────────────────────────────────────────────
def base_layout(title: str = "") -> dict:
    return dict(
        plot_bgcolor  = "rgba(0,0,0,0)",
        paper_bgcolor = "rgba(0,0,0,0)",
        font          = dict(family="'DM Mono', 'Courier New', monospace", color="#94a3b8", size=11),
        title         = dict(text=title, font=dict(size=13, color="#e2e8f0"), x=0, xref="paper", pad=dict(b=8)),
        xaxis         = dict(gridcolor="#1e293b", linecolor="#1e293b", tickfont=dict(size=10, color="#64748b"), zeroline=False),
        yaxis         = dict(gridcolor="#1e293b", linecolor="#1e293b", tickfont=dict(size=10, color="#64748b"), zeroline=True, zerolinecolor="#334155"),
        margin        = dict(l=8, r=8, t=44, b=8),
        legend        = dict(bgcolor="rgba(15,23,42,0.8)", bordercolor="#1e293b", borderwidth=1,
                             font=dict(size=10, color="#94a3b8"), orientation="h", yanchor="bottom",
                             y=1.02, xanchor="left", x=0),
        hoverlabel    = dict(bgcolor="#0f172a", bordercolor="#334155", font=dict(size=11, color="#e2e8f0")),
    )

# ─────────────────────────────────────────────────────────────
# METRIC CALCULATIONS
# All financials are already in RM thousands from fetch_quarterly_financials.
# Balance sheet comes raw (full RM), so divide by 1000 when mixing with financials.
# ─────────────────────────────────────────────────────────────
def _get(df, row, col):
    """Safe cell getter."""
    if row in df.index and col in df.columns:
        v = df.loc[row, col]
        return float(v) if pd.notna(v) else float("nan")
    return float("nan")

def _pct(num, den):
    return (num / den * 100) if (pd.notna(num) and pd.notna(den) and den != 0) else float("nan")

def _ratio(num, den):
    return (num / den) if (pd.notna(num) and pd.notna(den) and den != 0) else float("nan")


def calc_profitability(fin: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "Gross Margin (%)", "Operating Margin (%)", "Pretax Margin (%)",
        "PAT Margin (%)", "PATMI Margin (%)", "EBITDA Margin (%)",
        "Effective Tax Rate (%)", "Interest Coverage (x)",
    ]
    out = pd.DataFrame(index=metrics, columns=fin.columns, dtype=float)
    for col in fin.columns:
        rev    = _get(fin, "Total Revenue", col)
        gp     = _get(fin, "Gross Profit", col)
        opex   = _get(fin, "Operating Expense", col)
        pbt    = _get(fin, "Pretax Income", col)
        tax    = _get(fin, "Tax Provision", col)
        ebitda = _get(fin, "EBITDA", col)
        intexp = _get(fin, "Interest Expense", col)
        patmi  = _get(fin, "Net Income From Continuing Operation Net Minority Interest", col)

        out.loc["Gross Margin (%)",       col] = _pct(gp, rev)
        out.loc["Operating Margin (%)",   col] = _pct(gp - opex if pd.notna(gp) and pd.notna(opex) else float("nan"), rev)
        out.loc["Pretax Margin (%)",      col] = _pct(pbt, rev)
        out.loc["PAT Margin (%)",         col] = _pct(pbt - tax if pd.notna(pbt) and pd.notna(tax) else float("nan"), rev)
        out.loc["PATMI Margin (%)",       col] = _pct(patmi, rev)
        out.loc["EBITDA Margin (%)",      col] = _pct(ebitda, rev)
        out.loc["Effective Tax Rate (%)", col] = _pct(tax, pbt)
        out.loc["Interest Coverage (x)",  col] = _ratio(intexp, pbt)
    return out.apply(pd.to_numeric, errors="coerce")


def calc_liquidity(bs: pd.DataFrame) -> pd.DataFrame:
    # bs is raw (full RM), ratios are unitless so no scaling needed
    metrics = ["Current Ratio (x)", "Quick Ratio (x)"]
    out = pd.DataFrame(index=metrics, columns=bs.columns, dtype=float)
    for col in bs.columns:
        ca  = _get(bs, "Current Assets", col)
        inv = _get(bs, "Inventory", col)
        cl  = _get(bs, "Current Liabilities", col)
        inv = 0.0 if pd.isna(inv) else inv
        out.loc["Current Ratio (x)", col] = _ratio(ca, cl)
        out.loc["Quick Ratio (x)",   col] = _ratio(ca - inv, cl)
    return out.apply(pd.to_numeric, errors="coerce")


def calc_return(fin: pd.DataFrame, bs: pd.DataFrame) -> pd.DataFrame:
    # fin is in RM thousands; bs is raw RM → divide bs by 1000 to match
    metrics = ["Return on Equity (%)", "Return on Assets (%)"]
    common  = fin.columns.intersection(bs.columns)
    out     = pd.DataFrame(index=metrics, columns=common, dtype=float)
    for col in common:
        ni = _get(fin, "Net Income Common Stockholders", col)          # RM thousands
        eq = _get(bs,  "Total Equity Gross Minority Interest", col)    # raw RM → /1000
        ta = _get(bs,  "Total Assets", col)                            # raw RM → /1000
        eq = eq / 1000 if pd.notna(eq) else float("nan")
        ta = ta / 1000 if pd.notna(ta) else float("nan")
        out.loc["Return on Equity (%)", col] = _pct(ni, eq)
        out.loc["Return on Assets (%)", col] = _pct(ni, ta)
    return out.apply(pd.to_numeric, errors="coerce")


def calc_solvency(bs: pd.DataFrame) -> pd.DataFrame:
    # all from bs, same units, ratios are unitless
    metrics = [
        "Debt / Equity (Owners) (x)", "Debt / Total Equity (x)",
        "Net Debt / Equity (Owners) (x)", "Net Debt / Total Equity (x)",
    ]
    out = pd.DataFrame(index=metrics, columns=bs.columns, dtype=float)
    for col in bs.columns:
        td  = _get(bs, "Total Debt", col)
        cse = _get(bs, "Common Stock Equity", col)
        te  = _get(bs, "Total Equity Gross Minority Interest", col)
        nd  = _get(bs, "Net Debt", col)
        out.loc["Debt / Equity (Owners) (x)",     col] = _ratio(td, cse)
        out.loc["Debt / Total Equity (x)",         col] = _ratio(td, te)
        out.loc["Net Debt / Equity (Owners) (x)", col] = _ratio(nd, cse)
        out.loc["Net Debt / Total Equity (x)",     col] = _ratio(nd, te)
    return out.apply(pd.to_numeric, errors="coerce")


def calc_valuation(fin: pd.DataFrame, bs: pd.DataFrame, ticker_code: str) -> pd.DataFrame:
    # fin in RM thousands; bs raw RM; market cap in native currency (RM)
    metrics = [
        "Enterprise Multiple (x)", "P/E Ratio (x)",
        "Price / Book (x)", "Price / Revenue (x)", "Price / Cashflow (x)",
    ]
    out    = pd.DataFrame(index=metrics, columns=fin.columns, dtype=float)
    info   = fetch_ticker_info(ticker_code)
    cf_raw = fetch_quarterly_cashflow(ticker_code)
    mc     = info.get("marketCap", None)   # full RM
    pe     = info.get("trailingPE", None)

    for col in fin.columns:
        rev    = _get(fin, "Total Revenue", col)   # RM thousands
        ebitda = _get(fin, "EBITDA", col)          # RM thousands
        td     = _get(bs,  "Total Debt", col)      # raw RM
        cash   = _get(bs,  "Cash And Cash Equivalents", col)  # raw RM
        ta     = _get(bs,  "Total Assets", col)    # raw RM
        tl     = _get(bs,  "Total Liabilities Net Minority Interest", col)  # raw RM
        ocf    = float("nan")
        if cf_raw is not None and not cf_raw.empty and "Operating Cash Flow" in cf_raw.index and col in cf_raw.columns:
            ocf = _get(cf_raw, "Operating Cash Flow", col)  # raw RM

        # convert mc to thousands for comparison with fin rows
        mc_k = mc / 1000 if mc is not None else float("nan")

        if pd.notna(mc) and pd.notna(td) and pd.notna(cash) and pd.notna(ebitda) and ebitda != 0:
            # EV = mc (full) + td (full) - cash (full); ebitda in thousands → convert EV to thousands
            ev = (mc + td - cash) / 1000
            out.loc["Enterprise Multiple (x)", col] = _ratio(ev, ebitda)

        if pd.notna(pe):
            out.loc["P/E Ratio (x)", col] = pe

        if pd.notna(mc) and pd.notna(ta) and pd.notna(tl):
            bv = (ta - tl) / 1000  # book value in thousands
            out.loc["Price / Book (x)", col] = _ratio(mc_k, bv)

        if pd.notna(mc_k) and pd.notna(rev) and rev != 0:
            out.loc["Price / Revenue (x)", col] = _ratio(mc_k, rev)

        if pd.notna(mc) and pd.notna(ocf) and ocf != 0:
            out.loc["Price / Cashflow (x)", col] = _ratio(mc, ocf)

    return out.apply(pd.to_numeric, errors="coerce")


# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────
def make_bar_chart(data: dict, metric: str, quarter: pd.Timestamp, comp_list: list) -> go.Figure:
    comps, vals, colors = [], [], []
    for comp, df in data.items():
        if metric not in df.index:
            continue
        col = next((c for c in df.columns if pd.Timestamp(c) == quarter), None)
        if col is None:
            continue
        v = df.loc[metric, col]
        if pd.notna(v):
            comps.append(comp)
            vals.append(round(float(v), 2))
            colors.append(company_color(comp, comp_list))

    fig = go.Figure(go.Bar(
        x            = comps,
        y            = vals,
        marker       = dict(color=colors, line=dict(width=0)),
        text         = [f"{v:.2f}" for v in vals],
        textposition = "outside",
        textfont     = dict(size=10, color="#94a3b8"),
        hovertemplate= "<b>%{x}</b><br>" + metric + ": %{y:.2f}<extra></extra>",
    ))
    layout = base_layout(metric)
    layout["yaxis"]["tickformat"] = ".2f"
    fig.update_layout(**layout, height=320)
    return fig


def make_line_chart(data: dict, metric: str, comp_list: list) -> go.Figure:
    fig = go.Figure()
    for comp, df in data.items():
        if metric not in df.index:
            continue
        series = df.loc[metric].dropna().sort_index()
        if series.empty:
            continue
        colour = company_color(comp, comp_list)
        fig.add_trace(go.Scatter(
            x             = series.index.strftime("%b '%y"),
            y             = series.values.round(2),
            name          = comp,
            mode          = "lines+markers",
            line          = dict(color=colour, width=2.5),
            marker        = dict(size=7, color=colour, line=dict(width=1.5, color="#0f172a")),
            hovertemplate = f"<b>{comp}</b><br>%{{x}}: %{{y:.2f}}<extra></extra>",
        ))
    layout = base_layout(metric)
    layout["yaxis"]["tickformat"] = ".2f"
    fig.update_layout(**layout, height=340)
    return fig


def make_radar(data: dict, metrics: list, quarter: pd.Timestamp, comp_list: list) -> go.Figure:
    if len(metrics) < 3:
        return None
    fig = go.Figure()
    for comp, df in data.items():
        vals = []
        for metric in metrics:
            col = next((c for c in df.columns if pd.Timestamp(c) == quarter), None)
            v   = _get(df, metric, col) if col is not None else float("nan")
            vals.append(float(v) if pd.notna(v) else 0.0)

        # Normalise to 0-100 scale per metric for fair radar comparison
        colour = company_color(comp, comp_list)
        fig.add_trace(go.Scatterpolar(
            r             = vals + [vals[0]],
            theta         = metrics + [metrics[0]],
            fill          = "toself",
            name          = comp,
            line          = dict(color=colour, width=2),
            fillcolor     = colour + "22",
            hovertemplate = f"<b>{comp}</b><br>%{{theta}}: %{{r:.2f}}<extra></extra>",
        ))
    fig.update_layout(
        plot_bgcolor  = "rgba(0,0,0,0)",
        paper_bgcolor = "rgba(0,0,0,0)",
        font          = dict(family="'DM Mono', monospace", color="#94a3b8", size=10),
        polar         = dict(
            bgcolor    = "rgba(15,23,42,0.6)",
            radialaxis = dict(visible=True, gridcolor="#1e293b", linecolor="#334155",
                              tickfont=dict(size=9, color="#64748b"), tickformat=".1f"),
            angularaxis= dict(gridcolor="#1e293b", linecolor="#334155",
                              tickfont=dict(size=10, color="#94a3b8")),
        ),
        legend        = dict(bgcolor="rgba(15,23,42,0.8)", bordercolor="#1e293b", borderwidth=1,
                             font=dict(size=10, color="#94a3b8"), orientation="h",
                             yanchor="bottom", y=1.05, xanchor="left", x=0),
        margin        = dict(l=40, r=40, t=60, b=40),
        height        = 420,
        hoverlabel    = dict(bgcolor="#0f172a", bordercolor="#334155", font=dict(size=11)),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# SECTION RENDERER
# ─────────────────────────────────────────────────────────────
SECTION_COLORS = {
    "Profitability": "#22c55e",
    "Liquidity":     "#38bdf8",
    "Returns":       "#a78bfa",
    "Solvency":      "#f97316",
    "Valuation":     "#f43f5e",
}

def render_section(section_name, icon, metrics_df_map, all_metrics, selected_quarter, comp_list, section_key):
    accent = SECTION_COLORS.get(section_name, "#58a6ff")

    # Header bar
    st.markdown(
        f"""<div style='display:flex;align-items:center;gap:10px;margin-bottom:16px;
            padding:12px 16px;background:linear-gradient(90deg,rgba(15,23,42,0.9) 0%,rgba(15,23,42,0.4) 100%);
            border-left:3px solid {accent};border-radius:4px;'>
            <span style='font-size:18px'>{icon}</span>
            <span style='font-size:15px;font-weight:600;color:#e2e8f0;letter-spacing:0.02em'>{section_name}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # Controls row
    ctrl1, ctrl2, ctrl3 = st.columns([3, 3, 1])
    with ctrl1:
        sel_metrics = st.multiselect(
            "Metrics", all_metrics,
            default=all_metrics[:min(3, len(all_metrics))],
            key=f"{section_key}_metrics",
            label_visibility="collapsed",
        )
    with ctrl2:
        chart_type = st.radio(
            "Chart", ["📊 Bar", "📈 Line", "🕸 Radar"],
            horizontal=True, key=f"{section_key}_chart_type",
            label_visibility="collapsed",
        )
    with ctrl3:
        show_table = st.toggle("Table", value=False, key=f"{section_key}_table")

    if not sel_metrics:
        st.caption("Select at least one metric.")
        return

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Bar ───────────────────────────────────────────────────
    if "Bar" in chart_type:
        if len(sel_metrics) == 1:
            fig = make_bar_chart(metrics_df_map, sel_metrics[0], selected_quarter, comp_list)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            pairs = [sel_metrics[i:i+2] for i in range(0, len(sel_metrics), 2)]
            for pair in pairs:
                cols = st.columns(len(pair))
                for col_ui, metric in zip(cols, pair):
                    with col_ui:
                        fig = make_bar_chart(metrics_df_map, metric, selected_quarter, comp_list)
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Line ──────────────────────────────────────────────────
    elif "Line" in chart_type:
        if len(sel_metrics) == 1:
            fig = make_line_chart(metrics_df_map, sel_metrics[0], comp_list)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            pairs = [sel_metrics[i:i+2] for i in range(0, len(sel_metrics), 2)]
            for pair in pairs:
                cols = st.columns(len(pair))
                for col_ui, metric in zip(cols, pair):
                    with col_ui:
                        fig = make_line_chart(metrics_df_map, metric, comp_list)
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Radar ─────────────────────────────────────────────────
    else:
        if len(sel_metrics) < 3:
            st.info("Select at least 3 metrics for a radar chart.")
        else:
            fig = make_radar(metrics_df_map, sel_metrics, selected_quarter, comp_list)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Data table ────────────────────────────────────────────
    if show_table:
        quarter_col = next(
            (c for df in metrics_df_map.values() for c in df.columns if pd.Timestamp(c) == selected_quarter),
            None,
        )
        rows = []
        for metric in sel_metrics:
            row = {"Metric": metric}
            for comp, df in metrics_df_map.items():
                v = _get(df, metric, quarter_col) if quarter_col is not None else float("nan")
                row[comp] = f"{v:.2f}" if pd.notna(v) else "--"
            rows.append(row)
        tbl = pd.DataFrame(rows).set_index("Metric")
        st.dataframe(
            tbl.style.set_table_styles([
                {"selector": "thead th",     "props": [("background-color","#0f172a"),("color","#94a3b8"),("font-size","11px"),("border-bottom","1px solid #1e293b")]},
                {"selector": "tbody td",     "props": [("background-color","#0d1117"),("color","#e2e8f0"),("text-align","right"),("font-size","12px")]},
                {"selector": "th.row_heading","props":[("background-color","#0d1117"),("color","#94a3b8"),("text-align","left"),("min-width","220px"),("font-size","11px")]},
                {"selector": "tbody tr:hover td","props":[("background-color","#1e293b")]},
            ]),
            use_container_width=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def main():
    st.markdown("""
        <style>
        .stExpander { border: 1px solid #1e293b !important; border-radius: 8px !important; margin-bottom: 12px !important; }
        .stExpander > div:first-child { background: #0d1117 !important; }
        div[data-testid="stRadio"] label { font-size: 13px !important; }
        div[data-testid="stMultiSelect"] span { font-size: 12px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 Financial Ratios")
    st.caption("Select companies and a reference quarter. Toggle between Bar, Line, and Radar views per section.")

    # ── Top controls ──────────────────────────────────────────
    col_comp, col_quarter = st.columns([3, 2])

    with col_comp:
        selected_companies = st.multiselect(
            "Companies",
            list(companies.keys()),
            default=["LBS Bina", "Matrix Concepts"],
            key="ratios_companies",
        )

    if not selected_companies:
        st.info("Select at least one company.")
        return

    with st.spinner("Loading quarters…"):
        all_q: set = set()
        for comp in selected_companies:
            tk = companies.get(comp)
            if not tk:
                continue
            df_tmp = fetch_quarterly_financials(tk)
            if not df_tmp.empty:
                all_q.update([c for c in df_tmp.columns if pd.notna(c)])
        quarters_sorted = sorted(all_q, reverse=True)

    if not quarters_sorted:
        st.warning("No quarterly data found.")
        return

    with col_quarter:
        q_labels    = [q.strftime("%d %b %Y") for q in quarters_sorted]
        sel_label   = st.selectbox("Reference quarter", q_labels, index=0, key="ratios_quarter")
        sel_quarter = quarters_sorted[q_labels.index(sel_label)]

    # ── Fetch button ──────────────────────────────────────────
    if st.button("Calculate Ratios", type="primary", key="ratios_calc_btn"):
        fin_data = {}
        bs_data  = {}
        tk_codes = {}
        with st.spinner(f"Fetching data for {len(selected_companies)} companies…"):
            for comp in selected_companies:
                tk_code = companies.get(comp)
                if not tk_code:
                    continue
                df_fin = fetch_quarterly_financials(tk_code)
                bs_raw = fetch_balance_sheet_raw(tk_code)
                if df_fin.empty or bs_raw.empty:
                    st.warning(f"Incomplete data for {comp}, skipping.")
                    continue
                fin_data[comp] = df_fin
                bs_data[comp]  = bs_raw
                tk_codes[comp] = tk_code

        if not fin_data:
            st.error("No data could be loaded.")
            return

        comp_list = list(fin_data.keys())
        st.session_state["ratios_prof_map"]  = {c: calc_profitability(fin_data[c])                    for c in comp_list}
        st.session_state["ratios_liq_map"]   = {c: calc_liquidity(bs_data[c])                         for c in comp_list}
        st.session_state["ratios_ret_map"]   = {c: calc_return(fin_data[c], bs_data[c])               for c in comp_list}
        st.session_state["ratios_solv_map"]  = {c: calc_solvency(bs_data[c])                          for c in comp_list}
        st.session_state["ratios_val_map"]   = {c: calc_valuation(fin_data[c], bs_data[c], tk_codes[c]) for c in comp_list}
        st.session_state["ratios_comp_list"] = comp_list

    if "ratios_prof_map" not in st.session_state:
        st.caption("Press **Calculate Ratios** to load the dashboard.")
        return

    prof_map  = st.session_state["ratios_prof_map"]
    liq_map   = st.session_state["ratios_liq_map"]
    ret_map   = st.session_state["ratios_ret_map"]
    solv_map  = st.session_state["ratios_solv_map"]
    val_map   = st.session_state["ratios_val_map"]
    comp_list = st.session_state["ratios_comp_list"]

    # ── Colour legend ─────────────────────────────────────────
    dots = " &nbsp;·&nbsp; ".join(
        f"<span style='color:{company_color(c, comp_list)};font-weight:700'>◆</span>"
        f"<span style='color:#94a3b8;font-size:12px'> {c}</span>"
        for c in comp_list
    )
    st.markdown(f"<p style='margin:8px 0 20px;line-height:2'>{dots}</p>", unsafe_allow_html=True)

    # ── Sections ──────────────────────────────────────────────
    sections = [
        ("Profitability", "💹", prof_map,  "prof"),
        ("Liquidity",     "💧", liq_map,   "liq"),
        ("Returns",       "📐", ret_map,   "ret"),
        ("Solvency",      "🏦", solv_map,  "solv"),
        ("Valuation",     "🏷️", val_map,   "val"),
    ]

    for section_name, icon, mdf_map, key in sections:
        all_metrics = list(next(iter(mdf_map.values())).index)
        with st.expander(f"{icon}  {section_name}", expanded=True):
            render_section(
                section_name     = section_name,
                icon             = icon,
                metrics_df_map   = mdf_map,
                all_metrics      = all_metrics,
                selected_quarter = sel_quarter,
                comp_list        = comp_list,
                section_key      = key,
            )


if __name__ == "__main__":
    main()
