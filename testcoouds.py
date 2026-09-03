import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Bulk Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Server Deployment (Livewire Direct)")
st.markdown("إنشاء السيرفرات مباشرة عبر مسار Laravel Livewire لتفادي خطأ 404.")

# --- Simple Sidebar: API Key & Root Password ---
st.sidebar.header("🔑 Session & Password")
api_key = st.sidebar.text_input("Session Cookie / Token", type="password", help="أدخل Cookie أو CSRF Token")
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

LIVEWIRE_URL = "https://cloudcenmax.com/livewire/update"

# --- Button to Test Livewire Connection ---
if st.sidebar.button("🔌 Test API Connection"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Livewire": "true",
        "Content-Type": "application/json",
        "Accept": "text/html, application/xhtml+xml",
        "Cookie": api_key if api_key else ""
    }
    
    # اختبار بسيط عن طريق إرسال Empty Payload لـ Livewire
    try:
        res = requests.post(LIVEWIRE_URL, json={"components": []}, headers=headers, timeout=10)
        
        # Livewire كيرجع 200 أو 419 (CSRF Mismatch) ولكن السيرفر موجود وكيستاجب!
        if res.status_code in [200, 419]:
            st.sidebar.success(f"✅ Livewire Endpoint Active! (Status: {res.status_code})")
        else:
            st.sidebar.error(f"❌ Connection Failed: Status {res.status_code}")
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Livewire": "true",
        "Content-Type": "application/json",
        "Accept": "text/html, application/xhtml+xml",
        "Cookie": api_key if api_key else "",
        "Origin": "https://cloudcenmax.com",
        "Referer": "https://cloudcenmax.com/deploy"
    }

    progress = st.progress(0)
    status_box = st.container()
    logs_and_errors = []

    for idx, srv in enumerate(server_list):
        payload = {
            "components": [
                {
                    "snapshot": '{"memo":{"name":"deploy-cloud-server"}}',
                    "updates": {},
                    "calls": [
                        {
                            "path": "",
                            "method": "deploy",
                            "params": [
                                {
                                    "hostname": srv["hostname"],
                                    "location": srv["location"],
                                    "continent": srv["continent"],
                                    "country": srv["country"],
                                    "city": srv["city"],
                                    "os": "almalinux-8.10",
                                    "plan": "4vcpu-8gb-80gb",
                                    "password": root_password,
                                    "root_password": root_password
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        try:
            res = requests.post(LIVEWIRE_URL, json=payload, headers=headers, timeout=15)
            
            if res.status_code == 200:
                status_box.success(
                    f"✅ **{srv['hostname']}** created successfully! (Location: {srv['location']})"
                )
            else:
                status_box.error(
                    f"❌ Failed **{srv['hostname']}**: HTTP Status {res.status_code}"
                )
                logs_and_errors.append({
                    "hostname": srv["hostname"],
                    "status_code": res.status_code,
                    "url_called": LIVEWIRE_URL,
                    "payload_sent": payload,
                    "response_body": res.text
                })
        except Exception as e:
            status_box.error(f"❌ Connection Error on **{srv['hostname']}**: {str(e)}")
            logs_and_errors.append({
                "hostname": srv["hostname"],
                "status_code": "EXCEPTION",
                "url_called": LIVEWIRE_URL,
                "payload_sent": payload,
                "response_body": str(e)
            })

        progress.progress((idx + 1) / len(server_list))

    # --- Error Diagnostics Interface ---
    if logs_and_errors:
        st.markdown("---")
        st.subheader("🚨 Detailed Error Logs & Diagnostics")
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
