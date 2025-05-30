import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from io import BytesIO
from fpdf import FPDF
from datetime import datetime

st.set_page_config(page_title="Multi-Bank Statement Analyzer", layout="wide")
st.title("🏦 Multi-Bank Statement Analyzer (ICICI, HDFC, SBI)")

uploaded_file = st.file_uploader("Upload your bank statement PDF", type=["pdf"])

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

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
    pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+((?:\d{1,3},?)+\.\d{2})?\s+((?:\d{1,3},?)+\.\d{2})?\s+((?:\d{1,3},?)+\.\d{2})")
    transactions = []
    for match in pattern.finditer(text):
        date, desc, credit, debit, balance = match.groups()
        transactions.append({
            "Date": datetime.strptime(date, "%d/%m/%Y"),
            "Description": desc.strip(),
            "Credit": float(credit.replace(",", "")) if credit else 0.0,
            "Debit": float(debit.replace(",", "")) if debit else 0.0,
            "Balance": float(balance.replace(",", "")) if balance else 0.0
        })
    return pd.DataFrame(transactions)

def parse_generic(text):
    # Basic fallback parser
    pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+CR|DR\s+((?:\d{1,3},?)+\.\d{2})")
    transactions = []
    for match in pattern.finditer(text):
        date, desc, amt = match.groups()
        transactions.append({
            "Date": datetime.strptime(date, "%d/%m/%Y"),
            "Description": desc.strip(),
            "Credit": float(amt.replace(",", "")) if "CR" in text else 0.0,
            "Debit": float(amt.replace(",", "")) if "DR" in text else 0.0,
            "Balance": 0.0
        })
    return pd.DataFrame(transactions)

def generate_summary(df):
    df["Month"] = df["Date"].dt.to_period("M")
    summary = df.groupby("Month").agg({
        "Credit": "sum",
        "Debit": "sum",
        "Balance": "mean"
    }).rename(columns={"Balance": "Average Balance"})
    return summary

def detect_salary(df):
    return df[df["Description"].str.contains("SALARY|PAYROLL|HRMS", case=False, na=False)]

def detect_emi_bounces(df):
    return df[df["Description"].str.contains("EMI|ACH RETURN|BOUNCE", case=False, na=False)]

def detect_cash(df):
    return df[(df["Credit"] > 100000) & (df["Description"].str.contains("CASH", case=False, na=False))]

if uploaded_file:
    raw_text = extract_text_from_pdf(uploaded_file)
    bank_type = detect_bank(raw_text)
    st.info(f"Detected Bank Type: {bank_type}")

    if bank_type == "ICICI":
        df = parse_icici(raw_text)
    else:
        df = parse_generic(raw_text)

    if not df.empty:
        st.subheader("📋 Extracted Transactions")
        st.dataframe(df)

        st.subheader("📈 Monthly Summary")
        summary = generate_summary(df)
        st.dataframe(summary)

        st.subheader("💼 Salary Credits")
        st.dataframe(detect_salary(df))

        st.subheader("⚠️ EMI Bounces")
        st.dataframe(detect_emi_bounces(df))

        st.subheader("🚨 Suspicious Cash Deposits")
        st.dataframe(detect_cash(df))

        st.success("✅ Analysis completed.")
    else:
        st.warning("Unable to parse transactions from this statement.")
