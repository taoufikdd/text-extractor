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

st.set_page_config(page_title="Affiliate Suppression Links & Extractor", page_icon="🛡️", layout="wide")

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

def deep_search_url(obj):
    if not obj:
        return ""
    try:
        str_obj = json.dumps(obj)
    except Exception:
        str_obj = str(obj)

    patterns = [
        r'https?://[^\s"]+\.(?:zip|rar|7z|gz|csv|txt|tar)[^\s"]*',
        r'https?://[^\s"]*optizmo[^\s"]*',
        r'https?://[^\s"]*unsubcentral[^\s"]*',
        r'https?://[^\s"]*suppress[^\s"]*'
    ]
    
    for pat in patterns:
        m = re.findall(pat, str_obj, re.IGNORECASE)
        if m:
            return str(m[0])
    return ""

def parse_stream_lines(file_obj, temp_file_path):
    count = 0
    with open(temp_file_path, "a", encoding="utf-8") as out:
        for line in file_obj:
            for em in EMAIL_REGEX.findall(line):
                out.write(em.decode('utf-8', errors='ignore').lower() + "\n")
                count += 1
    return count

def extract_emails_from_uploaded_files(uploaded_files, output_temp_file):
    total_count = 0
    for uploaded_file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False) as raw_tmp:
            raw_tmp.write(uploaded_file.read())
            raw_path = raw_tmp.name

        # 1. ZIP
        try:
            with zipfile.ZipFile(raw_path, 'r') as z:
                for name in z.namelist():
                    if not name.endswith('/'):
                        with z.open(name) as zf:
                            total_count += parse_stream_lines(zf, output_temp_file)
            os.remove(raw_path)
            continue
        except Exception:
            pass

        # 2. RAR
        try:
            with rarfile.RarFile(raw_path, 'r') as rf:
                for name in rf.namelist():
                    if not name.endswith('/'):
                        with rf.open(name) as rff:
                            total_count += parse_stream_lines(rff, output_temp_file)
            os.remove(raw_path)
            continue
        except Exception:
            pass

        # 3. TAR
        try:
            with tarfile.open(raw_path, 'r:*') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            total_count += parse_stream_lines(f, output_temp_file)
            os.remove(raw_path)
            continue
        except Exception:
            pass

        # 4. GZIP
        try:
            with gzip.open(raw_path, 'rb') as gz:
                total_count += parse_stream_lines(gz, output_temp_file)
            os.remove(raw_path)
            continue
        except Exception:
            pass

        # 5. Plain Text / CSV
        try:
            with open(raw_path, 'rb') as f:
                total_count += parse_stream_lines(f, output_temp_file)
            os.remove(raw_path)
            continue
        except Exception:
            pass

        if os.path.exists(raw_path):
            os.remove(raw_path)
            
    return total_count

st.title("🛡️ Suppression Offers Link Extractor & Manual Cleaner")

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
                        
                        # Generate manual direct link for Everflow UI if URL not in API
                        portal_base = api_url.split("/v1/")[0].replace("api.", "")
                        ui_link = f"{portal_base}/offers/{offer_id}"

                        processed.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "Suppression Found": has_suppression,
                            "Suppression ID": str(supp_id),
                            "Direct Download Link": dl_url if dl_url else "N/A",
                            "Offer Portal Link": ui_link
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed)
                    st.session_state["sponsor_name"] = sponsor_name
                    st.success(f"Scanned {len(processed)} offers successfully.")
            except Exception as e:
                st.error(f"Error: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    st.subheader("📋 Offers & Suppression Links")
    
    # Show Data Editor with clickable links
    st.dataframe(
        df,
        column_config={
            "Direct Download Link": st.column_config.LinkColumn("Direct Download Link"),
            "Offer Portal Link": st.column_config.LinkColumn("Offer Portal Link")
        },
        use_container_width=True
    )

    # Export CSV of Links
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CSV List of All Offers & Links",
        data=csv_data,
        file_name=f"suppression_offers_list_{s_name}.csv",
        mime="text/csv"
    )

    st.markdown("---")
    st.subheader("📦 Bulk Cleaner: Upload Downloaded Files (Zip/Rar/Txt)")
    st.write("ملي تليشارجي الملفات يدوياً، حطهم كاملين هنا باش يجمعهم فـ ملف واحد خالي من التكرار وبدون حدود للـ Size:")
    
    uploaded_files = st.file_uploader("Upload Suppression Archives/Files", accept_multiple_files=True)
    
    if uploaded_files and st.button("🚀 Clean & Merge Uploaded Files", type="primary"):
        with st.spinner("Extracting and cleaning emails..."):
            with tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8") as tmp_merged:
                tmp_path = tmp_merged.name

            total_extracted = extract_emails_from_uploaded_files(uploaded_files, tmp_path)

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

                st.success(f"Done! Cleaned {unique_count:,} unique emails from {total_extracted:,} total extracted.")
                
                with open(final_temp_path, "rb") as f_download:
                    st.download_button(
                        label=f"💾 Download Cleaned Master List ({unique_count:,} Emails)",
                        data=f_download,
                        file_name=f"master_suppression_{s_name}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error: {str(e)}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if os.path.exists(final_temp_path):
                    os.remove(final_temp_path)
