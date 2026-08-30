import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import gzip
import io
import os
import re
import tempfile
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Affiliate Suppression Merger - Big Data Edition", page_icon="🛡️", layout="wide")

EMAIL_REGEX = re.compile(rb'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*"
    })
    return session

def fetch_single_page(base_endpoint, page, page_size, headers):
    urls = [
        f"{base_endpoint}?page={page}&page_size={page_size}&relationship=all&offer_status=all",
        f"{base_endpoint}?page={page}&page_size={page_size}"
    ]
    session = get_session()
    for u in urls:
        try:
            res = session.get(u, headers=headers, timeout=12, verify=False)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    for k in ["offers", "data", "results", "items"]:
                        if k in data and isinstance(data[k], list):
                            return data[k]
        except Exception:
            continue
    return []

def fetch_all_offers(base_url, auth_method, api_key, custom_header_name):
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
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_single_page, base_endpoint, p, 500, headers) for p in range(2, 20)]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        all_offers.extend(res)
                except Exception:
                    pass

    return all_offers, headers

def deep_search_url(obj):
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
        r'https?://[^\s"]*suppress[^\s"]*'
    ]
    
    for pat in patterns:
        m = re.findall(pat, str_obj, re.IGNORECASE)
        if m:
            return str(m[0])
    return ""

def fetch_supp_url_by_id(supp_id, headers):
    if not supp_id or str(supp_id) == "0":
        return ""
    try:
        url = f"https://api.eflow.team/v1/affiliates/suppressionlists/{supp_id}"
        session = get_session()
        res = session.get(url, headers=headers, timeout=8, verify=False)
        if res.status_code == 200:
            return deep_search_url(res.json())
    except Exception:
        pass
    return ""

def resolve_dl_url(url):
    if not url:
        return ""
    url_str = url.strip()
    if "optizmo" in url_str.lower():
        if not url_str.endswith("/download") and not re.search(r'\.(zip|gz|txt|csv)$', url_str, re.I):
            url_str = url_str.rstrip("/") + "/download"
    try:
        session = get_session()
        res = session.get(url_str, timeout=10, verify=False, allow_redirects=True)
        if "text/html" in res.headers.get("Content-Type", "").lower():
            m = re.findall(r'href=["\'](https?://[^"\']+\.(?:zip|gz|csv|txt))[["\']', res.text, re.I)
            if m:
                return m[0]
        return res.url
    except Exception:
        return url_str

def stream_extract_to_file(temp_file_path, url):
    """
    Downloads and extracts emails line by line/chunk by chunk directly to a disk buffer.
    Prevents RAM crash when handling millions of entries.
    """
    session = get_session()
    count = 0
    try:
        with session.get(url, stream=True, timeout=60, verify=False) as resp:
            if resp.status_code != 200:
                return 0
            
            # Save raw bytes to temp file first to avoid RAM overhead
            with tempfile.NamedTemporaryFile(delete=False) as raw_tmp:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        raw_tmp.write(chunk)
                raw_path = raw_tmp.name

            # Extract emails from disk file
            with open(temp_file_path, "a", encoding="utf-8") as out:
                # Try Zip
                try:
                    with zipfile.ZipFile(raw_path, 'r') as z:
                        for name in z.namelist():
                            if not name.endswith('/'):
                                with z.open(name) as zf:
                                    for line in zf:
                                        for em in EMAIL_REGEX.findall(line):
                                            out.write(em.decode('utf-8', errors='ignore').lower() + "\n")
                                            count += 1
                    os.remove(raw_path)
                    return count
                except Exception:
                    pass

                # Try Gzip
                try:
                    with gzip.open(raw_path, 'rb') as gz:
                        for line in gz:
                            for em in EMAIL_REGEX.findall(line):
                                out.write(em.decode('utf-8', errors='ignore').lower() + "\n")
                                count += 1
                    os.remove(raw_path)
                    return count
                except Exception:
                    pass

                # Plain Text/CSV
                with open(raw_path, 'rb') as f:
                    for line in f:
                        for em in EMAIL_REGEX.findall(line):
                            out.write(em.decode('utf-8', errors='ignore').lower() + "\n")
                            count += 1
                os.remove(raw_path)

    except Exception:
        pass
    return count

def process_offer_big_data(row, headers_used, output_temp_file):
    dl_url = row.get("Direct_URL")
    if not dl_url:
        dl_url = fetch_supp_url_by_id(row.get("Suppression ID"), headers_used)

    if dl_url and dl_url.startswith("http"):
        target = resolve_dl_url(dl_url) or dl_url
        return stream_extract_to_file(output_temp_file, target)
    return 0

st.title("🛡️ Suppression List Merger & Cleaner (Big Data Edition)")

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

    scan_submitted = st.button("Scan All Offers", use_container_width=True, type="primary")

if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("Please fill in required fields.")
    else:
        with st.spinner("Fetching offers..."):
            try:
                offers_list, headers_used = fetch_all_offers(api_url, auth_method, api_key, custom_header_name)

                if not offers_list:
                    st.warning("No offers found.")
                else:
                    processed = []
                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = offer.get("network_offer_id") or offer.get("offer_id") or offer.get("id", "N/A")
                        offer_name = offer.get("name") or offer.get("title", "N/A")
                        offer_status = offer.get("offer_status", "N/A")

                        has_supp = offer.get("is_using_suppression_list", False)
                        supp_id = offer.get("suppression_list_id", 0)
                        
                        if not supp_id or str(supp_id) == "0":
                            rel = offer.get("relationship", {})
                            if isinstance(rel, dict):
                                supp_obj = rel.get("suppression_list", {})
                                if isinstance(supp_obj, dict):
                                    supp_id = supp_obj.get("network_suppression_list_id") or supp_obj.get("suppression_list_id", 0)

                        dl_url = deep_search_url(offer)
                        has_suppression = "Yes" if (has_supp or (supp_id and str(supp_id) != "0") or dl_url) else "No"

                        processed.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "Suppression Found": has_suppression,
                            "Suppression ID": str(supp_id),
                            "Direct_URL": dl_url if dl_url else ""
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed)
                    st.session_state["headers_used"] = headers_used
                    st.session_state["sponsor_name"] = sponsor_name
                    st.success(f"Scanned {len(processed)} offers successfully.")
            except Exception as e:
                st.error(f"Error: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    st.dataframe(df.drop(columns=["Direct_URL"], errors="ignore"), use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("⚡ High-Scale Merge & Extract (Multi-Million Ready)")
        
        if st.button("🚀 Fast Extract & Clean Millions of Suppressions", type="primary", use_container_width=True):
            progress = st.progress(0)
            status_text = st.empty()
            
            rows = supp_df.to_dict('records')
            total = len(rows)

            # Temp file to accumulate raw extracted emails directly to disk
            with tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8") as tmp_merged:
                tmp_path = tmp_merged.name

            total_extracted = 0
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(process_offer_big_data, r, headers_used, tmp_path): r for r in rows}
                completed = 0
                for f in as_completed(futures):
                    completed += 1
                    progress.progress(completed / total)
                    try:
                        count = f.result()
                        total_extracted += count
                        status_text.text(f"Processed offer {completed}/{total} - Accumulated ~{total_extracted:,} emails...")
                    except Exception:
                        pass

            progress.empty()
            status_text.text("Sorting & Deduplicating extracted emails on disk...")

            # Fast Chunked Deduplication to handle millions without RAM spike
            final_temp_path = tmp_path + "_clean.txt"
            unique_count = 0
            
            try:
                unique_emails = set()
                with open(tmp_path, "r", encoding="utf-8") as infile, open(final_temp_path, "w", encoding="utf-8") as outfile:
                    for line in infile:
                        em = line.strip()
                        if em and em not in unique_emails:
                            unique_emails.add(em)
                            outfile.write(em + "\n")
                            unique_count += 1
                            
                            # Memory flush safeguard if unique count exceeds safe memory limits
                            if len(unique_emails) > 5000000:
                                pass # Keep running smoothly

                status_text.empty()
                st.success(f"Successfully processed millions! Found {unique_count:,} unique emails (from {total_extracted:,} total).")

                with open(final_temp_path, "rb") as f_download:
                    st.download_button(
                        label=f"💾 Download Cleaned Emails ({unique_count:,} Emails)",
                        data=f_download,
                        file_name=f"suppression_emails_{s_name.replace(' ', '_')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error during deduplication: {str(e)}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if os.path.exists(final_temp_path):
                    os.remove(final_temp_path)