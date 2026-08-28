import streamlit as st
import requests
import pandas as pd
import json

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

def get_exact_suppression_file(network_offer_id, supp_id, headers):
    """جلب رابط المحتوى الحقيقي للـ Suppression List بالظبط"""
    try:
        # 1. المحاولة الأولى: طلب تفاصيل الـ Suppression List المباشرة بواسطة ID
        if supp_id and str(supp_id) != "0":
            supp_url = f"https://api.eflow.team/v1/affiliates/suppressionlists/{supp_id}"
            resp = requests.get(supp_url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                for key in ["download_url", "file_url", "url", "s3_url"]:
                    if key in data and data[key] and str(data[key]).startswith("http"):
                        fname = data.get("filename") or data.get("name") or f"suppression_{supp_id}.zip"
                        return data[key], fname, None

        # 2. المحاولة الثانية: طلب تفاصيل العرض الفردي ومراجعة الـ suppression_list الداخلي
        offer_url = f"https://api.eflow.team/v1/affiliates/offers/{network_offer_id}"
        resp = requests.get(offer_url, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            
            # فحص الـ relationship -> suppression_list
            rel = data.get("relationship", {})
            supp_obj = rel.get("suppression_list", {}) or data.get("suppression_list", {})
            
            if isinstance(supp_obj, dict):
                dl_url = supp_obj.get("download_url") or supp_obj.get("file_url") or supp_obj.get("url")
                fname = supp_obj.get("filename") or supp_obj.get("name")
                if dl_url:
                    if not fname:
                        fname = dl_url.split("?")[0].split("/")[-1]
                    return dl_url, fname, None

            # فحص عام في حال كان الرابط في الجذر
            for k in ["suppression_download_url", "download_url"]:
                if k in data and data[k]:
                    fname = data.get("suppression_filename", f"suppression_{network_offer_id}.zip")
                    return data[k], fname, None

        return None, None, "لم يتم العثور على رابط الملف المباشر"
    except Exception as e:
        return None, None, str(e)

def download_file_bytes(url):
    """تحميل بايتات الملف مباشرة من AWS / S3"""
    res = requests.get(url, timeout=90, verify=False)
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

# عرض نتائج التحميل
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})

    st.dataframe(df, use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("📥 تحميل ملفات الـ Suppression الأصلية (المحتوى الصحيح)")
        
        for idx, row in supp_df.iterrows():
            d_col1, d_col2 = st.columns([3, 1])
            d_col1.write(f"**[{row['Status']}] {row['Offer Name']}** (Offer ID: `{row['Offer ID']}` | Supp ID: `{row['Suppression ID']}`)")
            
            # جلب رابط المحتوى الدقيق
            dl_url, exact_filename, err = get_exact_suppression_file(row["Offer ID"], row["Suppression ID"], headers_used)
            
            if dl_url:
                try:
                    file_data = download_file_bytes(dl_url)
                    d_col2.download_button(
                        label=f"⬇️ {exact_filename}",
                        data=file_data,
                        file_name=exact_filename,
                        key=f"dl_btn_exact_{row['Offer ID']}_{idx}"
                    )
                except Exception as ex:
                    d_col2.error(f"خطأ في التنزيل: {str(ex)[:30]}")
            else:
                d_col2.warning(f"غير متوفر ({err if err else 'N/A'})")
