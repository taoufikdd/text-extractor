import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup

# ==============================================================================
# CONFIGURATION / الإعدادات
# ==============================================================================
EMAIL_USER = "your_email@gmail.com"     # الإيميل ديالك
APP_PASSWORD = "xxxx xxxx xxxx xxxx"    # App Password من جوجل

# 1. الكلمات المفتاحية (خليه خاوي [] إذا بغيتي يستخرج أي إيميل)
KEYWORDS = ["reset password", "County Expands"]  

# 2. عدد الإيميلات المراد استخراجها
MAX_EMAILS = 10                         

# 3. حالة الإيميل: 'UNREAD' (غير المقروءة) | 'READ' (المقروءة) | 'ALL' (الكل)
EMAIL_STATUS = "UNREAD"                 

# 4. تصفية حسب الإيميلات المهمة فقط: True أو False
ONLY_IMPORTANT = False                  

# 5. التحديد بالتاريخ (نظام YYYY/MM/DD) - دير None إذا ما بغيتيش تحدد التاريخ
START_DATE = "2026/01/01"   # تاريخ البداية (after:YYYY/MM/DD)
END_DATE = "2026/08/12"     # تاريخ النهاية (before:YYYY/MM/DD)
# ==============================================================================

def clean_html_content(html_content):
    """ تنظيف كود HTML واستخراج النص الصافي """
    soup = BeautifulSoup(html_content, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def decode_mime_header(header_value):
    """ فك ترميز العناوين """
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
    """ بناء استعلام البحث الخاص بـ Gmail """
    query_parts = []
    
    # حالة القراءة (Read/Unread)
    if status.upper() == "UNREAD":
        query_parts.append("is:unread")
    elif status.upper() == "READ":
        query_parts.append("is:read")
        
    # المهمة (Important)
    if important_only:
        query_parts.append("is:important")
        
    # نطاق التاريخ (Date Range)
    if start_date:
        query_parts.append(f"after:{start_date}")
    if end_date:
        query_parts.append(f"before:{end_date}")
        
    # الكلمات المفتاحية (Keywords)
    if keywords:
        kw_query = " OR ".join([f'"{kw}"' for kw in keywords])
        query_parts.append(f"({kw_query})")
        
    return " ".join(query_parts) if query_parts else "ALL"

def extract_gmail_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, APP_PASSWORD)
        mail.select("inbox")
        
        search_query = build_gmail_query(
            KEYWORDS, EMAIL_STATUS, ONLY_IMPORTANT, START_DATE, END_DATE
        )
        
        print(f"[*] Searching inbox with filter: {search_query}")
        
        if search_query == "ALL":
            status, response = mail.search(None, "ALL")
        else:
            status, response = mail.search(None, f'X-GM-RAW "{search_query}"')
        
        if status != "OK" or not response[0]:
            print("[!] No emails found matching your criteria.")
            return []

        email_ids = response[0].split()
        latest_email_ids = email_ids[-MAX_EMAILS:][::-1]
        
        results = []

        for e_id in latest_email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = decode_mime_header(msg.get("Subject"))
                    from_sender = decode_mime_header(msg.get("From"))
                    date = msg.get("Date")
                    
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

                    results.append({
                        "subject": subject,
                        "from": from_sender,
                        "date": date,
                        "body": body_text
                    })

        mail.logout()
        return results

    except Exception as e:
        print(f"[!] Error: {e}")
        return []

if __name__ == "__main__":
    emails = extract_gmail_emails()
    print(f"\n[+] Extracted {len(emails)} emails:\n")
    
    for i, e in enumerate(emails, 1):
        print("=" * 60)
        print(f"RESULT #{i}")
        print(f"Subject : {e['subject']}")
        print(f"From    : {e['from']}")
        print(f"Date    : {e['date']}")
        print("-" * 60)
        print(e['body'])
        print("=" * 60 + "\n")