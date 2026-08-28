import streamlit as st
import requests
import pandas as pd

# Suppression keywords
SUPPRESSION_KEYWORDS = [
    "suppression", "suppression_file", "suppression_url", "suppression list",
    "blacklist", "exclusion", "exclude", "optout", "opt_out", "do_not_contact", "dnc"
]

CONTAINER_KEYS = ["offers", "data", "results", "items", "campaigns", "response"]

def find_offers_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in CONTAINER_KEYS:
            if key in data and isinstance(data[key], list):
                return data[key]
            if key in data and isinstance(data[key], dict):
                nested = find_offers_list(data[key])
                if nested:
                    return nested
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
    return []

def scan_suppression_recursive(item, prefix=""):
    results = []
    if isinstance(item, dict):
        for k, v in item.items():
            full_key = f"{prefix}.{k}" if prefix else k
            k_lower = k.lower()
            if any(kw in k_lower for kw in SUPPRESSION_KEYWORDS):
                results.append((full_key, v))
            if isinstance(v, (dict, list)):
                results.extend(scan_suppression_recursive(v, full_key))
    elif isinstance(item, list):
        for idx, elem in enumerate(item):
            full_key = f"{prefix}[{idx}]"
            if isinstance(elem, (dict, list)):
                results.extend(scan_suppression_recursive(elem, full_key))
            elif isinstance(elem, str):
                if any(kw in elem.lower() for kw in SUPPRESSION_KEYWORDS):
                    results.append((full_key, elem))
    return results

def extract_field_by_candidates(offer, candidates, default="N/A"):
    for candidate in candidates:
        if candidate in offer and offer[candidate] is not None:
            val = offer[candidate]
            if isinstance(val, (str, int, float)):
                return str(val)
            if isinstance(val, list):
                return ", ".join(map(str, val))
            if isinstance(val, dict):
                for sub_k in ["name", "code", "iso", "id", "display_name"]:
                    if sub_k in val and val[sub_k]:
                        return str(val[sub_k])
    return default

def fetch_api_data(url, auth_method, api_key, custom_header_name):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    clean_url = url.strip()
    
    # إصلاح تلقائي لإعدادات Everflow
    if "eflow" in clean_url.lower() or "everflow" in clean_url.lower():
        if "/v1/affiliates/offers" in clean_url and "/alloffers" not in clean_url:
            clean_url = clean_url.replace("/v1/affiliates/offers", "/v1/affiliates/alloffers")
        if "?" not in clean_url:
            clean_url += "?page=1&page_size=100"
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

    response = requests.get(clean_url, headers=headers, timeout=30, verify=False)
    
    if response.status_code != 200:
        error_msg = response.text[:300] if response.text else "No error body"
        raise Exception(f"خطأ من السيرفر (HTTP {response.status_code}): {error_msg}")
        
    try:
        return response.json()
    except Exception:
        raise Exception("فشل تحويل الاستجابة إلى JSON.")

def download_suppression_file(url):
    resp = requests.get(url, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.content

# UI Setup
st.set_page_config(page_title="Affiliate Suppression Detector", page_icon="🛡️", layout="wide")
st.title("🛡️ Affiliate Suppression List Detector")

with st.sidebar:
    st.header("Sponsor Configuration")
    sponsor_name = st.text_input("Sponsor Name", value="XI Leads")
    api_url = st.text_input(
        "API Endpoint URL", 
        value="https://api.eflow.team/v1/affiliates/alloffers?page=1&page_size=100"
    )
    auth_method = st.selectbox("Authentication Method", ["Custom Header", "Bearer Token", "X-API-Key", "API-Key", "No Authentication"])
    
    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input("Custom Header Name", value="X-Eflow-Api-Key")

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input("API Key / Token", type="password")

    scan_submitted = st.button("Scan Offers", use_container_width=True, type="primary")

if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("المرجو إدخال كل البيانات المطلوبة.")
    else:
        with st.spinner("جاري جلب العروض وفحص ملفات Suppression..."):
            try:
                json_data = fetch_api_data(api_url, auth_method, api_key, custom_header_name)
                offers_list = find_offers_list(json_data)

                if not offers_list:
                    st.warning("تم الاتصال بنجاح، لكن لم يتم العثور على عروض فـ JSON.")
                else:
                    processed_records = []
                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = extract_field_by_candidates(offer, ["network_offer_id", "offer_id", "id", "campaign_id"])
                        offer_name = extract_field_by_candidates(offer, ["name", "title", "offer_name"])
                        geo = extract_field_by_candidates(offer, ["geo", "countries", "country"])

                        suppression_matches = scan_suppression_recursive(offer)
                        
                        if suppression_matches:
                            field_names = ", ".join([m[0] for m in suppression_matches])
                            urls = [str(m[1]) for m in suppression_matches if isinstance(m[1], str) and m[1].startswith("http")]
                            file_url = urls[0] if urls else "Found (No Direct URL)"
                            has_suppression = "Yes"
                        else:
                            field_names = "None"
                            file_url = "N/A"
                            has_suppression = "No"

                        processed_records.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": offer_id,
                            "Offer Name": offer_name,
                            "GEO": geo,
                            "Suppression Found": has_suppression,
                            "Suppression Field": field_names,
                            "Suppression File URL": file_url
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.success(f"تم فحص {len(processed_records)} عرض بنجاح!")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    st.dataframe(df, use_container_width=True)
