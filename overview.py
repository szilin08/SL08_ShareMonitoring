# overview.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import date
from streamlit_plotly_events import plotly_events

st.set_page_config(page_title="Overview", layout="wide")

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
ALL = [BASE_NAME] + list(COMPETITORS.keys())

CACHE_VERSION = 3  # bump to bust cache


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    """
    yfinance can return:
    - normal columns: ['Open','High','Low','Close',...]
    - MultiIndex columns (Price, Ticker) or (Ticker, Price)

    This function returns a 1D Close Series reliably.
    """
    if df is None or df.empty:
        return pd.Series(dtype="float64")

    # Normal case
    if "Close" in df.columns and isinstance(df["Close"], pd.Series):
        return df["Close"]

    # MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        # Try common layouts
        # 1) level contains 'Close'
        for lvl in range(df.columns.nlevels):
            if "Close" in df.columns.get_level_values(lvl):
                try:
                    close_df = df.xs("Close", axis=1, level=lvl)
                    # close_df might still be DataFrame if multiple tickers
                    if isinstance(close_df, pd.DataFrame):
                        return close_df.iloc[:, 0]
                    return close_df
                except Exception:
                    pass

        # Fallback: search any column name containing 'Close'
        close_cols = [c for c in df.columns if any(str(x).lower() == "close" for x in c)]
        if close_cols:
            s = df[close_cols[0]]
            if isinstance(s, pd.DataFrame):
                return s.iloc[:, 0]
            return s

    # Last resort: try attribute-style
    if hasattr(df, "Close"):
        s = getattr(df, "Close")
        if isinstance(s, pd.Series):
            return s

    return pd.Series(dtype="float64")


@st.cache_data(show_spinner=False)
def fetch_close(ticker: str, start_dt: date, end_dt: date, _v: int = CACHE_VERSION) -> pd.DataFrame:
    """
    Fetch Close prices with yf.download(), robust to MultiIndex columns.
    """
    df = yf.download(
        tickers=ticker,
        start=start_dt,
        end=end_dt,
        progress=False,
        auto_adjust=False,
        actions=False,
        threads=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    close = _extract_close_series(df)
    if close is None or close.empty:
        return pd.DataFrame()

    out = close.to_frame(name="Close").reset_index()

    # Normalize date column name
    if "Datetime" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"Datetime": "Date"})
    elif "index" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"index": "Date"})

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Close"] = pd.to_numeric(out["Close"], errors="coerce")
    out = out.dropna(subset=["Date", "Close"])

    return out[["Date", "Close"]]


def ticker_for(company: str) -> str:
    return BASE_TICKER if company == BASE_NAME else COMPETITORS[company]


def fix_bursa_unit_if_needed(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    If Yahoo returns Close in sen*1000 (e.g. 759), convert to RM (0.759).
    Only apply when it's obviously wrong (max > 50).
    """
    if df_all.empty:
        return df_all
    mx = float(df_all["Close"].max())
    if mx > 50:
        df_all = df_all.copy()
        df_all["Close"] = df_all["Close"] / 1000.0
    return df_all


def main():
    st.title("📊 Overview Dashboard")

    # state
    if "ov_df_all" not in st.session_state:
        st.session_state.ov_df_all = pd.DataFrame()
    if "ov_generated" not in st.session_state:
        st.session_state.ov_generated = False
    if "ov_picks" not in st.session_state:
        st.session_state.ov_picks = []

    # UNIQUE keys (no collision)
    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="ov_start")
    end_dt = st.date_input("End date", value=date.today(), key="ov_end")
    selected = st.multiselect("Select companies", options=ALL, default=[BASE_NAME], key="ov_companies")

    if st.button("Generate Overview", type="primary", key="ov_generate"):
        if not selected:
            st.warning("Pick at least one company.")
            return
        if start_dt >= end_dt:
            st.warning("Start date must be earlier than end date.")
            return

        dfs = []
        with st.spinner("Fetching historical share price..."):
            for comp in selected:
                t = ticker_for(comp)
                df = fetch_close(t, start_dt, end_dt + pd.Timedelta(days=1))
                if df.empty:
                    continue
                df["Company"] = comp
                dfs.append(df)

        if not dfs:
            st.warning("No data returned for that range.")
            st.session_state.ov_generated = False
            st.session_state.ov_df_all = pd.DataFrame()
            st.session_state.ov_picks = []
            return

        df_all = pd.concat(dfs, ignore_index=True)
        df_all = df_all.dropna(subset=["Date", "Close", "Company"])
        df_all = df_all.sort_values(["Company", "Date"]).reset_index(drop=True)

        # Make it match real Bursa chart shape/axis if Yahoo sent scaled units
        df_all = fix_bursa_unit_if_needed(df_all)

        st.session_state.ov_df_all = df_all
        st.session_state.ov_generated = True
        st.session_state.ov_picks = []

    if not st.session_state.ov_generated or st.session_state.ov_df_all.empty:
        st.caption("Pick companies + dates, then click **Generate Overview**.")
        return

    df_all = st.session_state.ov_df_all.copy()

    # Debug so you can see if units are sane
    with st.expander("Debug"):
        st.write("Close min:", float(df_all["Close"].min()))
        st.write("Close max:", float(df_all["Close"].max()))
        st.dataframe(df_all.head(10), use_container_width=True)

    st.subheader("Closing Price Comparison")

    company_order = list(df_all["Company"].unique())

    fig = px.line(df_all, x="Date", y="Close", color="Company", title="Closing Price", height=520)
    fig.update_traces(mode="lines", line=dict(width=2))
    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        paper_bgcolor="#0b0f14",
        plot_bgcolor="#0b0f14",
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="Company",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False, tickformat=".4f")

    clicked = plotly_events(
        fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="ov_close_clicks",
        override_height=520,
    )

    # record picks
    if clicked:
        c = clicked[0]
        curve = c.get("curveNumber")
        point_index = c.get("pointIndex")

        if curve is not None and point_index is not None and 0 <= curve < len(company_order):
            comp = company_order[curve]
            df_comp = df_all[df_all["Company"] == comp].reset_index(drop=True)

            if 0 <= point_index < len(df_comp):
                row = df_comp.loc[point_index]
                st.session_state.ov_picks.append(
                    {"Company": comp, "Date": pd.to_datetime(row["Date"]), "Close": float(row["Close"])}
                )
                st.session_state.ov_picks = st.session_state.ov_picks[-2:]

    picks = st.session_state.ov_picks
    c1, c2, c3 = st.columns([1.2, 1.2, 0.7])

    with c1:
        st.write("**Pick #1**")
        if len(picks) >= 1:
            p1 = picks[0]
            st.caption(p1["Company"])
            st.write(f"{p1['Date'].date()} • **{p1['Close']:.4f}**")
        else:
            st.caption("Click a point")

    with c2:
        st.write("**Pick #2**")
        if len(picks) >= 2:
            p2 = picks[1]
            st.caption(p2["Company"])
            st.write(f"{p2['Date'].date()} • **{p2['Close']:.4f}**")
        else:
            st.caption("Click a second point")

    with c3:
        if st.button("Reset picks", key="ov_reset_picks"):
            st.session_state.ov_picks = []
            st.rerun()

    if len(picks) == 2:
        p1, p2 = picks
        diff = p2["Close"] - p1["Close"]
        pct = (diff / p1["Close"]) * 100 if p1["Close"] else 0.0
        days = int((p2["Date"] - p1["Date"]).days)

        st.markdown("### Difference")
        st.write(f"**Δ Close:** {diff:+.4f}")
        st.write(f"**% Change:** {pct:+.2f}%")
        st.write(f"**Days between:** {days} day(s)")

        if p1["Company"] != p2["Company"]:
            st.warning("Pick two points on the same company line for a clean variance.")


if __name__ == "__main__":
    main()
