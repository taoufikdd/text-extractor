import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import io
import os

def fetch_all_offers_everflow(base_url, auth_method, api_key, custom_header_name):
    """جلب جميع العروض مع التفاصيل الكاملة بما فيها روابط suppression الخفية"""
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

def extract_suppression_url_from_offer_obj(offer):
    """استخراج رابط AWS S3 المباشر من بيانات العرض نفسها بدون 404"""
    urls = []
    
    # 1. البحث فـ relationship
    rel = offer.get("relationship", {})
    if isinstance(rel, dict):
        supp = rel.get("suppression_list", {}) or rel.get("suppression", {})
        if isinstance(supp, dict):
            for k in ["download_url", "file_url", "url", "opt_out_url", "unsubscribe_url"]:
                if supp.get(k) and str(supp.get(k)).startswith("http"):
                    urls.append(supp.get(k))

    # 2. البحث فـ الجذر الرئيسي للـ Offer
    supp_main = offer.get("suppression_list", {}) or offer.get("suppression", {})
    if isinstance(supp_main, dict):
        for k in ["download_url", "file_url", "url", "opt_out_url", "unsubscribe_url"]:
            if supp_main.get(k) and str(supp_main.get(k)).startswith("http"):
                urls.append(supp_main.get(k))

    # 3. البحث في الحقول النصية المباشرة
    for k in ["suppression_download_url", "suppression_file_url", "suppression_url", "unsubscribe_url", "optout_url"]:
        val = offer.get(k)
        if val and isinstance(val, str) and val.startswith("http"):
            urls.append(val)

    if urls:
        return urls[0]
    return None

def download_and_unpack_zip(url):
    """تحميل الأرشيف وتفكيكه فـ الـ Memory لاستخراج ملفات txt مباشرة"""
    extracted_files = {}
    res = requests.get(url, timeout=120, verify=False)
    res.raise_for_status()
    
    # محاولة فك الضغط إذا كان zip
    try:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            for zip_info in z.infolist():
                if zip_info.is_dir():
                    continue
                fname = os.path.basename(zip_info.filename)
                if fname and not fname.startswith('.'):
                    file_content = z.read(zip_info.filename)
                    extracted_files[fname] = file_content
    except Exception:
        # إذا لم يكن ZIP، إرجاع الملف كما هو
        fname = url.split("?")[0].split("/")[-1] or "suppression_file.txt"
        extracted_files[fname] = res.content
        
    return extracted_files

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
        with st.spinner("جاري فحص جميع العروض واكتشاف روابط Suppression..."):
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
                        
                        # استخراج الرابط الحقيقي المباشر
                        dl_url = extract_suppression_url_from_offer_obj(offer)

                        if has_supp or (supp_id and str(supp_id) != "0") or dl_url:
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
                            "Suppression ID": str(supp_id),
                            "Direct_URL": dl_url,
                            "Raw_Offer_Data": offer
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.session_state["headers_used"] = headers_used
                    st.success(f"تم فحص جميع العروض بنجاح! الإجمالي: {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

# عرض أزرار التحميل
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    # عرض جدول العروض العام
    display_df = df.drop(columns=["Direct_URL", "Raw_Offer_Data"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("📄 استخراج وتحميل ملفات TXT مباشرة (Unpacked)")
        
        for idx, row in supp_df.iterrows():
            st.markdown(f"#### 🔹 [{row['Status']}] {row['Offer Name']} (ID: `{row['Offer ID']}` | Supp ID: `{row['Suppression ID']}`)")
            
            dl_url = row.get("Direct_URL")
            offer_obj = row.get("Raw_Offer_Data", {})

            # إذا لم يجد الرابط المباشر في الكائن، يحاول تجربة الـ API الخاصة بالـ optout برقم العرض
            if not dl_url:
                try:
                    opt_res = requests.get(f"https://api.eflow.team/v1/affiliates/offers/{row['Offer ID']}/optout", headers=headers_used, timeout=10, verify=False)
                    if opt_res.status_code == 200:
                        opt_data = opt_res.json()
                        dl_url = opt_data.get("download_url") or opt_data.get("url")
                except Exception:
                    pass

            if dl_url:
                try:
                    files_dict = download_and_unpack_zip(dl_url)
                    cols = st.columns(min(len(files_dict), 4))
                    c_idx = 0
                    for fname, content in files_dict.items():
                        col = cols[c_idx % len(cols)]
                        col.download_button(
                            label=f"📄 {fname}",
                            data=content,
                            file_name=fname,
                            key=f"dl_txt_file_{row['Offer ID']}_{c_idx}_{idx}"
                        )
                        c_idx += 1
                except Exception as ex:
                    st.error(f"خطأ أثناء استخراج الملف: {str(ex)}")
            else:
                st.warning("الرابط المباشر للملف غائب في استجابة السبونسر لهاد العرض (يتطلب طلب يدوي من الداشبورد)")
