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
    keys = [
        "suppression_list_id",
        "network_suppression_list_id",
        "suppression_id"
    ]

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
            r = session.get(
                url, headers=headers, timeout=30,
                verify=False, allow_redirects=True
            )
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
            clean = clean.replace(
                "/v1/affiliates/offers",
                "/v1/affiliates/alloffers"
            )

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
        oid = (
            offer.get("network_offer_id")
            or offer.get("offer_id")
            or offer.get("id")
        ) if isinstance(offer, dict) else None
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

    targets = []
    for u in direct_urls or []:
        if u and u.startswith(("http://", "https://")):
            targets.append(u)

    # Fetch detailed offer JSON first if direct URLs are empty or failing
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

    # Fallback endpoint variants for Everflow
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
            r = session.get(
                target,
                headers=dict(headers),
                timeout=60,
                verify=False,
                allow_redirects=True
            )

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
                        # Try requesting discovered URL without API auth headers if it's an external bucket or Optizmo link
                        req_headers = {} if any(x in next_url for x in ["s3.amazonaws", "optizmo", "unsub"]) else dict(headers)
                        r2 = session.get(
                            next_url,
                            headers=req_headers,
                            timeout=90,
                            verify=False,
                            allow_redirects=True
                        )
                        ct2 = r2.headers.get("Content-Type", "")
                        diagnostics.append(
                            f"{r2.status_code} | {next_url} | {ct2}"
                        )

                        if (
                            r2.status_code == 200
                            and len(r2.content) > 20
                            and looks_like_archive_or_file(r2)
                        ):
                            return (
                                r2.content,
                                detect_extension(r2, next_url),
                                diagnostics
                            )
                    except Exception as e:
                        diagnostics.append(f"ERROR | {next_url} | {e}")
                continue

            if looks_like_archive_or_file(r):
                return (
                    r.content,
                    detect_extension(r, target),
                    diagnostics
                )

        except Exception as e:
            diagnostics.append(f"ERROR | {target} | {e}")

    return None, None, diagnostics

def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*]+', "_", str(value))
    return value[:120].strip(" ._") or "suppression"

def unzip_bytes(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members = [
            x for x in z.infolist()
            if not x.is_dir() and not x.filename.startswith("__MACOSX/")
        ]
        if not members:
            return None, None

        members.sort(key=lambda x: (
            0 if x.filename.lower().endswith((".csv", ".txt")) else 1,
            len(x.filename)
        ))
        chosen = members[0]
        return chosen.filename.split("/")[-1], z.read(chosen)

def make_final_file(data, ext, offer_id):
    if ext != "zip":
        return [(f"Offer_{offer_id}_Suppression.{ext}", data, "application/octet-stream")]

    try:
        inner_name, inner_data = unzip_bytes(data)
        result = [
            (
                f"Offer_{offer_id}_Suppression.zip",
                data,
                "application/zip"
            )
        ]
        if inner_name and inner_data:
            inner_ext = Path(inner_name).suffix.lower().lstrip(".") or "bin"
            mime = "text/plain" if inner_ext == "txt" else (
                "text/csv" if inner_ext == "csv" else "application/octet-stream"
            )
            result.append((
                f"Offer_{offer_id}_Suppression_extracted.{inner_ext}",
                inner_data,
                mime
            ))
        return result
    except zipfile.BadZipFile:
        return [(
            f"Offer_{offer_id}_Suppression.zip",
            data,
            "application/octet-stream"
        )]

# ========================= UI =========================

st.title("🛡️ Everflow Suppression Downloader")
st.caption("Scan offers and download available suppression files.")

with st.sidebar:
    st.header("Sponsor Configuration")

    sponsor_name = st.text_input(
        "Sponsor Name",
        value="XI Leads"
    )

    api_url = st.text_input(
        "API Endpoint URL",
        value="https://api.eflow.team/v1/affiliates/alloffers"
    )

    auth_method = st.selectbox(
        "Authentication Method",
        [
            "Custom Header",
            "Bearer Token",
            "X-API-Key",
            "API-Key",
            "No Authentication"
        ]
    )

    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input(
            "Custom Header Name",
            value="X-Eflow-Api-Key"
        )

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input(
            "API Key / Token",
            type="password"
        )

    scan_submitted = st.button(
        "🔎 Scan All Offers",
        use_container_width=True,
        type="primary"
    )

if scan_submitted:
    if not api_url:
        st.error("Please enter the API Endpoint URL.")
    elif auth_method != "No Authentication" and not api_key:
        st.error("Please enter the API Key / Token.")
    else:
        with st.spinner("Fetching offers and suppression information..."):
            try:
                offers_list, headers_used = fetch_all_offers(
                    api_url,
                    auth_method,
                    api_key,
                    custom_header_name
                )

                if not offers_list:
                    st.warning(
                        "No offers found. Check API URL and authentication."
                    )
                else:
                    processed = []

                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue

                        offer_id = (
                            offer.get("network_offer_id")
                            or offer.get("offer_id")
                            or offer.get("id")
                            or "N/A"
                        )

                        offer_name = (
                            offer.get("name")
                            or offer.get("title")
                            or "N/A"
                        )

                        offer_status = (
                            offer.get("offer_status")
                            or offer.get("status")
                            or "N/A"
                        )

                        suppression_id, direct_urls = (
                            extract_suppression_info(offer)
                        )

                        processed.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "Suppression Found": (
                                "Yes"
                                if str(suppression_id) != "0" or direct_urls
                                else "No"
                            ),
                            "Suppression ID": str(suppression_id),
                            "Download URLs": "\n".join(direct_urls)
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed)
                    st.session_state["sponsor_name"] = sponsor_name
                    st.session_state["headers_used"] = headers_used

                    st.success(
                        f"Scanned {len(processed)} offers successfully!"
                    )

            except Exception as error:
                st.error(f"Error while scanning offers: {error}")

if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    st.subheader("📋 Offers List & Suppression Download")

    supp_df = df[
        (df["Suppression ID"] != "0")
        | (df["Download URLs"] != "")
    ].copy()

    st.write(
        f"لقينا **{len(supp_df)}** Offer فيه Suppression information."
    )

    for idx, row in supp_df.iterrows():
        col1, col2, col3, col4 = st.columns([1, 4, 2, 3])

        with col1:
            st.write(f"**#{row['Offer ID']}**")

        with col2:
            st.write(row["Offer Name"])

        with col3:
            st.write(f"Supp ID: `{row['Suppression ID']}`")

        with col4:
            btn_key = f"dl_{row['Offer ID']}_{row['Suppression ID']}_{idx}"

            if st.button("⬇️ Get File", key=btn_key):
                direct_urls = [
                    x.strip()
                    for x in str(row["Download URLs"]).split("\n")
                    if x.strip()
                ]

                with st.spinner("Trying to download suppression file..."):
                    file_bytes, ext, diagnostics = download_file_bytes(
                        row["Offer ID"],
                        row["Suppression ID"],
                        direct_urls,
                        headers_used
                    )

                if file_bytes:
                    st.success(
                        f"File ready: {len(file_bytes) / 1024 / 1024:.2f} MB"
                    )

                    files_to_save = make_final_file(
                        file_bytes,
                        ext,
                        row["Offer ID"]
                    )

                    for filename, content, mime in files_to_save:
                        st.download_button(
                            label=f"💾 Save {filename}",
                            data=content,
                            file_name=filename,
                            mime=mime,
                            key=f"save_{btn_key}_{filename}"
                        )

                else:
                    st.error(
                        "ما قدرناش نحمّلو الملف. شوف Diagnostics لتحت."
                    )
                    with st.expander("🔍 Diagnostics"):
                        for line in diagnostics:
                            st.code(line)
