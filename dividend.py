# dividend.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

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

# -------------------------
# Helpers
# -------------------------
def _ticker_for_company(company: str) -> str | None:
    if company == BASE_COMPANY_NAME:
        return BASE_TICKER
    return COMPETITORS.get(company)

def _safe_pct(a, b):
    # (a-b)/b but safe
    if b is None or pd.isna(b) or b == 0:
        return pd.NA
    return (a - b) / b

def _clamp01(x):
    if pd.isna(x):
        return pd.NA
    return max(0.0, min(1.0, float(x)))

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_dividends(ticker: str) -> pd.DataFrame:
    """
    Yahoo Finance dividends via yfinance.
    Returns DataFrame with columns: Date, Dividend
    """
    t = yf.Ticker(ticker)
    s = t.dividends  # pandas Series indexed by date
    if s is None or len(s) == 0:
        return pd.DataFrame(columns=["Date", "Dividend"])

    df = s.reset_index()
    df.columns = ["Date", "Dividend"]
    df["Date"] = pd.to_datetime(df["Date"])
    df["Dividend"] = pd.to_numeric(df["Dividend"], errors="coerce")
    df = df.dropna(subset=["Dividend"]).sort_values("Date")
    return df

@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_prices(ticker: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    """
    Price history for yield calc. Uses Adj Close where possible.
    """
    t = yf.Ticker(ticker)
    hist = t.history(start=start_dt, end=end_dt + timedelta(days=1), auto_adjust=False)
    if hist is None or hist.empty:
        return pd.DataFrame(columns=["Date", "Adj Close", "Close"])
    hist = hist.reset_index()
    # yfinance index could be Datetime/Date depending on interval
    hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
    keep = [c for c in ["Date", "Adj Close", "Close"] if c in hist.columns]
    hist = hist[keep].dropna(subset=["Close"])
    return hist

def build_dividend_dataset(selected_companies: list[str], start_dt: date, end_dt: date) -> pd.DataFrame:
    rows = []
    for comp in selected_companies:
        ticker = _ticker_for_company(comp)
        if not ticker:
            continue

        df = fetch_dividends(ticker)
        if df.empty:
            continue

        df = df.copy()
        df["Company"] = comp
        df["Ticker"] = ticker
        rows.append(df)

    if not rows:
        return pd.DataFrame(columns=["Date", "Dividend", "Company", "Ticker"])

    all_df = pd.concat(rows, ignore_index=True)
    all_df["DateOnly"] = all_df["Date"].dt.date
    all_df = all_df[(all_df["DateOnly"] >= start_dt) & (all_df["DateOnly"] <= end_dt)].copy()
    all_df = all_df.drop(columns=["DateOnly"])
    all_df = all_df.sort_values(["Company", "Date"])
    return all_df

# -------------------------
# Analytics
# -------------------------
def annual_dividends(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Company", "Year", "AnnualDividend"])
    out = (
        df.assign(Year=df["Date"].dt.year)
          .groupby(["Company", "Ticker", "Year"], as_index=False)["Dividend"]
          .sum()
          .rename(columns={"Dividend": "AnnualDividend"})
          .sort_values(["Company", "Year"])
    )
    out["YoY_Growth"] = out.groupby("Company")["AnnualDividend"].pct_change()
    return out

def consistency_metrics(df: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    """
    Frequency proxy + streak.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "Company","Ticker","Payments","YearsPaid","YearsObserved","Coverage","LongestStreakYears","PaymentsPerYear"
        ])

    payments = df.groupby(["Company","Ticker"], as_index=False).size().rename(columns={"size": "Payments"})

    if annual.empty:
        annual_info = pd.DataFrame(columns=["Company","Ticker","YearsPaid","YearsObserved","Coverage","LongestStreakYears","PaymentsPerYear"])
        return payments.merge(annual_info, on=["Company","Ticker"], how="left")

    years_paid = (
        annual.groupby(["Company","Ticker"], as_index=False)
              .agg(YearsPaid=("Year","nunique"),
                   FirstYear=("Year","min"),
                   LastYear=("Year","max"))
    )
    years_paid["YearsObserved"] = years_paid["LastYear"] - years_paid["FirstYear"] + 1
    years_paid["Coverage"] = years_paid["YearsPaid"] / years_paid["YearsObserved"]

    # longest streak of years with dividend
    streak_rows = []
    for (comp, tic), g in annual.groupby(["Company","Ticker"]):
        ys = sorted(g["Year"].unique())
        best = 0
        cur = 0
        prev = None
        for y in ys:
            if prev is None or y == prev + 1:
                cur += 1
            else:
                best = max(best, cur)
                cur = 1
            prev = y
        best = max(best, cur)
        streak_rows.append({"Company": comp, "Ticker": tic, "LongestStreakYears": best})
    streak = pd.DataFrame(streak_rows)

    payments_per_year = (
        df.assign(Year=df["Date"].dt.year)
          .groupby(["Company","Ticker","Year"], as_index=False).size()
          .groupby(["Company","Ticker"], as_index=False)["size"].mean()
          .rename(columns={"size":"PaymentsPerYear"})
    )

    out = payments.merge(years_paid[["Company","Ticker","YearsPaid","YearsObserved","Coverage"]], on=["Company","Ticker"], how="left")
    out = out.merge(streak, on=["Company","Ticker"], how="left")
    out = out.merge(payments_per_year, on=["Company","Ticker"], how="left")
    return out

def volatility_metrics(annual: pd.DataFrame) -> pd.DataFrame:
    if annual.empty:
        return pd.DataFrame(columns=["Company","Ticker","AnnualMean","AnnualStd","CV","Cuts"])
    g = annual.groupby(["Company","Ticker"])
    out = g["AnnualDividend"].agg(AnnualMean="mean", AnnualStd="std").reset_index()
    out["CV"] = out["AnnualStd"] / out["AnnualMean"]
    out["Cuts"] = annual.groupby(["Company","Ticker"])["YoY_Growth"].apply(lambda s: int((s < 0).sum())).reset_index(drop=True)
    return out

def cagr_metrics(annual: pd.DataFrame) -> pd.DataFrame:
    """
    Dividend CAGR based on first and last non-zero annual dividend.
    """
    if annual.empty:
        return pd.DataFrame(columns=["Company","Ticker","DivCAGR"])
    rows = []
    for (comp, tic), g in annual.groupby(["Company","Ticker"]):
        gg = g.dropna(subset=["AnnualDividend"]).sort_values("Year")
        gg = gg[gg["AnnualDividend"] > 0]
        if gg.shape[0] < 2:
            rows.append({"Company": comp, "Ticker": tic, "DivCAGR": pd.NA})
            continue
        first = gg.iloc[0]
        last = gg.iloc[-1]
        n = int(last["Year"] - first["Year"])
        if n <= 0 or first["AnnualDividend"] <= 0:
            rows.append({"Company": comp, "Ticker": tic, "DivCAGR": pd.NA})
            continue
        cagr = (last["AnnualDividend"] / first["AnnualDividend"]) ** (1 / n) - 1
        rows.append({"Company": comp, "Ticker": tic, "DivCAGR": cagr})
    return pd.DataFrame(rows)

def yield_metrics(selected_companies: list[str], start_dt: date, end_dt: date, df_events: pd.DataFrame) -> pd.DataFrame:
    """
    - TTM yield: sum of dividends over last 365 days / avg price over last 365 days
    - Period avg yield: sum(dividends in selected period) / avg price in selected period
    """
    rows = []
    ttm_start = end_dt - timedelta(days=365)

    for comp in selected_companies:
        tic = _ticker_for_company(comp)
        if not tic:
            continue

        # dividends
        div_all = fetch_dividends(tic)
        if div_all.empty:
            rows.append({"Company": comp, "Ticker": tic, "TTM_Dividend": pd.NA, "TTM_Yield": pd.NA, "Period_Yield": pd.NA})
            continue

        div_all["DateOnly"] = div_all["Date"].dt.date

        ttm_div = div_all[(div_all["DateOnly"] >= ttm_start) & (div_all["DateOnly"] <= end_dt)]["Dividend"].sum()
        period_div = df_events[df_events["Company"] == comp]["Dividend"].sum() if not df_events.empty else 0.0

        # prices
        p_ttm = fetch_prices(tic, ttm_start, end_dt)
        p_period = fetch_prices(tic, start_dt, end_dt)

        # choose Adj Close if available else Close
        def avg_price(p):
            if p is None or p.empty:
                return pd.NA
            col = "Adj Close" if "Adj Close" in p.columns else "Close"
            return float(p[col].dropna().mean()) if p[col].dropna().shape[0] else pd.NA

        avg_ttm = avg_price(p_ttm)
        avg_period = avg_price(p_period)

        ttm_yield = (ttm_div / avg_ttm) if (not pd.isna(avg_ttm) and avg_ttm != 0) else pd.NA
        period_yield = (period_div / avg_period) if (not pd.isna(avg_period) and avg_period != 0) else pd.NA

        rows.append({
            "Company": comp,
            "Ticker": tic,
            "TTM_Dividend": ttm_div if ttm_div != 0 else pd.NA,
            "TTM_Yield": ttm_yield,
            "Period_Yield": period_yield,
        })

    return pd.DataFrame(rows)

def add_persona(score_df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple persona labels based on metrics.
    """
    df = score_df.copy()

    def persona_row(r):
        # defensive: high coverage, low CV, not too many cuts
        if pd.notna(r.get("Coverage")) and pd.notna(r.get("CV")):
            if r["Coverage"] >= 0.7 and (pd.isna(r["CV"]) or r["CV"] <= 0.6) and (pd.isna(r["Cuts"]) or r["Cuts"] <= 1):
                return "🛡 Income Defensive"
        # growth income: positive CAGR
        if pd.notna(r.get("DivCAGR")) and r["DivCAGR"] is not pd.NA:
            if r["DivCAGR"] is not None and pd.notna(r["DivCAGR"]) and r["DivCAGR"] >= 0.05:
                return "📈 Growth Income"
        # yield hunter: high TTM yield
        if pd.notna(r.get("TTM_Yield")):
            if r["TTM_Yield"] >= 0.05:
                return "🎯 Yield Hunter"
        # speculative fallback
        return "🚨 Speculative"

    df["Persona"] = df.apply(persona_row, axis=1)
    return df

def dividend_score(score_df: pd.DataFrame) -> pd.DataFrame:
    """
    0-100 score:
      40% Consistency (Coverage + streak)
      25% Growth (DivCAGR, YoY)
      20% Yield (TTM yield)
      15% Stability (1 - CV, cuts)
    Normalization is simple and robust (no fancy ML).
    """
    df = score_df.copy()

    # Normalize components to 0..1
    # Consistency:
    df["cons_coverage"] = df["Coverage"].apply(lambda x: _clamp01(x) if pd.notna(x) else pd.NA)
    df["cons_streak"] = df["LongestStreakYears"]
    if df["cons_streak"].notna().any():
        mx = df["cons_streak"].max()
        df["cons_streak"] = df["cons_streak"].apply(lambda x: (x / mx) if (pd.notna(x) and mx and mx > 0) else pd.NA)
    else:
        df["cons_streak"] = pd.NA
    df["consistency"] = df[["cons_coverage","cons_streak"]].mean(axis=1, skipna=True)

    # Growth:
    # DivCAGR: clamp between -50% and +50% to avoid crazy values
    def norm_cagr(x):
        if pd.isna(x):
            return pd.NA
        x = max(-0.5, min(0.5, float(x)))
        return (x + 0.5) / 1.0  # map -0.5..0.5 to 0..1

    df["growth"] = df["DivCAGR"].apply(norm_cagr)

    # Yield:
    # clamp 0..10% to 0..1
    def norm_yield(x):
        if pd.isna(x):
            return pd.NA
        x = max(0.0, min(0.10, float(x)))
        return x / 0.10

    df["yield_score"] = df["TTM_Yield"].apply(norm_yield)

    # Stability:
    # CV lower is better. clamp 0..2 then invert.
    def norm_cv(x):
        if pd.isna(x):
            return pd.NA
        x = max(0.0, min(2.0, float(x)))
        return 1.0 - (x / 2.0)

    df["stability_cv"] = df["CV"].apply(norm_cv)
    # cuts: 0 cuts best, >=4 worst
    def norm_cuts(x):
        if pd.isna(x):
            return pd.NA
        x = int(x)
        x = max(0, min(4, x))
        return 1.0 - (x / 4.0)

    df["stability_cuts"] = df["Cuts"].apply(norm_cuts)
    df["stability"] = df[["stability_cv","stability_cuts"]].mean(axis=1, skipna=True)

    # Weighted score
    df["DividendScore"] = (
        0.40 * df["consistency"].fillna(0) +
        0.25 * df["growth"].fillna(0) +
        0.20 * df["yield_score"].fillna(0) +
        0.15 * df["stability"].fillna(0)
    ) * 100

    return df

# -------------------------
# UI
# -------------------------
def main():
    st.title("💸 Dividend Dashboard")

    start_dt = st.date_input("Start date", value=date(2020, 1, 1), key="div_start")
    end_dt = st.date_input("End date", value=date.today(), key="div_end")

    company_options = [BASE_COMPANY_NAME] + list(COMPETITORS.keys())
    selected_companies = st.multiselect(
        "Select companies",
        company_options,
        default=[BASE_COMPANY_NAME],
        key="div_companies",
    )

    # optional persona filter (applies after we compute metrics)
    persona_filter = st.multiselect(
        "Persona filter (optional)",
        ["🛡 Income Defensive", "📈 Growth Income", "🎯 Yield Hunter", "🚨 Speculative"],
        default=[],
        help="Filter after metrics are computed. Leave blank to show all.",
    )

    st.divider()

    if st.button("Generate Dividends", key="div_generate"):
        if not selected_companies:
            st.warning("Select at least 1 company.")
            return
        if start_dt > end_dt:
            st.error("Start date cannot be after end date.")
            return

        with st.spinner("Fetching dividend data + prices from Yahoo Finance..."):
            df = build_dividend_dataset(selected_companies, start_dt, end_dt)

            if df.empty:
                st.warning("No dividend events found for this period (Yahoo Finance may have no data).")
                return

            ann = annual_dividends(df)
            cons = consistency_metrics(df, ann)
            vol = volatility_metrics(ann)
            cagr = cagr_metrics(ann)
            yld = yield_metrics(selected_companies, start_dt, end_dt, df)

            # master metrics table
            metrics = cons.merge(vol, on=["Company","Ticker"], how="left")
            metrics = metrics.merge(cagr, on=["Company","Ticker"], how="left")
            metrics = metrics.merge(yld, on=["Company","Ticker"], how="left")

            metrics = dividend_score(metrics)
            metrics = add_persona(metrics)

            if persona_filter:
                metrics = metrics[metrics["Persona"].isin(persona_filter)].copy()
                df = df[df["Company"].isin(metrics["Company"].unique())].copy()
                ann = ann[ann["Company"].isin(metrics["Company"].unique())].copy()

        # -------------------------
        # 1) Totals (you had this)
        # -------------------------
        st.subheader("📌 Total Dividends in Period")
        totals = (
            df.groupby("Company", as_index=False)["Dividend"]
              .sum()
              .rename(columns={"Dividend": "Total Dividend"})
              .sort_values("Total Dividend", ascending=False)
        )
        st.dataframe(totals.style.format({"Total Dividend": "{:.4f}"}), use_container_width=True)

        # -------------------------
        # 2) Dividend Score + Rankings
        # -------------------------
        st.subheader("🏆 Dividend Score & Peer Ranking")
        show_cols = [
            "Company","Ticker","DividendScore","Persona",
            "Coverage","LongestStreakYears","PaymentsPerYear",
            "DivCAGR","TTM_Yield","CV","Cuts"
        ]
        view = metrics[show_cols].sort_values("DividendScore", ascending=False)

        st.dataframe(
            view.style.format({
                "DividendScore": "{:.1f}",
                "Coverage": "{:.0%}",
                "PaymentsPerYear": "{:.2f}",
                "DivCAGR": "{:.1%}",
                "TTM_Yield": "{:.2%}",
                "CV": "{:.2f}",
            }),
            use_container_width=True
        )

        # -------------------------
        # 3) Timeline (your scatter)
        # -------------------------
        st.subheader("📈 Dividend Payout Timeline")
        fig = px.scatter(
            df,
            x="Date",
            y="Dividend",
            color="Company",
            title=f"Dividend Events ({start_dt} → {end_dt})",
        )
        fig.update_traces(marker=dict(size=10), mode="markers")
        fig.update_layout(xaxis_title="Date", yaxis_title="Dividend (per share)")
        st.plotly_chart(fig, use_container_width=True)

        # -------------------------
        # 4) Annual dividends + YoY growth
        # -------------------------
        st.subheader("📊 Annual Dividends (and Growth)")
        if not ann.empty:
            ann_chart = px.line(
                ann,
                x="Year",
                y="AnnualDividend",
                color="Company",
                markers=True,
                title="Annual Dividend per Share",
            )
            ann_chart.update_layout(xaxis_title="Year", yaxis_title="Annual Dividend (per share)")
            st.plotly_chart(ann_chart, use_container_width=True)

            growth_df = ann.dropna(subset=["YoY_Growth"]).copy()
            if not growth_df.empty:
                growth_chart = px.bar(
                    growth_df,
                    x="Year",
                    y="YoY_Growth",
                    color="Company",
                    title="YoY Dividend Growth",
                )
                growth_chart.update_layout(xaxis_title="Year", yaxis_title="YoY Growth")
                st.plotly_chart(growth_chart, use_container_width=True)

        # -------------------------
        # 5) Yield comparison (TTM)
        # -------------------------
        st.subheader("💰 Dividend Yield Comparison (TTM)")
        if metrics["TTM_Yield"].notna().any():
            y = metrics.dropna(subset=["TTM_Yield"]).sort_values("TTM_Yield", ascending=False)
            y_fig = px.bar(y, x="Company", y="TTM_Yield", title="Trailing 12M Dividend Yield")
            y_fig.update_layout(xaxis_title="", yaxis_title="TTM Yield")
            st.plotly_chart(y_fig, use_container_width=True)
        else:
            st.info("TTM yield not available (price history missing for selected tickers).")

        # -------------------------
        # 6) Stability / volatility
        # -------------------------
        st.subheader("🧊 Stability / Volatility")
        stab_cols = ["Company","CV","Cuts","Coverage","LongestStreakYears"]
        st.dataframe(
            metrics[stab_cols].sort_values(["Coverage","CV"], ascending=[False, True]).style.format({
                "Coverage": "{:.0%}",
                "CV": "{:.2f}",
            }),
            use_container_width=True
        )

        # -------------------------
        # 7) Event table (your table)
        # -------------------------
        st.subheader("🧾 Dividend Event Table")
        table_df = df.copy()
        table_df["Date"] = table_df["Date"].dt.date
        st.dataframe(
            table_df.rename(columns={"Dividend": "Dividend (per share)"}).style.format({"Dividend (per share)": "{:.4f}"}),
            use_container_width=True,
        )

        st.caption("Note: Data source is Yahoo Finance via yfinance. Some KL tickers may have missing dividend history or price series gaps.")

if __name__ == "__main__":
    main()
