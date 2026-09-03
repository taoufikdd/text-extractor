import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Bulk Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Server Deployment")
st.markdown("إنشاء السيرفرات دفعة واحدة باستخدام الـ API Key الرسمي (`https://cloudcenmax.com/api/v1`).")

# --- Sidebar: API Key ---
st.sidebar.header("🔑 API Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="ضع المفتاح مثل ck_Kd99...")
base_url = "https://cloudcenmax.com/api/v1"
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

# --- Test API Connection ---
if st.sidebar.button("🔌 Test API Connection"):
    if not api_key:
        st.sidebar.error("❌ أُدخل الـ API Key أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # تجربة الاتصال بحسابك أو بطلب القائمة
        try:
            res = requests.get(f"{base_url}/account", headers=headers, timeout=8)
            if res.status_code == 200:
                st.sidebar.success(f"✅ Connected Successfully! (Status 200)")
            elif res.status_code in [401, 403]:
                st.sidebar.error(f"❌ API Key غير صحيح أو صلاحيته منتهية (Status {res.status_code})")
            else:
                # تجربة مسار آخر مثل /servers
                res_servers = requests.get(f"{base_url}/servers", headers=headers, timeout=8)
                if res_servers.status_code == 200:
                    st.sidebar.success("✅ Connected Successfully! (Status 200)")
                else:
                    st.sidebar.warning(f"⚠️ Response Status: {res_servers.status_code}")
        except Exception as e:
            st.sidebar.error(f"❌ Connection Error: {str(e)}")

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
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        progress = st.progress(0)
        status_box = st.container()
        logs_and_errors = []

        target_url = f"{base_url}/servers"

        for idx, srv in enumerate(server_list):
            payload = {
                "hostname": srv["hostname"],
                "region": srv["location"],
                "os": "almalinux-8.10",
                "plan": "4vcpu-8gb-80gb",
                "password": root_password
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
            st.subheader("🚨 Detailed Error Logs")
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
