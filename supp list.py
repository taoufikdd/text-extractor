import streamlit as st
import requests
import pandas as pd
import json

# الكلمات المفتاحية للبحث عن ملفات/روابط الإلغاء فـ JSON
SUPPRESSION_KEYWORDS = [
    "suppression", "suppression_file", "suppression_url", "suppression list",
    "blacklist", "exclusion", "exclude", "optout", "opt_out", "do_not_contact", "dnc"
]

# المفاتيح الشائعة التي تحتوي على مصفوفة العروض
CONTAINER_KEYS = ["offers", "data", "results", "items", "campaigns", "response"]

def find_offers_list(data):
    """البحث الذكي عن قائمة العروض داخل الاستجابة"""
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
    """البحث التكراري عن حقول Suppression داخل العرض"""
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
    """استخراج المعطيات الأساسية مثل ID و Name و GEO"""
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
    """الاتصال بـ API واستخراج البيانات بحماية ضد أخطاء SSL والـ Pagination"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    if auth_method == "Bearer Token":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_method == "X-API-Key":
        headers["X-API-Key"] = api_key
    elif auth_method == "API-Key":
        headers["API-Key"] = api_key
    elif auth_method == "Custom Header" and custom_header_name:
        headers[custom_header_name.strip()] = api_key.strip()

    clean_url = url.strip()
    # إضافة المعطيات تلقائياً لـ Everflow لمنع خطأ 500
    if ("everflow" in clean_url.lower() or "eflow" in clean_url.lower()) and "?" not in clean_url:
        clean_url += "?page=1&page_size=100"

    response = requests.get(clean_url, headers=headers, timeout=30, verify=False)
    
    if response.status_code == 401 or response.status_code == 403:
        raise Exception(f"خطأ في التوثيق (HTTP {response.status_code}): تأكد من صحة الـ API Key و Header Name.")
    elif response.status_code != 200:
        error_msg = response.text[:200] if response.text else "No error body"
        raise Exception(f"خطأ من السيرفر (HTTP {response.status_code}): {error_msg}")
        
    if not response.text.strip():
        raise Exception("الـ API أرجع استجابة فارغة. تأكد من صحة الرابط.")

    try:
        return response.json()
    except Exception:
        raise Exception("فشل تحويل الاستجابة إلى JSON.")

def download_suppression_file(url):
    """تحميل ملف Suppression"""
    resp = requests.get(url, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.content

# --- واجهة المستخدم (Streamlit UI) ---
st.set_page_config(
    page_title="Affiliate Suppression Detector",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Affiliate Suppression List Detector")
st.caption("كشف واستخراج ملفات Suppression تلقائياً من شبكات الأفلييت")

# القائمة الجانبية
with st.sidebar:
    st.header("Sponsor Configuration")
    sponsor_name = st.text_input("Sponsor Name", value="XI Leads", placeholder="e.g., XI Leads")
    api_url = st.text_input(
        "API Endpoint URL", 
        value="https://api.eflow.team/v1/affiliates/offers?page=1&page_size=100",
        placeholder="https://api.eflow.team/v1/affiliates/offers?page=1&page_size=100"
    )
    
    auth_method = st.selectbox(
        "Authentication Method",
        ["Custom Header", "Bearer Token", "X-API-Key", "API-Key", "No Authentication"]
    )
    
    custom_header_name = ""
    if auth_method == "Custom Header":
        custom_header_name = st.text_input("Custom Header Name", value="x-eflow-api-key")

    api_key = ""
    if auth_method != "No Authentication":
        api_key = st.text_input("API Key / Token", type="password")

    scan_submitted = st.button("Scan Offers", use_container_width=True, type="primary")

# التنفيذ عند الضغط على Scan
if scan_submitted:
    if not api_url or (auth_method != "No Authentication" and not api_key):
        st.error("المرجو إدخال رابط الـ API والمعطيات المطلوبة.")
    else:
        with st.spinner("جاري الاتصال بـ API وفحص العروض..."):
            try:
                json_data = fetch_api_data(api_url, auth_method, api_key, custom_header_name)
                offers_list = find_offers_list(json_data)

                if not offers_list:
                    st.warning("تم الاتصال بنجاح، لكن لم يتم العثور على قائمة عروض داخل JSON.")
                else:
                    processed_records = []
                    for offer in offers_list:
                        if not isinstance(offer, dict):
                            continue
                        
                        offer_id = extract_field_by_candidates(offer, ["network_offer_id", "offer_id", "id", "campaign_id"])
                        offer_name = extract_field_by_candidates(offer, ["name", "title", "offer_name", "campaign_name"])
                        geo = extract_field_by_candidates(offer, ["geo", "countries", "country", "relationship", "target_countries"])

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
                    st.success(f"تمت العملية بنجاح! تم فحص {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

# عرض النتائج والفلاتر
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]

    st.subheader("الإحصائيات")
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي العروض", len(df))
    col2.metric("Suppression متوفر", len(df[df["Suppression Found"] == "Yes"]))
    col3.metric("Suppression غير متوفر", len(df[df["Suppression Found"] == "No"]))

    st.markdown("---")
    st.subheader("الفلاتر والبحث")

    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    with f_col1:
        supp_filter = st.selectbox("حالة الـ Suppression", ["الكل", "المتوفر فقط", "غير المتوفر"])
    with f_col2:
        search_name = st.text_input("بحث باسم العرض", "")
    with f_col3:
        all_geos = ["الكل"] + sorted(list(set(df["GEO"].dropna().astype(str))))
        selected_geo = st.selectbox("تصفية حسب GEO", all_geos)
    with f_col4:
        all_sponsors = ["الكل"] + sorted(list(set(df["Sponsor"].dropna().astype(str))))
        selected_sponsor = st.selectbox("تصفية حسب Sponsor", all_sponsors)

    filtered_df = df.copy()

    if supp_filter == "المتوفر فقط":
        filtered_df = filtered_df[filtered_df["Suppression Found"] == "Yes"]
    elif supp_filter == "غير المتوفر":
        filtered_df = filtered_df[filtered_df["Suppression Found"] == "No"]

    if search_name:
        filtered_df = filtered_df[filtered_df["Offer Name"].str.contains(search_name, case=False, na=False)]

    if selected_geo != "الكل":
        filtered_df = filtered_df[filtered_df["GEO"] == selected_geo]

    if selected_sponsor != "الكل":
        filtered_df = filtered_df[filtered_df["Sponsor"] == selected_sponsor]

    st.dataframe(filtered_df, use_container_width=True)

    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 تحميل النتائج المفلترة (CSV)",
        data=csv_data,
        file_name="suppression_results.csv",
        mime="text/csv"
    )

    # أزرار التحميل المباشرة للملفات
    supp_urls = filtered_df[filtered_df["Suppression File URL"].str.startswith("http", na=False)]
    if not supp_urls.empty:
        st.markdown("---")
        st.subheader("تحميل ملفات Suppression المكتشفة")
        for idx, row in supp_urls.iterrows():
            d_col1, d_col2 = st.columns([3, 1])
            d_col1.write(f"**{row['Offer Name']}** (ID: {row['Offer ID']}) — `{row['Suppression File URL']}`")
            
            try:
                file_content = download_suppression_file(row["Suppression File URL"])
                file_name = row["Suppression File URL"].split("/")[-1].split("?")[0]
                if not file_name or "." not in file_name:
                    file_name = f"suppression_{row['Offer ID']}.txt"
                
                d_col2.download_button(
                    label=f"تحميل {file_name}",
                    data=file_content,
                    file_name=file_name,
                    key=f"dl_{idx}"
                )
            except Exception:
                d_col2.error("تعذر التحميل")
