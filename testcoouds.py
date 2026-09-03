import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Bulk Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Server Deployment")
st.markdown("قم بإنشاء السيرفرات دفعة واحدة مع أداة كشف وتتبع الأخطاء (Error Diagnostics).")

# --- Simple Sidebar: API Key & Root Password ---
st.sidebar.header("🔑 Authentication & Security")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="أدخل مفتاح الـ API الخاص بك")
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

BASE_URL = "https://cloudcenmax.com/api/v1"

# --- Button to Test API Connection ---
if st.sidebar.button("🔌 Test API Connection"):
    if not api_key:
        st.sidebar.error("❌ أدخل API Key أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Accept": "application/json"
        }
        try:
            # نحاول الاتصال بنقطة النهاية الخاصة بالـ User أو Profile
            res = requests.get(f"{BASE_URL}/user", headers=headers, timeout=10)
            if res.status_code == 200:
                st.sidebar.success("✅ Connected successfully to API!")
            elif res.status_code == 401:
                st.sidebar.error("❌ Authentication Failed (401): API Key غير صحيح.")
            elif res.status_code == 404:
                # تجربة مسار آخر عام للتأكد
                res_alt = requests.get(f"{BASE_URL}/locations", headers=headers, timeout=10)
                if res_alt.status_code in [200, 401]:
                    st.sidebar.warning(f"⚠️ API Reached (Status {res_alt.status_code}), Endpoint '/user' not found.")
                else:
                    st.sidebar.error(f"❌ Connection failed: Status {res.status_code}")
            else:
                st.sidebar.warning(f"⚠️ API Response Code: {res.status_code}")
        except Exception as e:
            st.sidebar.error(f"❌ Connection Error: {str(e)}")

# --- Locations Data (Dropdown Selection) ---
LOCATIONS_DATA = {
    "North America": {
        "Puerto Rico": {
            "San Juan": "san-juan"
        },
        "United States": {
            "New York": "ny",
            "Los Angeles": "la",
            "Miami": "miami",
            "Dallas": "dallas"
        },
        "Canada": {
            "Toronto": "toronto"
        }
    },
    "Europe": {
        "Angola / Europe Hub": {
            "AO Main": "AO"
        },
        "Germany": {
            "Frankfurt": "fra"
        },
        "United Kingdom": {
            "London": "lon"
        },
        "France": {
            "Paris": "par"
        }
    },
    "Asia / Other": {
        "Japan": {
            "Tokyo": "tyo"
        },
        "Singapore": {
            "Singapore": "sgp"
        }
    }
}

# --- Fixed Specifications ---
st.subheader("📋 Targeted Specs (Fixed)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CPU", "4 vCPU")
col2.metric("RAM", "8192 MB")
col3.metric("Disk", "80 GB")
col4.metric("OS", "AlmaLinux 8.10 64bit")

st.divider()

# --- Bulk Configuration ---
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

    # Custom Region/Location override
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

# --- Execution & Error Interface ---
if st.button("🔥 Deploy All Servers Now", type="primary"):
    if not api_key:
        st.error("❌ يرجى إدخال API Key فـ الـ Sidebar أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        progress = st.progress(0)
        status_box = st.container()
        
        # قائمة لتجميع تفاصيل الأخطاء
        logs_and_errors = []

        for idx, srv in enumerate(server_list):
            payload = {
                "hostname": srv["hostname"],
                "name": srv["hostname"],
                "region": srv["location"],
                "location": srv["location"],
                "continent": srv["continent"],
                "country": srv["country"],
                "city": srv["city"],
                "plan": "standard-4vcpu-8gb",
                "vcpus": 4,
                "ram": 8192,
                "disk": 80,
                "image": "almalinux-8.10-x64",
                "os": "almalinux-8.10",
                "password": root_password,
                "root_password": root_password
            }

            try:
                res = requests.post(f"{BASE_URL}/servers", json=payload, headers=headers, timeout=15)
                
                if res.status_code in [200, 201, 202]:
                    status_box.success(
                        f"✅ **{srv['hostname']}** created successfully! "
                        f"(Location: {srv['location']})"
                    )
                else:
                    status_box.error(
                        f"❌ Failed **{srv['hostname']}**: HTTP Status {res.status_code}"
                    )
                    # حفظ تفاصيل الخطأ للعرض
                    logs_and_errors.append({
                        "hostname": srv["hostname"],
                        "status_code": res.status_code,
                        "url_called": f"{BASE_URL}/servers",
                        "payload_sent": payload,
                        "response_body": res.text
                    })
            except Exception as e:
                status_box.error(f"❌ Connection Error on **{srv['hostname']}**: {str(e)}")
                logs_and_errors.append({
                    "hostname": srv["hostname"],
                    "status_code": "EXCEPTION",
                    "url_called": f"{BASE_URL}/servers",
                    "payload_sent": payload,
                    "response_body": str(e)
                })

            progress.progress((idx + 1) / len(server_list))

        # --- Error Diagnostics Interface ---
        if logs_and_errors:
            st.markdown("---")
            st.subheader("🚨 Detailed Error Logs & Diagnostics")
            st.warning("تم تسجيل أخطاء أثناء تنفيذ الطلبات. يمكنك مراجعة التفاصيل أدناه لمعرفة السبب بالتحديد:")

            for err in logs_and_errors:
                with st.expander(f"❌ Error Log for: {err['hostname']} (Status: {err['status_code']})"):
                    st.write("**URL Endpoint:**", err["url_called"])
                    st.write("**Sent Payload:**")
                    st.json(err["payload_sent"])
                    st.write("**Server Response (Body):**")
                    try:
                        st.json(json.loads(err["response_body"]))
                    except Exception:
                        st.code(err["response_body"], language="html")
        else:
            st.balloons()
