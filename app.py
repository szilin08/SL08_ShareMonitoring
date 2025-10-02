# app.py
import streamlit as st
st.set_page_config(page_title="LBS Bina Competitor Dashboard", layout="wide")

import stock_monitoring, financials, balance_sheet, cash_flow, overview

tabs = st.tabs(["Overview","Stock Monitoring", "Financials", "Balance Sheet","Cash Flow"])

with tabs[0]:
    overview.main()
with tabs[1]:
    stock_monitoring.main()
with tabs[2]:
    financials.main()
with tabs[3]:
    balance_sheet.main()
with tabs[4]:
    cash_flow.main()


