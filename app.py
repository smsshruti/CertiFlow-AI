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
    client = genai.Client(api_key=api_key)

st.set_page_config(page_title="CertiFlow AI", layout="wide")

st.title("CertiFlow AI - Automated Certificate Generation & Data Verification Pipeline")
st.write("Upload participant data, clean records with Gemini AI, auto-generate PDF certificates, and create QR codes for verification.")
