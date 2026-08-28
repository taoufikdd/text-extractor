import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import io
import os

def fetch_all_offers_everflow(base_url, auth_method, api_key, custom_header_name):
    """جلب جميع العروض"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
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

    all_offers = []
    page = 1
    page_size = 500
    base_endpoint = clean_url.split("?")[0]

    while True:
        paginated_url = f"{base_endpoint}?page={page}&page_size={page_size}&relationship=all&offer_status=all"
        response = requests.get(paginated_url, headers=headers, timeout=30, verify=False)
        
        if response.status_code != 200:
            if page == 1:
                paginated_url = f"{base_endpoint}?page={page}&page_size={page_size}"
                response = requests.get(paginated_url, headers=headers, timeout=30, verify=False)
                if response.status_code != 200:
                    raise Exception(f"خطأ من السيرفر (HTTP {response.status_code}): {response.text[:200]}")
            else:
                break

        json_data = response.json()
        offers_chunk = []
        if isinstance(json_data, list):
            offers_chunk = json_data
        elif isinstance(json_data, dict):
            for k in ["offers", "data", "results", "items"]:
                if k in json_data and isinstance(json_data[k], list):
                    offers_chunk = json_data[k]
                    break

        if not offers_chunk:
            break

        all_offers.extend(offers_chunk)
        if len(offers_chunk) < page_size:
            break
        page += 1

    return all_offers, headers

def get_everflow_optout_download_link(network_offer_id, supp_id, headers):
    """جلب رابط التحميل الأصلي"""
    try:
        optout_url = f"https://api.eflow.team/v1/affiliates/offers/{network_offer_id}/optout"
        resp = requests.get(optout_url, headers=headers, timeout=15, verify=False)
        
        if resp.status_code == 200:
            data = resp.json()
            dl_url = data.get("download_url") or data.get("opt_out_list_url") or data.get("url") or data.get("file_url")
            filename = data.get("filename") or data.get("name")
            if dl_url:
                if not filename:
                    filename = dl_url.split("?")[0].split("/")[-1]
                return dl_url, filename, None

        if supp_id and str(supp_id) != "0":
            supp_url = f"https://api.eflow.team/v1/affiliates/suppressionlists/{supp_id}/download"
            resp_supp = requests.get(supp_url, headers=headers, timeout=15, verify=False)
            if resp_supp.status_code == 200:
                data = resp_supp.json()
                dl_url = data.get("download_url") or data.get("url")
                if dl_url:
                    filename = data.get("filename") or dl_url.split("?")[0].split("/")[-1]
                    return dl_url, filename, None

        return None, None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, None, str(e)

def extract_txt_files_from_zip_bytes(zip_bytes):
    """استخراج الملفات النصية المباشرة (.txt / .csv) من الأرشيف وسحب محتواها"""
    extracted_files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for zip_info in z.infolist():
                if zip_info.is_dir():
                    continue
                # البحث عن الملفات النصية أو ملفات الـ suppression داخل المجلدات
                fname = os.path.basename(zip_info.filename)
                if fname and not fname.startswith('.'):
                    file_content = z.read(zip_info.filename)
                    extracted_files[fname] = file_content
    except Exception as e:
        pass
    return extracted_files

def download_file_bytes(url):
    """تحميل الملف من S3"""
    res = requests.get(url, timeout=120, verify=False)
    res.raise_for_status()
    return res.content

# --- UI Setup ---
st.set_page_config(page_title="Affiliate Suppression Detector", page_icon="🛡️", layout="wide")
st.title("🛡️ Affiliate Suppression List Detector")

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
        with st.spinner("جاري فحص العروض..."):
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

                        if has_supp or (supp_id and str(supp_id) != "0"):
                            has_suppression = "Yes"
                        else:
                            has_suppression = "No"

                        processed_records.append({
                            "Sponsor": sponsor_name,
                            "Offer ID": str(offer_id),
                            "Offer Name": str(offer_name),
                            "Status": str(offer_status),
                            "GEO": geo_info,
                            "Suppression Found": has_suppression,
                            "Suppression ID": str(supp_id)
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.session_state["headers_used"] = headers_used
                    st.success(f"تم فحص جميع العروض بنجاح! الإجمالي: {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

# عرض أزرار التحميل المباشر لملفات TXT المقتطعة
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    st.dataframe(df, use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("📄 استخراج ملفات الـ TXT المباشرة (Unpacked Files)")
        
        for idx, row in supp_df.iterrows():
            st.markdown(f"### 🔹 [{row['Status']}] {row['Offer Name']} (ID: `{row['Offer ID']}`)")
            
            dl_url, exact_filename, err = get_everflow_optout_download_link(row["Offer ID"], row["Suppression ID"], headers_used)
            
            if dl_url:
                try:
                    with st.spinner(f"جاري تحضير وتفكيك الملف لـ {row['Offer Name']}..."):
                        zip_bytes = download_file_bytes(dl_url)
                        extracted_files = extract_txt_files_from_zip_bytes(zip_bytes)

                    if extracted_files:
                        cols = st.columns(min(len(extracted_files), 4))
                        c_idx = 0
                        for fname, content_bytes in extracted_files.items():
                            col = cols[c_idx % len(cols)]
                            col.download_button(
                                label=f"📄 {fname}",
                                data=content_bytes,
                                file_name=fname,
                                key=f"dl_txt_{row['Offer ID']}_{c_idx}_{idx}"
                            )
                            c_idx += 1
                    else:
                        # إذا لم يكن ملف zip حقيقي، تنزيل الملف كما هو
                        st.download_button(
                            label=f"⬇️ {exact_filename}",
                            data=zip_bytes,
                            file_name=exact_filename,
                            key=f"dl_raw_{row['Offer ID']}_{idx}"
                        )
                except Exception as ex:
                    st.error(f"خطأ فـ معالجة الملف: {str(ex)}")
            else:
                st.warning(f"غير متوفر ({err if err else 'N/A'})")
