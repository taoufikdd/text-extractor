# app.py
import streamlit as st
import imaplib
import email
import re
import csv
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.header import decode_header

st.set_page_config(
    page_title="Gmail Bounce Collector",
    page_icon="📧",
    layout="wide"
)

# ============================================================
# SETTINGS / REGEX
# ============================================================

SEARCH_QUERIES = [
    '(FROM "mailer-daemon")',
    '(FROM "postmaster")',
    '(SUBJECT "Delivery Status Notification")',
    '(SUBJECT "Mail Delivery")',
    '(SUBJECT "Undeliverable")',
    '(SUBJECT "Failure Notice")',
    '(SUBJECT "Returned mail")',
]

NONEXISTENT_STATUS = re.compile(
    r'\bstatus:\s*5\.(1\.1|2\.1)\b',
    re.IGNORECASE
)

NONEXISTENT_DIAG = re.compile(
    r'(does not exist|no such user|user unknown|'
    r'account.*not found|inactive|disabled)',
    re.IGNORECASE | re.DOTALL
)

FULL_MAILBOX_STATUS = re.compile(
    r'\bstatus:\s*5\.2\.2\b',
    re.IGNORECASE
)

FULL_MAILBOX_DIAG = re.compile(
    r'(mailbox full|over quota|storage limit|'
    r'user is over|quota exceeded|out of storage)',
    re.IGNORECASE
)

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@gmail\.com',
    re.IGNORECASE
)


# ============================================================
# PARSE BULK FILE
# ============================================================

def parse_accounts(text):
    """
    Supported:
        email@gmail.com:app_password
        email@gmail.com|app_password

    Blank lines and lines starting with # are ignored.
    """

    accounts = []
    invalid = []
    seen = set()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):

        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        # email:password
        if ":" in line:
            user, password = line.split(":", 1)

        # email|password
        elif "|" in line:
            user, password = line.split("|", 1)

        else:
            invalid.append((line_number, line))
            continue

        user = user.strip()
        password = password.strip().replace(" ", "")

        if not user or not password or "@" not in user:
            invalid.append((line_number, line))
            continue

        # avoid duplicate source accounts
        key = user.lower()

        if key in seen:
            continue

        seen.add(key)

        accounts.append({
            "email": user,
            "password": password
        })

    return accounts, invalid


# ============================================================
# EMAIL HELPERS
# ============================================================

def decode_str(value):

    if not value:
        return ""

    result = []

    try:
        parts = decode_header(value)

        for part, enc in parts:

            if isinstance(part, bytes):
                try:
                    result.append(
                        part.decode(enc or "utf-8", errors="replace")
                    )
                except Exception:
                    result.append(
                        part.decode("utf-8", errors="replace")
                    )

            else:
                result.append(str(part))

    except Exception:
        return str(value)

    return " ".join(result).strip()


def parse_headers(raw_bytes):

    msg = email.message_from_bytes(raw_bytes)

    headers = {}

    for key in msg.keys():

        k = key.lower()

        if k not in headers:
            headers[k] = decode_str(msg[key])

    return headers


# ============================================================
# DETECT BOUNCE
# ============================================================

def is_bounce_header(headers):

    sender = headers.get("from", "").lower()
    subject = headers.get("subject", "").lower()

    x_failed = headers.get(
        "x-failed-recipients",
        ""
    )

    ctype = headers.get(
        "content-type",
        ""
    ).lower()

    rpath = headers.get(
        "return-path",
        ""
    ).strip()

    score = 0

    if "mailer-daemon" in sender:
        score += 2

    if "postmaster" in sender:
        score += 2

    keywords = [
        "delivery status notification",
        "mail delivery",
        "undeliverable",
        "failure notice",
        "returned mail",
    ]

    if any(k in subject for k in keywords):
        score += 2

    if rpath in ("<>", ""):
        score += 1

    if "multipart/report" in ctype:
        score += 1

    if x_failed:
        score += 3

    return score >= 2


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_bounce(text):

    if not text:
        return None

    if (
        NONEXISTENT_STATUS.search(text)
        and NONEXISTENT_DIAG.search(text)
    ):
        return "nonexistent"

    if (
        FULL_MAILBOX_STATUS.search(text)
        or FULL_MAILBOX_DIAG.search(text)
    ):
        return "full_mailbox"

    return None


# ============================================================
# EXTRACT FAILED ADDRESS
# ============================================================

def extract_address(headers, ds_text):

    # 1. X-Failed-Recipients
    x_failed = headers.get(
        "x-failed-recipients",
        ""
    )

    if x_failed:

        match = EMAIL_RE.search(x_failed)

        if match:
            return match.group(0).lower()

    # 2. Final-Recipient
    if ds_text:

        match = re.search(
            r'final-recipient:\s*rfc822;\s*'
            r'([a-zA-Z0-9._%+\-]+@gmail\.com)',
            ds_text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).lower()

    # 3. Subject fallback
    subject = headers.get("subject", "")

    match = EMAIL_RE.search(subject)

    if match:
        return match.group(0).lower()

    return None


# ============================================================
# FETCH DELIVERY STATUS
# ============================================================

def fetch_delivery_status(mail, eid):

    # Common DSN MIME positions
    for part in ["2", "3", "1.2", "2.1"]:

        try:

            status, data = mail.fetch(
                eid,
                f"(BODY.PEEK[{part}])"
            )

            if status != "OK":
                continue

            if not data:
                continue

            for item in data:

                if not isinstance(item, tuple):
                    continue

                raw = item[1]

                if not raw:
                    continue

                if isinstance(raw, bytes):

                    text = raw.decode(
                        "utf-8",
                        errors="replace"
                    )

                else:
                    text = str(raw)

                low = text.lower()

                if (
                    "status:" in low
                    or "final-recipient" in low
                    or "diagnostic-code" in low
                ):
                    return text

        except Exception:
            continue

    return ""


# ============================================================
# PROCESS ONE ACCOUNT
# ============================================================

def process_account(account, include_full=False):

    gmail_user = account["email"]
    gmail_pass = account["password"]

    result = {
        "account": gmail_user,
        "status": "OK",
        "error": "",
        "found": []
    }

    mail = None

    try:

        # ----------------------------------
        # Connect
        # ----------------------------------

        mail = imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
            timeout=20
        )

        mail.login(
            gmail_user,
            gmail_pass
        )

        # ----------------------------------
        # READ ONLY
        # ----------------------------------

        status, _ = mail.select(
            '"[Gmail]/All Mail"',
            readonly=True
        )

        if status != "OK":

            status, _ = mail.select(
                "INBOX",
                readonly=True
            )

        if status != "OK":
            raise Exception(
                "Could not open mailbox"
            )

        # ----------------------------------
        # Find candidate bounce emails
        # ----------------------------------

        candidate_ids = set()

        for query in SEARCH_QUERIES:

            try:

                status, data = mail.search(
                    None,
                    query
                )

                if (
                    status == "OK"
                    and data
                    and data[0]
                ):

                    candidate_ids.update(
                        data[0].split()
                    )

            except Exception:
                continue

        # ----------------------------------
        # Process candidates
        # ----------------------------------

        found = {}

        for eid in candidate_ids:

            try:

                # HEADER ONLY / PEEK
                status, hdata = mail.fetch(
                    eid,
                    "(BODY.PEEK[HEADER])"
                )

                if status != "OK":
                    continue

                if not hdata:
                    continue

                raw_header = None

                for item in hdata:

                    if isinstance(item, tuple):
                        raw_header = item[1]
                        break

                if not raw_header:
                    continue

                headers = parse_headers(
                    raw_header
                )

                if not is_bounce_header(headers):
                    continue

                # Delivery Status
                ds_text = fetch_delivery_status(
                    mail,
                    eid
                )

                bounce_type = classify_bounce(
                    ds_text
                )

                if not bounce_type:
                    continue

                if (
                    bounce_type == "full_mailbox"
                    and not include_full
                ):
                    continue

                addr = extract_address(
                    headers,
                    ds_text
                )

                if addr:

                    found[addr] = {
                        "email": addr,
                        "type": bounce_type
                    }

            except Exception:
                continue

        result["found"] = list(
            found.values()
        )

    except imaplib.IMAP4.error:

        result["status"] = "LOGIN_FAILED"
        result["error"] = "Gmail login failed"

    except Exception as exc:

        result["status"] = "ERROR"

        result["error"] = str(exc)[:120]

    finally:

        if mail:

            try:
                mail.logout()
            except Exception:
                pass

    return result


# ============================================================
# EXPORT
# ============================================================

def make_csv(items):

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "email",
        "type",
        "source_account"
    ])

    for item in items:

        writer.writerow([
            item["email"],
            item["type"],
            item["source_account"]
        ])

    return output.getvalue()


def make_txt(items):

    return "\n".join(
        item["email"]
        for item in items
    )


# ============================================================
# STREAMLIT UI
# ============================================================

st.title("📧 Gmail Bounce Collector")

st.caption(
    "Bulk Gmail/App Password scanner — read-only IMAP"
)

st.info(
    "TXT format: email@gmail.com:app_password — "
    "one account per line."
)


uploaded_file = st.file_uploader(
    "Upload accounts TXT",
    type=["txt"]
)


col1, col2 = st.columns(2)

with col1:

    workers = st.slider(
        "Concurrent accounts",
        min_value=1,
        max_value=5,
        value=2
    )

with col2:

    include_full = st.checkbox(
        "Include mailbox full (5.2.2)",
        value=False
    )


# ============================================================
# FILE PREVIEW
# ============================================================

accounts = []

if uploaded_file:

    raw = uploaded_file.getvalue()

    try:

        text_data = raw.decode("utf-8")

    except UnicodeDecodeError:

        text_data = raw.decode(
            "latin-1",
            errors="replace"
        )

    accounts, invalid = parse_accounts(
        text_data
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Accounts",
        len(accounts)
    )

    c2.metric(
        "Invalid lines",
        len(invalid)
    )

    c3.metric(
        "Workers",
        workers
    )

    if invalid:

        with st.expander(
            "Show invalid lines"
        ):

            for line_number, line in invalid[:100]:

                st.write(
                    f"Line {line_number}: {line}"
                )


# ============================================================
# START SCAN
# ============================================================

if uploaded_file and accounts:

    if st.button(
        "🚀 Start Scan",
        type="primary",
        use_container_width=True
    ):

        progress = st.progress(0)

        status_box = st.empty()

        results_box = st.empty()

        total = len(accounts)

        completed = 0
        login_errors = 0

        all_bounces = {}

        account_results = []

        # Keep worker count intentionally small.
        with ThreadPoolExecutor(
            max_workers=workers
        ) as executor:

            futures = {
                executor.submit(
                    process_account,
                    account,
                    include_full
                ): account["email"]

                for account in accounts
            }

            for future in as_completed(futures):

                source_account = futures[future]

                try:

                    result = future.result()

                except Exception as exc:

                    result = {
                        "account": source_account,
                        "status": "ERROR",
                        "error": str(exc),
                        "found": []
                    }

                completed += 1

                account_results.append(
                    result
                )

                if result["status"] != "OK":
                    login_errors += 1

                for item in result["found"]:

                    address = item[
                        "email"
                    ].lower()

                    # Global deduplication
                    if address not in all_bounces:

                        all_bounces[address] = {
                            "email": address,
                            "type": item["type"],
                            "source_account":
                                source_account
                        }

                percent = completed / total

                progress.progress(
                    percent
                )

                status_box.write(
                    f"Processed **{completed}/{total}** "
                    f"accounts — "
                    f"**{len(all_bounces)}** "
                    f"unique bounces found."
                )

                # Small pause in UI loop
                time.sleep(0.05)


        # ====================================================
        # RESULTS
        # ====================================================

        final_results = sorted(
            all_bounces.values(),
            key=lambda x: x["email"]
        )

        nonexistent = [
            x for x in final_results
            if x["type"] == "nonexistent"
        ]

        full_mailbox = [
            x for x in final_results
            if x["type"] == "full_mailbox"
        ]


        st.success("Scan completed.")


        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Accounts scanned",
            completed
        )

        m2.metric(
            "Errors",
            login_errors
        )

        m3.metric(
            "Nonexistent",
            len(nonexistent)
        )

        m4.metric(
            "Mailbox full",
            len(full_mailbox)
        )


        # ====================================================
        # BOUNCES TABLE
        # ====================================================

        st.subheader(
            "Bounced Emails"
        )

        if final_results:

            st.dataframe(
                final_results,
                use_container_width=True,
                hide_index=True
            )

            csv_data = make_csv(
                final_results
            )

            txt_data = make_txt(
                final_results
            )

            d1, d2 = st.columns(2)

            with d1:

                st.download_button(
                    "⬇️ Download CSV",
                    data=csv_data,
                    file_name="bounced_emails.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with d2:

                st.download_button(
                    "⬇️ Download TXT",
                    data=txt_data,
                    file_name="bounced_emails.txt",
                    mime="text/plain",
                    use_container_width=True
                )

        else:

            st.warning(
                "No matching bounced addresses found."
            )


        # ====================================================
        # ACCOUNT STATUS
        # ====================================================

        with st.expander(
            "Account Scan Status"
        ):

            safe_results = []

            for r in account_results:

                safe_results.append({
                    "account": r["account"],
                    "status": r["status"],
                    "bounces": len(
                        r["found"]
                    ),
                    "error": r["error"]
                })

            st.dataframe(
                safe_results,
                use_container_width=True,
                hide_index=True
            )