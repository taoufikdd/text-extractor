import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax API Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax API Bulk Server Deployment")
st.markdown("إنشاء السيرفرات دفعة واحدة باستخدام الـ API Key الرسمي.")

# --- Sidebar: API Key & Base URL ---
st.sidebar.header("🔑 API Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="ضع الـ API Key هنا (مثال: ck_...)")
base_url = st.sidebar.text_input("API Base URL", value="https://cloudcenmax.com/api", help="رابط الـ API الأساسي")
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

# --- Test API Connection Button ---
if st.sidebar.button("🔌 Test API Connection"):
    if not api_key:
        st.sidebar.error("❌ أُدخل الـ API Key أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        # نجرب نقطة نهاية عامة (مثل servers أو user)
        test_endpoints = ["/servers", "/v1/servers", "/user", "/account"]
        success = False
        
        for ep in test_endpoints:
            try:
                res = requests.get(f"{base_url.rstrip('/')}{ep}", headers=headers, timeout=5)
                if res.status_code in [200, 401, 403, 422]:
                    st.sidebar.success(f"✅ API Reachable! Endpoint found: `{ep}` (Status: {res.status_code})")
                    success = True
                    break
            except Exception:
                continue
                
        if not success:
            st.sidebar.error("❌ لم يتم العثور على المسار الصحيح. تحقق من الـ API Docs في الموقع.")

# --- Locations Data ---
LOCATIONS_DATA = {
    "North America": {
        "Puerto Rico": {"San Juan": "san-juan"},
        "United States": {"New York": "ny", "Los Angeles": "la", "Miami": "miami", "Dallas": "dallas"},
        "Canada": {"Toronto": "toronto"}
    },
    "Europe": {
        "Angola / Europe Hub": {"AO Main": "AO"},
        "Germany": {"Frankfurt": "fra"},
        "United Kingdom": {"London": "lon"},
        "France": {"Paris": "par"}
    },
    "Asia / Other": {
        "Japan": {"Tokyo": "tyo"},
        "Singapore": {"Singapore": "sgp"}
    }
}

# --- Specs ---
st.subheader("📋 Targeted Specs (Fixed)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CPU", "4 vCPU")
col2.metric("RAM", "8192 MB")
col3.metric("Disk", "80 GB")
col4.metric("OS", "AlmaLinux 8.10 64bit")

st.divider()

# --- Deployment Form ---
st.subheader("🚀 Setup Bulk Deployment")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=50, value=1, step=1)

server_list = []
st.markdown("### 🌍 Select Location for Each Server:")

for i in range(int(num_servers)):
    st.markdown(f"#### 🖥️ Server #{i+1}")
    col_host, col_cont, col_country, col_city = st.columns([2, 2, 2, 2])
    
    with col_host:
        h_name = st.text_input("Hostname", value=f"server-alma8-{i+1}", key=f"host_{i}")
    with col_cont:
        selected_cont = st.selectbox("Continent", options=list(LOCATIONS_DATA.keys()), key=f"cont_{i}")
    with col_country:
        country_options = list(LOCATIONS_DATA[selected_cont].keys())
        selected_country = st.selectbox("Country", options=country_options, key=f"country_{i}")
    with col_city:
        city_dict = LOCATIONS_DATA[selected_cont][selected_country]
        selected_city_name = st.selectbox("City / State", options=list(city_dict.keys()), key=f"city_{i}")
        location_code = city_dict[selected_city_name]

    custom_code = st.text_input(
        f"Region Code: ({location_code}) — [Type custom code if needed]:", 
        value=location_code, 
        key=f"code_override_{i}"
    )

    server_list.append({
        "hostname": h_name,
        "location": custom_code if custom_code else location_code,
        "continent": selected_cont,
        "country": selected_country,
        "city": selected_city_name
    })
    st.divider()

# --- Execution ---
if st.button("🔥 Deploy All Servers Now", type="primary"):
    if not api_key:
        st.error("❌ أُدخل الـ API Key أولاً في الـ Sidebar!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        progress = st.progress(0)
        status_box = st.container()
        logs_and_errors = []

        # محاولة إرسال الطلب لـ /servers (يمكنك تعديلها بناء على الـ Docs)
        target_url = f"{base_url.rstrip('/')}/servers"

        for idx, srv in enumerate(server_list):
            payload = {
                "hostname": srv["hostname"],
                "name": srv["hostname"],
                "region": srv["location"],
                "location": srv["location"],
                "os": "almalinux-8.10",
                "plan": "4vcpu-8gb-80gb",
                "vcpus": 4,
                "ram": 8192,
                "disk": 80,
                "password": root_password,
                "root_password": root_password
            }

            try:
                res = requests.post(target_url, json=payload, headers=headers, timeout=15)
                if res.status_code in [200, 201, 202]:
                    status_box.success(f"✅ Created **{srv['hostname']}** successfully!")
                else:
                    status_box.error(f"❌ Failed **{srv['hostname']}**: HTTP Status {res.status_code}")
                    logs_and_errors.append({
                        "hostname": srv["hostname"],
                        "status_code": res.status_code,
                        "url_called": target_url,
                        "payload_sent": payload,
                        "response_body": res.text
                    })
            except Exception as e:
                status_box.error(f"❌ Connection Error on **{srv['hostname']}**: {str(e)}")
                logs_and_errors.append({
                    "hostname": srv["hostname"],
                    "status_code": "EXCEPTION",
                    "url_called": target_url,
                    "payload_sent": payload,
                    "response_body": str(e)
                })

            progress.progress((idx + 1) / len(server_list))

        if logs_and_errors:
            st.markdown("---")
            st.subheader("🚨 Detailed Error Logs & Diagnostics")
            st.info("💡 ملاحظة: إذا ظهر خطأ 404، يرجى النقر على رابط **'Read the API docs'** في أعلى يمين موقع CloudCenmax لمعرفة المسار الصحيح (Endpoint) لإنشاء السيرفرات وإخباري به.")
            for err in logs_and_errors:
                with st.expander(f"❌ Error Log: {err['hostname']} (Status: {err['status_code']})"):
                    st.write("**URL:**", err["url_called"])
                    st.write("**Payload:**")
                    st.json(err["payload_sent"])
                    st.write("**Response:**")
                    try:
                        st.json(json.loads(err["response_body"]))
                    except Exception:
                        st.code(err["response_body"], language="html")
        else:
            st.balloons()
