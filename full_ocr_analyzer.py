
import streamlit as st
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import tempfile
import pandas as pd
import re
from datetime import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
import os

st.set_page_config(page_title="📊 Full Bank Statement Analyzer", layout="wide")
st.title("🏦 Full OCR Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload scanned bank statement (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"])
ocr_lang = st.selectbox("OCR Language", ["eng"])
min_confidence = st.slider("Minimum OCR confidence", 0, 100, 70)

# OCR Helper
def extract_text_from_image(image):
    return pytesseract.image_to_string(image, lang=ocr_lang)

# PDF to image converter
def convert_pdf_to_images(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_file.read())
        tmp_pdf_path = tmp_pdf.name
    return convert_from_path(tmp_pdf_path, dpi=300)

# Transaction Parser
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

# Fraud Detection
def flag_anomalies(df):
    suspicious = df[
        (df["Description"].str.contains("cash", case=False)) & (df["Credit"] > 10000)
        | (df["Description"].str.contains("EMI|Bounce|Late", case=False))
    ]
    return suspicious

# PDF Exporter
def export_pdf(df, suspicious_df, summary_img):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Bank Statement Summary Report", ln=True, align="C")
    pdf.ln(10)
    pdf.cell(200, 10, txt="Transaction Summary", ln=True)
    for i in range(min(10, len(df))):
        row = df.iloc[i]
        pdf.cell(200, 10, txt=f"{row['Date'].strftime('%d-%b-%y')} | {row['Description'][:50]} | +{row['Credit']} / -{row['Debit']}", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt="⚠️ Suspicious Transactions", ln=True)
    for i in range(min(5, len(suspicious_df))):
        row = suspicious_df.iloc[i]
        pdf.cell(200, 10, txt=f"{row['Date'].strftime('%d-%b-%y')} | {row['Description'][:50]} | +{row['Credit']} / -{row['Debit']}", ln=True)
    pdf.image(summary_img, x=10, y=None, w=180)
    out_path = "/mnt/data/statement_summary.pdf"
    pdf.output(out_path)
    return out_path

if uploaded_file:
    st.info("🔄 Processing OCR... please wait.")
    if uploaded_file.type == "application/pdf":
        images = convert_pdf_to_images(uploaded_file)
    else:
        image = Image.open(uploaded_file)
        images = [image]

    text = ""
    for img in images:
        text += extract_text_from_image(img)

    df = parse_transactions(text)

    if not df.empty:
        df["Month"] = df["Date"].dt.to_period("M")
        st.success("✅ Transactions parsed successfully!")
        st.dataframe(df)

        st.subheader("📊 Cashflow Summary")
        summary = df.groupby("Month").agg({"Credit": "sum", "Debit": "sum"})
        st.bar_chart(summary)

        avg_bal = df.groupby("Month")["Balance"].mean().reset_index().rename(columns={"Balance": "Average Balance"})
        st.line_chart(avg_bal.set_index("Month"))

        st.subheader("⚠️ Fraud/Anomaly Detection")
        suspicious = flag_anomalies(df)
        st.dataframe(suspicious)

        fig, ax = plt.subplots()
        summary.plot(kind="bar", ax=ax)
        plt.title("Monthly Inflow vs Outflow")
        plt.tight_layout()
        chart_img_path = "/mnt/data/chart.png"
        fig.savefig(chart_img_path)

        pdf_file = export_pdf(df, suspicious, chart_img_path)
        with open(pdf_file, "rb") as f:
            st.download_button("📥 Download PDF Summary", f, file_name="bank_summary.pdf", mime="application/pdf")

    else:
        st.error("❌ Unable to parse any transaction. Try uploading a clearer image.")
