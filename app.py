
import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Multi-Bank Analyzer - Phase 2", layout="wide")
st.title("🏦 Multi-Bank Financial Analyzer (ICICI, HDFC, SBI)")

uploaded_file = st.file_uploader("Upload your bank statement PDF", type=["pdf"])
pdf_password = st.text_input("PDF Password (if any)", type="password")

def extract_text(file, password=None):
    try:
        reader = PdfReader(file)
        if reader.is_encrypted:
            if password:
                reader.decrypt(password)
            else:
                st.warning("PDF is encrypted. Please provide password.")
                return ""
        return "".join([page.extract_text() for page in reader.pages])
    except Exception as e:
        st.error(f"Failed to extract text: {e}")
        return ""

def detect_bank(text):
    if "ICICI BANK" in text.upper():
        return "ICICI"
    elif "HDFC BANK" in text.upper():
        return "HDFC"
    elif "STATE BANK OF INDIA" in text.upper() or "SBI" in text.upper():
        return "SBI"
    else:
        return "UNKNOWN"

def parse_icici(text):
    pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+((?:\d{1,3},?)*\d+\.\d{2})?\s+((?:\d{1,3},?)*\d+\.\d{2})?\s+((?:\d{1,3},?)*\d+\.\d{2})")
    data = []
    for match in pattern.finditer(text):
        date, desc, credit, debit, balance = match.groups()
        try:
            data.append({
                "Date": datetime.strptime(date, "%d/%m/%Y"),
                "Description": desc.strip(),
                "Credit": float(credit.replace(',', '')) if credit else 0.0,
                "Debit": float(debit.replace(',', '')) if debit else 0.0,
                "Balance": float(balance.replace(',', '')) if balance else 0.0
            })
        except:
            continue
    return pd.DataFrame(data)

def fallback_parser(text):
    fallback_pattern = re.compile(
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<rest>.+?)(?=\n\d{2}/\d{2}/\d{4}|$)',
        re.DOTALL
    )
    entries = []
    for match in fallback_pattern.finditer(text):
        date_str = match.group("date")
        rest = match.group("rest").strip().replace('\n', ' ')
        date = datetime.strptime(date_str, "%d/%m/%Y")

        # Try to extract amounts from end of line
        amount_matches = re.findall(r'(\d{1,3}(?:,\d{3})*\.\d{2})', rest)
        credit = debit = 0.0
        if "CR" in rest.upper():
            credit = float(amount_matches[-1].replace(",", "")) if amount_matches else 0.0
        elif "DR" in rest.upper():
            debit = float(amount_matches[-1].replace(",", "")) if amount_matches else 0.0

        entries.append({
            "Date": date,
            "Description": rest,
            "Credit": credit,
            "Debit": debit,
            "Balance": 0.0
        })
    return pd.DataFrame(entries)

def classify_transactions(df):
    df["Category"] = "Others"
    df.loc[df["Description"].str.contains("SALARY|PAYROLL|HRMS", case=False, na=False), "Category"] = "Salary"
    df.loc[df["Description"].str.contains("EMI|ACH RETURN|BOUNCE", case=False, na=False), "Category"] = "EMI Bounce"
    df.loc[df["Description"].str.contains("UPI", case=False, na=False), "Category"] = "UPI"
    df.loc[(df["Credit"] > 100000) & (df["Description"].str.contains("CASH", case=False, na=False)), "Category"] = "Suspicious Cash Deposit"
    return df

if uploaded_file:
    text = extract_text(uploaded_file, pdf_password)
    if not text:
        st.stop()

    bank = detect_bank(text)
    st.info(f"Detected Bank: {bank}")

    if bank == "ICICI":
        df = parse_icici(text)
    else:
        df = fallback_parser(text)

    if not df.empty:
        df = classify_transactions(df)
        st.subheader("📋 Transactions")
        st.dataframe(df)

        st.subheader("📊 Summary by Category")
        summary = df.groupby("Category").agg({"Credit": "sum", "Debit": "sum"}).reset_index()
        st.dataframe(summary)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "parsed_statement.csv", "text/csv")
    else:
        st.error("⚠️ Unable to parse transactions from this statement.")
