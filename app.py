import pandas as pd
import streamlit as st

uploaded_file = st.file_uploader("Upload participant data (CSV)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
else:
    df = pd.read_csv("sample_data.csv")
    st.info("💡 Showing pre-loaded sample data. Upload a custom CSV to override!")