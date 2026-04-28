import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Financials Comparison", layout="wide")

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
}

KEY_METRICS = [
    "Total Revenue",
    "Gross Profit",
    "Operating Income",
    "Pretax Income",
    "Net Income Common Stockholders",
    "EBITDA",
]

# -------------------------
# FETCH DATA
# -------------------------
@st.cache_data
def fetch_data(ticker):
    t = yf.Ticker(ticker)
    df = t.quarterly_financials

    if df is None or df.empty:
        return pd.DataFrame()

    df.columns = pd.to_datetime(df.columns)
    df = df.apply(pd.to_numeric, errors="coerce")

    # scale to thousands
    df = df / 1000.0

    return df


# -------------------------
# BUILD COMPARISON TABLE
# -------------------------
def build_comparison(selected_companies, mode, period):
    combined = pd.DataFrame()

    for comp in selected_companies:
        ticker = companies[comp]
        df = fetch_data(ticker)

        if df.empty:
            continue

        if mode == "Quarter":
            col = pd.to_datetime(period)
            if col not in df.columns:
                continue
            series = df[col]

        else:  # Year mode
            yearly = df.groupby(df.columns.year, axis=1).sum()
            year = int(period)
            if year not in yearly.columns:
                continue
            series = yearly[year]

        series.name = comp
        combined = pd.concat([combined, series], axis=1)

    return combined


# -------------------------
# FORMAT DISPLAY
# -------------------------
def format_df(df):
    return df.applymap(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")


# -------------------------
# UI HEADER
# -------------------------
st.markdown("## 📊 Company Financials Comparison")
st.caption("Compare companies properly. No more messy tables.")

# -------------------------
# CONTROLS
# -------------------------
col1, col2, col3 = st.columns(3)

with col1:
    selected_companies = st.multiselect(
        "Select Companies",
        list(companies.keys()),
        default=["LBS Bina", "S P Setia"]
    )

with col2:
    mode = st.radio("View Mode", ["Quarter", "Year"], horizontal=True)

with col3:
    metric = st.selectbox("Focus Metric", KEY_METRICS)

# -------------------------
# PERIOD SELECTION
# -------------------------
sample_df = fetch_data(list(companies.values())[0])

if not sample_df.empty:

    if mode == "Quarter":
        periods = sorted(sample_df.columns, reverse=True)
        period = st.selectbox(
            "Select Quarter",
            [p.strftime("%Y-%m-%d") for p in periods]
        )

    else:
        years = sorted(sample_df.columns.year.unique(), reverse=True)
        period = st.selectbox("Select Year", years)

else:
    st.warning("No data available.")
    st.stop()

# -------------------------
# BUILD DATA
# -------------------------
comparison_df = build_comparison(selected_companies, mode, period)

if comparison_df.empty:
    st.warning("No data for selected filters.")
    st.stop()

# -------------------------
# KPI + CHART
# -------------------------
st.markdown("### 🔥 Quick Comparison")

metric_row = comparison_df.loc[metric].dropna()

colA, colB = st.columns([1, 2])

with colA:
    for comp in metric_row.index:
        st.metric(
            label=comp,
            value=f"{metric_row[comp]:,.0f}"
        )

with colB:
    fig = px.bar(
        x=metric_row.index,
        y=metric_row.values,
        title=f"{metric} Comparison",
        text_auto=".2s"
    )

    fig.update_layout(
        template="plotly_dark",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

# -------------------------
# TABLE
# -------------------------
st.markdown("### 📊 Detailed Financials")

st.dataframe(
    format_df(comparison_df),
    use_container_width=True
)
