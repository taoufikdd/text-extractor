import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import gzip
import io
import os
import re
import gc
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

# تعطيل تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Affiliate Suppression List Merger", page_icon="🛡️", layout="wide")

@st.cache_resource
def get_http_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*"
    })
    return session

http_session = get_http_session()

def fetch_single_page(base_endpoint, page, page_size, headers):
    urls_to_try = [
        f"{base_endpoint}?page={page}&page_size={page_size}&relationship=all&offer_status=all",
        f"{base_endpoint}?page={page}&page_size={page_size}"
    ]
    for target_url in urls_to_try:
        try:
            res = http_session.get(target_url, headers=headers, timeout=15, verify=False)
            if res.status_code == 200:
                json_data = res.json()
                if isinstance(json_data, list):
                    return json_data
                elif isinstance(json_data, dict):
                    for k in ["offers", "data", "results", "items"]:
                        if k in json_data and isinstance(json_data[k], list):
                            return json_data[k]
        except Exception:
            continue
    return []

def fetch_all_offers_everflow(base_url, auth_method, api_key, custom_header_name):
    headers = {}
    clean_url = base_url.strip()
    
    if "eflow" in clean_url.lower() or "everflow" in clean_url.lower():
        if "/v1/affiliates/offers" in clean_url and "/alloffers" not in clean_url:
            clean_url = clean_url.replace("/v1/affiliates/offers", "/v1/affiliates/alloffers")
        if custom_header_name.lower() == "x-eflow-api-key":
            custom_header_name = "X-Eflow-Api-Key"

    if auth_method == "Bearer Token":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_method == "X-API-Key":
        headers["X-API-Key"] = api_key
    elif auth_method == "API-Key":
        headers["API-Key"] = api_key
    elif auth_method == "Custom Header" and custom_header_name:
        headers[custom_header_name.strip()] = api_key.strip()

    base_endpoint = clean_url.split("?")[0]
    first_page = fetch_single_page(base_endpoint, 1, 500, headers)
    if not first_page:
        return [], headers

    all_offers = list(first_page)
    
    if len(first_page) >= 500:
        max_pages_to_check = 20
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_single_page, base_endpoint, p, 500, headers): p for p in range(2, max_pages_to_check + 1)}
            for future in as_completed(futures):
                chunk = future.result()
                if chunk:
                    all_offers.extend(chunk)

    return all_offers, headers

def deep_search_suppression_url(obj):
    if not obj:
        return ""
    try:
        str_obj = json.dumps(obj)
    except Exception:
        str_obj = str(obj)

    patterns = [
        r'https?://[^\s"]+\.(?:zip|gz|csv|txt|tar)[^\s"]*',
        r'https?://[^\s"]*optizmo[^\s"]*',
        r'https?://[^\s"]*unsubcentral[^\s"]*',
        r'https?://[^\s"]*suppress[^\s"]*',
        r'https?://[^\s"]*download[^\s"]*'
    ]
    
    for pat in patterns:
        matches = re.findall(pat, str_obj, re.IGNORECASE)
        if matches:
            return str(matches[0])

    if isinstance(obj, dict):
        for key in ["download_url", "file_url", "url", "opt_out_url", "unsubscribe_url", "suppression_download_url"]:
            val = obj.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                return val

    return ""

def fetch_suppression_url_by_id(supp_id, headers):
    if not supp_id or str(supp_id) == "0":
        return ""
    try:
        url = f"https://api.eflow.team/v1/affiliates/suppressionlists/{supp_id}"
        res = http_session.get(url, headers=headers, timeout=8, verify=False)
        if res.status_code == 200:
            return deep_search_suppression_url(res.json())
    except Exception:
        pass
    return ""

def resolve_optizmo_or_direct_download(url):
    if not url or not isinstance(url, str):
        return ""

    url_str = url.strip()

    if "optizmo" in url_str.lower():
        if not url_str.endswith("/download") and not re.search(r'\.(zip|gz|txt|csv)$', url_str, re.I):
            url_str = url_str.rstrip("/") + "/download"

    try:
        res = http_session.get(url_str, timeout=12, verify=False, allow_redirects=True)
        if "text/html" in res.headers.get("Content-Type", "").lower():
            html_text = res.text
            found_dl = re.findall(r'href=["\'](https?://[^"\']+\.(?:zip|gz|csv|txt))[["\']', html_text, re.I)
            if found_dl:
                return found_dl[0]
            
            optizmo_dl = re.findall(r'https?://[^\s"\'<>]*/download[^\s"\'<>]*', html_text, re.I)
            if optizmo_dl:
                return optizmo_dl[0]

        return res.url
    except Exception:
        return url_str

def parse_emails_from_stream(stream_data):
    """استخراج الإيميلات كتل كتل للحفاظ على الـ RAM"""
    emails = set()
    email_regex = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    
    # 1. تجربة ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(stream_data)) as z:
            for zip_info in z.infolist():
                if zip_info.is_dir():
                    continue
                with z.open(zip_info.filename) as f:
                    for line in f:
                        line_str = line.decode('utf-8', errors='ignore')
                        matches = email_regex.findall(line_str)
                        if matches:
                            emails.update([e.lower().strip() for e in matches])
        if emails:
            return emails
    except Exception:
        pass

    # 2. تجربة GZIP
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(stream_data)) as gz:
            for line in gz:
                line_str = line.decode('utf-8', errors='ignore')
                matches = email_regex.findall(line_str)
                if matches:
                    emails.update([e.lower().strip() for e in matches])
        if emails:
            return emails
    except Exception:
        pass

    # 3. Plain text / CSV
    try:
        text_str = stream_data.decode('utf-8', errors='ignore')
        matches = email_regex.findall(text_str)
        if matches:
            emails.update([e.lower().strip() for e in matches])
    except Exception:
        pass

    return emails

def fetch_and_extract_emails_from_offer(offer_row, headers_used):
    emails = set()
    dl_url = offer_row.get("Direct_URL")
    
    if not dl_url or not isinstance(dl_url, str) or dl_url.strip() == "":
        dl_url = fetch_suppression_url_by_id(offer_row.get("Suppression ID"), headers_used)

    if dl_url and isinstance(dl_url, str) and dl_url.startswith("http"):
        try:
            download_target = resolve_optizmo_or_direct_download(dl_url) or dl_url
            res = http_session.get(download_target, timeout=30, verify=False, stream=True)
            if res.status_code == 200:
                content_bytes = res.content
                emails = parse_emails_from_stream(content_bytes)
                del content_bytes
                gc.collect()
        except Exception:
            pass
    return emails

# --- UI Interface ---
st.title("🛡️ Memory-Safe Suppression List Merger")

with st.sidebar:
    st.header("Sponsor Configuration")
    sponsor_name = st.text_input("Sponsor Name", value="XI Leads")
    api_url = st.text_input("API Endpoint URL", value="https://api.eflow.team/v1/affiliates/alloffers")
    auth_method = st.selectbox("Authentication Method", ["Custom Header", "Bearer Token", "X-API-Key", "API-Key", "No Authentication"])
    
    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input("Custom Header Name", value="X-Eflow-Api-Key")

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input("API Key / Token", type="password")

    scan_submitted = st.button("Scan All Offers (Active + Paused)", use_container_width=True, type="primary")

if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("المرجو إدخال البيانات المطلوبة.")
    else:
        with st.spinner("جاري فحص جميع العروض..."):
            try:
                offers_list, headers_used = fetch_all_offers_everflow(api_url, auth_method, api_key, custom_header_name)

                if not offers_list:
                    st.warning("تم الاتصال بنجاح، لكن لم يتم العثور على عروض.")
                else:
                    processed_records = []
                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = offer.get("network_offer_id") or offer.get("offer_id") or offer.get("id", "N/A")
                        offer_name = offer.get("name") or offer.get("title", "N/A")
                        offer_status = offer.get("offer_status", "N/A")

                        geo_info = "N/A"
                        if "relationship" in offer and isinstance(offer["relationship"], dict):
                            geos = offer["relationship"].get("target_countries", [])
                            if geos:
                                geo_info = ", ".join([g.get("code", str(g)) if isinstance(g, dict) else str(g) for g in geos])

                        has_supp = offer.get("is_using_suppression_list", False)
                        supp_id = offer.get("suppression_list_id", 0)
                        
                        if not supp_id or str(supp_id) == "0":
                            rel = offer.get("relationship", {})
                            if isinstance(rel, dict):
                                supp_obj = rel.get("suppression_list", {})
                                if isinstance(supp_obj, dict):
                                    supp_id = supp_obj.get("network_suppression_list_id") or supp_obj.get("suppression_list_id", 0)

                        dl_url = deep_search_suppression_url(offer)
                        has_suppression = "Yes" if (has_supp or (supp_id and str(supp_id) != "0") or dl_url) else "No"

                        processed_records.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "GEO": geo_info,
                            "Suppression Found": has_suppression,
                            "Suppression ID": str(supp_id),
                            "Direct_URL": dl_url if dl_url else ""
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.session_state["headers_used"] = headers_used
                    st.session_state["sponsor_name"] = sponsor_name
                    st.success(f"تم فحص جميع العروض بنجاح! الإجمالي: {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    display_df = df.drop(columns=["Direct_URL"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("⚡ دمج سريع وتنقية جميع ملفات الـ Suppression")
        st.info(f"تم إيجاد {len(supp_df)} عرض يحتوي على ملفات Suppression.")

        if st.button("🚀 Fast Merge & Clean All Suppressions", type="primary", use_container_width=True):
            all_unique_emails = set()
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_offers = len(supp_df)
            completed = 0
            rows_list = supp_df.to_dict('records')

            # خفض عدد الـ workers إلى 4 لتفادي الـ Crash بسبب الـ RAM limit
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_offer = {executor.submit(fetch_and_extract_emails_from_offer, row, headers_used): row for row in rows_list}
                
                for future in as_completed(future_to_offer):
                    completed += 1
                    status_text.text(f"معالجة الملفات بنجاح فـ الـ Memory: ({completed}/{total_offers})...")
                    progress_bar.progress(completed / total_offers)
                    
                    try:
                        extracted = future.result()
                        all_unique_emails.update(extracted)
                        del extracted
                        gc.collect()
                    except Exception:
                        pass

            status_text.empty()
            progress_bar.empty()

            if all_unique_emails:
                cleaned_content = "\n".join(sorted(all_unique_emails))
                st.success(f"⚡ اكتملت العملية! تم استخراج {len(all_unique_emails):,} إيميل فريد.")

                st.download_button(
                    label=f"💾 تحميل ملف الإيميلات المدمج النهائي ({len(all_unique_emails):,} Emails)",
                    data=cleaned_content,
                    file_name=f"suppression_emails_{s_name.replace(' ', '_')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            else:
                st.warning("لم يتم العثور على إيميلات فـ الملفات المفحوصة.")
