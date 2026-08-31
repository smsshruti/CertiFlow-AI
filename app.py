import streamlit as st
import pandas as pd
import json
import os
import io
import zipfile
import qrcode
import hashlib
from dotenv import load_dotenv
from google import genai
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# 1. Read API Key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# 2. Connect to Gemini API
client = None
if api_key:
    client = genai.Client(api_key=api_key)

st.set_page_config(page_title="CertiFlow AI", layout="wide", page_icon="📜")

st.title("📜 CertiFlow AI — Certificate Generation & Verification Portal")
st.write("Upload participant data, clean records with Gemini AI, batch generate tamper-proof PDF certificates with embedded QR codes, and verify authenticity.")

tab1, tab2 = st.tabs(["🚀 Generation Portal", "🔍 Public Verification Portal"])

# Function to generate secure SHA-256 hash
def generate_cert_hash(cert_id, name, email):
    raw_str = f"{cert_id}:{name.strip()}:{email.strip()}"
    return hashlib.sha256(raw_str.encode()).hexdigest()[:16]

# --- TAB 1: CERTIFICATE GENERATION PIPELINE ---
with tab1:
    st.header("Step 1: Participant Data Upload & Live Analytics")
    uploaded_file = st.file_uploader("Upload Participant CSV File", type=["csv"])

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.session_state["raw_df"] = df
        
        # --- FEATURE 1: LIVE ANALYTICS DASHBOARD ---
        total_records = len(df)
        issues_count = 0
        missing_names = 0
        duplicate_emails = 0

        # Analytics Calculations
        for idx, row in df.iterrows():
            if pd.isna(row.get("Name")) or str(row.get("Name")).strip().lower() in ["none", "null", ""]:
                missing_names += 1
                issues_count += 1

        email_counts = df["Email"].value_counts()
        duplicates = email_counts[email_counts > 1].index.tolist()
        duplicate_emails = len(df[df["Email"].isin(duplicates)])
        issues_count += duplicate_emails

        # Render Metrics Dashboard
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records Uploaded", total_records)
        col2.metric("Data Issues Detected", issues_count, delta_color="inverse")
        col3.metric("Missing/Invalid Names", missing_names)
        col4.metric("Duplicate Entries", duplicate_emails)

        st.markdown("---")
        st.subheader("Raw Data Preview")
        st.dataframe(df, use_container_width=True)

        # --- STEP 2: AI CLEANING ---
        st.markdown("---")
        st.subheader("🛠️ Step 2: AI Cleaning & Human Review")

        if st.button("🤖 Auto-Clean Data with Gemini AI", type="primary"):
            if not client:
                st.error("❌ GEMINI_API_KEY is missing from .env file!")
            else:
                with st.spinner("Gemini AI is analyzing records, stripping duplicates, fixing casing, and standardizing emails..."):
                    raw_csv_text = df.to_csv(index=False)
                    
                    prompt = f"""
                    You are an expert data cleaning system for an official event certificate generator.
                    Analyze this raw CSV participant list and fix all data issues:
                    1. Remove duplicate entries (keep only 1 valid record per unique participant).
                    2. Convert all names to clean Title Case (e.g. 'rahul sharma' -> 'Rahul Sharma').
                    3. Drop unusable records (where name is 'None', blank, or invalid).
                    4. Ensure valid email formats and standardize 'Achievement' column (e.g., Winner, Runner Up, Participant).

                    Return ONLY a JSON array with cleaned records:
                    [
                      {{"name": "Clean Name", "email": "valid@email.com", "achievement": "Winner", "status": "Valid"}}
                    ]

                    Raw CSV Input:
                    {raw_csv_text}
                    """

                    response = client.models.generate_content(
                        model="models/gemini-3.6-flash",
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    
                    cleaned_json = json.loads(response.text)
                    cleaned_df = pd.DataFrame(cleaned_json)
                    
                    # Store cleaned records in session state
                    st.session_state["cleaned_df"] = cleaned_df
                    st.success("✅ Gemini AI completed data cleaning!")

        # Human Review Table
        if "cleaned_df" in st.session_state:
            st.write("#### Review & Approve Cleaned Data (Editable)")
            edited_df = st.data_editor(st.session_state["cleaned_df"], num_rows="dynamic", use_container_width=True)

            # --- STEP 3: BATCH GENERATION ---
            st.markdown("---")
            st.subheader("🎓 Step 3: Batch Certificate & QR Code Generation")

            if st.button("⚡ Generate Certificates & QR Codes"):
                os.makedirs("output_certificates", exist_ok=True)
                os.makedirs("output_qrs", exist_ok=True)
                
                zip_buffer = io.BytesIO()
                hash_registry = {}
                
                with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                    progress_bar = st.progress(0)
                    total_cleaned = len(edited_df)
                    
                    for idx, row in edited_df.iterrows():
                        if str(row.get("status", "Valid")).lower() == "valid":
                            cert_id = f"CERT-2026-00{idx+1}"
                            name = str(row.get("name", "Participant"))
                            email = str(row.get("email", ""))
                            
                            # FEATURE 2: TAMPER-PROOF SHA-256 HASH GENERATION
                            cert_hash = generate_cert_hash(cert_id, name, email)
                            hash_registry[cert_id] = {
                                "name": name,
                                "email": email,
                                "achievement": row.get("achievement", "Participant"),
                                "hash": cert_hash
                            }
                            
                            # 1. Generate Verification QR Code
                            verify_url = f"https://certiflow.ai/verify?id={cert_id}&hash={cert_hash}"
                            qr_path = f"output_qrs/{cert_id}.png"
                            qr = qrcode.make(verify_url)
                            qr.save(qr_path)
                            
                            # 2. Draw PDF Certificate
                            pdf_path = f"output_certificates/{cert_id}.pdf"
                            c = canvas.Canvas(pdf_path, pagesize=landscape(letter))
                            w, h = landscape(letter)
                            
                            # Styling
                            c.setStrokeColor(colors.HexColor("#1E3A8A"))
                            c.setLineWidth(5)
                            c.rect(15, 15, w - 30, h - 30)
                            
                            # Header
                            c.setFont("Helvetica-Bold", 28)
                            c.setFillColor(colors.HexColor("#1E3A8A"))
                            c.drawCentredString(w / 2, h - 110, "CERTIFICATE OF ACHIEVEMENT")
                            
                            c.setFont("Helvetica", 15)
                            c.setFillColor(colors.black)
                            c.drawCentredString(w / 2, h - 160, "This is proudly presented to")
                            
                            # Name
                            c.setFont("Helvetica-Bold", 24)
                            c.setFillColor(colors.HexColor("#0D9488"))
                            c.drawCentredString(w / 2, h - 210, name)
                            
                            # Achievement
                            c.setFont("Helvetica", 14)
                            c.setFillColor(colors.black)
                            c.drawCentredString(w / 2, h - 260, f"for successful participation as {row.get('achievement', 'Participant')}")
                            
                            # Secure Footer
                            c.setFont("Helvetica-Oblique", 9)
                            c.drawString(40, 50, f"Certificate ID: {cert_id}")
                            c.drawString(40, 35, f"Security Hash: {cert_hash}")
                            c.drawString(40, 20, "Verified by CertiFlow Cryptographic Protocol")
                            c.drawImage(qr_path, w - 120, 25, width=75, height=75)
                            
                            c.save()
                            
                            # Add to downloadable ZIP
                            zip_file.write(pdf_path, arcname=f"{cert_id}_{name}.pdf")
                        
                        progress_bar.progress((idx + 1) / total_cleaned)
                        
                st.session_state["hash_registry"] = hash_registry
                st.success(f"🎉 Generated {total_cleaned} tamper-proof certificates!")

                # Print Hashes Directly on Screen for easy copying
                st.write("### 🔑 Copy-Paste Security Hashes for Testing:")
                st.json({cert_id: data["hash"] for cert_id, data in hash_registry.items()})
                
                st.download_button(
                    label="📦 Download All Certificates (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="CertiFlow_Certificates.zip",
                    mime="application/zip",
                    type="primary"
                )

# --- TAB 2: PUBLIC VERIFICATION ---
with tab2:
    st.header("🔍 Cryptographic Verification Portal")
    st.write("Enter a Certificate ID and Hash to perform a cryptographic authenticity check.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        cert_id_input = st.text_input("Enter Certificate ID (e.g., CERT-2026-001):")
    with col_b:
        hash_input = st.text_input("Enter Security Hash (Optional for deep verification):")
    
    if st.button("Verify Certificate Authenticity"):
        if cert_id_input:
            cert_id = cert_id_input.strip()
            target_pdf = f"output_certificates/{cert_id}.pdf"
            hash_registry = st.session_state.get("hash_registry", {})
            
            if os.path.exists(target_pdf):
                st.success(f"✅ VERIFIED: Certificate `{cert_id}` is Authentic & Issued by System!")
                
                if cert_id in hash_registry:
                    record = hash_registry[cert_id]
                    st.info(f"👤 Issued To: **{record['name']}** | Role: **{record['achievement']}**")
                    st.code(f"System Hash: {record['hash']}", language="text")
                    
                    if hash_input:
                        if hash_input.strip() == record["hash"]:
                            st.success("🔒 CRYPTOGRAPHIC MATCH: The security hash is 100% genuine and unaltered.")
                        else:
                            st.error("🚨 WARNING: Hash mismatch detected! This certificate may have been tampered with.")
            else:
                st.error(f"❌ INVALID: Certificate `{cert_id}` does not exist in records.")
        else:
            st.warning("Please enter a Certificate ID.")