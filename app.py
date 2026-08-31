import streamlit as st
import pandas as pd
import json
import os
import io
import zipfile
import qrcode
import hashlib
from dotenv import load_dotenv
import google.generativeai as genai
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# 1. Load API Key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# 2. Connect to Gemini AI
client = None
if api_key:
    genai.configure(api_key=api_key)
    client = genai

st.set_page_config(page_title="CertiFlow AI", layout="wide")

st.title("CertiFlow AI - Automated Certificate Generation & Data Verification Pipeline")
st.write("Upload participant data, clean records with Gemini AI, auto-generate PDF certificates, and create QR codes for verification.")

# Step 1: File Upload
st.header("Step 1: Upload Participant Data")
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Raw Data Preview")
    st.dataframe(df)

    # Step 2: AI Cleaning
    st.header("Step 2: AI Data Cleaning & Standardization")
    if st.button("Clean Data with Gemini AI"):
        if not api_key:
            st.error("Gemini API key is not configured in environment variables.")
        else:
            with st.spinner("AI is cleaning and standardizing participant data..."):
                raw_data_str = df.to_csv(index=False)
                prompt = f"Clean and format this data properly into a valid JSON array of objects with keys 'name', 'email', and 'achievement':\n{raw_data_str}"
                
                try:
                    model = genai.GenerativeModel('gemini-3.6-flash')
                    response = model.generate_content(prompt)
                    cleaned_text = response.text.strip()
                    if cleaned_text.startswith("```json"):
                        cleaned_text = cleaned_text[7:-3].strip()
                    cleaned_json = json.loads(cleaned_text)
                    cleaned_df = pd.DataFrame(cleaned_json)
                    st.session_state['cleaned_df'] = cleaned_df
                    st.success("Data cleaned successfully!")
                except Exception as e:
                    st.error(f"Error during cleaning: {e}")

    if 'cleaned_df' in st.session_state:
        st.write("### Cleaned Data Preview")
        st.dataframe(st.session_state['cleaned_df'])
