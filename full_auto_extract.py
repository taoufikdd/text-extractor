import email
from email.utils import parseaddr
import imaplib
import re

# ==========================================
# 1. إعدادات أسماء الملفات
# ==========================================
FILE_CONFIG = "Email_for_extract.txt"
FILE_RESULT_EMAILS = "Result_emails.txt"
FILE_ALL_SMTPS = "All_smtps.txt"
FILE_FINAL_RESULT = "Result_smtps_with_app.txt"

# Regex للتحقق من أن البريد ينتهي بـ gmail.com
GMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@gmail\.com$", re.IGNORECASE
)


def get_credentials():
    """قراءة البريد والـ App Password من ملف Email_for_extract.txt"""
    user_email = ""
    app_password = ""

    with open(FILE_CONFIG, "r", encoding="utf-8") as f:
        for line in f:
            if "Email:" in line:
                user_email = line.split("Email:")[1].strip()
            elif "App password:" in line:
                app_password = line.split("App password:")[1].strip()

    return user_email, app_password


def fetch_senders_from_inbox(user_email, app_password):
    """جلب عنوان المرسل (From Header) فقط من جميع رسائل الـ Inbox"""
    print(f"[*] Connecting to Gmail IMAP for {user_email}...")
    sender_emails = set()

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        clean_pass = app_password.replace(" ", "")
        mail.login(user_email, clean_pass)

        mail.select("inbox")
        status, messages = mail.search(None, "ALL")

        mail_ids = messages[0].split()
        total_msgs = len(mail_ids)
        print(
            f"[+] Found {total_msgs} messages in Inbox. Extracting senders (From:)..."
        )

        # جلب الهيدر (FROM) فقط في دفعات لتسريع العملية
        batch_size = 100
        for i in range(0, total_msgs, batch_size):
            batch_ids = mail_ids[i : i + batch_size]
            batch_str = b",".join(batch_ids)

            # طلب خفيف جداً: جلب خانة FROM فقط
            _, msg_data = mail.fetch(
                batch_str, "(BODY.PEEK[HEADER.FIELDS (FROM)])"
            )

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    try:
                        raw_header = response_part[1].decode(
                            "utf-8", errors="ignore"
                        )
                        msg = email.message_from_string(raw_header)
                        from_header = msg.get("From", "")

                        # استخراج البريد من صيغة "Name <email@gmail.com>"
                        real_name, email_address = parseaddr(from_header)
                        email_address = email_address.strip().lower()

                        if GMAIL_REGEX.match(email_address):
                            sender_emails.add(email_address)
                    except Exception:
                        pass

            print(
                f"    -> Processed {min(i + batch_size, total_msgs)} / {total_msgs} headers (Unique senders: {len(sender_emails)})..."
            )

        mail.logout()
        print(
            f"[+] Successfully extracted {len(sender_emails)} unique sender Gmail addresses."
        )

    except Exception as e:
        print(f"[-] IMAP Error: {e}")

    return sender_emails


def main():
    # 1. جلب إيميلات المرسلين من Inbox
    user_email, app_password = get_credentials()
    if not user_email or not app_password:
        print(f"[-] Error: Could not read credentials from {FILE_CONFIG}")
        return

    extracted_senders = fetch_senders_from_inbox(user_email, app_password)

    # حفظ إيميلات المرسلين في Result_emails.txt
    with open(FILE_RESULT_EMAILS, "w", encoding="utf-8") as f_out:
        for em in extracted_senders:
            f_out.write(em + "\n")

    print(f"[+] Saved extracted sender emails to '{FILE_RESULT_EMAILS}'.")

    # 2. المطابقة مع ملف All_smtps.txt
    print(f"[*] Matching with '{FILE_ALL_SMTPS}'...")
    smtp_db = {}

    try:
        with open(FILE_ALL_SMTPS, "r", encoding="utf-8") as f_smtp:
            for line in f_smtp:
                clean_line = line.strip()
                if not clean_line:
                    continue

                # استخراج البريد من سطر الـ SMTP
                parts = clean_line.split(",")
                for part in parts:
                    clean_part = part.strip().lower()
                    if GMAIL_REGEX.match(clean_part):
                        smtp_db[clean_part] = clean_line
                        break
    except FileNotFoundError:
        print(f"[-] Error: File '{FILE_ALL_SMTPS}' not found!")
        return

    # 3. كتابة الأسطر المطابقة في النتيجة النهائية
    matched_count = 0
    with open(FILE_FINAL_RESULT, "w", encoding="utf-8") as f_final:
        for em in extracted_senders:
            if em in smtp_db:
                f_final.write(smtp_db[em] + "\n")
                matched_count += 1

    print("=" * 60)
    print(
        f"[SUCCESS] Done! Saved {matched_count} matching full SMTP lines into '{FILE_FINAL_RESULT}'."
    )


if __name__ == "__main__":
    main()