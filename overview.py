import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import plotly.express as px
from streamlit_plotly_events import plotly_events

st.set_page_config(page_title="Overview", layout="wide")

# -------------------------
# Config
# -------------------------
BASE_NAME = "LBS Bina"
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

ALL_COMPANIES = [BASE_NAME] + list(COMPETITORS.keys())
CACHE_VERSION = 1  # bump to bust cache if needed


# -------------------------
# Fetch
# -------------------------
@st.cache_data(show_spinner=False)
def fetch_history(ticker: str, start_dt: date, end_dt: date, _v: int = CACHE_VERSION) -> pd.DataFrame:
    """
    Fetch OHLCV history from yfinance.
    Returns DataFrame with Date as index (DatetimeIndex).
    """
    df = yf.Ticker(ticker).history(start=start_dt, end=end_dt)
    if df is None or df.empty:
        return pd.DataFrame()
    return df


def ticker_for(company: str) -> str:
    return BASE_TICKER if company == BASE_NAME else COMPETITORS[company]


def build_df_all(selected_companies, start_dt, end_dt) -> pd.DataFrame:
    """
    Build a clean df_all with columns:
    Date, Close, Volume, Company
    Sorted properly so Plotly draws the real shape (not a fake straight line).
    """
    dfs = []

    for comp in selected_companies:
        t = ticker_for(comp)

        # end is exclusive-ish, add a day so end date included
        df = fetch_history(t, start_dt, end_dt + pd.Timedelta(days=1))
        if df.empty:
            continue

        # Bring index -> Date column cleanly
        df = df.reset_index()
        if "Datetime" in df.columns and "Date" not in df.columns:
            df = df.rename(columns={"Datetime": "Date"})

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Close"] = pd.to_numeric(df.get("Close"), errors="coerce")
        df["Volume"] = pd.to_numeric(df.get("Volume"), errors="coerce")

        df["Company"] = comp

        df = df.dropna(subset=["Date", "Close", "Company"])
        df = df[["Date", "Close", "Volume", "Company"]]

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)
    df_all = df_all.dropna(subset=["Date", "Close", "Company"])
    df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

    return df_all


# -------------------------
# Chart (dark + clickable picks)
# -------------------------
def render_close_chart_with_picks(df_all: pd.DataFrame):
    st.subheader("Closing Price Comparison")

    if df_all.empty:
        st.warning("No data returned for that range.")
        return

    # init picks
    if "picks" not in st.session_state:
        st.session_state.picks = []

    # Build fig exactly like your simple px.line style, but dark.
    fig_close = px.line(
        df_all,
        x="Date",
        y="Close",
        color="Company",
        title="Closing Price",
        height=500
    )

    fig_close.update_traces(mode="lines", line=dict(width=2))
    fig_close.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        paper_bgcolor="#0b0f14",
        plot_bgcolor="#0b0f14",
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="Company",
    )
    fig_close.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    fig_close.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)

    # IMPORTANT: trace order == company order in the figure
    # Use the order Plotly created from df_all
    companies_in_plot = list(df_all["Company"].unique())

    clicked = plotly_events(
        fig_close,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="close_clicks",
        override_height=500,
    )

    if clicked:
        c = clicked[0]
        curve = c.get("curveNumber")
        point_index = c.get("pointIndex")

        if curve is not None and point_index is not None and 0 <= curve < len(companies_in_plot):
            company = companies_in_plot[curve]

            # Use df_all filtered by company, reset index so point_index matches
            df_comp = df_all[df_all["Company"] == company].reset_index(drop=True)

            if 0 <= point_index < len(df_comp):
                row = df_comp.loc[point_index]
                st.session_state.picks.append({
                    "Company": company,
                    "Date": pd.to_datetime(row["Date"]),
                    "Close": float(row["Close"]),
                })
                st.session_state.picks = st.session_state.picks[-2:]

    # Show picks + variance
    picks = st.session_state.picks
    c1, c2, c3 = st.columns([1.2, 1.2, 0.7])

    with c1:
        st.write("**Pick #1**")
        if len(picks) >= 1:
            p1 = picks[0]
            st.caption(p1["Company"])
            st.write(f"{p1['Date'].date()} • **{p1['Close']:.4f}**")
        else:
            st.caption("Click a point on the chart")

    with c2:
        st.write("**Pick #2**")
        if len(picks) >= 2:
            p2 = picks[1]
            st.caption(p2["Company"])
            st.write(f"{p2['Date'].date()} • **{p2['Close']:.4f}**")
        else:
            st.caption("Click a second point")

    with c3:
        if st.button("Reset picks", key="reset_picks"):
            st.session_state.picks = []
            st.rerun()

    if len(picks) == 2:
        p1, p2 = picks
        diff = p2["Close"] - p1["Close"]
        pct = (diff / p1["Close"]) * 100 if p1["Close"] else 0.0
        days = int((p2["Date"] - p1["Date"]).days)

        st.markdown("### Difference (Pick #2 − Pick #1)")
        st.write(f"**Δ Close:** {diff:+.4f}")
        st.write(f"**% Change:** {pct:+.2f}%")
        st.write(f"**Days between:** {days} day(s)")

        if p1["Company"] != p2["Company"]:
            st.warning("Pick both points on the same company line for a clean variance.")


def render_volume_chart(df_all: pd.DataFrame):
    st.subheader("Volume Comparison")

    if df_all.empty:
        st.warning("No data returned for that range.")
        return

    fig_vol = px.line(
        df_all,
        x="Date",
        y="Volume",
        color="Company",
        title="Trading Volume",
        height=500
    )
    fig_vol.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b0f14",
        plot_bgcolor="#0b0f14",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig_vol, use_container_width=True)


# -------------------------
# Main
# -------------------------
def main():
    st.title("📈 Competitor Stock Monitoring – LBS Bina as Base")

    # session state to stop resets
    if "df_all" not in st.session_state:
        st.session_state.df_all = pd.DataFrame()
    if "generated" not in st.session_state:
        st.session_state.generated = False
    if "picks" not in st.session_state:
        st.session_state.picks = []

    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="monitoring_start")
    end_dt = st.date_input("End date", value=date.today(), key="monitoring_end")

    selected_competitors = st.multiselect(
        "Select competitors to compare against LBS Bina",
        list(COMPETITORS.keys()),
        key="competitors_select"
    )

    # Always include base
    selected_companies = [BASE_NAME] + selected_competitors

    if st.button("Get Historical Data", type="primary"):
        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            return

        with st.spinner("Fetching historical data..."):
            df_all = build_df_all(selected_companies, start_dt, end_dt)

        if df_all.empty:
            st.warning("No data returned. Try another date range.")
            st.session_state.generated = False
            st.session_state.df_all = pd.DataFrame()
            st.session_state.picks = []
            return

        st.session_state.df_all = df_all
        st.session_state.generated = True
        st.session_state.picks = []  # reset picks each fetch

    if not st.session_state.generated or st.session_state.df_all.empty:
        st.caption("Select competitors + dates, then click **Get Historical Data**.")
        return

    df_all = st.session_state.df_all.copy()

    col1, col2 = st.columns(2)

    with col1:
        render_close_chart_with_picks(df_all)

    with col2:
        render_volume_chart(df_all)

    st.subheader("📊 Historical Data Table")
    st.dataframe(df_all, use_container_width=True)

