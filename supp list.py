import streamlit as st
import requests
import pandas as pd
import json

def fetch_all_offers_everflow(base_url, auth_method, api_key, custom_header_name):
    """جلب جميع العروض (Active + Paused)"""
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

def get_suppression_url_from_offer_obj(offer):
    """بحث داخل عنصر العرض عن أي رابط مخصص لـ Suppression"""
    keys_to_check = [
        "suppression_list_url", "suppression_file_url", "suppression_url",
        "suppression_download_url", "unsubscribe_url", "suppression_link"
    ]
    for key in keys_to_check:
        val = offer.get(key)
        if val and isinstance(val, str) and val.startswith("http"):
            return val
            
    # البحث داخل الأحافير الفرعية مثل relationship أو details
    if "relationship" in offer and isinstance(offer["relationship"], dict):
        rel = offer["relationship"]
        for key in keys_to_check:
            val = rel.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                return val
                
    return None

def fetch_single_offer_details(network_offer_id, headers):
    """طلب تفاصيل عرض فردي لربما يحتوي على رابط الـ suppression"""
    try:
        url = f"https://api.eflow.team/v1/affiliates/offers/{network_offer_id}"
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return get_suppression_url_from_offer_obj(data), data
    except Exception:
        pass
    return None, None

def download_file_bytes(download_url, headers=None):
    """تحميل الملف من الرابط النهائي"""
    # جرب التنزيل بدون الهيدر أولاً (إذا كان S3/CloudFront)
    try:
        resp = requests.get(download_url, timeout=40, verify=False)
        if resp.status_code == 200:
            filename = download_url.split("?")[0].split("/")[-1]
            if not filename or "." not in filename:
                filename = "suppression_list.zip"
            return resp.content, filename
    except Exception:
        pass
        
    # إذا فشل، جرب بالهيدرات
    resp = requests.get(download_url, headers=headers, timeout=40, verify=False)
    resp.raise_for_status()
    filename = download_url.split("?")[0].split("/")[-1]
    if not filename or "." not in filename:
        filename = "suppression_list.zip"
    return resp.content, filename

# --- UI Setup ---
st.set_page_config(page_title="Affiliate Suppression Detector", page_icon="🛡️", layout="wide")
st.title("🛡️ Affiliate Suppression List Detector")

with st.sidebar:
    st.header("Sponsor Configuration")
    sponsor_name = st.text_input("Sponsor Name", value="XI Leads")
    api_url = st.text_input(
        "API Endpoint URL", 
        value="https://api.eflow.team/v1/affiliates/alloffers"
    )
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
        with st.spinner("جاري فحص جميع العروض (النشطة والموقوفة)..."):
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
                        
                        # استخراج الرابط المباشر إن وجد فـ الـ Object المباشر
                        supp_url = get_suppression_url_from_offer_obj(offer)

                        if has_supp or (supp_id and supp_id != 0) or supp_url:
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
                            "Direct Supp URL": supp_url if supp_url else ""
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.session_state["raw_offers"] = offers_list
                    st.session_state["headers_used"] = headers_used
                    st.success(f"تم فحص جميع العروض بنجاح! الإجمالي: {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

# عرض الجدول وقائمة التحميل
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    st.subheader("الإحصائيات")
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي العروض المجلوبة", len(df))
    col2.metric("عروض بـ Suppression", len(df[df["Suppression Found"] == "Yes"]))
    col3.metric("عروض بدون Suppression", len(df[df["Suppression Found"] == "No"]))

    st.markdown("---")
    st.dataframe(df, use_container_width=True)

    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 تحميل الجدول الكامل كـ CSV",
        data=csv_data,
        file_name="all_offers_with_suppression.csv",
        mime="text/csv"
    )

    # قائمة التحميل المباشرة
    supp_df = df[df["Suppression Found"] == "Yes"]
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("📥 تحميل ملفات الـ Suppression مباشرة")
        
        for idx, row in supp_df.iterrows():
            d_col1, d_col2 = st.columns([3, 1])
            d_col1.write(f"**[{row['Status']}] {row['Offer Name']}** (Offer ID: `{row['Offer ID']}` | Supp ID: `{row['Suppression ID']}`)")
            
            target_url = row["Direct Supp URL"]
            
            # إذا لم يوجد الرابط فـ القائمة العامة نطلب التفاصيل الفردية للعرض
            if not target_url:
                with st.spinner(f"جلب رابط العرض {row['Offer ID']}..."):
                    target_url, _ = fetch_single_offer_details(row["Offer ID"], headers_used)

            if target_url:
                try:
                    file_data, fname = download_file_bytes(target_url, headers_used)
                    d_col2.download_button(
                        label=f"⬇️ تحميل {fname}",
                        data=file_data,
                        file_name=f"Offer_{row['Offer ID']}_{fname}",
                        key=f"dl_btn_{row['Offer ID']}_{idx}"
                    )
                except Exception as ex:
                    d_col2.error(f"خطأ أثناء التحميل: {str(ex)[:50]}")
            else:
                d_col2.warning("لم يتم العثور على رابط مباشر فـ API العرض")
