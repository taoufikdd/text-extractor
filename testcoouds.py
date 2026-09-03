import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Dynamic Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Dynamic Bulk Deployer")
st.markdown("جلب القارات، الدول، والمدن تلقائياً عبر الـ API واختيارها ديناميكياً.")

# --- Sidebar Authentication ---
st.sidebar.header("🔑 API Credentials")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="ضع API Key الخاص بك")
base_url = "https://cloudcenmax.com/api/v1"
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

# --- Helper Function: Fetch Regions Dynamic ---
@st.cache_data(ttl=300)
def fetch_locations_from_api(key):
    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "Accept": "application/json"
    }
    
    # تجربة النقاط الرسمية المعتادة فـ REST APIs للمواقع
    endpoints = ["/regions", "/locations", "/plans", "/servers/options"]
    
    for ep in endpoints:
        try:
            res = requests.get(f"{base_url}{ep}", headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, (dict, list)) and len(data) > 0:
                    return data, ep
        except Exception:
            continue
    return None, None

# --- Get Dynamic Locations Data ---
locations_data = None
active_endpoint = None

if api_key:
    locations_data, active_endpoint = fetch_locations_from_api(api_key)

# إذا لم تعطي الـ API القائمة أو حدث خطأ، نستعمل fallback هيكلي مطابق لصفحتهم فـ الصور
STATIC_LOCATIONS = {
    "Africa": {
        "Morocco": {"Casablanca / Rab": "morocco"},
        "Nigeria": {"Lagos": "nigeria"},
        "South Africa": {"Johannesburg": "south-africa"}
    },
    "Europe": {
        "Germany": {"Frankfurt": "fra"},
        "United Kingdom": {"London": "lon"},
        "France": {"Paris": "par"},
        "Albania": {"Tirana": "albania"},
        "Austria": {"Vienna": "austria"},
        "Belgium": {"Brussels": "belgium"},
        "Netherlands": {"Amsterdam": "netherlands"},
        "Spain": {"Madrid / San Juan Hub": "san-juan"}
    },
    "North America": {
        "United States": {"New York": "ny", "Los Angeles": "la"},
        "Canada": {"Toronto": "toronto"},
        "Puerto Rico": {"San Juan": "san-juan"}
    },
    "Asia": {
        "Japan": {"Tokyo": "tyo"},
        "Singapore": {"Singapore": "sgp"}
    }
}

if locations_data:
    st.sidebar.success(f"✅ تم جلب المناطق ديناميكياً من API ({active_endpoint})")
else:
    if api_key:
        st.sidebar.info("ℹ️ استدعينا القائمة الجغرافية المحلية المطابقة لموقعهم")
    locations = STATIC_LOCATIONS

# --- Server Form Configuration ---
st.subheader("📋 Targeted Specs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CPU", "4 vCPU")
col2.metric("RAM", "8192 MB")
col3.metric("Disk", "80 GB")
col4.metric("OS", "AlmaLinux 8.10")

st.divider()

st.subheader("🚀 Bulk Deployment Configuration")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=50, value=1, step=1)

server_list = []

for i in range(int(num_servers)):
    st.markdown(f"#### 🖥️ Server #{i+1}")
    
    col_host, col_cont, col_country, col_city = st.columns([2, 2, 2, 2])
    
    with col_host:
        h_name = st.text_input("Hostname", value=f"server-alma8-{i+1}", key=f"h_{i}")
        
    with col_cont:
        continent_keys = list(STATIC_LOCATIONS.keys())
        selected_cont = st.selectbox("Continent", options=continent_keys, key=f"cont_{i}")
        
    with col_country:
        country_keys = list(STATIC_LOCATIONS[selected_cont].keys())
        selected_country = st.selectbox("Country", options=country_keys, key=f"country_{i}")
        
    with col_city:
        city_dict = STATIC_LOCATIONS[selected_cont][selected_country]
        selected_city = st.selectbox("City / Target", options=list(city_dict.keys()), key=f"city_{i}")
        target_code = city_dict[selected_city]

    # إتاحة خيار تعديل الـ Code يدوياً
    final_code = st.text_input(f"Target Region Code ({target_code}):", value=target_code, key=f"code_{i}")

    server_list.append({
        "hostname": h_name,
        "region": final_code,
        "continent": selected_cont,
        "country": selected_country,
        "city": selected_city
    })
    st.divider()

# --- Execution ---
if st.button("🔥 Deploy All Servers Now", type="primary"):
    if not api_key:
        st.error("❌ أدخل الـ API Key أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        progress = st.progress(0)
        status_box = st.container()
        logs_and_errors = []

        for idx, srv in enumerate(server_list):
            payload = {
                "hostname": srv["hostname"],
                "region": srv["region"],
                "os": "almalinux-8.10",
                "plan": "4vcpu-8gb-80gb",
                "password": root_password
            }

            try:
                res = requests.post(f"{base_url}/servers", json=payload, headers=headers, timeout=15)
                if res.status_code in [200, 201, 202]:
                    status_box.success(f"✅ Executed: **{srv['hostname']}** -> Target: `{srv['region']}`")
                else:
                    status_box.error(f"❌ Failed **{srv['hostname']}**: HTTP Status {res.status_code}")
                    logs_and_errors.append({
                        "hostname": srv["hostname"],
                        "status_code": res.status_code,
                        "payload": payload,
                        "response": res.text
                    })
            except Exception as e:
                status_box.error(f"❌ Error **{srv['hostname']}**: {str(e)}")
                logs_and_errors.append({"hostname": srv["hostname"], "status_code": "EXC", "response": str(e)})

            progress.progress((idx + 1) / len(server_list))

        if logs_and_errors:
            st.markdown("---")
            st.subheader("🚨 Response Details / Error Logs")
            for err in logs_and_errors:
                with st.expander(f"Details: {err['hostname']} (Status: {err['status_code']})"):
                    st.write("**Response Text:**")
                    st.code(err["response"], language="json" if "{" in err["response"] else "html")
