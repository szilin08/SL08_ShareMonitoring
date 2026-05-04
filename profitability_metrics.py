# pages/financial_ratios.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
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


# ─────────────────────────────────────────────────────────────
# CHART THEME
# ─────────────────────────────────────────────────────────────
CHART_THEME = dict(
    plot_bgcolor  = "#0d1117",
    paper_bgcolor = "#0d1117",
    font          = dict(family="'IBM Plex Mono', monospace", color="#c9d1d9", size=11),
    xaxis         = dict(gridcolor="#21262d", linecolor="#30363d", tickfont=dict(size=10)),
    yaxis         = dict(gridcolor="#21262d", linecolor="#30363d", tickfont=dict(size=10)),
    margin        = dict(l=10, r=10, t=40, b=10),
    legend        = dict(bgcolor="rgba(0,0,0,0)", bordercolor="#30363d", borderwidth=1),
)

LBS_COLOR  = "#58a6ff"   # blue  — base company
PEER_COLORS = [
    "#f0883e", "#3fb950", "#bc8cff", "#ff7b72",
    "#ffa657", "#79c0ff", "#56d364", "#d2a8ff",
]

def company_color(comp: str, comp_list: list) -> str:
    if comp == "LBS Bina":
        return LBS_COLOR
    peers = [c for c in comp_list if c != "LBS Bina"]
    idx   = peers.index(comp) if comp in peers else 0
    return PEER_COLORS[idx % len(PEER_COLORS)]


# ─────────────────────────────────────────────────────────────
# METRIC CALCULATIONS  (returns float DataFrame: index=metrics, cols=quarters)
# ─────────────────────────────────────────────────────────────
def calc_profitability(df: pd.DataFrame) -> pd.DataFrame:
    rows = [
        "Gross Margin (%)",
        "Operating Margin (%)",
        "Pretax Margin (%)",
        "PAT Margin (%)",
        "PATMI Margin (%)",
        "EBITDA Margin (%)",
        "Effective Tax Rate (%)",
        "Interest Coverage (x)",
    ]
    out = pd.DataFrame(index=rows, columns=df.columns, dtype=float)
    for col in df.columns:
        rev  = df.loc["Total Revenue", col]          if "Total Revenue"          in df.index else float("nan")
        gp   = df.loc["Gross Profit", col]           if "Gross Profit"           in df.index else float("nan")
        opex = df.loc["Operating Expense", col]      if "Operating Expense"      in df.index else float("nan")
        pbt  = df.loc["Pretax Income", col]          if "Pretax Income"          in df.index else float("nan")
        tax  = df.loc["Tax Provision", col]          if "Tax Provision"          in df.index else float("nan")
        ni   = df.loc["Net Income Common Stockholders", col] \
                                                     if "Net Income Common Stockholders" in df.index else float("nan")
        ebitda = df.loc["EBITDA", col]               if "EBITDA"                 in df.index else float("nan")
        intexp = df.loc["Interest Expense", col]     if "Interest Expense"       in df.index else float("nan")
        patmi  = df.loc["Net Income From Continuing Operation Net Minority Interest", col] \
                                                     if "Net Income From Continuing Operation Net Minority Interest" in df.index else float("nan")

        def pct(num, den): return (num / den * 100) if pd.notna(num) and pd.notna(den) and den != 0 else float("nan")

        out.loc["Gross Margin (%)",       col] = pct(gp, rev)
        out.loc["Operating Margin (%)",   col] = pct(gp - opex if pd.notna(gp) and pd.notna(opex) else float("nan"), rev)
        out.loc["Pretax Margin (%)",      col] = pct(pbt, rev)
        out.loc["PAT Margin (%)",         col] = pct(pbt - tax if pd.notna(pbt) and pd.notna(tax) else float("nan"), rev)
        out.loc["PATMI Margin (%)",       col] = pct(patmi, rev)
        out.loc["EBITDA Margin (%)",      col] = pct(ebitda, rev)
        out.loc["Effective Tax Rate (%)", col] = pct(tax, pbt)
        out.loc["Interest Coverage (x)",  col] = (intexp / pbt) if pd.notna(intexp) and pd.notna(pbt) and pbt != 0 else float("nan")

    return out.apply(pd.to_numeric, errors="coerce")


def calc_liquidity(bs: pd.DataFrame) -> pd.DataFrame:
    rows = ["Current Ratio (x)", "Quick Ratio (x)"]
    out  = pd.DataFrame(index=rows, columns=bs.columns, dtype=float)
    for col in bs.columns:
        ca  = bs.loc["Current Assets", col]    if "Current Assets"    in bs.index else float("nan")
        inv = bs.loc["Inventory", col]          if "Inventory"         in bs.index else 0.0
        cl  = bs.loc["Current Liabilities", col] if "Current Liabilities" in bs.index else float("nan")
        if pd.notna(ca) and pd.notna(cl) and cl != 0:
            out.loc["Current Ratio (x)", col] = ca / cl
            out.loc["Quick Ratio (x)",   col] = (ca - (inv if pd.notna(inv) else 0)) / cl
    return out.apply(pd.to_numeric, errors="coerce")


def calc_return(df: pd.DataFrame, bs: pd.DataFrame) -> pd.DataFrame:
    rows = ["Return on Equity (%)", "Return on Assets (%)"]
    # align columns — use intersection
    common = df.columns.intersection(bs.columns)
    out = pd.DataFrame(index=rows, columns=common, dtype=float)
    for col in common:
        ni  = df.loc["Net Income Common Stockholders", col] if "Net Income Common Stockholders" in df.index else float("nan")
        eq  = bs.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in bs.index else float("nan")
        ta  = bs.loc["Total Assets", col] if "Total Assets" in bs.index else float("nan")
        if pd.notna(ni) and pd.notna(eq) and eq != 0:
            out.loc["Return on Equity (%)", col] = ni / eq * 100
        if pd.notna(ni) and pd.notna(ta) and ta != 0:
            out.loc["Return on Assets (%)", col] = ni / ta * 100
    return out.apply(pd.to_numeric, errors="coerce")


def calc_solvency(bs: pd.DataFrame) -> pd.DataFrame:
    rows = [
        "Debt / Equity (Owners) (x)",
        "Debt / Total Equity (x)",
        "Net Debt / Equity (Owners) (x)",
        "Net Debt / Total Equity (x)",
    ]
    out = pd.DataFrame(index=rows, columns=bs.columns, dtype=float)
    for col in bs.columns:
        td  = bs.loc["Total Debt", col]         if "Total Debt"         in bs.index else float("nan")
        cse = bs.loc["Common Stock Equity", col] if "Common Stock Equity" in bs.index else float("nan")
        te  = bs.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in bs.index else float("nan")
        nd  = bs.loc["Net Debt", col]            if "Net Debt"            in bs.index else float("nan")

        def ratio(n, d): return (n / d) if pd.notna(n) and pd.notna(d) and d != 0 else float("nan")

        out.loc["Debt / Equity (Owners) (x)",     col] = ratio(td, cse)
        out.loc["Debt / Total Equity (x)",         col] = ratio(td, te)
        out.loc["Net Debt / Equity (Owners) (x)", col] = ratio(nd, cse)
        out.loc["Net Debt / Total Equity (x)",     col] = ratio(nd, te)
    return out.apply(pd.to_numeric, errors="coerce")


def calc_valuation(df: pd.DataFrame, bs: pd.DataFrame, ticker_code: str) -> pd.DataFrame:
    rows = [
        "Enterprise Multiple (x)",
        "P/E Ratio (x)",
        "Price / Book (x)",
        "Price / Revenue (x)",
        "Price / Cashflow (x)",
    ]
    out    = pd.DataFrame(index=rows, columns=df.columns, dtype=float)
    info   = fetch_ticker_info(ticker_code)
    cf_raw = fetch_quarterly_cashflow(ticker_code)
    mc     = info.get("marketCap", None)
    pe     = info.get("trailingPE", None)

    for col in df.columns:
        rev    = df.loc["Total Revenue", col] if "Total Revenue" in df.index else float("nan")
        ebitda = df.loc["EBITDA", col]        if "EBITDA"        in df.index else float("nan")
        td     = bs.loc["Total Debt", col]    if "Total Debt" in bs.index and col in bs.columns else float("nan")
        cash   = bs.loc["Cash And Cash Equivalents", col] if "Cash And Cash Equivalents" in bs.index and col in bs.columns else float("nan")
        ta     = bs.loc["Total Assets", col]  if "Total Assets" in bs.index and col in bs.columns else float("nan")
        tl     = bs.loc["Total Liabilities Net Minority Interest", col] if "Total Liabilities Net Minority Interest" in bs.index and col in bs.columns else float("nan")
        ocf    = cf_raw.loc["Operating Cash Flow", col] if (cf_raw is not None and "Operating Cash Flow" in cf_raw.index and col in cf_raw.columns) else float("nan")

        if pd.notna(mc) and pd.notna(td) and pd.notna(cash) and pd.notna(ebitda) and ebitda != 0:
            out.loc["Enterprise Multiple (x)", col] = (mc + td - cash) / ebitda
        if pd.notna(pe):
            out.loc["P/E Ratio (x)", col] = pe
        if pd.notna(mc) and pd.notna(ta) and pd.notna(tl):
            bv = ta - tl
            if bv != 0:
                out.loc["Price / Book (x)", col] = mc / bv
        if pd.notna(mc) and pd.notna(rev) and rev != 0:
            out.loc["Price / Revenue (x)", col] = mc / rev
        if pd.notna(mc) and pd.notna(ocf) and ocf != 0:
            out.loc["Price / Cashflow (x)", col] = mc / ocf

    return out.apply(pd.to_numeric, errors="coerce")


# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────
def make_line_chart(data: dict, metric: str, comp_list: list) -> go.Figure:
    """Line chart: x=quarters, y=metric value, one line per company."""
    fig = go.Figure()
    for comp, df in data.items():
        if metric not in df.index:
            continue
        series = df.loc[metric].dropna().sort_index()
        if series.empty:
            continue
        fig.add_trace(go.Scatter(
            x    = series.index.strftime("%b %Y"),
            y    = series.values,
            name = comp,
            mode = "lines+markers",
            line = dict(color=company_color(comp, comp_list), width=2),
            marker= dict(size=6),
        ))
    fig.update_layout(**CHART_THEME, title=dict(text=metric, font=dict(size=13), x=0, xref="paper"))
    return fig


def make_bar_chart(data: dict, metric: str, quarter: pd.Timestamp, comp_list: list) -> go.Figure:
    """Bar chart: x=company, y=metric value for a given quarter."""
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
            vals.append(float(v))
            colors.append(company_color(comp, comp_list))

    fig = go.Figure(go.Bar(
        x             = comps,
        y             = vals,
        marker_color  = colors,
        text          = [f"{v:.2f}" for v in vals],
        textposition  = "outside",
        textfont      = dict(size=10),
    ))
    fig.update_layout(**CHART_THEME, title=dict(text=metric, font=dict(size=13), x=0, xref="paper"))
    fig.update_yaxes(zeroline=True, zerolinecolor="#30363d")
    return fig


def make_grouped_bar(data: dict, metrics: list, quarter: pd.Timestamp, comp_list: list) -> go.Figure:
    """Grouped bar: multiple metrics side-by-side per company."""
    fig = go.Figure()
    for i, metric in enumerate(metrics):
        comps, vals = [], []
        for comp, df in data.items():
            if metric not in df.index:
                continue
            col = next((c for c in df.columns if pd.Timestamp(c) == quarter), None)
            if col is None:
                continue
            v = df.loc[metric, col]
            if pd.notna(v):
                comps.append(comp)
                vals.append(float(v))
        if comps:
            fig.add_trace(go.Bar(name=metric, x=comps, y=vals,
                                 text=[f"{v:.2f}" for v in vals],
                                 textposition="outside", textfont=dict(size=9)))
    fig.update_layout(**CHART_THEME, barmode="group",
                      title=dict(text=" · ".join(metrics[:3]), font=dict(size=13), x=0, xref="paper"))
    return fig


def make_radar(data: dict, metrics: list, quarter: pd.Timestamp, comp_list: list) -> go.Figure:
    """Radar / spider chart comparing companies across multiple metrics."""
    fig = go.Figure()
    for comp, df in data.items():
        vals = []
        for metric in metrics:
            if metric not in df.index:
                vals.append(0)
                continue
            col = next((c for c in df.columns if pd.Timestamp(c) == quarter), None)
            v   = df.loc[metric, col] if col is not None else float("nan")
            vals.append(float(v) if pd.notna(v) else 0)
        fig.add_trace(go.Scatterpolar(
            r     = vals + [vals[0]],
            theta = metrics + [metrics[0]],
            fill  = "toself",
            name  = comp,
            line  = dict(color=company_color(comp, comp_list)),
            fillcolor = company_color(comp, comp_list).replace(")", ", 0.15)").replace("rgb", "rgba") if "rgb" in company_color(comp, comp_list) else company_color(comp, comp_list) + "26",
        ))
    fig.update_layout(
        **CHART_THEME,
        polar=dict(
            bgcolor    = "#0d1117",
            radialaxis = dict(visible=True, gridcolor="#21262d", linecolor="#30363d",
                              tickfont=dict(size=9)),
            angularaxis= dict(gridcolor="#21262d", linecolor="#30363d"),
        ),
        title=dict(text="Radar Comparison", font=dict(size=13), x=0, xref="paper"),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# PAGE SECTION RENDERER
# ─────────────────────────────────────────────────────────────
def render_section(
    section_name: str,
    icon: str,
    metrics_df_map: dict,      # {comp: DataFrame(index=metrics, cols=quarters)}
    all_metrics: list,
    selected_quarter: pd.Timestamp,
    comp_list: list,
    section_key: str,
):
    st.markdown(f"### {icon} {section_name}")

    # ── metric picker ─────────────────────────────────────────
    sel_metrics = st.multiselect(
        "Metrics to display",
        all_metrics,
        default=all_metrics[:min(3, len(all_metrics))],
        key=f"{section_key}_metrics",
    )

    if not sel_metrics:
        st.caption("Select at least one metric above.")
        return

    # ── chart type picker ─────────────────────────────────────
    c1, c2 = st.columns([2, 1])
    with c1:
        chart_type = st.radio(
            "Chart type",
            ["Bar (single quarter)", "Line (trend over quarters)", "Radar (overview)"],
            horizontal=True,
            key=f"{section_key}_chart_type",
        )
    with c2:
        show_table = st.toggle("Show data table", value=False, key=f"{section_key}_table")

    st.markdown("---")

    # ── charts ───────────────────────────────────────────────
    if chart_type == "Bar (single quarter)":
        if len(sel_metrics) == 1:
            fig = make_bar_chart(metrics_df_map, sel_metrics[0], selected_quarter, comp_list)
            st.plotly_chart(fig, use_container_width=True)
        else:
            # grid of bar charts, 2 per row
            pairs = [sel_metrics[i:i+2] for i in range(0, len(sel_metrics), 2)]
            for pair in pairs:
                cols = st.columns(len(pair))
                for col_ui, metric in zip(cols, pair):
                    with col_ui:
                        fig = make_bar_chart(metrics_df_map, metric, selected_quarter, comp_list)
                        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Line (trend over quarters)":
        for metric in sel_metrics:
            fig = make_line_chart(metrics_df_map, metric, comp_list)
            st.plotly_chart(fig, use_container_width=True)

    else:  # Radar
        if len(sel_metrics) < 3:
            st.info("Select at least 3 metrics for a meaningful radar chart.")
        fig = make_radar(metrics_df_map, sel_metrics, selected_quarter, comp_list)
        st.plotly_chart(fig, use_container_width=True)

    # ── optional data table ────────────────────────────────────
    if show_table:
        quarter_col = next(
            (c for df in metrics_df_map.values()
             for c in df.columns if pd.Timestamp(c) == selected_quarter),
            None
        )
        rows = []
        for metric in sel_metrics:
            row = {"Metric": metric}
            for comp, df in metrics_df_map.items():
                if metric in df.index and quarter_col is not None and quarter_col in df.columns:
                    v = df.loc[metric, quarter_col]
                    row[comp] = f"{v:.2f}" if pd.notna(v) else "--"
                else:
                    row[comp] = "--"
            rows.append(row)
        tbl = pd.DataFrame(rows).set_index("Metric")
        st.dataframe(
            tbl.style.set_table_styles([
                {"selector": "thead th", "props": [("background-color","#1e1e1e"),("color","white"),("font-size","12px")]},
                {"selector": "tbody td", "props": [("background-color","#121212"),("color","white"),("text-align","right")]},
                {"selector": "th.row_heading", "props": [("background-color","#121212"),("color","#d1d5db"),("text-align","left"),("min-width","260px")]},
            ]),
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# STREAMLIT PAGE
# ─────────────────────────────────────────────────────────────
def main():
    st.title("📈 Financial Ratios Dashboard")
    st.caption(
        "Select companies and a reference quarter. "
        "Each section lets you pick which metrics to visualise and your preferred chart type."
    )

    # ── top controls ──────────────────────────────────────────
    col_comp, col_quarter = st.columns([3, 2])

    with col_comp:
        selected_companies = st.multiselect(
            "Select companies",
            list(companies.keys()),
            default=["LBS Bina", "Matrix Concepts"],
            key="ratios_companies",
        )

    if not selected_companies:
        st.info("Select at least one company to continue.")
        return

    # Discover quarters from the first available company
    with st.spinner("Loading available quarters…"):
        all_quarters: set = set()
        for comp in selected_companies:
            tk = companies.get(comp)
            if not tk:
                continue
            df_tmp = fetch_quarterly_financials(tk)
            if not df_tmp.empty:
                all_quarters.update([c for c in df_tmp.columns if pd.notna(c)])
        quarters_sorted = sorted(all_quarters, reverse=True)

    if not quarters_sorted:
        st.warning("No quarterly data found for selected companies.")
        return

    with col_quarter:
        q_labels      = [q.strftime("%d %b %Y") for q in quarters_sorted]
        sel_label     = st.selectbox("Reference quarter (for bar/radar charts)", q_labels, index=0, key="ratios_quarter")
        sel_quarter   = quarters_sorted[q_labels.index(sel_label)]

    # ── fetch button ──────────────────────────────────────────
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
                bs_raw = yf.Ticker(tk_code).quarterly_balance_sheet
                if df_fin.empty or bs_raw is None or bs_raw.empty:
                    st.warning(f"Incomplete data for {comp}, skipping.")
                    continue
                try:
                    bs_raw.columns = pd.to_datetime(bs_raw.columns)
                except Exception:
                    pass
                fin_data[comp] = df_fin
                bs_data[comp]  = bs_raw
                tk_codes[comp] = tk_code

        if not fin_data:
            st.error("No data could be loaded.")
            return

        comp_list = list(fin_data.keys())
        st.session_state["ratios_prof_map"]  = {c: calc_profitability(fin_data[c]) for c in comp_list}
        st.session_state["ratios_liq_map"]   = {c: calc_liquidity(bs_data[c])      for c in comp_list}
        st.session_state["ratios_ret_map"]   = {c: calc_return(fin_data[c], bs_data[c]) for c in comp_list}
        st.session_state["ratios_solv_map"]  = {c: calc_solvency(bs_data[c])        for c in comp_list}
        st.session_state["ratios_val_map"]   = {c: calc_valuation(fin_data[c], bs_data[c], tk_codes[c]) for c in comp_list}
        st.session_state["ratios_comp_list"] = comp_list

    # ── guard: nothing loaded yet ─────────────────────────────
    if "ratios_prof_map" not in st.session_state:
        st.caption("Press **Calculate Ratios** to load the dashboard.")
        return

    prof_map  = st.session_state["ratios_prof_map"]
    liq_map   = st.session_state["ratios_liq_map"]
    ret_map   = st.session_state["ratios_ret_map"]
    solv_map  = st.session_state["ratios_solv_map"]
    val_map   = st.session_state["ratios_val_map"]
    comp_list = st.session_state["ratios_comp_list"]

    # ── colour legend ─────────────────────────────────────────
    legend_html = " &nbsp; ".join(
        f"<span style='color:{company_color(c, comp_list)};font-weight:600;'>■ {c}</span>"
        for c in comp_list
    )
    st.markdown(
        f"<p style='font-size:12px;margin-bottom:16px;'>{legend_html}</p>",
        unsafe_allow_html=True,
    )

    # ── sections ──────────────────────────────────────────────
    sections = [
        ("Profitability",  "💹", prof_map,  list(next(iter(prof_map.values())).index), "prof"),
        ("Liquidity",      "💧", liq_map,   list(next(iter(liq_map.values())).index),  "liq"),
        ("Returns",        "📐", ret_map,   list(next(iter(ret_map.values())).index),  "ret"),
        ("Solvency",       "🏦", solv_map,  list(next(iter(solv_map.values())).index), "solv"),
        ("Valuation",      "🏷️", val_map,   list(next(iter(val_map.values())).index),  "val"),
    ]

    for section_name, icon, mdf_map, all_metrics, key in sections:
        with st.expander(f"{icon}  {section_name}", expanded=True):
            render_section(
                section_name  = section_name,
                icon          = icon,
                metrics_df_map= mdf_map,
                all_metrics   = all_metrics,
                selected_quarter = sel_quarter,
                comp_list     = comp_list,
                section_key   = key,
            )


if __name__ == "__main__":
    main()
