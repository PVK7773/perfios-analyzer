
import streamlit as st
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import tempfile
import pandas as pd
import re
from datetime import datetime
import os

st.set_page_config(page_title="OCR Bank Statement Analyzer", layout="wide")
st.title("📄 OCR Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload scanned bank statement (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"])
ocr_lang = st.selectbox("OCR Language", ["eng"])
min_confidence = st.slider("Minimum OCR confidence", 0, 100, 70)

def extract_text_from_image(image):
    return pytesseract.image_to_string(image, lang=ocr_lang)

def convert_pdf_to_images(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_file.read())
        tmp_pdf_path = tmp_pdf.name
    return convert_from_path(tmp_pdf_path, dpi=300)

def parse_transactions(text):
    lines = text.splitlines()
    transactions = []
    buffer = []

    for line in lines:
        line = line.strip()
        if re.match(r"\d{2}/\d{2}/\d{2,4}", line):
            if buffer:
                transactions.append(" ".join(buffer))
                buffer = []
        buffer.append(line)
    if buffer:
        transactions.append(" ".join(buffer))

    data = []
    for entry in transactions:
        try:
            date_match = re.search(r"(\d{2}/\d{2}/\d{2,4})", entry)
            date = datetime.strptime(date_match.group(1), "%d/%m/%y")
            amounts = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", entry)
            amount = float(amounts[-2].replace(",", "")) if len(amounts) >= 2 else 0.0
            balance = float(amounts[-1].replace(",", "")) if len(amounts) >= 2 else 0.0
            credit = amount if "CR" in entry.upper() or "CREDIT" in entry.upper() else 0.0
            debit = amount if credit == 0 else 0.0
            desc = re.sub(r"^\d{2}/\d{2}/\d{2,4}", "", entry).strip()
            desc = re.sub(r"\d{1,3}(?:,\d{3})*\.\d{2}.*$", "", desc).strip()
            data.append({
                "Date": date,
                "Description": desc,
                "Credit": credit,
                "Debit": debit,
                "Balance": balance
            })
        except:
            continue

    return pd.DataFrame(data)

if uploaded_file:
    st.info("Extracting OCR text...")
    if uploaded_file.type == "application/pdf":
        images = convert_pdf_to_images(uploaded_file)
    else:
        image = Image.open(uploaded_file)
        images = [image]

    full_text = ""
    for img in images:
        full_text += extract_text_from_image(img)

    df = parse_transactions(full_text)

    if not df.empty:
        st.success("✅ Transactions extracted!")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "transactions.csv", "text/csv")
    else:
        st.error("❌ No transactions could be parsed. Try uploading a clearer image.")
