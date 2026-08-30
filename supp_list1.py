import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import gzip
import tarfile
import rarfile
import os
import re
import tempfile
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Everflow Suppression Fetcher", page_icon="🛡️", layout="wide")

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
            futures = [executor.submit(fetch_single_page, base_endpoint, p, 500, headers) for p in range(2, 25)]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        all_offers.extend(res)
                except Exception:
                    pass

    return all_offers, headers

def fetch_suppression_download_url(suppression_id, headers):
    """
    Fetch the direct download URL for a specific suppression_id via Everflow API
    """
    if not suppression_id or str(suppression_id) == "0":
        return ""

    endpoints = [
        f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}",
        f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}/download",
        f"https://api.eflow.team/v1/networks/suppressionlists/{suppression_id}"
    ]
    
    session = get_session()
    for ep in endpoints:
        try:
            res = session.get(ep, headers=headers, timeout=8, verify=False)
            if res.status_code == 200:
                data = res.json()
                str_data = json.dumps(data)
                
                # Check direct fields
                for key in ["download_url", "url", "file_url", "location"]:
                    if isinstance(data, dict) and key in data and data[key]:
                        return str(data[key])
                
                # Search full HTTP links inside JSON
                m = re.findall(r'https?://[^\s"]+\.(?:zip|rar|7z|gz|csv|txt|tar)[^\s"]*', str_data, re.I)
                if m:
                    return m[0]
                
                # Search Optizmo or Unsubcentral
                m_opt = re.findall(r'https?://[^\s"]*(?:optizmo|unsubcentral|suppress)[^\s"]*', str_data, re.I)
                if m_opt:
                    return m_opt[0]
        except Exception:
            continue
            
    return ""

def parse_stream_lines(file_obj, temp_file_path):
    count = 0
    with open(temp_file_path, "a", encoding="utf-8") as out:
        for line in file_obj:
            for em in EMAIL_REGEX.findall(line):
                out.write(em.decode('utf-8', errors='ignore').lower() + "\n")
                count += 1
    return count

def stream_extract_to_file(temp_file_path, url):
    session = get_session()
    count = 0
    try:
        with session.get(url, stream=True, timeout=90, verify=False) as resp:
            if resp.status_code != 200:
                return 0
            
            with tempfile.NamedTemporaryFile(delete=False) as raw_tmp:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        raw_tmp.write(chunk)
                raw_path = raw_tmp.name

            # 1. ZIP
            try:
                with zipfile.ZipFile(raw_path, 'r') as z:
                    for name in z.namelist():
                        if not name.endswith('/'):
                            with z.open(name) as zf:
                                count += parse_stream_lines(zf, temp_file_path)
                os.remove(raw_path)
                return count
            except Exception:
                pass

            # 2. RAR
            try:
                with rarfile.RarFile(raw_path, 'r') as rf:
                    for name in rf.namelist():
                        if not name.endswith('/'):
                            with rf.open(name) as rff:
                                count += parse_stream_lines(rff, temp_file_path)
                os.remove(raw_path)
                return count
            except Exception:
                pass

            # 3. GZIP / Plain Text
            try:
                with open(raw_path, 'rb') as f:
                    count += parse_stream_lines(f, temp_file_path)
                os.remove(raw_path)
                return count
            except Exception:
                pass

            if os.path.exists(raw_path):
                os.remove(raw_path)

    except Exception:
        pass
    return count

st.title("🛡️ Everflow Suppression Link Extractor & Auto-Downloader")

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

    scan_submitted = st.button("Scan All Offers & Fetch Links", use_container_width=True, type="primary")

if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("Please fill in required fields.")
    else:
        with st.spinner("Step 1: Fetching all offers..."):
            try:
                offers_list, headers_used = fetch_all_offers(api_url, auth_method, api_key, custom_header_name)

                if not offers_list:
                    st.warning("No offers found.")
                else:
                    st.info(f"Fetched {len(offers_list)} offers. Step 2: Querying Suppression API for download links...")
                    
                    # Process initial offer metadata
                    raw_processed = []
                    supp_ids_to_fetch = {}

                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = offer.get("network_offer_id") or offer.get("offer_id") or offer.get("id", "N/A")
                        offer_name = offer.get("name") or offer.get("title", "N/A")
                        offer_status = offer.get("offer_status", "N/A")

                        supp_id = offer.get("suppression_list_id", 0)
                        if not supp_id or str(supp_id) == "0":
                            rel = offer.get("relationship", {})
                            if isinstance(rel, dict):
                                supp_obj = rel.get("suppression_list", {})
                                if isinstance(supp_obj, dict):
                                    supp_id = supp_obj.get("network_suppression_list_id") or supp_obj.get("suppression_list_id", 0)

                        str_supp_id = str(supp_id) if supp_id else "0"
                        if str_supp_id != "0":
                            supp_ids_to_fetch[str_supp_id] = None

                        raw_processed.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "Suppression Found": "Yes" if str_supp_id != "0" else "No",
                            "Suppression ID": str_supp_id,
                            "Direct File URL": "N/A"
                        })

                    # Parallel Fetch Download URLs for unique Suppression IDs
                    if supp_ids_to_fetch:
                        prog = st.progress(0)
                        st_text = st.empty()
                        total_sids = len(supp_ids_to_fetch)
                        completed = 0

                        with ThreadPoolExecutor(max_workers=5) as executor:
                            future_to_sid = {
                                executor.submit(fetch_suppression_download_url, sid, headers_used): sid 
                                for sid in supp_ids_to_fetch.keys()
                            }
                            for future in as_completed(future_to_sid):
                                sid = future_to_sid[future]
                                completed += 1
                                prog.progress(completed / total_sids)
                                st_text.text(f"Extracting file URLs for Suppression ID {sid} ({completed}/{total_sids})...")
                                try:
                                    url_found = future.result()
                                    if url_found:
                                        supp_ids_to_fetch[sid] = url_found
                                except Exception:
                                    pass
                        prog.empty()
                        st_text.empty()

                    # Attach fetched URLs back to dataset
                    for item in raw_processed:
                        sid = item["Suppression ID"]
                        if sid in supp_ids_to_fetch and supp_ids_to_fetch[sid]:
                            item["Direct File URL"] = supp_ids_to_fetch[sid]

                    st.session_state["scan_results"] = pd.DataFrame(raw_processed)
                    st.session_state["sponsor_name"] = sponsor_name
                    st.success(f"Scanned {len(raw_processed)} offers successfully!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    st.subheader("📋 Offers List & Direct File Download Links")

    st.dataframe(
        df,
        column_config={
            "Direct File URL": st.column_config.LinkColumn("Direct File URL", help="Click to download suppression file directly")
        },
        use_container_width=True
    )

    # Export CSV of Links
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CSV List of Offers & Links",
        data=csv_data,
        file_name=f"suppression_offers_{s_name}.csv",
        mime="text/csv"
    )

    supp_df = df[df["Direct File URL"] != "N/A"]
    
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("⚡ Bulk Auto-Download & Clean Emails")
        st.write(f"لقينا **{len(supp_df)}** رابط مباشر جاهز للتحميل والدمج تلقائياً:")

        if st.button("🚀 Download All Files & Auto-Extract Clean Emails", type="primary", use_container_width=True):
            progress = st.progress(0)
            status_text = st.empty()
            
            rows = supp_df.to_dict('records')
            total = len(rows)

            with tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8") as tmp_merged:
                tmp_path = tmp_merged.name

            total_extracted = 0
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(stream_extract_to_file, tmp_path, r["Direct File URL"]): r for r in rows if r["Direct File URL"].startswith("http")}
                completed = 0
                for f in as_completed(futures):
                    completed += 1
                    progress.progress(completed / total)
                    try:
                        count = f.result()
                        total_extracted += count
                        status_text.text(f"Processed file {completed}/{total} - Extracted ~{total_extracted:,} emails...")
                    except Exception:
                        pass

            progress.empty()
            status_text.text("Sorting & Deduplicating extracted emails...")

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

                status_text.empty()
                if unique_count > 0:
                    st.success(f"Done! Extracted & cleaned {unique_count:,} unique emails (from {total_extracted:,} total).")
                    with open(final_temp_path, "rb") as f_download:
                        st.download_button(
                            label=f"💾 Download Cleaned Master File ({unique_count:,} Emails)",
                            data=f_download,
                            file_name=f"suppression_master_{s_name.replace(' ', '_')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                else:
                    st.warning("No emails extracted. Check if the generated links require active browser login.")
            except Exception as e:
                st.error(f"Error: {str(e)}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if os.path.exists(final_temp_path):
                    os.remove(final_temp_path)
