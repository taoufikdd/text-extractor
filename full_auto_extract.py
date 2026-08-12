import email
from email.utils import parseaddr
import imaplib
import re
import streamlit as st

# ==========================================
# 1. إعدادات الصفحة
# ==========================================
st.set_page_config(
    page_title="Gmail IMAP Direct Extractor & Matcher",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Direct Gmail Extractor & SMTP Matcher")
st.write("حط معلوماتك وقائمة الـ SMTPs ديريكت هنا بلا ما تحتاج تنزل ولا ترفع حتى شي ملف!")

GMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@gmail\.com$", re.IGNORECASE
)

# ==========================================
# 2. وظيفة جلب الإيميلات من IMAP
# ==========================================
def fetch_senders_from_inbox(user_email, app_password, status_placeholder, progress_bar):
    sender_emails = set()

    try:
        status_placeholder.info(f"[*] الاتصال بـ Gmail IMAP لحساب: {user_email}...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        clean_pass = app_password.replace(" ", "")
        mail.login(user_email, clean_pass)

        mail.select("inbox")
        status, messages = mail.search(None, "ALL")

        mail_ids = messages[0].split()
        total_msgs = len(mail_ids)

        if total_msgs == 0:
            status_placeholder.warning("⚠️ لم يتم العثور على أي رسائل فـ Inbox.")
            mail.logout()
            return sender_emails

        status_placeholder.info(f"[+] تم العثور على {total_msgs} رسالة. جاري استخراج المرسلين...")

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
                f"تم معالجة: {processed_count} / {total_msgs} | إيميلات فريدة: {len(sender_emails)}"
            )

        mail.logout()
        return sender_emails

    except Exception as e:
        status_placeholder.error(f"[-] خطأ فـ الاتصال بـ IMAP: {e}")
        return sender_emails

# ==========================================
# 3. واجهة المدخلات المباشرة (Paste Directly)
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔑 1. معلومات Gmail")
    user_email = st.text_input("Gmail Address:", placeholder="example@gmail.com")
    app_password = st.text_input("App Password (16 حرف):", type="password")

with col2:
    st.subheader("📋 2. حط قائمة الـ SMTPs هنا")
    smtp_raw_input = st.text_area(
        "Copy / Paste لـ All SMTPs هنا ديريكت:",
        height=140,
        placeholder="smtp.gmail.com,587,email1@gmail.com,pass1\nsmtp.gmail.com,587,email2@gmail.com,pass2"
    )

st.markdown("---")

# ==========================================
# 4. زر التنفيذ وعرض النتائج المباشرة مع زر Copy
# ==========================================
if st.button("🚀 ابدأ الاستخراج والمطابقة", type="primary"):
    if not user_email or not app_password:
        st.error("⚠️ عفاك دخل Gmail و App Password بعدا.")
    else:
        status_box = st.empty()
        p_bar = st.progress(0)

        # استخراج الإيميلات
        extracted_senders = fetch_senders_from_inbox(user_email, app_password, status_box, p_bar)

        if extracted_senders:
            status_box.success(f"✅ تم استخراج {len(extracted_senders)} إيميل بنجاح!")

            col_res1, col_res2 = st.columns(2)

            # النتيجة 1: قائمة الإيميلات المستخرجة
            extracted_txt = "\n".join(sorted(extracted_senders))
            with col_res1:
                st.subheader("📬 1. الإيميلات المستخرجة (Senders)")
                st.caption("📋 تكوبي بضغطة زر واحدة (كليك على أيقونة Copy الفوق على اليمين ديال المربع):")
                st.code(extracted_txt, language="text")

            # النتيجة 2: مطابقة الـ SMTPs
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
                    st.subheader("⚡ 2. نتائج المطابقة (Matched SMTPs)")
                    st.caption("📋 تكوبي بضغطة زر واحدة:")
                    if matched_lines:
                        st.code(matched_txt, language="text")
                    else:
                        st.warning("ما كاينا حتى مطابقة بين الإيميلات المستخرجة والقائمة اللي تلصقات.")
            else:
                with col_res2:
                    st.info("💡 يلا بغيتي المطابقة ديريكت، حط قائمة SMTPs فـ الخانة الفوق.")
