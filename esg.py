# esg.py
import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------
# CONFIG
# -----------------------
CSV_PATH = "ftse_esg_selected_companies_3y.csv"

NAME_TO_CODE = {
    "LBS Bina": "5789",
    "S P Setia": "8664",
    "Sime Darby Property": "5288",
    "Eco World": "8206",
    "UEM Sunrise": "5148",
    "IOI Properties": "5249",
    "Mah Sing": "8583",
    "IJM Corporation": "3336",
    "Sunway": "5211",
    "Gamuda": "5398",
    "OSK Holdings": "5053",
    "UOA Development": "5200",
}

CODE_TO_NAME = {v: k for k, v in NAME_TO_CODE.items()}

@st.cache_data(show_spinner=False)
def load_esg_table() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)

    # Normalize types
    df["Year"] = df["Year"].astype(int)
    df["StockCode"] = df["StockCode"].astype(str).str.zfill(4)
    df["ESG_Stars"] = pd.to_numeric(df["ESG_Stars"], errors="coerce")

    # Ensure Company exists (if your extractor already has Company, keep it)
    if "Company" not in df.columns or df["Company"].isna().all():
        df["Company"] = df["StockCode"].map(CODE_TO_NAME).fillna(df["StockCode"])

    # Add a clean display label
    df["Label"] = df["Company"] + " (" + df["StockCode"] + ")"
    return df

def compute_3y_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns per StockCode:
      ESG_2023, ESG_2024, ESG_2025 (if present), Change_3Y
    """
    wide = df.pivot_table(index=["StockCode", "Company"], columns="Year", values="ESG_Stars", aggfunc="max")
    wide = wide.reset_index()

    years = sorted([c for c in wide.columns if isinstance(c, int)])
    if not years:
        return pd.DataFrame()

    first_year = years[0]
    last_year = years[-1]

    wide["FirstYear"] = first_year
    wide["LastYear"] = last_year
    wide["ESG_First"] = wide[first_year]
    wide["ESG_Last"] = wide[last_year]
    wide["Change_3Y"] = wide["ESG_Last"] - wide["ESG_First"]
    return wide

def main():
    st.title("🌿 ESG Dashboard (FTSE Russell via Bursa PDFs)")

    df = load_esg_table()
    if df.empty:
        st.error("CSV is empty or not found. Make sure ftse_esg_selected_companies_3y.csv exists.")
        return

    all_labels = sorted(df["Label"].unique().tolist())

    # Defaults
    default_base = "LBS Bina (5789)" if "LBS Bina (5789)" in all_labels else all_labels[0]

    base = st.selectbox("Base developer", all_labels, index=all_labels.index(default_base))
    others = [x for x in all_labels if x != base]

    compare = st.multiselect(
        "Compare against",
        others,
        default=others[:3] if len(others) >= 3 else others,
    )

    selected = [base] + compare
    dsel = df[df["Label"].isin(selected)].copy()

    st.divider()

    # -----------------------
    # 1) Trend line (2023–2025)
    # -----------------------
    st.subheader("📈 ESG Stars Trend (by year)")
    line_fig = px.line(
        dsel.sort_values("Year"),
        x="Year",
        y="ESG_Stars",
        color="Label",
        markers=True,
        title="ESG Stars over time",
    )
    line_fig.update_layout(xaxis_title="Year", yaxis_title="ESG Stars")
    st.plotly_chart(line_fig, use_container_width=True)

    # -----------------------
    # 2) Latest year comparison (bar)
    # -----------------------
    latest_year = int(dsel["Year"].max())
    st.subheader(f"📊 ESG Stars Comparison ({latest_year})")
    latest = dsel[dsel["Year"] == latest_year].copy()

    bar_latest = px.bar(
        latest.sort_values("ESG_Stars", ascending=False),
        x="Label",
        y="ESG_Stars",
        title=f"Latest ESG Stars ({latest_year})",
    )
    bar_latest.update_layout(xaxis_title="", yaxis_title="ESG Stars")
    st.plotly_chart(bar_latest, use_container_width=True)

    # -----------------------
    # 3) 3-year change comparison (bar)
    # -----------------------
    st.subheader("🔁 ESG Change (First year → Last year)")
    wide = compute_3y_change(dsel)

    if wide.empty:
        st.info("Not enough year data to compute change.")
    else:
        wide["Label"] = wide["Company"] + " (" + wide["StockCode"] + ")"
        change_fig = px.bar(
            wide.sort_values("Change_3Y", ascending=False),
            x="Label",
            y="Change_3Y",
            title=f"ESG Change ({int(wide['FirstYear'].iloc[0])} → {int(wide['LastYear'].iloc[0])})",
        )
        change_fig.update_layout(xaxis_title="", yaxis_title="Star change")
        st.plotly_chart(change_fig, use_container_width=True)

    # -----------------------
    # Table
    # -----------------------
    st.subheader("🧾 Data Table")
    show_cols = ["Year", "StockCode", "Company", "ESG_Stars", "FTSE4Good_Index", "FTSE4Good_Shariah"]
    show_cols = [c for c in show_cols if c in dsel.columns]
    st.dataframe(dsel[show_cols].sort_values(["Company", "Year"]), use_container_width=True)

    st.caption("Source: Bursa Malaysia PDFs of FTSE Russell ESG ratings (Main Market only).")


