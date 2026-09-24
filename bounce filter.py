# ============================================================
# Gmail Bounce Collector - Streamlit
# STRICT MODE
#
# Output ONLY:
#   5.1.1 -> recipient does not exist
#   5.2.1 -> recipient disabled / inactive
#
# Ignore:
#   4.x.x -> temporary / deferred
#   5.7.x -> policy / spam / rate limit
#   5.2.2 -> mailbox full
#   sender limits / daily limits
#
# Bulk input:
#   email1@gmail.com:app_password
#   email2@gmail.com:app_password
# ============================================================

import streamlit as st
import imaplib
import email
import re
import csv
import io
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from email.header import decode_header


# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title="Gmail Bounce Collector",
    page_icon="📧",
    layout="wide"
)


# ============================================================
# SEARCH QUERIES
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


# ============================================================
# REGEX
# ============================================================

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@gmail\.com',
    re.IGNORECASE
)


NONEXISTENT_STATUS = re.compile(
    r'\bstatus:\s*5\.1\.1\b',
    re.IGNORECASE
)


DISABLED_STATUS = re.compile(
    r'\bstatus:\s*5\.2\.1\b',
    re.IGNORECASE
)


NONEXISTENT_DIAG = re.compile(
    r'(does not exist|'
    r'no such user|'
    r'user unknown|'
    r'account.*not found|'
    r'address.*not found|'
    r'recipient.*not found)',
    re.IGNORECASE | re.DOTALL
)


DISABLED_DIAG = re.compile(
    r'(account.*disabled|'
    r'account.*inactive|'
    r'user.*disabled|'
    r'user.*inactive|'
    r'recipient.*disabled|'
    r'recipient.*inactive)',
    re.IGNORECASE | re.DOTALL
)


# ============================================================
# BULK FILE PARSER
# ============================================================

def parse_accounts(text):

    accounts = []
    invalid = []
    seen = set()

    for line_number, raw_line in enumerate(
        text.splitlines(),
        start=1
    ):

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        # Format:
        # email@gmail.com:password

        if ":" in line:

            user, password = line.split(
                ":",
                1
            )

        # Also support:
        # email@gmail.com|password

        elif "|" in line:

            user, password = line.split(
                "|",
                1
            )

        else:

            invalid.append({
                "line": line_number,
                "content": line
            })

            continue

        user = user.strip().lower()

        # Google App Password can be pasted
        # with spaces, remove those spaces.

        password = password.strip().replace(
            " ",
            ""
        )

        if (
            not user
            or not password
            or "@" not in user
        ):

            invalid.append({
                "line": line_number,
                "content": line
            })

            continue

        # Deduplicate source accounts

        if user in seen:
            continue

        seen.add(user)

        accounts.append({
            "email": user,
            "password": password
        })

    return accounts, invalid


# ============================================================
# HEADER DECODER
# ============================================================

def decode_str(value):

    if not value:
        return ""

    try:

        parts = decode_header(value)

        output = []

        for part, encoding in parts:

            if isinstance(part, bytes):

                try:

                    output.append(
                        part.decode(
                            encoding or "utf-8",
                            errors="replace"
                        )
                    )

                except Exception:

                    output.append(
                        part.decode(
                            "utf-8",
                            errors="replace"
                        )
                    )

            else:

                output.append(
                    str(part)
                )

        return " ".join(output).strip()

    except Exception:

        return str(value)


# ============================================================
# PARSE HEADERS
# ============================================================

def parse_headers(raw_bytes):

    try:

        msg = email.message_from_bytes(
            raw_bytes
        )

        headers = {}

        for key in msg.keys():

            lower_key = key.lower()

            if lower_key not in headers:

                headers[lower_key] = decode_str(
                    msg[key]
                )

        return headers

    except Exception:

        return {}


# ============================================================
# BOUNCE HEADER DETECTION
# ============================================================

def is_bounce_header(headers):

    sender = headers.get(
        "from",
        ""
    ).lower()

    subject = headers.get(
        "subject",
        ""
    ).lower()

    x_failed = headers.get(
        "x-failed-recipients",
        ""
    )

    content_type = headers.get(
        "content-type",
        ""
    ).lower()

    return_path = headers.get(
        "return-path",
        ""
    ).strip()

    score = 0


    # Mailer daemon

    if "mailer-daemon" in sender:
        score += 2


    # Postmaster

    if "postmaster" in sender:
        score += 2


    # Common subjects

    bounce_subjects = [
        "delivery status notification",
        "mail delivery",
        "undeliverable",
        "failure notice",
        "returned mail",
    ]

    if any(
        word in subject
        for word in bounce_subjects
    ):
        score += 2


    # Empty return path common for DSNs

    if return_path in ("<>", ""):
        score += 1


    # RFC delivery report

    if "multipart/report" in content_type:
        score += 1


    # Very useful Gmail header

    if x_failed:
        score += 3


    return score >= 2


# ============================================================
# STRICT CLASSIFICATION
# ============================================================

def classify_bounce(ds_text):

    if not ds_text:
        return None

    text = ds_text.lower()


    # ========================================================
    # IGNORE ALL TEMPORARY ERRORS
    # ========================================================

    if re.search(
        r'\bstatus:\s*4\.\d+\.\d+\b',
        text
    ):
        return None


    temporary_phrases = [
        "temporarily deferred",
        "temporary failure",
        "try again later",
        "temporarily unavailable",
        "please try again",
        "rate limit",
        "rate limited",
        "too many requests",
        "sending limit",
        "daily limit",
        "daily sending quota",
        "sender quota",
        "quota exceeded for sender",
    ]


    if any(
        phrase in text
        for phrase in temporary_phrases
    ):
        return None


    # ========================================================
    # IGNORE POLICY / SPAM / AUTHENTICATION
    # ========================================================

    if re.search(
        r'\bstatus:\s*5\.7\.\d+\b',
        text
    ):
        return None


    policy_phrases = [
        "message rejected",
        "policy rejection",
        "spam detected",
        "spam policy",
        "authentication required",
        "unauthenticated email",
        "spf",
        "dkim",
        "dmarc",
        "suspicious rate",
    ]


    if any(
        phrase in text
        for phrase in policy_phrases
    ):
        return None


    # ========================================================
    # IGNORE MAILBOX FULL
    # ========================================================

    if re.search(
        r'\bstatus:\s*5\.2\.2\b',
        text
    ):
        return None


    mailbox_full_phrases = [
        "mailbox full",
        "over quota",
        "storage limit",
        "out of storage",
        "recipient inbox full",
    ]


    if any(
        phrase in text
        for phrase in mailbox_full_phrases
    ):
        return None


    # ========================================================
    # ACCEPT 5.1.1 ONLY WITH DIAGNOSTIC CONFIRMATION
    # ========================================================

    if NONEXISTENT_STATUS.search(
        ds_text
    ):

        if NONEXISTENT_DIAG.search(
            ds_text
        ):

            return "nonexistent"


    # ========================================================
    # ACCEPT 5.2.1 ONLY WITH DIAGNOSTIC CONFIRMATION
    # ========================================================

    if DISABLED_STATUS.search(
        ds_text
    ):

        if DISABLED_DIAG.search(
            ds_text
        ):

            return "disabled"


    # Unknown -> don't remove

    return None


# ============================================================
# EXTRACT FAILED RECIPIENT
# ============================================================

def extract_address(
    headers,
    ds_text
):

    # ========================================================
    # 1. X-Failed-Recipients
    # ========================================================

    x_failed = headers.get(
        "x-failed-recipients",
        ""
    )

    if x_failed:

        match = EMAIL_RE.search(
            x_failed
        )

        if match:

            return (
                match.group(0)
                .lower()
            )


    # ========================================================
    # 2. Final-Recipient
    # ========================================================

    if ds_text:

        match = re.search(
            r'final-recipient:\s*rfc822;\s*'
            r'([a-zA-Z0-9._%+\-]+@gmail\.com)',
            ds_text,
            re.IGNORECASE
        )

        if match:

            return (
                match.group(1)
                .lower()
            )


    # ========================================================
    # 3. Original-Recipient
    # ========================================================

    if ds_text:

        match = re.search(
            r'original-recipient:\s*rfc822;\s*'
            r'([a-zA-Z0-9._%+\-]+@gmail\.com)',
            ds_text,
            re.IGNORECASE
        )

        if match:

            return (
                match.group(1)
                .lower()
            )


    # ========================================================
    # 4. Subject fallback
    # ========================================================

    subject = headers.get(
        "subject",
        ""
    )

    match = EMAIL_RE.search(
        subject
    )

    if match:

        return (
            match.group(0)
            .lower()
        )


    return None


# ============================================================
# FETCH DELIVERY STATUS
# ============================================================

def fetch_delivery_status(
    mail,
    eid
):

    # Common MIME part locations.

    parts = [
        "2",
        "3",
        "1.2",
        "2.1",
        "2.2",
        "3.1",
    ]


    for part in parts:

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

                if not isinstance(
                    item,
                    tuple
                ):
                    continue


                raw = item[1]


                if not raw:
                    continue


                if isinstance(
                    raw,
                    bytes
                ):

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
# PROCESS ONE SOURCE GMAIL ACCOUNT
# ============================================================

def process_account(account):

    gmail_user = account["email"]
    gmail_pass = account["password"]

    result = {

        "account": gmail_user,

        "status": "OK",

        "error": "",

        "candidates": 0,

        "found": []
    }


    mail = None


    try:

        # ====================================================
        # CONNECT
        # ====================================================

        mail = imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
            timeout=20
        )


        # ====================================================
        # LOGIN
        # ====================================================

        mail.login(
            gmail_user,
            gmail_pass
        )


        # ====================================================
        # READ ONLY MAILBOX
        # ====================================================

        status, _ = mail.select(
            '"[Gmail]/All Mail"',
            readonly=True
        )


        # Fallback

        if status != "OK":

            status, _ = mail.select(
                "INBOX",
                readonly=True
            )


        if status != "OK":

            raise Exception(
                "Could not open mailbox"
            )


        # ====================================================
        # SEARCH FOR POSSIBLE DSN / BOUNCES
        # ====================================================

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


        result["candidates"] = len(
            candidate_ids
        )


        # ====================================================
        # LOCAL DEDUPLICATION
        # ====================================================

        found = {}


        # ====================================================
        # PROCESS EACH DSN
        # ====================================================

        for eid in candidate_ids:

            try:

                # ============================================
                # HEADERS ONLY
                # BODY.PEEK DOES NOT INTENTIONALLY SET \Seen
                # ============================================

                status, header_data = mail.fetch(
                    eid,
                    "(BODY.PEEK[HEADER])"
                )


                if status != "OK":
                    continue


                if not header_data:
                    continue


                raw_header = None


                for item in header_data:

                    if isinstance(
                        item,
                        tuple
                    ):

                        raw_header = item[1]

                        break


                if not raw_header:
                    continue


                headers = parse_headers(
                    raw_header
                )


                # ============================================
                # MUST LOOK LIKE A BOUNCE
                # ============================================

                if not is_bounce_header(
                    headers
                ):
                    continue


                # ============================================
                # FETCH DELIVERY STATUS
                # ============================================

                ds_text = fetch_delivery_status(
                    mail,
                    eid
                )


                if not ds_text:
                    continue


                # ============================================
                # STRICT CLASSIFICATION
                # ============================================

                bounce_type = classify_bounce(
                    ds_text
                )


                # Anything uncertain is kept / ignored

                if bounce_type not in (
                    "nonexistent",
                    "disabled"
                ):

                    continue


                # ============================================
                # EXTRACT RECIPIENT
                # ============================================

                address = extract_address(
                    headers,
                    ds_text
                )


                if not address:
                    continue


                # ============================================
                # ADD ONLY CONFIRMED BAD RECIPIENT
                # ============================================

                found[address] = {

                    "email": address,

                    "type": bounce_type
                }


            except Exception:

                # One malformed message must not
                # stop the whole mailbox.

                continue


        result["found"] = list(
            found.values()
        )


    # ========================================================
    # LOGIN FAILURE
    # ========================================================

    except imaplib.IMAP4.error:

        result["status"] = (
            "LOGIN_FAILED"
        )

        result["error"] = (
            "Gmail login failed"
        )


    # ========================================================
    # OTHER ERROR
    # ========================================================

    except Exception as exc:

        result["status"] = "ERROR"

        result["error"] = str(
            exc
        )[:150]


    # ========================================================
    # ALWAYS LOGOUT
    # ========================================================

    finally:

        if mail:

            try:

                mail.logout()

            except Exception:

                pass


    return result


# ============================================================
# CSV EXPORT
# ============================================================

def make_csv(items):

    output = io.StringIO()

    writer = csv.writer(
        output
    )


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


# ============================================================
# TXT EXPORT
# ============================================================

def make_txt(items):

    return "\n".join(

        item["email"]

        for item in items
    )


# ============================================================
# PAGE
# ============================================================

st.title(
    "📧 Gmail Bounce Collector"
)


st.caption(
    "STRICT MODE — only confirmed nonexistent / disabled recipients"
)


st.warning(
    "Only use Gmail accounts you own or are authorized to access. "
    "Credentials are used for the current scan and are not intentionally "
    "written to the result files."
)


# ============================================================
# INPUT FORMAT
# ============================================================

with st.expander(
    "📄 TXT Format",
    expanded=False
):

    st.code(
        """email1@gmail.com:app_password_1
email2@gmail.com:app_password_2
email3@gmail.com:app_password_3"""
    )


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_file = st.file_uploader(

    "Upload Gmail accounts TXT",

    type=[
        "txt"
    ]
)


# ============================================================
# WORKERS
# ============================================================

workers = st.slider(

    "Concurrent accounts",

    min_value=1,

    max_value=5,

    value=2,

    help=(
        "Keep this low. "
        "This controls simultaneous IMAP connections."
    )
)


# ============================================================
# PARSE UPLOAD
# ============================================================

accounts = []
invalid = []


if uploaded_file:

    raw = uploaded_file.getvalue()


    try:

        text_data = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError:

        text_data = raw.decode(
            "latin-1",
            errors="replace"
        )


    accounts, invalid = parse_accounts(
        text_data
    )


    # ========================================================
    # FILE STATS
    # ========================================================

    c1, c2, c3 = st.columns(3)


    c1.metric(
        "Accounts loaded",
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


    # ========================================================
    # INVALID LINES
    # ========================================================

    if invalid:

        with st.expander(
            "⚠️ Invalid lines"
        ):

            for item in invalid[:100]:

                st.write(
                    f"Line {item['line']}: "
                    f"{item['content']}"
                )


# ============================================================
# SCAN
# ============================================================

if uploaded_file and accounts:

    start_button = st.button(

        "🚀 START SCAN",

        type="primary",

        use_container_width=True
    )


    if start_button:

        # ====================================================
        # UI ELEMENTS
        # ====================================================

        progress_bar = st.progress(
            0
        )


        status_box = st.empty()


        current_box = st.empty()


        # ====================================================
        # COUNTERS
        # ====================================================

        total = len(accounts)

        completed = 0

        errors = 0

        total_candidates = 0


        # ====================================================
        # GLOBAL RESULT
        # ====================================================

        all_bad = {}


        account_results = []


        # ====================================================
        # THREAD POOL
        # ====================================================

        with ThreadPoolExecutor(
            max_workers=workers
        ) as executor:


            futures = {}


            for account in accounts:

                future = executor.submit(
                    process_account,
                    account
                )

                futures[future] = (
                    account["email"]
                )


            # =================================================
            # COLLECT RESULTS
            # =================================================

            for future in as_completed(
                futures
            ):

                source_account = futures[
                    future
                ]


                try:

                    result = future.result()


                except Exception as exc:

                    result = {

                        "account":
                            source_account,

                        "status":
                            "ERROR",

                        "error":
                            str(exc),

                        "candidates":
                            0,

                        "found":
                            []
                    }


                completed += 1


                total_candidates += (
                    result["candidates"]
                )


                account_results.append(
                    result
                )


                if result["status"] != "OK":

                    errors += 1


                # =============================================
                # GLOBAL DEDUPLICATION
                # =============================================

                for item in result["found"]:

                    address = (
                        item["email"]
                        .lower()
                    )


                    if address not in all_bad:

                        all_bad[address] = {

                            "email":
                                address,

                            "type":
                                item["type"],

                            "source_account":
                                source_account
                        }


                # =============================================
                # PROGRESS
                # =============================================

                percent = (
                    completed / total
                )


                progress_bar.progress(
                    percent
                )


                status_box.markdown(

                    f"""
**Processed:** {completed}/{total}  
**Confirmed bad:** {len(all_bad)}  
**Account errors:** {errors}
"""
                )


                current_box.caption(
                    f"Finished: {source_account}"
                )


                time.sleep(
                    0.03
                )


        # ====================================================
        # FINISHED
        # ====================================================

        progress_bar.progress(
            1.0
        )


        status_box.success(
            "Scan completed."
        )


        # ====================================================
        # SORT RESULTS
        # ====================================================

        final_results = sorted(

            all_bad.values(),

            key=lambda x:
                x["email"]
        )


        nonexistent = [

            x

            for x in final_results

            if x["type"]
            == "nonexistent"
        ]


        disabled = [

            x

            for x in final_results

            if x["type"]
            == "disabled"
        ]


        # ====================================================
        # METRICS
        # ====================================================

        st.divider()


        m1, m2, m3, m4 = st.columns(
            4
        )


        m1.metric(
            "Accounts scanned",
            completed
        )


        m2.metric(
            "Confirmed bad",
            len(final_results)
        )


        m3.metric(
            "Doesn't exist",
            len(nonexistent)
        )


        m4.metric(
            "Disabled",
            len(disabled)
        )


        # ====================================================
        # IMPORTANT INFO
        # ====================================================

        st.info(
            "Deferred, temporary failures, sender limits, "
            "5.7.x policy errors and mailbox-full responses "
            "are NOT added to the bad-email list."
        )


        # ====================================================
        # RESULT TABLE
        # ====================================================

        st.subheader(
            "Confirmed Bad Recipients"
        )


        if final_results:

            st.dataframe(

                final_results,

                use_container_width=True,

                hide_index=True
            )


            # =================================================
            # DOWNLOAD DATA
            # =================================================

            csv_data = make_csv(
                final_results
            )


            txt_data = make_txt(
                final_results
            )


            d1, d2 = st.columns(
                2
            )


            with d1:

                st.download_button(

                    "⬇️ Download CSV",

                    data=csv_data,

                    file_name=(
                        "confirmed_bad_emails.csv"
                    ),

                    mime="text/csv",

                    use_container_width=True
                )


            with d2:

                st.download_button(

                    "⬇️ Download TXT",

                    data=txt_data,

                    file_name=(
                        "confirmed_bad_emails.txt"
                    ),

                    mime="text/plain",

                    use_container_width=True
                )


        else:

            st.success(
                "No confirmed nonexistent/disabled "
                "recipients were found."
            )


        # ====================================================
        # ACCOUNT STATUS
        # ====================================================

        with st.expander(
            "📊 Source Account Status"
        ):

            safe_results = []


            for result in account_results:

                safe_results.append({

                    "account":
                        result["account"],

                    "status":
                        result["status"],

                    "DSN candidates":
                        result["candidates"],

                    "confirmed bad":
                        len(
                            result["found"]
                        ),

                    "error":
                        result["error"]
                })


            st.dataframe(

                safe_results,

                use_container_width=True,

                hide_index=True
            )
