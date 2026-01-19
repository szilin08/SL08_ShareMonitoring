# overview_dashboard.py
# Streamlit: Overview Dashboard (Share Price + A→B change, Revenue vs PATMI, placeholder Sales)

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

# You must implement these in financials.py
# Expected return format:
#   get_revenue_data(selected_companies, start, end) -> DataFrame columns: Company, Revenue
#   get_patmi_data(selected_companies, start, end)   -> DataFrame columns: Company, PATMI
from financials import get_revenue_data, get_patmi_data


# -----------------------------
# CONFIG
# -----------------------------
BASE_COMPANY_NAME = "LBS Bina"
BASE_TICKER = "5789.KL"

COMPETITORS = {
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
}


# -----------------------------
# DATA FETCH
# -----------------------------
@st.cache_data(show_spinner=False, ttl=60 * 30)
def fetch_price_history(ticker: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    """
    Fetch daily price history from yfinance.
    yfinance end is exclusive-ish; we add +1 day when calling it.
    """
    start_ts = pd.Timestamp(start_dt)
    end_ts = pd.Timestamp(end_dt) + pd.Timedelta(days=1)

    df = yf.Ticker(ticker).history(start=start_ts, end=end_ts)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    # yfinance returns Date or Datetime depending on asset; normalize
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def build_price_dataset(selected_companies: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    dfs = []
    for comp in selected_companies:
        ticker = BASE_TICKER if comp == BASE_COMPANY_NAME else COMPETITORS.get(comp)
        if not ticker:
            continue

        df = fetch_price_history(ticker, start_dt, end_dt)
        if df.empty:
            continue

        df["Company"] = comp
        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)
    # Keep only useful columns (still safe if others exist)
    keep_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "Company"] if c in df_all.columns]
    df_all = df_all[keep_cols].copy()
    df_all = df_all.sort_values(["Company", "Date"])
    return df_all


def compute_period_change(df_all: pd.DataFrame, selected_companies: list[str], a_date: date, b_date: date) -> pd.DataFrame:
    """
    For each company: A price = first Close in period, B price = last Close in period.
    Return a table of RM change and % change.
    """
    if df_all.empty:
        return pd.DataFrame()

    df_all = df_all.copy()
    df_all["DateOnly"] = df_all["Date"].dt.date

    df_period = df_all[(df_all["DateOnly"] >= a_date) & (df_all["DateOnly"] <= b_date)].copy()
    if df_period.empty:
        return pd.DataFrame()

    rows = []
    for comp in selected_companies:
        d = df_period[df_period["Company"] == comp].sort_values("Date")
        if d.empty:
            continue

        a_price = float(d.iloc[0]["Close"])
        b_price = float(d.iloc[-1]["Close"])
        diff = b_price - a_price
        pct = (diff / a_price * 100) if a_price != 0 else 0.0

        rows.append(
            {
                "Company": comp,
                "A Date": a_date,
                "A Price": a_price,
                "B Date": b_date,
                "B Price": b_price,
                "Change (RM)": diff,
                "Change (%)": pct,
            }
        )

    return pd.DataFrame(rows)


# -----------------------------
# UI
# -----------------------------
def render_price_chart(df_all: pd.DataFrame):
    fig = px.line(
        df_all,
        x="Date",
        y="Close",
        color="Company",
        title="Share Price (Close) Over Time",
    )
    fig.update_traces(mode="lines")
    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Price",
        legend_title_text="Company",
    )
    fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)


def render_revenue_patmi(selected_companies: list[str], start_dt: date, end_dt: date):
    st.subheader("💰 Revenue vs PATMI Comparison")

    rev_df = get_revenue_data(selected_companies, start_dt, end_dt)
    patmi_df = get_patmi_data(selected_companies, start_dt, end_dt)

    if rev_df is None or patmi_df is None or rev_df.empty or patmi_df.empty:
        st.warning("No Revenue or PATMI data available for the selected period.")
        return

    # Merge
    combined_df = rev_df.merge(patmi_df, on="Company", how="inner")

    if combined_df.empty:
        st.warning("Revenue/PATMI merge produced no rows (check Company names).")
        return

    # Millions label (your code used /1_000; keep same behavior)
    combined_df["Revenue_M"] = (combined_df["Revenue"] / 1_000).round(2)
    combined_df["PATMI_M"] = (combined_df["PATMI"] / 1_000).round(2)

    fig = go.Figure(
        data=[
            go.Bar(
                name="Revenue",
                x=combined_df["Company"],
                y=combined_df["Revenue"],
                marker_color="steelblue",
                text=combined_df["Revenue_M"].astype(str) + "M",
                textposition="outside",
            ),
            go.Bar(
                name="PATMI",
                x=combined_df["Company"],
                y=combined_df["PATMI"],
                marker_color="darkorange",
                text=combined_df["PATMI_M"].astype(str) + "M",
                textposition="outside",
            ),
        ]
    )

    fig.update_layout(
        barmode="group",
        title=f"Revenue vs PATMI Comparison ({start_dt} → {end_dt})",
        xaxis_title="Company",
        yaxis_title="Amount (RM)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80),
    )

    st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(page_title="Overview Dashboard", layout="wide")
    st.title("📊 Overview Dashboard")

    # Sidebar / Inputs
    st.caption("Compare share price performance and key financials across LBS Bina + peers.")

    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="overview_start")
    end_dt = st.date_input("End date", value=date.today(), key="overview_end")

    company_options = [BASE_COMPANY_NAME] + list(COMPETITORS.keys())
    selected_companies = st.multiselect("Select companies", company_options, default=[BASE_COMPANY_NAME])

    if st.button("Generate Overview"):
        if not selected_companies:
            st.warning("Select at least 1 company.")
            return

        if start_dt > end_dt:
            st.error("Start date cannot be after end date.")
            return

        with st.spinner("Fetching price data..."):
            df_all = build_price_dataset(selected_companies, start_dt, end_dt)

        if df_all.empty:
            st.error("No price data returned. Check tickers / date range / internet access.")
            return

        # --- Graph 1: Share Price ---
        st.subheader("📈 Share Price Comparison")
        render_price_chart(df_all)

        # --- A → B comparison (RM + %) ---
        st.markdown("#### 🧮 Pick 2 points (A → B) to see RM + % change")
        all_dates = sorted(df_all["Date"].dt.date.unique().tolist())

        if len(all_dates) < 2:
            st.warning("Not enough dates to compare.")
        else:
            a_date, b_date = st.select_slider(
                "Select period",
                options=all_dates,
                value=(all_dates[0], all_dates[-1]),
                key="price_compare_period",
            )

            summary_df = compute_period_change(df_all, selected_companies, a_date, b_date)

            if summary_df.empty:
                st.warning("No price data found in that selected period.")
            else:
                st.dataframe(
                    summary_df.style.format(
                        {
                            "A Price": "{:.3f}",
                            "B Price": "{:.3f}",
                            "Change (RM)": "{:+.3f}",
                            "Change (%)": "{:+.2f}%",
                        }
                    ),
                    use_container_width=True,
                )

                # Highlight LBS metric if included
                if BASE_COMPANY_NAME in selected_companies:
                    lbs = summary_df[summary_df["Company"] == BASE_COMPANY_NAME]
                    if not lbs.empty:
                        r = lbs.iloc[0]
                        st.metric(
                            label=f"{BASE_COMPANY_NAME} Change (A → B)",
                            value=f"RM {r['B Price']:.3f}",
                            delta=f"{r['Change (RM)']:+.3f} ({r['Change (%)']:+.2f}%)",
                        )

        # --- Graph 2: Revenue + PATMI ---
        render_revenue_patmi(selected_companies, start_dt, end_dt)

        # --- Graph 3: Sales Target vs Actual (Placeholder) ---
        st.subheader("🎯 Sales Target vs Actual (Placeholder)")
        st.info("This requires additional data (annual reports / sales target dataset).")

        # Example placeholder if you later add CSV
        # sales_df = pd.read_csv("sales_targets.csv")  # Columns: Company, Target, Actual
        # fig_sales = px.bar(sales_df, x="Company", y=["Target", "Actual"], barmode="group")
        # st.plotly_chart(fig_sales, use_container_width=True)


if __name__ == "__main__":
    main()
