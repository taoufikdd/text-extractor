import streamlit as st
import re

st.set_page_config(layout="wide", page_title="SMTP Extractor & Scan Matcher")

# Custom Dark Theme Styling
st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; color: #d4d4d4; }
    div[data-baseweb="textarea"] textarea {
        background-color: #252526 !important;
        color: #d4d4d4 !important;
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 13px !important;
        border: 1px solid #3c3c3c !important;
    }
    label p { font-weight: bold !important; color: #61afef !important; font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ SMTP Extractor & Scan Matcher")

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

col1, col2 = st.columns(2)

with col1:
    all_smtps = st.text_area(
        "1. ALL_SMTPS (PASTE RAW SMTPS)", 
        height=320, 
        placeholder="Paste All_smtps list here...",
        key="input_smtps"
    )
    good_scan = st.text_area(
        "3. GOOD_SCAN (PASTE SCANNED EMAILS/LIST)", 
        height=320, 
        placeholder="Paste Good_scan emails here...",
        key="input_scan"
    )

# Extract Logic
extracted_emails = []
smtp_map = {}

if all_smtps and all_smtps.strip():
    for line in all_smtps.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        matches = re.findall(EMAIL_REGEX, line_clean)
        for email in matches:
            email_lower = email.lower()
            if email_lower not in smtp_map:
                smtp_map[email_lower] = line_clean
            if email_lower not in extracted_emails:
                extracted_emails.append(email_lower)

# Match Logic
matched_smtps = []
if good_scan and good_scan.strip() and smtp_map:
    scan_matches = re.findall(EMAIL_REGEX, good_scan)
    seen_lines = set()
    for scan_email in scan_matches:
        em_lower = scan_email.lower()
        if em_lower in smtp_map:
            full_line = smtp_map[em_lower]
            if full_line not in seen_lines:
                seen_lines.add(full_line)
                matched_smtps.append(full_line)

# Output Display (Without blocking keys)
with col2:
    extracted_text = "\n".join(extracted_emails)
    st.text_area(
        f"2. EXTRACT_EMAIL (EXTRACTED: {len(extracted_emails)})", 
        value=extracted_text, 
        height=320
    )
    
    matched_text = "\n".join(matched_smtps)
    st.text_area(
        f"4. TEST_ALL (MATCHED: {len(matched_smtps)})", 
        value=matched_text, 
        height=320
    )
