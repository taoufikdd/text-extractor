import email
from email.utils import parseaddr
import imaplib
import re
import streamlit as st

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(
    page_title="Gmail Extractor & SMTP Matcher",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Gmail Extractor & SMTP Matcher")
st.write("Extract sender emails via IMAP and match them directly with your SMTP list.")

GMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@gmail\.com$", re.IGNORECASE
)

# ==========================================
# 2. IMAP Sender Extractor Function
# ==========================================
def fetch_senders_from_inbox(user_email, app_password, status_placeholder, progress_bar):
    sender_emails = set()

    try:
        status_placeholder.info(f"Connecting to IMAP for {user_email}...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        clean_pass = app_password.replace(" ", "")
        mail.login(user_email, clean_pass)

        mail.select("inbox")
        status, messages = mail.search(None, "ALL")

        mail_ids = messages[0].split()
        total_msgs = len(mail_ids)

        if total_msgs == 0:
            status_placeholder.warning("No messages found in Inbox.")
            mail.logout()
            return sender_emails

        status_placeholder.info(f"Found {total_msgs} messages. Extracting senders...")

        batch_size = 100
        for i in range(0, total_msgs, batch_size):
            batch_ids = mail_ids[i : i + batch_size]
            batch_str = b",".join(batch_ids)

            _, msg_data = mail.fetch(
                batch_str, "(BODY.PEEK[HEADER.FIELDS (FROM)])"
            )

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    try:
                        raw_header = response_part[1].decode("utf-8", errors="ignore")
                        msg = email.message_from_string(raw_header)
                        from_header = msg.get("From", "")

                        real_name, email_address = parseaddr(from_header)
                        email_address = email_address.strip().lower()

                        if GMAIL_REGEX.match(email_address):
                            sender_emails.add(email_address)
                    except Exception:
                        pass

            processed_count = min(i + batch_size, total_msgs)
            progress_bar.progress(processed_count / total_msgs)
            status_placeholder.info(
                f"Processed: {processed_count}/{total_msgs} | Unique senders: {len(sender_emails)}"
            )

        mail.logout()
        return sender_emails

    except Exception as e:
        status_placeholder.error(f"IMAP Error: {e}")
        return sender_emails

# ==========================================
# 3. Input Layout
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔑 1. Gmail Credentials")
    user_email = st.text_input("Gmail Address:", placeholder="example@gmail.com")
    app_password = st.text_input("App Password (16-char):", type="password")

with col2:
    st.subheader("📋 2. SMTP List")
    smtp_raw_input = st.text_area(
        "Paste SMTP list directly here:",
        height=140,
        placeholder="smtp.gmail.com,587,email1@gmail.com,pass1\nsmtp.gmail.com,587,email2@gmail.com,pass2"
    )

st.markdown("---")

# ==========================================
# 4. Execution & Results Display
# ==========================================
if st.button("🚀 Start Extraction & Matching", type="primary"):
    if not user_email or not app_password:
        st.error("Please enter both Gmail Address and App Password.")
    else:
        status_box = st.empty()
        p_bar = st.progress(0)

        extracted_senders = fetch_senders_from_inbox(user_email, app_password, status_box, p_bar)

        if extracted_senders:
            status_box.success(f"Successfully extracted {len(extracted_senders)} unique sender(s)!")

            col_res1, col_res2 = st.columns(2)

            # Column 1: Extracted Senders Result
            extracted_txt = "\n".join(sorted(extracted_senders))
            with col_res1:
                st.subheader("📬 1. Extracted Senders")
                st.caption("Copy with one click using the top-right button in the box:")
                st.code(extracted_txt, language="text")

            # Column 2: Matched SMTPs Result
            if smtp_raw_input.strip():
                smtp_lines = smtp_raw_input.strip().splitlines()
                smtp_db = {}
                for line in smtp_lines:
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    parts = clean_line.split(",")
                    for part in parts:
                        clean_part = part.strip().lower()
                        if GMAIL_REGEX.match(clean_part):
                            smtp_db[clean_part] = clean_line
                            break

                matched_lines = [smtp_db[em] for em in extracted_senders if em in smtp_db]
                matched_txt = "\n".join(matched_lines)

                with col_res2:
                    st.subheader("⚡ 2. Matched SMTPs")
                    st.caption("Copy with one click using the top-right button in the box:")
                    if matched_lines:
                        st.code(matched_txt, language="text")
                    else:
                        st.warning("No matches found between extracted senders and the SMTP list.")
            else:
                with col_res2:
                    st.info("Paste your SMTP list above if you want to perform matching.")
