import email
from email.utils import parseaddr
import imaplib
import re
import streamlit as st

# Config Page
st.set_page_config(page_title="Gmail IMAP Extractor & Matcher", page_icon="⚡", layout="wide")

st.title("⚡ Gmail Real IMAP Extractor & SMTP Matcher")
st.write("استخراج الحسابات الحقيقي عبر بروتوكول IMAP والمطابقة المباشرة")

GMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", re.IGNORECASE)

def extract_senders_from_folder(mail, folder_name, status_box, progress_bar, p_start, p_end):
    senders = set()
    try:
        status, _ = mail.select(f'"{folder_name}"')
        if status != "OK":
            return senders

        status, messages = mail.search(None, "ALL")
        if status != "OK" or not messages[0]:
            return senders

        mail_ids = messages[0].split()
        total = len(mail_ids)
        if total == 0:
            return senders

        batch_size = 50
        for i in range(0, total, batch_size):
            batch_ids = mail_ids[i:i + batch_size]
            batch_str = b",".join(batch_ids)

            _, msg_data = mail.fetch(batch_str, "(BODY.PEEK[HEADER.FIELDS (FROM)])")

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    try:
                        raw_header = response_part[1].decode("utf-8", errors="ignore")
                        msg = email.message_from_string(raw_header)
                        from_hdr = msg.get("From", "")
                        _, addr = parseaddr(from_hdr)
                        addr = addr.strip().lower()
                        if GMAIL_REGEX.match(addr):
                            senders.add(addr)
                    except Exception:
                        pass

            processed = min(i + batch_size, total)
            prog = p_start + (processed / total) * (p_end - p_start)
            progress_bar.progress(min(prog, 1.0))
            status_box.info(f"📁 [{folder_name}] Processed {processed}/{total} emails | Found {len(senders)} unique senders")

    except Exception as e:
        status_box.warning(f"Warning reading {folder_name}: {e}")

    return senders

def run_extraction(email_addr, app_pass, folder_choice, status_box, progress_bar):
    all_senders = set()
    try:
        status_box.info("Connecting to imap.gmail.com:993...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        clean_pass = app_pass.replace(" ", "")
        mail.login(email_addr, clean_pass)

        if folder_choice == "INBOX":
            all_senders.update(extract_senders_from_folder(mail, "INBOX", status_box, progress_bar, 0.0, 1.0))
        elif folder_choice == "SPAM":
            all_senders.update(extract_senders_from_folder(mail, "[Gmail]/Spam", status_box, progress_bar, 0.0, 1.0))
        elif folder_choice == "ALL (INBOX + SPAM)":
            status_box.info("Scanning INBOX...")
            inbox_s = extract_senders_from_folder(mail, "INBOX", status_box, progress_bar, 0.0, 0.5)
            all_senders.update(inbox_s)
            
            status_box.info("Scanning SPAM...")
            spam_s = extract_senders_from_folder(mail, "[Gmail]/Spam", status_box, progress_bar, 0.5, 1.0)
            all_senders.update(spam_s)

        mail.logout()
        return all_senders

    except Exception as e:
        status_box.error(f"❌ Connection Error: {e}")
        return all_senders

# UI Layout
col1, col2 = st.columns(2)
with col1:
    st.subheader("🔑 1. Gmail Credentials")
    user_email = st.text_input("Gmail Address", placeholder="example@gmail.com")
    app_password = st.text_input("App Password (16-digit)", type="password")
    folder_target = st.selectbox("Target Folder", ["INBOX", "SPAM", "ALL (INBOX + SPAM)"])

with col2:
    st.subheader("📋 2. SMTP List")
    smtp_input = st.text_area("Paste SMTP list here:", height=200, placeholder="smtp.gmail.com,587,email@gmail.com,pass")

if st.button("🚀 Start Real IMAP Extraction", type="primary"):
    if not user_email or not app_password:
        st.error("Please enter Email Address & App Password!")
    else:
        status_box = st.empty()
        p_bar = st.progress(0)
        
        senders = run_extraction(user_email, app_password, folder_target, status_box, p_bar)
        
        if senders:
            status_box.success(f" Done! Successfully extracted {len(senders)} senders.")
            res_col1, res_col2 = st.columns(2)
            
            senders_txt = "\n".join(sorted(senders))
            with res_col1:
                st.subheader(f"📬 Extracted Senders ({len(senders)})")
                st.code(senders_txt, language="text")

            if smtp_input.strip():
                smtp_db = {}
                for line in smtp_input.strip().splitlines():
                    for part in line.split(","):
                        clean_part = part.strip().lower()
                        if GMAIL_REGEX.match(clean_part):
                            smtp_db[clean_part] = line.strip()
                            break
                
                matched = [smtp_db[s] for s in senders if s in smtp_db]
                with res_col2:
                    st.subheader(f"⚡ Matched SMTPs ({len(matched)})")
                    st.code("\n".join(matched) if matched else "No matches found.", language="text")
        else:
            status_box.warning("No senders found or authentication failed.")
