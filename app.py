import streamlit as st
import pandas as pd
import re
from io import BytesIO
from PyPDF2 import PdfReader
from fpdf import FPDF

st.set_page_config(page_title="Perfios-Like Bank Analyzer", layout="wide")
st.title("🏦 Perfios-Like Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload a PDF bank statement", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    text = "".join([page.extract_text() for page in reader.pages])

    pattern = re.compile(
        r"(\d{2}/\d{2}/\d{2})\s+([A-Z0-9\-\.\@\s]+?)\s+(\d{2}/\d{2}/\d{2})\s+((?:\d{1,3},?)+\.\d{2})?\s*((?:\d{1,3},?)+\.\d{2})?\s+((?:\d{1,3},?)+\.\d{2})"
    )

    transactions = []
    for match in pattern.finditer(text):
        date, desc, val_date, wd, dp, bal = match.groups()
        transactions.append({
            "Date": date,
            "Description": desc.strip(),
            "Value Date": val_date,
            "Withdrawal Amt": float(wd.replace(',', '')) if wd else 0.0,
            "Deposit Amt": float(dp.replace(',', '')) if dp else 0.0,
            "Closing Balance": float(bal.replace(',', ''))
        })

    df = pd.DataFrame(transactions)
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%y")
    df["Month"] = df["Date"].dt.to_period("M")

    st.subheader("📊 Raw Transactions")
    st.dataframe(df, use_container_width=True)

    st.subheader("📌 Key Metrics")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Deposits", f"₹{df['Deposit Amt'].sum():,.2f}")
    col2.metric("Total Withdrawals", f"₹{df['Withdrawal Amt'].sum():,.2f}")
    col3.metric("Average Balance", f"₹{df['Closing Balance'].mean():,.2f}")

    salary_keywords = r"\b(SALARY|PAYROLL|HRMS|SAL|EMPLOYER)\b"
    emi_keywords = r"\b(EMI|BOUNCE|RETURN|ACH D-.*RETURN|REJECTED|CHARGES|FAIL)\b"

    salary_df = df[df["Description"].str.contains(salary_keywords, case=False, na=False)]
    emi_df = df[df["Description"].str.contains(emi_keywords, case=False, na=False)]

    st.subheader("💼 Salary Credits")
    st.write(salary_df if not salary_df.empty else "No salary credits detected.")

    st.subheader("⚠️ EMI Bounce / Return Entries")
    st.write(emi_df if not emi_df.empty else "No EMI bounce or return entries found.")

    st.subheader("📈 Monthly Summary")
    monthly_summary = df.groupby("Month")[["Deposit Amt", "Withdrawal Amt", "Closing Balance"]].agg({
        "Deposit Amt": "sum",
        "Withdrawal Amt": "sum",
        "Closing Balance": "mean"
    }).rename(columns={"Closing Balance": "Avg Balance"})
    st.dataframe(monthly_summary)

    st.subheader("🔍 Fraud Detection")
    upi_df = df[df["Description"].str.contains("UPI", case=False, na=False)]
    upi_freq = upi_df.groupby(df["Date"].dt.date).size().reset_index(name="UPI Txn Count")
    flagged_days = upi_freq[upi_freq["UPI Txn Count"] > 5]
    if not flagged_days.empty:
        st.warning("High UPI usage (>5/day) detected on:")
        st.dataframe(flagged_days)
    else:
        st.success("✅ No high-frequency UPI activity detected.")

    st.subheader("🚨 Suspicious Cash Deposits")
    suspicious_deposits = df[(df['Deposit Amt'] > 100000) & (df['Description'].str.contains("CASH", case=False, na=False))]
    if not suspicious_deposits.empty:
        st.warning("Large cash deposits detected:")
        st.dataframe(suspicious_deposits)
    else:
        st.success("✅ No large cash deposits detected.")

    st.subheader("📤 Export Options")

    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8')

    csv = convert_df(df)
    st.download_button(
        label="Download Transactions as CSV",
        data=csv,
        file_name='bank_statement_analysis.csv',
        mime='text/csv',
    )

    def generate_pdf():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Bank Statement Analysis Report", ln=1, align='C')
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Total Deposits: ₹{df['Deposit Amt'].sum():,.2f}", ln=1)
        pdf.cell(200, 10, txt=f"Total Withdrawals: ₹{df['Withdrawal Amt'].sum():,.2f}", ln=1)
        pdf.cell(200, 10, txt=f"Average Balance: ₹{df['Closing Balance'].mean():,.2f}", ln=1)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Salary Credits: {len(salary_df)}", ln=1)
        pdf.cell(200, 10, txt=f"EMI Bounces: {len(emi_df)}", ln=1)
        pdf.cell(200, 10, txt=f"High-Frequency UPI Days: {len(flagged_days)}", ln=1)
        pdf.cell(200, 10, txt=f"Suspicious Cash Deposits: {len(suspicious_deposits)}", ln=1)

        output = BytesIO()
        pdf.output(output)
        return output.getvalue()

    pdf_report = generate_pdf()
    st.download_button(
        label="Download Summary PDF",
        data=pdf_report,
        file_name="Bank_Statement_Summary.pdf",
        mime="application/pdf"
    )

    st.success("✅ Analysis complete.")
