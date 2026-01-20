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
    st.title("🌿 ESG Comparison (FTSE Russell via Bursa PDFs)")

    df = load_esg_table()
    if df.empty:
        st.error("CSV is empty or not found.")
        return

    # -----------------------
    # Company selection
    # -----------------------
    all_labels = sorted(df["Label"].unique().tolist())
    selected = st.multiselect(
        "Select developers to compare",
        all_labels,
        default=all_labels,
    )

    if not selected:
        st.warning("Select at least one developer.")
        return

    dsel = df[df["Label"].isin(selected)].copy()

    st.divider()

    # -----------------------
    # 1) SIDE-BY-SIDE BAR CHART (ORDERED BY LATEST YEAR, ASC)
    # -----------------------
    latest_year = dsel["Year"].max()

    st.subheader(f"📊 ESG Stars by Year (Ordered by {latest_year})")

    # Order companies by latest year ESG stars (ascending)
    order_df = (
        dsel[dsel["Year"] == latest_year]
        .sort_values("ESG_Stars", ascending=True)
    )
    company_order = order_df["Label"].tolist()

    bar_fig = px.bar(
        dsel,
        x="Label",
        y="ESG_Stars",
        color="Year",
        barmode="group",
        category_orders={"Label": company_order},
        title=f"ESG Stars Comparison Across Years (Ordered by {latest_year})",
    )
    bar_fig.update_layout(
        xaxis_title="",
        yaxis_title="ESG Stars",
        legend_title="Year",
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    # -----------------------
    # 2) YoY MOVEMENT TABLES
    # -----------------------
    st.subheader("🔁 ESG Stars YoY Movement")

    prev_year = latest_year - 1

    latest = dsel[dsel["Year"] == latest_year][
        ["StockCode", "Company", "ESG_Stars"]
    ].rename(columns={"ESG_Stars": "ESG_Latest"})

    prev = dsel[dsel["Year"] == prev_year][
        ["StockCode", "ESG_Stars"]
    ].rename(columns={"ESG_Stars": "ESG_Previous"})

    yoy = latest.merge(prev, on="StockCode", how="inner")
    yoy["YoY_Change"] = yoy["ESG_Latest"] - yoy["ESG_Previous"]

    increased = yoy[yoy["YoY_Change"] > 0][
        ["Company", "ESG_Previous", "ESG_Latest", "YoY_Change"]
    ]
    constant = yoy[yoy["YoY_Change"] == 0][
        ["Company", "ESG_Previous", "ESG_Latest", "YoY_Change"]
    ]
    decreased = yoy[yoy["YoY_Change"] < 0][
        ["Company", "ESG_Previous", "ESG_Latest", "YoY_Change"]
    ]

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"### ⬆️ Increased ({prev_year} → {latest_year})")
        st.dataframe(increased, use_container_width=True)

    with c2:
        st.markdown(f"### ➖ Constant ({prev_year} → {latest_year})")
        st.dataframe(constant, use_container_width=True)

    with c3:
        st.markdown(f"### ⬇️ Decreased ({prev_year} → {latest_year})")
        st.dataframe(decreased, use_container_width=True)

    st.caption(
        "Source: FTSE Russell ESG Ratings via Bursa Malaysia (Main Market). "
        "YoY comparison is based on latest available year vs previous year."
    )




