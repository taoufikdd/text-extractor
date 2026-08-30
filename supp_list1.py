import io
import json
import re
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="Everflow Suppression Downloader",
    page_icon="🛡️",
    layout="wide"
)

# Initialize state management
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None
if "downloaded_files" not in st.session_state:
    st.session_state["downloaded_files"] = {}  # {offer_id: [(filename, bytes, mime)]}
if "diagnostics_log" not in st.session_state:
    st.session_state["diagnostics_log"] = {}
if "sort_by" not in st.session_state:
    st.session_state["sort_by"] = "Offer ID"
if "sort_order" not in st.session_state:
    st.session_state["sort_order"] = True  # True = Ascending, False = Descending

def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    })
    return s

def build_headers(auth_method, api_key, custom_header_name):
    headers = {}
    key = (api_key or "").strip()
    if not key or auth_method == "No Authentication":
        return headers
    if auth_method == "Bearer Token":
        headers["Authorization"] = f"Bearer {key}"
    elif auth_method == "X-API-Key":
        headers["X-API-Key"] = key
    elif auth_method == "API-Key":
        headers["API-Key"] = key
    elif auth_method == "Custom Header" and custom_header_name:
        name = custom_header_name.strip()
        if name.lower() == "x-eflow-api-key":
            name = "X-Eflow-Api-Key"
        headers[name] = key
    return headers

def is_json_response(response):
    ct = response.headers.get("Content-Type", "").lower()
    if "json" in ct:
        return True
    try:
        response.json()
        return True
    except Exception:
        return False

def extract_urls(obj):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, str):
                if v.startswith(("http://", "https://")) and (
                    "url" in kl or "download" in kl or "file" in kl or
                    "location" in kl or "suppression" in kl or "link" in kl
                ):
                    found.append(v)
            elif isinstance(v, (dict, list)):
                found.extend(extract_urls(v))
    elif isinstance(obj, list):
        for x in obj:
            found.extend(extract_urls(x))
    return list(dict.fromkeys(found))

def extract_suppression_info(offer):
    if not isinstance(offer, dict):
        return 0, []

    suppression_id = 0
    keys = ["suppression_list_id", "network_suppression_list_id", "suppression_id"]

    for k in keys:
        v = offer.get(k)
        if v not in (None, "", 0, "0"):
            suppression_id = v
            break

    relationship = offer.get("relationship")
    if isinstance(relationship, dict):
        supp = relationship.get("suppression_list")
        if isinstance(supp, dict):
            for k in ["network_suppression_list_id", "suppression_list_id", "id"]:
                v = supp.get(k)
                if v not in (None, "", 0, "0"):
                    suppression_id = v
                    break

    urls = extract_urls(offer)
    relevant = []
    for u in urls:
        ul = u.lower()
        if any(x in ul for x in [
            "suppression", "download", ".zip", ".rar", ".7z",
            "optizmo", "unsub", "ezdownload", ".gz", ".csv", ".txt"
        ]):
            relevant.append(u)

    try:
        raw = json.dumps(offer)
        direct = re.findall(
            r'https?://[^\s"\\]+(?:zip|rar|7z|gz|csv|txt)(?:[^\s"\\]*)',
            raw,
            re.I
        )
        relevant.extend(direct)
    except Exception:
        pass

    return suppression_id, list(dict.fromkeys(relevant))

def fetch_single_page(base_endpoint, page, page_size, headers):
    urls = [
        f"{base_endpoint}?page={page}&page_size={page_size}&relationship=all&offer_status=all",
        f"{base_endpoint}?page={page}&page_size={page_size}",
    ]
    session = get_session()

    for url in urls:
        try:
            r = session.get(url, headers=headers, timeout=30, verify=False, allow_redirects=True)
            if r.status_code != 200:
                continue
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ["offers", "data", "results", "items"]:
                    if isinstance(data.get(key), list):
                        return data[key]
        except Exception:
            continue
    return []

def fetch_all_offers(base_url, auth_method, api_key, custom_header_name):
    headers = build_headers(auth_method, api_key, custom_header_name)
    clean = base_url.strip()

    if "eflow" in clean.lower() or "everflow" in clean.lower():
        if "/v1/affiliates/offers" in clean and "/alloffers" not in clean:
            clean = clean.replace("/v1/affiliates/offers", "/v1/affiliates/alloffers")

    endpoint = clean.split("?")[0]
    first = fetch_single_page(endpoint, 1, 500, headers)

    if not first:
        return [], headers

    all_offers = list(first)

    if len(first) >= 500:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(fetch_single_page, endpoint, page, 500, headers)
                for page in range(2, 25)
            ]
            for f in as_completed(futures):
                try:
                    result = f.result()
                    if result:
                        all_offers.extend(result)
                except Exception:
                    pass

    seen = set()
    unique = []
    for offer in all_offers:
        oid = (offer.get("network_offer_id") or offer.get("offer_id") or offer.get("id")) if isinstance(offer, dict) else None
        marker = str(oid) if oid is not None else json.dumps(offer, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            unique.append(offer)

    return unique, headers

def detect_extension(response, url=""):
    ct = response.headers.get("Content-Type", "").lower()
    cd = response.headers.get("Content-Disposition", "").lower()
    head = response.content[:16]
    combined = f"{ct} {cd} {url.lower()}"

    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return "zip"
    if head.startswith(b"Rar!\x1a\x07"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if head.startswith(b"\x1f\x8b"):
        return "gz"

    for ext in ["zip", "rar", "7z", "csv", "txt", "gz"]:
        if ext in combined:
            return ext
    return "bin"

def looks_like_archive_or_file(response):
    if not response.content:
        return False
    if is_json_response(response):
        return False
    ext = detect_extension(response)
    if ext in {"zip", "rar", "7z", "gz", "csv", "txt"}:
        return True
    ct = response.headers.get("Content-Type", "").lower()
    return "octet-stream" in ct and len(response.content) > 20

def download_file_bytes(offer_id, suppression_id, direct_urls, headers):
    session = get_session()
    diagnostics = []

    if isinstance(direct_urls, str):
        direct_urls = [direct_urls]

    targets = [u for u in direct_urls or [] if u and u.startswith(("http://", "https://"))]

    if offer_id and str(offer_id) != "0":
        detailed_offer_url = f"https://api.eflow.team/v1/affiliates/offers/{offer_id}?relationship=all"
        try:
            r_detail = session.get(detailed_offer_url, headers=dict(headers), timeout=20, verify=False)
            if r_detail.status_code == 200 and is_json_response(r_detail):
                detail_data = r_detail.json()
                discovered = extract_urls(detail_data)
                for d_url in discovered:
                    if any(x in d_url.lower() for x in ["suppression", "download", ".zip", "optizmo", "unsub"]):
                        targets.append(d_url)
        except Exception as e:
            diagnostics.append(f"DETAIL FETCH FAILED | {e}")

    if suppression_id and str(suppression_id) != "0":
        targets.extend([
            f"https://api.eflow.team/v1/affiliates/offers/{offer_id}/suppressionlist",
            f"https://api.eflow.team/v1/affiliates/offers/{offer_id}/suppressionlist/download",
            f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}/download",
            f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}",
        ])

    targets = list(dict.fromkeys(targets))

    for target in targets:
        try:
            r = session.get(target, headers=dict(headers), timeout=60, verify=False, allow_redirects=True)
            ct = r.headers.get("Content-Type", "")
            diagnostics.append(f"{r.status_code} | {target} | {ct}")

            if r.status_code != 200 or len(r.content) <= 20:
                if r.text:
                    diagnostics.append(f"BODY | {r.text[:300]}")
                continue

            if is_json_response(r):
                try:
                    data = r.json()
                except Exception:
                    continue

                next_urls = extract_urls(data)
                for next_url in next_urls:
                    try:
                        req_headers = {} if any(x in next_url for x in ["s3.amazonaws", "optizmo", "unsub"]) else dict(headers)
                        r2 = session.get(next_url, headers=req_headers, timeout=90, verify=False, allow_redirects=True)
                        ct2 = r2.headers.get("Content-Type", "")
                        diagnostics.append(f"{r2.status_code} | {next_url} | {ct2}")

                        if r2.status_code == 200 and len(r2.content) > 20 and looks_like_archive_or_file(r2):
                            return r2.content, detect_extension(r2, next_url), diagnostics
                    except Exception as e:
                        diagnostics.append(f"ERROR | {next_url} | {e}")
                continue

            if looks_like_archive_or_file(r):
                return r.content, detect_extension(r, target), diagnostics

        except Exception as e:
            diagnostics.append(f"ERROR | {target} | {e}")

    return None, None, diagnostics

def unzip_bytes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members = [x for x in z.infolist() if not x.is_dir() and not x.filename.startswith("__MACOSX/")]
        if not members:
            return None, None

        members.sort(key=lambda x: (0 if x.filename.lower().endswith((".csv", ".txt")) else 1, len(x.filename)))
        chosen = members[0]
        return chosen.filename.split("/")[-1], z.read(chosen)

def make_final_file(data, ext, offer_id):
    if ext != "zip":
        return [(f"Offer_{offer_id}_Suppression.{ext}", data, "application/octet-stream")]

    try:
        inner_name, inner_data = unzip_bytes(data)
        result = [(f"Offer_{offer_id}_Suppression.zip", data, "application/zip")]
        if inner_name and inner_data:
            inner_ext = Path(inner_name).suffix.lower().lstrip(".") or "bin"
            mime = "text/plain" if inner_ext == "txt" else ("text/csv" if inner_ext == "csv" else "application/octet-stream")
            result.append((f"Offer_{offer_id}_Suppression_extracted.{inner_ext}", inner_data, mime))
        return result
    except zipfile.BadZipFile:
        return [(f"Offer_{offer_id}_Suppression.zip", data, "application/octet-stream")]

# ========================= UI =========================

st.title("🛡️ Everflow Suppression Downloader")

with st.sidebar:
    st.header("⚙️ Config & Actions")
    sponsor_name = st.text_input("Sponsor Name", value="XI Leads")
    api_url = st.text_input("API Endpoint URL", value="https://api.eflow.team/v1/affiliates/alloffers")
    auth_method = st.selectbox("Auth Method", ["Custom Header", "Bearer Token", "X-API-Key", "API-Key", "No Authentication"])
    
    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input("Custom Header Name", value="X-Eflow-Api-Key")

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input("API Key / Token", type="password")

    if st.button("🔎 Scan All Offers", use_container_width=True, type="primary"):
        if not api_url:
            st.error("Please enter the API Endpoint URL.")
        elif auth_method != "No Authentication" and not api_key:
            st.error("Please enter the API Key / Token.")
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
                            offer_id = offer.get("network_offer_id") or offer.get("offer_id") or offer.get("id") or 0
                            offer_name = offer.get("name") or offer.get("title") or "N/A"
                            offer_status = offer.get("offer_status") or offer.get("status") or "N/A"
                            suppression_id, direct_urls = extract_suppression_info(offer)

                            processed.append({
                                "Offer ID": int(offer_id) if str(offer_id).isdigit() else offer_id,
                                "Offer Name": str(offer_name),
                                "Suppression ID": int(suppression_id) if str(suppression_id).isdigit() else suppression_id,
                                "Status": str(offer_status),
                                "Download URLs": "\n".join(direct_urls)
                            })

                        st.session_state["scan_results"] = pd.DataFrame(processed)
                        st.session_state["headers_used"] = headers_used
                        st.session_state["downloaded_files"] = {}
                        st.session_state["diagnostics_log"] = {}
                        st.success(f"Successfully scanned {len(processed)} offers!")
                except Exception as error:
                    st.error(f"Error while scanning: {error}")

# Interactive Table View
if st.session_state["scan_results"] is not None and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    supp_df = df[(df["Suppression ID"] != 0) | (df["Download URLs"] != "")].copy()

    st.subheader(f"📋 Suppression Lists ({len(supp_df)} Offers)")

    # Sorting Controls
    sort_col1, sort_col2 = st.columns([2, 2])
    with sort_col1:
        sort_by = st.selectbox("Sort By:", ["Offer ID", "Suppression ID", "Offer Name"], index=0)
    with sort_col2:
        sort_order = st.radio("Order:", ["Ascending (من الصغير للبيطون)", "Descending (من البيطون للصغير)"], index=0)

    ascending = True if "Ascending" in sort_order else False
    supp_df = supp_df.sort_values(by=sort_by, ascending=ascending)

    st.divider()

    # Table Header Row
    h1, h2, h3, h4, h5 = st.columns([1.2, 4, 1.5, 1.2, 3])
    with h1: st.markdown("**Offer ID**")
    with h2: st.markdown("**Offer Name**")
    with h3: st.markdown("**Suppression ID**")
    with h4: st.markdown("**Status**")
    with h5: st.markdown("**Action / File**")
    
    st.divider()

    # Table Body Rows
    for idx, row in supp_df.iterrows():
        offer_id = row["Offer ID"]
        supp_id = row["Suppression ID"]
        
        c1, c2, c3, c4, c5 = st.columns([1.2, 4, 1.5, 1.2, 3])
        
        with c1:
            st.write(f"#{offer_id}")
        with c2:
            st.write(row["Offer Name"])
        with c3:
            st.write(f"`{supp_id}`")
        with c4:
            st.write(row["Status"])
        with c5:
            # Check if file has already been downloaded
            if offer_id in st.session_state["downloaded_files"]:
                for file_idx, (filename, content, mime) in enumerate(st.session_state["downloaded_files"][offer_id]):
                    st.download_button(
                        label=f"💾 Save {filename.split('.')[-1].upper()}",
                        data=content,
                        file_name=filename,
                        mime=mime,
                        key=f"dl_saved_{offer_id}_{file_idx}",
                        use_container_width=True
                    )
            else:
                if st.button("⬇️ Get File", key=f"btn_get_{offer_id}_{idx}", use_container_width=True):
                    direct_urls = [x.strip() for x in str(row["Download URLs"]).split("\n") if x.strip()]
                    with st.spinner("Downloading..."):
                        file_bytes, ext, diagnostics = download_file_bytes(
                            offer_id, supp_id, direct_urls, headers_used
                        )
                        st.session_state["diagnostics_log"][offer_id] = diagnostics

                        if file_bytes:
                            saved_files = make_final_file(file_bytes, ext, offer_id)
                            st.session_state["downloaded_files"][offer_id] = saved_files
                            st.rerun()
                        else:
                            st.error("Failed.")

        # Optional Expander for diagnostics if failed
        if offer_id in st.session_state["diagnostics_log"] and offer_id not in st.session_state["downloaded_files"]:
            with st.expander(f"🔍 Diagnostics for Offer #{offer_id}"):
                for line in st.session_state["diagnostics_log"][offer_id]:
                    st.code(line)
        
        st.markdown("<hr style='margin: 4px 0px; border-top: 1px solid #333;'>", unsafe_allow_html=True)
