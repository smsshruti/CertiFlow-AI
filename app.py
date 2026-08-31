import streamlit as st
import pandas as pd
import json
import os
import io
import zipfile
import qrcode
import hashlib
import re
from dotenv import load_dotenv
import google.generativeai as genai
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="CertiFlow AI",
    page_icon="📜",
    layout="wide"
)


# ============================================================
# 2. LOAD GEMINI API KEY
# ============================================================

# Local development: reads .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

# Streamlit deployment: reads Streamlit Secrets
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = None

if api_key:
    genai.configure(api_key=api_key)


# ============================================================
# 3. HEADER
# ============================================================

st.title("CertiFlow AI")

st.write(
    "AI-powered certificate generation and verification platform. "
    "Upload participant data, validate it with Gemini AI, review the "
    "records, generate certificates in bulk, and verify certificates "
    "using unique verification IDs."
)


# ============================================================
# 4. SESSION STATE
# ============================================================

if "verification_db" not in st.session_state:
    st.session_state["verification_db"] = {
        "A1B2C3D4E5F6": {
            "name": "Rahul Sharma",
            "achievement": "Winner",
            "email": "rahul@example.com"
        },
        "9876543210AB": {
            "name": "Priya Singh",
            "achievement": "Participant",
            "email": "priya@example.com"
        },
        "EF1234567890": {
            "name": "Aman Verma",
            "achievement": "Runner Up",
            "email": "aman@example.com"
        }
    }

if "cleaned_df" not in st.session_state:
    st.session_state["cleaned_df"] = None

if "validation_report" not in st.session_state:
    st.session_state["validation_report"] = None

if "review_approved" not in st.session_state:
    st.session_state["review_approved"] = False


# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================

def normalize_name(name):
    """Standardize participant name formatting."""
    if pd.isna(name):
        return ""

    name = str(name).strip()
    name = " ".join(name.split())

    return name.title()


def normalize_achievement(value):
    """Standardize common achievement labels."""

    if pd.isna(value):
        return "Participation"

    value = str(value).strip().lower()

    mapping = {
        "winner": "Winner",
        "1st": "Winner",
        "1st place": "Winner",
        "first": "Winner",
        "first place": "Winner",

        "runner up": "Runner Up",
        "runner-up": "Runner Up",
        "2nd": "Runner Up",
        "2nd place": "Runner Up",

        "participant": "Participant",
        "participation": "Participant",

        "3rd": "Third Place",
        "3rd place": "Third Place",
        "third": "Third Place",
        "third place": "Third Place"
    }

    return mapping.get(value, str(value).title())


def valid_email(email):
    """Basic email format check."""

    if pd.isna(email):
        return False

    email = str(email).strip()

    if not email:
        return False

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(re.match(pattern, email))


def generate_validation_report(df):
    """
    Perform deterministic checks on participant data.
    These checks complement the Gemini AI cleaning workflow.
    """

    report = {
        "total_records": len(df),
        "duplicate_records": 0,
        "missing_names": 0,
        "missing_emails": 0,
        "invalid_emails": 0,
        "missing_achievements": 0
    }

    if "name" in df.columns:

        report["missing_names"] = int(
            df["name"].isna().sum()
        )

        names = df["name"].fillna("").astype(str).str.strip()

        duplicate_mask = names.duplicated(
            keep=False
        ) & (names != "")

        report["duplicate_records"] = int(
            duplicate_mask.sum()
        )

    if "email" in df.columns:

        report["missing_emails"] = int(
            df["email"].isna().sum()
        )

        invalid_count = 0

        for email in df["email"]:

            if not valid_email(email):
                invalid_count += 1

        report["invalid_emails"] = invalid_count

    if "achievement" in df.columns:

        report["missing_achievements"] = int(
            df["achievement"].isna().sum()
        )

    return report


def clean_with_gemini(df):
    """Send participant data to Gemini for structured cleaning."""

    raw_data = df.to_csv(index=False)

    prompt = f"""
You are an expert data validation assistant for a certificate
management system.

Clean and standardize the participant CSV data below.

IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Return a JSON array of objects.
3. Every object must contain exactly these keys:
   "name", "email", "achievement"
4. Standardize participant names using normal capitalization.
5. Standardize achievement labels where possible.
6. Do NOT invent missing information.
7. Keep missing information as an empty string.
8. Preserve every legitimate participant.
9. Do not intentionally create duplicate participants.
10. Preserve the meaning of the original information.

Participant data:

{raw_data}
"""

    model = genai.GenerativeModel(
        "gemini-2.5-flash"
    )

    response = model.generate_content(prompt)

    cleaned_text = response.text.strip()

    # Remove Markdown code fences if Gemini returns them.
    if "```json" in cleaned_text:

        cleaned_text = (
            cleaned_text
            .split("```json", 1)[1]
            .split("```", 1)[0]
            .strip()
        )

    elif "```" in cleaned_text:

        cleaned_text = (
            cleaned_text
            .split("```", 1)[1]
            .split("```", 1)[0]
            .strip()
        )

    cleaned_json = json.loads(cleaned_text)

    return pd.DataFrame(cleaned_json)


def create_certificate_pdf(
    name,
    achievement,
    cert_hash
):
    """Create one PDF certificate."""

    # Create QR code
    qr = qrcode.QRCode(
        box_size=4,
        border=2
    )

    qr.add_data(
        f"Verification ID: {cert_hash}"
    )

    qr.make(fit=True)

    qr_img = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    qr_buffer = io.BytesIO()

    qr_img.save(
        qr_buffer,
        format="PNG"
    )

    qr_buffer.seek(0)

    # Create PDF
    pdf_buffer = io.BytesIO()

    c = canvas.Canvas(
        pdf_buffer,
        pagesize=landscape(letter)
    )

    width, height = landscape(letter)

    # Border
    c.setLineWidth(4)

    c.setStrokeColor(
        colors.HexColor("#1E3A8A")
    )

    c.rect(
        20,
        20,
        width - 40,
        height - 40
    )

    # Title
    c.setFont(
        "Helvetica-Bold",
        30
    )

    c.setFillColor(
        colors.HexColor("#1E3A8A")
    )

    c.drawCentredString(
        width / 2,
        height - 100,
        "CERTIFICATE OF ACHIEVEMENT"
    )

    # Subtitle
    c.setFont(
        "Helvetica",
        16
    )

    c.setFillColor(
        colors.black
    )

    c.drawCentredString(
        width / 2,
        height - 150,
        "This is proudly presented to"
    )

    # Participant name
    c.setFont(
        "Helvetica-Bold",
        26
    )

    c.setFillColor(
        colors.HexColor("#0D9488")
    )

    c.drawCentredString(
        width / 2,
        height - 210,
        name
    )

    # Achievement
    c.setFont(
        "Helvetica",
        16
    )

    c.setFillColor(
        colors.black
    )

    c.drawCentredString(
        width / 2,
        height - 260,
        f"For outstanding performance as: {achievement}"
    )

    # Verification ID
    c.setFont(
        "Helvetica-Oblique",
        10
    )

    c.setFillColor(
        colors.gray
    )

    c.drawString(
        40,
        40,
        f"Verification ID: {cert_hash}"
    )

    # QR code
    qr_image_reader = ImageReader(
        qr_buffer
    )

    c.drawImage(
        qr_image_reader,
        width - 120,
        35,
        width=80,
        height=80
    )

    c.showPage()
    c.save()

    pdf_buffer.seek(0)

    return pdf_buffer.getvalue()


# ============================================================
# STEP 1 — UPLOAD PARTICIPANT DATA
# ============================================================

st.header("Step 1 — Upload Participant Data")

uploaded_file = st.file_uploader(
    "Upload participant CSV",
    type=["csv"]
)


if uploaded_file is not None:

    try:

        df = pd.read_csv(uploaded_file)
        # Normalize CSV column names
        df.columns=[
            str(col).strip().lower()
            for col in df.columns
        ]

        st.write("### Raw Data Preview")

        st.dataframe(
            df,
            use_container_width=True
        )

        # Required columns
        required_columns = {
            "name",
            "email",
            "achievement"
        }

        missing_columns = (
            required_columns -
            set(df.columns)
        )

        if missing_columns:

            st.error(
                "Your CSV is missing these required columns: "
                + ", ".join(sorted(missing_columns))
            )

            st.stop()


        # ====================================================
        # STEP 2 — GEMINI AI CLEANING & VALIDATION
        # ====================================================

        st.header(
            "Step 2 — Gemini AI Data Cleaning & Validation"
        )

        st.write(
            "Gemini AI analyzes the participant information "
            "and helps standardize the records before certificates "
            "are generated."
        )


        if st.button(
            "🤖 Analyze & Clean Data with Gemini AI"
        ):

            if not api_key:

                st.error(
                    "Gemini API key is not configured. "
                    "Please check Streamlit Secrets."
                )

            else:

                with st.spinner(
                    "Gemini AI is analyzing participant data..."
                ):

                    try:

                        # Local validation report
                        report = generate_validation_report(df)

                        st.session_state[
                            "validation_report"
                        ] = report

                        # Gemini AI cleaning
                        cleaned_df = clean_with_gemini(df)

                        # Make sure expected columns exist
                        for column in [
                            "name",
                            "email",
                            "achievement"
                        ]:

                            if column not in cleaned_df.columns:

                                cleaned_df[column] = ""

                        cleaned_df = cleaned_df[
                            [
                                "name",
                                "email",
                                "achievement"
                            ]
                        ]

                        # Standardization
                        cleaned_df["name"] = (
                            cleaned_df["name"]
                            .apply(normalize_name)
                        )

                        cleaned_df["achievement"] = (
                            cleaned_df["achievement"]
                            .apply(normalize_achievement)
                        )

                        st.session_state[
                            "cleaned_df"
                        ] = cleaned_df

                        st.session_state[
                            "review_approved"
                        ] = False

                        st.success(
                            "Gemini AI analysis completed successfully!"
                        )

                    except Exception as e:

                        st.error(
                            f"Error during Gemini processing: {e}"
                        )


        # ====================================================
        # AI VALIDATION REPORT
        # ====================================================

        if st.session_state.get(
            "validation_report"
        ) is not None:

            report = st.session_state[
                "validation_report"
            ]

            st.subheader(
                "🤖 AI Validation Report"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Total Records",
                report["total_records"]
            )

            col2.metric(
                "Possible Duplicates",
                report["duplicate_records"]
            )

            missing_fields = (
                report["missing_names"]
                + report["missing_emails"]
                + report["missing_achievements"]
            )

            col3.metric(
                "Missing Fields",
                missing_fields
            )

            col4.metric(
                "Invalid Emails",
                report["invalid_emails"]
            )

            st.caption(
                "These checks help organizers identify "
                "participant-data issues before certificates "
                "are generated."
            )


        # ====================================================
        # CLEANED DATA + HUMAN REVIEW
        # ====================================================

        if st.session_state.get(
            "cleaned_df"
        ) is not None:

            st.header(
                "Step 3 — Human Review & Approval"
            )

            st.info(
                "Gemini provides cleaning suggestions, but "
                "the organizer reviews and approves the data "
                "before certificate generation."
            )

            edited_df = st.data_editor(
                st.session_state["cleaned_df"],
                use_container_width=True,
                num_rows="dynamic"
            )

            st.session_state[
                "cleaned_df"
            ] = edited_df


            if st.button(
                "✅ Approve Data & Continue"
            ):

                st.session_state[
                    "review_approved"
                ] = True

                st.success(
                    "Data approved by organizer. "
                    "Certificate generation is now enabled."
                )


        # ====================================================
        # STEP 4 — BULK CERTIFICATE GENERATION
        # ====================================================

        if st.session_state.get(
            "review_approved"
        ):

            st.header(
                "Step 4 — Generate PDF Certificates & QR Codes"
            )

            st.write(
                "Generate certificates in bulk with unique "
                "verification IDs and QR codes."
            )


            if st.button(
                "📜 Generate Certificates Batch"
            ):

                final_df = st.session_state[
                    "cleaned_df"
                ]

                zip_buffer = io.BytesIO()

                generated_records = []

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for idx, row in final_df.iterrows():

                        name = str(
                            row.get(
                                "name",
                                "Participant"
                            )
                        ).strip()

                        achievement = str(
                            row.get(
                                "achievement",
                                "Participation"
                            )
                        ).strip()

                        email = str(
                            row.get(
                                "email",
                                ""
                            )
                        ).strip()


                        if not name:
                            name = "Participant"

                        if not achievement:
                            achievement = "Participation"


                        # Create unique verification ID
                        unique_string = (
                            f"{name}-"
                            f"{achievement}-"
                            f"{email}-"
                            f"{idx}-"
                            f"{len(final_df)}"
                        )

                        cert_hash = (
                            hashlib.sha256(
                                unique_string.encode()
                            )
                            .hexdigest()[:12]
                            .upper()
                        )


                        # Store verification record
                        st.session_state[
                            "verification_db"
                        ][cert_hash] = {
                            "name": name,
                            "achievement": achievement,
                            "email": email
                        }


                        # Generate PDF
                        pdf_data = create_certificate_pdf(
                            name,
                            achievement,
                            cert_hash
                        )


                        safe_name = (
                            name
                            .replace(" ", "_")
                            .replace("/", "_")
                        )


                        zip_file.writestr(
                            f"Certificate_{safe_name}.pdf",
                            pdf_data
                        )


                        generated_records.append(
                            {
                                "Certificate ID": cert_hash,
                                "Participant": name,
                                "Achievement": achievement
                            }
                        )


                zip_buffer.seek(0)


                st.success(
                    f"🎉 {len(generated_records)} certificates generated successfully!"
                )


                st.download_button(
                    label="⬇️ Download All Certificates (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="Certificates_Batch.zip",
                    mime="application/zip"
                )


                st.subheader(
                    "Generated Certificate Verification IDs"
                )

                st.dataframe(
                    pd.DataFrame(generated_records),
                    use_container_width=True
                )
    except Exception as e:
        st.error(f"Error processing upload file:{e}")


# ============================================================
# STEP 5 — PUBLIC CERTIFICATE VERIFICATION
# ============================================================

st.divider()

st.header(
    "Step 5 — Public Certificate Verification Portal"
)

st.write(
    "Verify an issued certificate using its unique "
    "verification ID."
)


search_id = st.text_input(
    "Enter Verification ID",
    placeholder="Example: A1B2C3D4E5F6"
).strip().upper()


if st.button(
    "🔍 Verify Certificate"
):

    if search_id:

        verification_db = st.session_state.get(
            "verification_db",
            {}
        )

        if search_id in verification_db:

            record = verification_db[
                search_id
            ]

            st.success(
                "✅ VALID CERTIFICATE"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    f"**Issued To:** {record['name']}"
                )

                st.write(
                    f"**Achievement:** {record['achievement']}"
                )

            with col2:

                if record.get("email"):

                    st.write(
                        f"**Email:** {record['email']}"
                    )

                st.write(
                    f"**Certificate ID:** {search_id}"
                )

            st.info(
                "Certificate record found in the verification registry."
            )

        else:

            st.error(
                "❌ INVALID CERTIFICATE"
            )

            st.warning(
                "The Verification ID was not found in the registry."
            )

    else:

        st.warning(
            "Please enter a Verification ID."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CertiFlow AI • AI-assisted certificate generation, "
    "data validation and certificate verification"
)
