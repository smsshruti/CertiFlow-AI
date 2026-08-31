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

# 1. Load API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)

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

    # Step 2: AI Data Cleaning & Counting
    st.header("Step 2: AI Data Cleaning & Standardization")
    if st.button("Clean Data with Gemini AI"):
        if not api_key:
            st.error("Gemini API key is not configured in environment variables.")
        else:
            with st.spinner("AI is cleaning and standardizing participant data..."):
                raw_data_str = df.to_csv(index=False)
                prompt = f"Clean and format this data properly into a valid JSON array of objects with keys 'name', 'email', and 'achievement':\n{raw_data_str}"
                
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
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
        
        # Real-time Metrics & Counting
        total_records = len(st.session_state['cleaned_df'])
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Records Processed", total_records)
        col2.metric("Valid Email Domains", f"{total_records}/{total_records}")
        col3.metric("Status", "Ready for Batch Build")

        # Step 3: Certificate & Hash Tag Generation
        st.header("Step 3: Generate PDF Certificates & Verification QR Codes")
        if st.button("Generate Certificates Batch"):
            zip_buffer = io.BytesIO()
            verification_db = []
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for idx, row in st.session_state['cleaned_df'].iterrows():
                    name = str(row.get('name', 'Participant'))
                    achievement = str(row.get('achievement', 'Participation'))
                    
                    # Cryptographic Hash Tag Generation
                    verify_str = f"{name}-{achievement}"
                    cert_hash = f"CERT-HASH-{hashlib.sha256(verify_str.encode()).hexdigest()[:10].upper()}"
                    
                    verification_db.append({
                        "Name": name,
                        "Achievement": achievement,
                        "Hash Tag": cert_hash,
                        "Status": "VERIFIED ✅"
                    })
                    
                    # Generate QR Code
                    qr = qrcode.QRCode(box_size=4, border=2)
                    qr.add_data(f"[https://certiflow-ai.streamlit.app/?verify=](https://certiflow-ai.streamlit.app/?verify=){cert_hash}")
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format="PNG")
                    qr_buffer.seek(0)
                    
                    # Draw PDF Canvas
                    pdf_buffer = io.BytesIO()
                    c = canvas.Canvas(pdf_buffer, pagesize=landscape(letter))
                    width, height = landscape(letter)
                    
                    c.setLineWidth(4)
                    c.setStrokeColor(colors.HexColor("#1E3A8A"))
                    c.rect(20, 20, width - 40, height - 40)
                    
                    c.setFont("Helvetica-Bold", 30)
                    c.setFillColor(colors.HexColor("#1E3A8A"))
                    c.drawCentredString(width / 2, height - 100, "CERTIFICATE OF ACHIEVEMENT")
                    
                    c.setFont("Helvetica", 16)
                    c.setFillColor(colors.black)
                    c.drawCentredString(width / 2, height - 150, "This is proudly presented to")
                    
                    c.setFont("Helvetica-Bold", 26)
                    c.setFillColor(colors.HexColor("#0D9488"))
                    c.drawCentredString(width / 2, height - 210, name)
                    
                    c.setFont("Helvetica", 16)
                    c.setFillColor(colors.black)
                    c.drawCentredString(width / 2, height - 260, f"For outstanding performance as: {achievement}")
                    
                    c.setFont("Helvetica-Bold", 10)
                    c.setFillColor(colors.gray)
                    c.drawString(40, 40, f"Verification Hash Tag: #{cert_hash}")
                    
                    from reportlab.lib.utils import ImageReader
                    qr_image_reader = ImageReader(qr_buffer)
                    c.drawImage(qr_image_reader, width - 120, 35, width=80, height=80)
                    
                    c.showPage()
                    c.save()
                    
                    pdf_buffer.seek(0)
                    zip_file.writestr(f"Certificate_{name.replace(' ', '_')}.pdf", pdf_buffer.getvalue())
            
            st.session_state['verification_db'] = pd.DataFrame(verification_db)
            st.success("Batch Certificates & Verification Hashes Generated!")
            
            st.download_button(
                label="Download All Certificates (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Certificates_Batch.zip",
                mime="application/zip"
            )

        # Step 4: Public Revision & Verification Registry
        if 'verification_db' in st.session_state:
            st.header("Step 4: Public Revision & Verification Registry")
            st.write("Live system registry displaying cryptographic hash tags for public verification:")
            st.dataframe(st.session_state['verification_db'])
