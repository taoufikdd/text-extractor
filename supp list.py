import streamlit as st
import requests
import pandas as pd
import json
import io
import zipfile

# Keywords used to identify suppression-related fields in JSON responses
SUPPRESSION_KEYWORDS = [
    "suppression", "suppression_file", "suppression_url", "suppression list",
    "blacklist", "exclusion", "exclude", "optout", "opt_out", "do_not_contact", "dnc"
]

# Common container keys in affiliate network API responses
CONTAINER_KEYS = ["offers", "data", "results", "items", "campaigns", "response"]

def find_offers_list(data):
    """
    Attempts to locate the primary list of offers within a JSON response object.
    """
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
    """
    Recursively scans a dictionary or list for key names matching suppression keywords.
    Returns a list of tuples: (matched_key_path, value)
    """
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
    """
    Extracts a scalar string or number for standard fields like ID, Name, or GEO.
    """
    for candidate in candidates:
        if candidate in offer and offer[candidate] is not None:
            val = offer[candidate]
            if isinstance(val, (str, int, float)):
                return str(val)
            if isinstance(val, list):
                return ", ".join(map(str, val))
    return default

def fetch_api_data(url, auth_method, api_key, custom_header_name):
    """
    Executes HTTP GET request using selected authentication scheme.
    """
    headers = {}
    if auth_method == "Bearer Token":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_method == "X-API-Key":
        headers["X-API-Key"] = api_key
    elif auth_method == "API-Key":
        headers["API-Key"] = api_key
    elif auth_method == "Custom Header" and custom_header_name:
        headers[custom_header_name] = api_key

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()

def download_suppression_file(url):
    """
    Downloads file content from detected suppression URL.
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content

# --- Streamlit UI Setup ---
st.set_page_config(
    page_title="Affiliate Suppression Detector",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Affiliate Suppression List Detector")
st.caption("Automatically scan sponsor API endpoints to discover and extract suppression files.")

# Sidebar Configuration
with st.sidebar:
    st.header("Sponsor Configuration")
    sponsor_name = st.text_input("Sponsor Name", placeholder="e.g., Sponsor A")
    api_url = st.text_input("API Endpoint URL", placeholder="https://api.sponsor.com/v1/offers")
    auth_method = st.selectbox(
        "Authentication Method",
        ["Bearer Token", "X-API-Key", "API-Key", "Custom Header", "No Authentication"]
    )
    
    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input("Custom Header Name", placeholder="e.g., X-Auth-Token")

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input("API Key / Token", type="password")

    scan_submitted = st.button("Scan Offers", use_container_width=True, type="primary")

# Main Logic Execution
if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("Please provide both the API Endpoint URL and required Authentication details.")
    else:
        with st.spinner("Connecting to Sponsor API and scanning offers..."):
            try:
                json_data = fetch_api_data(api_url, auth_method, api_key, custom_header_name)
                offers_list = find_offers_list(json_data)

                if not offers_list:
                    st.warning("Connected successfully, but no list of offers could be extracted from the JSON response.")
                else:
                    processed_records = []
                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = extract_field_by_candidates(offer, ["id", "offer_id", "campaign_id"])
                        offer_name = extract_field_by_candidates(offer, ["name", "title", "offer_name", "campaign_name"])
                        geo = extract_field_by_candidates(offer, ["geo", "countries", "country", "target_countries"])

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
                            "Sponsor": sponsor_name if sponsor_name else "Unknown Sponsor",
                            "Offer ID": offer_id,
                            "Offer Name": offer_name,
                            "GEO": geo,
                            "Suppression Found": has_suppression,
                            "Suppression Field": field_names,
                            "Suppression File URL": file_url
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.success(f"Scan complete! Processed {len(processed_records)} offers.")
            except Exception as e:
                st.error(f"API Request Failed: {str(e)}")

# Display Results & Filters
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]

    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)
    total_offers = len(df)
    supp_found = len(df[df["Suppression Found"] == "Yes"])
    no_supp = len(df[df["Suppression Found"] == "No"])

    col1.metric("Total Offers", total_offers)
    col2.metric("Suppression Found", supp_found)
    col3.metric("No Suppression Found", no_supp)

    st.markdown("---")
    st.subheader("Filter Results")

    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    with f_col1:
        supp_filter = st.selectbox("Suppression Status", ["Show All", "Suppression Only", "No Suppression"])
    with f_col2:
        search_name = st.text_input("Search Offer Name", "")
    with f_col3:
        all_geos = ["All"] + sorted(list(set(df["GEO"].dropna().astype(str))))
        selected_geo = st.selectbox("Filter GEO", all_geos)
    with f_col4:
        all_sponsors = ["All"] + sorted(list(set(df["Sponsor"].dropna().astype(str))))
        selected_sponsor = st.selectbox("Filter Sponsor", all_sponsors)

    filtered_df = df.copy()

    if supp_filter == "Suppression Only":
        filtered_df = filtered_df[filtered_df["Suppression Found"] == "Yes"]
    elif supp_filter == "No Suppression":
        filtered_df = filtered_df[filtered_df["Suppression Found"] == "No"]

    if search_name:
        filtered_df = filtered_df[filtered_df["Offer Name"].str.contains(search_name, case=False, na=False)]

    if selected_geo != "All":
        filtered_df = filtered_df[filtered_df["GEO"] == selected_geo]

    if selected_sponsor != "All":
        filtered_df = filtered_df[filtered_df["Sponsor"] == selected_sponsor]

    st.dataframe(filtered_df, use_container_width=True)

    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Filtered Results to CSV",
        data=csv_data,
        file_name="suppression_scan_results.csv",
        mime="text/csv"
    )

    # File Download Actions
    supp_urls = filtered_df[filtered_df["Suppression File URL"].str.startswith("http", na=False)]
    if not supp_urls.empty:
        st.markdown("---")
        st.subheader("Download Suppression Files")
        for idx, row in supp_urls.iterrows():
            d_col1, d_col2 = st.columns([3, 1])
            d_col1.write(f"**{row['Offer Name']}** (ID: {row['Offer ID']}) — `{row['Suppression File URL']}`")
            
            try:
                file_content = download_suppression_file(row["Suppression File URL"])
                file_name = row["Suppression File URL"].split("/")[-1].split("?")[0]
                if not file_name or "." not in file_name:
                    file_name = f"suppression_{row['Offer ID']}.txt"
                
                d_col2.download_button(
                    label=f"Download {file_name}",
                    data=file_content,
                    file_name=file_name,
                    key=f"dl_{idx}"
                )
            except Exception as ex:
                d_col2.error("Fetch failed")