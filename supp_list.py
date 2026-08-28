import streamlit as st
import requests
import pandas as pd
import json
import zipfile
import gzip
import io
import os
import re
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

# تعطيل تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Affiliate Suppression List Merger", page_icon="🛡️", layout="wide")

def fetch_all_offers_everflow(base_url, auth_method, api_key, custom_header_name):
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
        try:
            response = requests.get(paginated_url, headers=headers, timeout=20, verify=False)
            if response.status_code != 200:
                if page == 1:
                    paginated_url = f"{base_endpoint}?page={page}&page_size={page_size}"
                    response = requests.get(paginated_url, headers=headers, timeout=20, verify=False)
                    if response.status_code != 200:
                        break
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
        except Exception:
            break

    return all_offers, headers

def deep_search_suppression_url(obj):
    if not obj:
        return ""
    try:
        str_obj = json.dumps(obj)
    except Exception:
        str_obj = str(obj)

    patterns = [
        r'https?://[^\s"]+\.(?:zip|gz|csv|txt|tar)[^\s"]*',
        r'https?://[^\s"]*optizmo[^\s"]*',
        r'https?://[^\s"]*unsubcentral[^\s"]*',
        r'https?://[^\s"]*suppress[^\s"]*',
        r'https?://[^\s"]*download[^\s"]*'
    ]
    
    for pat in patterns:
        matches = re.findall(pat, str_obj, re.IGNORECASE)
        if matches:
            return str(matches[0])

    if isinstance(obj, dict):
        for key in ["download_url", "file_url", "url", "opt_out_url", "unsubscribe_url", "suppression_download_url"]:
            if obj.get(key) and isinstance(obj.get(key), str) and obj.get(key).startswith("http"):
                return obj.get(key)

    return ""

def fetch_suppression_url_by_id(supp_id, headers):
    if not supp_id or str(supp_id) == "0":
        return ""
    try:
        url = f"https://api.eflow.team/v1/affiliates/suppressionlists/{supp_id}"
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            return deep_search_suppression_url(res.json())
    except Exception:
        pass
    return ""

def resolve_optizmo_or_direct_download(url):
    """تحويل روابط Optizmo والروبط التفاعلية إلى روابط تحميل مباشرة للملفات"""
    if not url or not isinstance(url, str):
        return ""

    url_str = url.strip()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # معالجة Optizmo Access Links
    if "optizmo" in url_str.lower():
        if not url_str.endswith("/download") and not re.search(r'\.(zip|gz|txt|csv)$', url_str, re.I):
            url_str = url_str.rstrip("/") + "/download"

    try:
        session = requests.Session()
        res = session.get(url_str, headers=headers, timeout=20, verify=False, allow_redirects=True)
        
        # إذا كانت الاستجابة تحتوي على رابط تحميل داخلي (فـ حالة صفحات HTML)
        if "text/html" in res.headers.get("Content-Type", "").lower():
            html_text = res.text
            found_dl = re.findall(r'href=["\'](https?://[^"\']+\.(?:zip|gz|csv|txt))[["\']', html_text, re.I)
            if found_dl:
                return found_dl[0]
            
            # فحص أزرار Optizmo المباشرة
            optizmo_dl = re.findall(r'https?://[^\s"\'<>]*/download[^\s"\'<>]*', html_text, re.I)
            if optizmo_dl:
                return optizmo_dl[0]

        return res.url
    except Exception:
        return url_str

def fetch_file_content(url):
    """تنزيل محتوى الملف كيفما كان نوعه"""
    download_target = resolve_optizmo_or_direct_download(url)
    if not download_target:
        download_target = url

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = requests.get(download_target, headers=headers, timeout=40, verify=False, allow_redirects=True)
    res.raise_for_status()
    return res.content

def extract_files_and_emails(content_bytes):
    """استخراج جميع الإيميلات والملفات سواء كانت ZIP, GZ, CSV أو TXT"""
    emails = set()
    files_extracted = {}

    # 1. تجربة فك ضغط ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            for zip_info in z.infolist():
                if zip_info.is_dir():
                    continue
                fname = os.path.basename(zip_info.filename)
                if fname and not fname.startswith('.'):
                    raw_data = z.read(zip_info.filename)
                    files_extracted[fname] = raw_data
                    text_str = raw_data.decode('utf-8', errors='ignore')
                    found = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_str)
                    emails.update([e.lower().strip() for e in found])
        if files_extracted:
            return emails, files_extracted
    except Exception:
        pass

    # 2. تجربة فك ضغط GZIP (.gz)
    try:
        decompressed = gzip.decompress(content_bytes)
        text_str = decompressed.decode('utf-8', errors='ignore')
        found = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_str)
        emails.update([e.lower().strip() for e in found])
        files_extracted["suppression_list.txt"] = decompressed
        return emails, files_extracted
    except Exception:
        pass

    # 3. قراءة الملف مباشرة كـ Plain Text / CSV
    try:
        text_str = content_bytes.decode('utf-8', errors='ignore')
        found = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text_str)
        if found:
            emails.update([e.lower().strip() for e in found])
            files_extracted["suppression_list.txt"] = content_bytes
    except Exception:
        pass

    return emails, files_extracted

def fetch_and_extract_emails_from_offer(offer_row, headers_used):
    emails = set()
    dl_url = offer_row.get("Direct_URL")
    
    if not dl_url or not isinstance(dl_url, str) or dl_url.strip() == "":
        dl_url = fetch_suppression_url_by_id(offer_row.get("Suppression ID"), headers_used)

    if dl_url and isinstance(dl_url, str) and dl_url.startswith("http"):
        try:
            content_bytes = fetch_file_content(dl_url)
            extracted_emails, _ = extract_files_and_emails(content_bytes)
            emails.update(extracted_emails)
        except Exception:
            pass
    return emails

# --- UI Interface ---
st.title("🛡️ Fast Affiliate Suppression List Merger")

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
        with st.spinner("جاري فحص جميع العروض..."):
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
                        
                        if not supp_id or str(supp_id) == "0":
                            rel = offer.get("relationship", {})
                            if isinstance(rel, dict):
                                supp_obj = rel.get("suppression_list", {})
                                if isinstance(supp_obj, dict):
                                    supp_id = supp_obj.get("network_suppression_list_id") or supp_obj.get("suppression_list_id", 0)

                        dl_url = deep_search_suppression_url(offer)

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
                            "Direct_URL": dl_url if dl_url else ""
                        })

                    st.session_state["scan_results"] = pd.DataFrame(processed_records)
                    st.session_state["headers_used"] = headers_used
                    st.session_state["sponsor_name"] = sponsor_name
                    st.success(f"تم فحص جميع العروض بنجاح! الإجمالي: {len(processed_records)} عرض.")
            except Exception as e:
                st.error(f"حدث خطأ: {str(e)}")

# Display Results & Actions
if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
    df = st.session_state["scan_results"]
    headers_used = st.session_state.get("headers_used", {})
    s_name = st.session_state.get("sponsor_name", "Sponsor")

    display_df = df.drop(columns=["Direct_URL"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

    supp_df = df[df["Suppression Found"] == "Yes"]
    
    if not supp_df.empty:
        st.markdown("---")
        st.subheader("⚡ دمج سريع وتنقية جميع ملفات الـ Suppression")
        st.info(f"تم إيجاد {len(supp_df)} عرض يحتوي على ملفات Suppression. اضغط على الزر للدمج والتنقية الفورية.")

        if st.button("🚀 Fast Merge & Clean All Suppressions", type="primary", use_container_width=True):
            all_unique_emails = set()
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_offers = len(supp_df)
            completed = 0

            rows_list = supp_df.to_dict('records')

            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_offer = {executor.submit(fetch_and_extract_emails_from_offer, row, headers_used): row for row in rows_list}
                
                for future in as_completed(future_to_offer):
                    completed += 1
                    status_text.text(f"جاري معالجة وتنزيل الملفات بالتوازي: ({completed}/{total_offers})...")
                    progress_bar.progress(completed / total_offers)
                    
                    try:
                        extracted = future.result()
                        all_unique_emails.update(extracted)
                    except Exception:
                        pass

            status_text.empty()
            progress_bar.empty()

            if all_unique_emails:
                cleaned_content = "\n".join(sorted(all_unique_emails))
                st.success(f"⚡ اكتملت العملية بنجاح! تم استخراج {len(all_unique_emails):,} إيميل فريد بدون أي تكرار.")

                st.download_button(
                    label=f"💾 تحميل ملف الإيميلات المدمج النهائي ({len(all_unique_emails):,} Emails)",
                    data=cleaned_content,
                    file_name=f"suppression_emails_{s_name.replace(' ', '_')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            else:
                st.warning("لم يتم العثور على إيميلات فـ الملفات المفحوصة.")

        st.markdown("---")
        st.subheader("📄 التحميل الفردي للملفات (Unpacked)")
        
        for idx, row in supp_df.iterrows():
            st.markdown(f"#### 🔹 [{row['Status']}] {row['Offer Name']} (ID: `{row['Offer ID']}` | Supp ID: `{row['Suppression ID']}`)")
            
            dl_url = row.get("Direct_URL")
            if not dl_url or not isinstance(dl_url, str) or dl_url.strip() == "":
                dl_url = fetch_suppression_url_by_id(row.get("Suppression ID"), headers_used)

            if dl_url and isinstance(dl_url, str) and dl_url.startswith("http"):
                try:
                    raw_bytes = fetch_file_content(dl_url)
                    _, files_dict = extract_files_and_emails(raw_bytes)
                    
                    if files_dict:
                        cols = st.columns(min(max(len(files_dict), 1), 4))
                        c_idx = 0
                        for fname, content in files_dict.items():
                            col = cols[c_idx % len(cols)]
                            col.download_button(
                                label=f"📄 {fname}",
                                data=content,
                                file_name=fname,
                                key=f"dl_btn_{row['Offer ID']}_{c_idx}_{idx}"
                            )
                            c_idx += 1
                    else:
                        st.warning("لم نتمكن من فك ضغط الملف مباشرة.")
                except Exception as ex:
                    st.error(f"خطأ أثناء جلب الملف: {str(ex)}")
            else:
                st.warning("لا يوجد رابط تحميل مباشر متوفر لهذا العرض.")
