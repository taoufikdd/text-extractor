import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import streamlit as st

# ==================== STREAMLIT UI ====================
st.set_page_config(page_title="Gmail Content Extractor", page_icon="📧", layout="wide")

st.title("📧 Gmail Content Extractor")
st.write("استخراج محتوى الإيميلات بنص صافي وتجميعها مع فاصل `__SEP__`")

# Sidebar Configuration
st.sidebar.header("🔑 Gmail Credentials")
email_user = st.sidebar.text_input("Gmail Address", value="", placeholder="example@gmail.com")
app_password = st.sidebar.text_input("App Password", type="password", placeholder="16-digit password")

st.sidebar.header("⚙️ Search Filters")
status_option = st.sidebar.selectbox("Email Status", ["UNREAD", "READ", "ALL"], index=0)
max_emails = st.sidebar.number_input("Max Emails to Fetch", min_value=1, max_value=100, value=5)
only_important = st.sidebar.checkbox("Only Important Emails", value=False)

keywords_input = st.sidebar.text_input("Keywords (comma separated)", value="reset password, County Expands")
keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]

use_date = st.sidebar.checkbox("Filter by Date Range", value=False)
start_date, end_date = None, None
if use_date:
    col1, col2 = st.sidebar.columns(2)
    start_d = col1.date_input("Start Date")
    end_d = col2.date_input("End Date")
    start_date = start_d.strftime("%Y/%m/%d")
    end_date = end_d.strftime("%Y/%m/%d")

# ==================== HELPER FUNCTIONS ====================
def clean_html_content(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def decode_mime_header(header_value):
    if not header_value:
        return ""
    decoded_list = decode_header(header_value)
    header_str = ""
    for decoded_string, encoding in decoded_list:
        if isinstance(decoded_string, bytes):
            header_str += decoded_string.decode(encoding or "utf-8", errors="ignore")
        else:
            header_str += str(decoded_string)
    return header_str

def build_gmail_query(keywords, status, important_only, start_date, end_date):
    query_parts = []
    if status == "UNREAD":
        query_parts.append("is:unread")
    elif status == "READ":
        query_parts.append("is:read")
        
    if important_only:
        query_parts.append("is:important")
        
    if start_date:
        query_parts.append(f"after:{start_date}")
    if end_date:
        query_parts.append(f"before:{end_date}")
        
    if keywords:
        kw_query = " OR ".join([f'"{kw}"' for kw in keywords])
        query_parts.append(f"({kw_query})")
        
    return " ".join(query_parts) if query_parts else "ALL"

def extract_gmail_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_user, app_password)
        mail.select("inbox")
        
        search_query = build_gmail_query(keywords, status_option, only_important, start_date, end_date)
        
        if search_query == "ALL":
            status, response = mail.search(None, "ALL")
        else:
            status, response = mail.search(None, f'X-GM-RAW "{search_query}"')
        
        if status != "OK" or not response[0]:
            st.warning("⚠️ No emails found matching your criteria.")
            return []

        email_ids = response[0].split()
        latest_email_ids = email_ids[-max_emails:][::-1]
        
        extracted_bodies = []
        for e_id in latest_email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    body_text = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body_text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                                    break
                            elif content_type == "text/html" and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    html_data = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                                    body_text = clean_html_content(html_data)
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            raw_data = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
                            if msg.get_content_type() == "text/html":
                                body_text = clean_html_content(raw_data)
                            else:
                                body_text = raw_data

                    if body_text.strip():
                        extracted_bodies.append(body_text.strip())

        mail.logout()
        return extracted_bodies

    except Exception as e:
        st.error(f"❌ Error connecting to Gmail: {e}")
        return []

# ==================== MAIN RUN BUTTON ====================
if st.button("🚀 Extract Emails", type="primary"):
    if not email_user or not app_password:
        st.error("Please provide both Email Address and App Password in the sidebar!")
    else:
        with st.spinner("Fetching emails..."):
            bodies = extract_gmail_emails()
            if bodies:
                st.success(f"Successfully extracted {len(bodies)} emails!")
                
                # تجميع جميع النصوص ومفروقة بـ __SEP__
                combined_text = "\n\n__SEP__\n\n".join(bodies)
                
                # إظهار الناتج فـ Text Area كبير فـ نفس الصفحة
                st.subheader("📄 Extracted Output:")
                st.text_area(
                    label="All extracted email contents separated by __SEP__",
                    value=combined_text,
                    height=450
                )
                
                # زِرّ لتنزيل الملف مباشرة
                st.download_button(
                    label="📥 Download Output File (.txt)",
                    data=combined_text,
                    file_name="extracted_emails.txt",
                    mime="text/plain"
                )
