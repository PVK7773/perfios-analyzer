
import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from datetime import datetime

st.set_page_config(page_title="Bank Statement Analyzer", layout="wide")
st.title("🏦 Ultra-Loose Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload your bank statement PDF", type=["pdf"])
pdf_password = st.text_input("PDF Password (if any)", type="password")

def extract_text(file, password=None):
    try:
        reader = PdfReader(file)
        if reader.is_encrypted:
            if password:
                reader.decrypt(password)
            else:
                st.warning("PDF is encrypted. Please provide a password.")
                return ""
        return "".join([page.extract_text() for page in reader.pages])
    except Exception as e:
        st.error(f"Failed to extract text: {e}")
        return ""

def ultra_loose_parser(text):
    pattern = re.compile(
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<desc>.*?)(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})(?P<type>CR|DR)?\s+(?P<balance>\d{1,3}(?:,\d{3})*\.\d{2})',
        re.DOTALL
    )
    results = []
    for match in pattern.finditer(text):
        try:
            date = datetime.strptime(match.group("date"), "%d/%m/%Y")
            desc = match.group("desc").strip().replace("\n", " ")
            amount = float(match.group("amount").replace(",", ""))
            tr_type = match.group("type") or ""
            credit = amount if tr_type == "CR" else 0.0
            debit = amount if tr_type == "DR" else 0.0
            balance = float(match.group("balance").replace(",", ""))

            results.append({
                "Date": date,
                "Description": desc,
                "Credit": credit,
                "Debit": debit,
                "Balance": balance
            })
        except:
            continue
    return pd.DataFrame(results)

if uploaded_file:
    text = extract_text(uploaded_file, pdf_password)
    if not text:
        st.stop()

    df = ultra_loose_parser(text)

    if not df.empty:
        st.success("✅ Transactions parsed successfully.")
        st.dataframe(df)

        st.subheader("📊 Summary")
        st.dataframe(df.groupby(df["Date"].dt.to_period("M")).agg({
            "Credit": "sum",
            "Debit": "sum"
        }).rename_axis("Month").reset_index())

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "parsed_statement.csv", "text/csv")
    else:
        st.error("⚠️ Unable to parse transactions from this statement.")
