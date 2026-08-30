import streamlit as st
import requests
import pandas as pd
import json
import re
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="Everflow Suppression Downloader",
    page_icon="🛡️",
    layout="wide"
)


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*"
    })
    return session


def build_headers(auth_method, api_key, custom_header_name):
    headers = {"Accept": "*/*"}

    if not api_key:
        return headers

    if auth_method == "Bearer Token":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_method == "X-API-Key":
        headers["X-API-Key"] = api_key
    elif auth_method == "API-Key":
        headers["API-Key"] = api_key
    elif auth_method == "Custom Header" and custom_header_name:
        headers[custom_header_name.strip()] = api_key.strip()

    return headers


def find_download_urls(obj):
    found = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).lower()

            if isinstance(value, str):
                if (
                    value.startswith("http")
                    and (
                        "download" in key_lower
                        or "file_url" in key_lower
                        or "download_url" in key_lower
                        or "location" in key_lower
                        or key_lower == "url"
                    )
                ):
                    found.append(value)

            elif isinstance(value, (dict, list)):
                found.extend(find_download_urls(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_download_urls(item))

    return list(dict.fromkeys(found))


def extract_suppression_info(offer):
    if not isinstance(offer, dict):
        return 0, []

    suppression_id = 0

    for key in [
        "suppression_list_id",
        "network_suppression_list_id",
        "suppression_id"
    ]:
        value = offer.get(key)
        if value:
            suppression_id = value
            break

    relationship = offer.get("relationship", {})

    if isinstance(relationship, dict):
        suppression = relationship.get("suppression_list", {})

        if isinstance(suppression, dict):
            for key in [
                "network_suppression_list_id",
                "suppression_list_id",
                "id"
            ]:
                value = suppression.get(key)
                if value:
                    suppression_id = value
                    break

    urls = find_download_urls(offer)

    try:
        raw_json = json.dumps(offer)
        regex_urls = re.findall(
            r'https?://[^\s"\\]+',
            raw_json,
            re.IGNORECASE
        )

        for url in regex_urls:
            if any(
                x in url.lower()
                for x in [
                    "suppression",
                    "download",
                    ".rar",
                    ".zip",
                    ".txt",
                    ".csv",
                    ".7z"
                ]
            ):
                urls.append(url)
    except Exception:
        pass

    return suppression_id, list(dict.fromkeys(urls))


def fetch_single_page(base_endpoint, page, page_size, headers):
    urls = [
        f"{base_endpoint}?page={page}&page_size={page_size}&relationship=all&offer_status=all",
        f"{base_endpoint}?page={page}&page_size={page_size}"
    ]

    session = get_session()

    for url in urls:
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=20,
                verify=False
            )

            if response.status_code != 200:
                continue

            data = response.json()

            if isinstance(data, list):
                return data

            if isinstance(data, dict):
                for key in [
                    "offers",
                    "data",
                    "results",
                    "items"
                ]:
                    if key in data and isinstance(data[key], list):
                        return data[key]

        except Exception:
            continue

    return []


def fetch_all_offers(
    base_url,
    auth_method,
    api_key,
    custom_header_name
):
    clean_url = base_url.strip()

    headers = build_headers(
        auth_method,
        api_key,
        custom_header_name
    )

    if "eflow" in clean_url.lower() or "everflow" in clean_url.lower():
        if (
            "/v1/affiliates/offers" in clean_url
            and "/alloffers" not in clean_url
        ):
            clean_url = clean_url.replace(
                "/v1/affiliates/offers",
                "/v1/affiliates/alloffers"
            )

        if custom_header_name.lower() == "x-eflow-api-key":
            headers["X-Eflow-Api-Key"] = api_key

    base_endpoint = clean_url.split("?")[0]

    first_page = fetch_single_page(
        base_endpoint,
        1,
        500,
        headers
    )

    if not first_page:
        return [], headers

    all_offers = list(first_page)

    if len(first_page) >= 500:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    fetch_single_page,
                    base_endpoint,
                    page,
                    500,
                    headers
                )
                for page in range(2, 25)
            ]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        all_offers.extend(result)
                except Exception:
                    pass

    return all_offers, headers


def detect_extension(response, url=""):
    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    content_disposition = response.headers.get(
        "Content-Disposition", ""
    ).lower()

    combined = (
        content_type
        + " "
        + content_disposition
        + " "
        + url.lower()
    )

    if ".rar" in combined or "rar" in content_type:
        return "rar"

    if ".7z" in combined or "7z" in content_type:
        return "7z"

    if ".zip" in combined or "zip" in content_type:
        return "zip"

    if ".csv" in combined or "csv" in content_type:
        return "csv"

    if ".txt" in combined or "text/plain" in content_type:
        return "txt"

    data = response.content[:20]

    if data.startswith(b"PK"):
        return "zip"

    if data.startswith(b"Rar!"):
        return "rar"

    if data.startswith(b"7z"):
        return "7z"

    return "bin"


def is_json_response(response):
    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if "json" in content_type:
        return True

    try:
        response.json()
        return True
    except Exception:
        return False


def extract_urls_from_response(data):
    urls = []

    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = str(key).lower()

            if isinstance(value, str):
                if (
                    value.startswith("http")
                    and (
                        "url" in key_lower
                        or "download" in key_lower
                        or "file" in key_lower
                        or "location" in key_lower
                    )
                ):
                    urls.append(value)

            elif isinstance(value, (dict, list)):
                urls.extend(extract_urls_from_response(value))

    elif isinstance(data, list):
        for item in data:
            urls.extend(extract_urls_from_response(item))

    return list(dict.fromkeys(urls))


def download_file_bytes(
    offer_id,
    suppression_id,
    direct_urls,
    headers
):
    session = get_session()
    diagnostics = []
    targets = []

    if isinstance(direct_urls, str):
        direct_urls = [direct_urls]

    if direct_urls:
        for url in direct_urls:
            if url and url.startswith("http"):
                targets.append(url)

    if suppression_id and str(suppression_id) != "0":
        targets.extend([
            f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}/download",
            f"https://api.eflow.team/v1/affiliates/offers/{offer_id}/suppressionlist/download",
            f"https://api.eflow.team/v1/affiliates/suppressionlists/{suppression_id}"
        ])

    targets = list(dict.fromkeys(targets))

    for target in targets:
        try:
            request_headers = dict(headers)

            response = session.get(
                target,
                headers=request_headers,
                timeout=45,
                verify=False,
                allow_redirects=True
            )

            status = response.status_code
            content_type = response.headers.get(
                "Content-Type", ""
            )

            diagnostics.append(
                f"{status} | {target} | {content_type}"
            )

            if status == 200 and len(response.content) > 20:

                if is_json_response(response):
                    try:
                        data = response.json()

                        next_urls = extract_urls_from_response(data)

                        for next_url in next_urls:
                            try:
                                response2 = session.get(
                                    next_url,
                                    headers=request_headers,
                                    timeout=60,
                                    verify=False,
                                    allow_redirects=True
                                )

                                diagnostics.append(
                                    f"{response2.status_code} | "
                                    f"{next_url} | "
                                    f"{response2.headers.get('Content-Type', '')}"
                                )

                                if (
                                    response2.status_code == 200
                                    and len(response2.content) > 20
                                    and not is_json_response(response2)
                                ):
                                    ext = detect_extension(
                                        response2,
                                        next_url
                                    )

                                    return (
                                        response2.content,
                                        ext,
                                        diagnostics
                                    )

                            except Exception as error:
                                diagnostics.append(
                                    f"ERROR | {next_url} | {error}"
                                )

                        continue

                    except Exception:
                        continue

                ext = detect_extension(
                    response,
                    target
                )

                return (
                    response.content,
                    ext,
                    diagnostics
                )

            try:
                body_preview = response.text[:500]
                if body_preview:
                    diagnostics.append(
                        f"BODY | {body_preview}"
                    )
            except Exception:
                pass

        except Exception as error:
            diagnostics.append(
                f"ERROR | {target} | {error}"
            )

    return None, None, diagnostics


# ========================= UI =========================

st.title("🛡️ Everflow Suppression Downloader")

st.caption(
    "Scan offers and download available suppression files."
)

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

        with st.spinner(
            "Fetching offers and suppression information..."
        ):
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
                                if (
                                    str(suppression_id) != "0"
                                    or direct_urls
                                )
                                else "No"
                            ),
                            "Suppression ID": str(suppression_id),
                            "Download URLs": "\n".join(direct_urls)
                        })

                    st.session_state["scan_results"] = (
                        pd.DataFrame(processed)
                    )

                    st.session_state["sponsor_name"] = sponsor_name
                    st.session_state["headers_used"] = headers_used

                    st.success(
                        f"Scanned {len(processed)} offers successfully!"
                    )

            except Exception as error:
                st.error(
                    f"Error while scanning offers: {error}"
                )


if (
    "scan_results" in st.session_state
    and not st.session_state["scan_results"].empty
):

    df = st.session_state["scan_results"]

    headers_used = st.session_state.get(
        "headers_used",
        {}
    )

    st.subheader(
        "📋 Offers List & Suppression Download"
    )

    supp_df = df[
        (df["Suppression ID"] != "0")
        | (df["Download URLs"] != "")
    ].copy()

    st.write(
        f"لقينا **{len(supp_df)}** Offer فيه Suppression information."
    )

    for idx, row in supp_df.iterrows():

        col1, col2, col3, col4 = st.columns(
            [1, 4, 2, 3]
        )

        with col1:
            st.write(
                f"**#{row['Offer ID']}**"
            )

        with col2:
            st.write(
                row["Offer Name"]
            )

        with col3:
            st.write(
                f"Supp ID: `{row['Suppression ID']}`"
            )

        with col4:

            btn_key = (
                f"dl_{row['Offer ID']}_"
                f"{row['Suppression ID']}_{idx}"
            )

            if st.button(
                "⬇️ Get File",
                key=btn_key
            ):

                direct_urls = []

                if row["Download URLs"]:

                    direct_urls = [
                        item.strip()
                        for item in row["Download URLs"].split("\n")
                        if item.strip()
                    ]

                with st.spinner(
                    "Trying to download suppression file..."
                ):

                    file_bytes, ext, diagnostics = (
                        download_file_bytes(
                            row["Offer ID"],
                            row["Suppression ID"],
                            direct_urls,
                            headers_used
                        )
                    )

                if file_bytes:

                    st.success(
                        f"File ready: "
                        f"{len(file_bytes) / 1024 / 1024:.2f} MB"
                    )

                    st.download_button(
                        label=(
                            f"💾 Save "
                            f"Offer_{row['Offer ID']}"
                            f"_Suppression.{ext}"
                        ),
                        data=file_bytes,
                        file_name=(
                            f"Offer_{row['Offer ID']}"
                            f"_Suppression.{ext}"
                        ),
                        mime="application/octet-stream",
                        key=f"save_{btn_key}"
                    )

                else:

                    st.error(
                        "❌ Failed to download the file."
                    )

                    st.warning(
                        "Download diagnostics:"
                    )

                    for line in diagnostics:
                        st.code(
                            line,
                            language="text"
                        )
