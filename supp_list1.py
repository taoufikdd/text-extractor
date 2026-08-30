import streamlit as st
import requests
import pandas as pd
import json
import os
import tempfile
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Everflow Suppression Direct Downloader", page_icon="🛡️", layout="wide")

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

def download_suppression_file_bytes(suppression_id, headers):
    """
    Downloads the raw suppression file (Zip/Rar/Csv) directly via API using headers
    """
    if not suppression_id or str(suppression_id) == "0":
        return None, None

    endpoints = [
        f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}/download",
        f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}"
    ]
    
    session = get_session()
    for ep in endpoints:
        try:
            res = session.get(ep, headers=headers, timeout=30, verify=False)
            if res.status_code == 200:
                # If JSON returned with a download url inside
                if "application/json" in res.headers.get("Content-Type", ""):
                    try:
                        data = res.json()
                        file_url = data.get("download_url") or data.get("url") or data.get("file_url")
                        if file_url:
                            file_res = session.get(file_url, timeout=40, verify=False)
                            if file_res.status_code == 200:
                                ext = "zip" if "zip" in file_url.lower() else ("rar" if "rar" in file_url.lower() else "file")
                                return file_res.content, ext
                    except Exception:
                        pass
                else:
                    # Direct binary file response
                    cd = res.headers.get("Content-Disposition", "")
                    ext = "zip"
                    if "rar" in cd.lower():
                        ext = "rar"
                    elif "csv" in cd.lower():
                        ext = "csv"
                    elif "txt" in cd.lower():
                        ext = "txt"
                    return res.content, ext
        except Exception:
            continue
            
    return None, None

st.title("🛡️ Everflow Direct Suppression Downloader")

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
        with st.spinner("Fetching offers list..."):
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

                        supp_id = offer.get("suppression_list_id", 0)
                        if not supp_id or str(supp_id) == "0":
                            rel = offer.get("relationship", {})
                            if isinstance(rel, dict):
                                supp_obj = rel.get("suppression_list", {})
                                if isinstance(supp_obj, dict):
                                    supp_id = supp_obj.get("network_suppression_list_id") or supp_obj.get("suppression_list_id", 0)

                        str_supp_id = str(supp_id) if supp_id else "0"

                        processed.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "Suppression Found": "Yes" if str_supp_id != "0" else "No",
                            "Suppression ID": str_supp_id
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed)
                    st.session_state["sponsor_name"] = sponsor_name
                    st.session_state["headers_used"] = headers_used
                    st.success(f"Scanned {len(processed)} offers successfully!")
            except Exception as e:
                st.error(f"Error: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    st.subheader("📋 Offers & Direct File Downloads")
    
    # Filter only offers with Suppression ID
    supp_df = df[df["Suppression ID"] != "0"].copy()
    
    st.write(f"لقينا **{len(supp_df)}** Offer فيه Suppression File جاهز للتحميل المباشر:")

    # Display interactive list with direct download buttons per offer
    for idx, row in supp_df.iterrows():
        col1, col2, col3, col4 = st.columns([1, 4, 2, 3])
        with col1:
            st.write(f"**#{row['Offer ID']}**")
        with col2:
            st.write(row['Offer Name'])
        with col3:
            st.write(f"Supp ID: `{row['Suppression ID']}`")
        with col4:
            # Dynamic download button for each offer
            btn_key = f"dl_{row['Offer ID']}_{row['Suppression ID']}"
            if st.button(f"⬇️ Get File (Offer {row['Offer ID']})", key=btn_key):
                with st.spinner("Downloading raw file via API..."):
                    file_bytes, ext = download_suppression_file_bytes(row['Suppression ID'], headers_used)
                    if file_bytes:
                        st.download_button(
                            label=f"💾 Save {row['Offer ID']}_suppression.{ext}",
                            data=file_bytes,
                            file_name=f"Offer_{row['Offer ID']}_Suppression_{row['Suppression ID']}.{ext}",
                            mime="application/octet-stream",
                            key=f"save_{btn_key}"
                        )
                    else:
                        st.error("Could not fetch file directly. API permissions might block direct downloads for this ID.")
