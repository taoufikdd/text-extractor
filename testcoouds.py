import streamlit as st
import requests

st.set_page_config(page_title="CloudCenmax Livewire Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Deployer (Livewire Engine)")
st.markdown("إرسال طلبات المباشرة إلى Livewire Component لإنشاء السيرفرات دفعة واحدة.")

# --- Livewire & Session Credentials ---
st.sidebar.header("🔑 Session & Tokens")
csrf_token = st.sidebar.text_input("X-CSRF-TOKEN", type="password", help="قيمة X-CSRF-TOKEN من Request Headers")
cookie_str = st.sidebar.text_input("Cookie Header", type="password", help="قيمة Cookie كاملة من Request Headers")

st.sidebar.subheader("🔒 Server Security")
default_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

LIVEWIRE_URL = "https://cloudcenmax.com/livewire/update"

# --- Locations Data (Hierarchical Selection) ---
# تقدر تزيد أي دولة أو مدينة بالـ Code ديالها هنا
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
st.subheader("📋 Targeted Specs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CPU", "4 vCPU")
col2.metric("RAM", "8192 MB")
col3.metric("Disk", "80 GB")
col4.metric("OS", "AlmaLinux 8.10 64bit")

st.divider()

# --- Bulk Configuration ---
st.subheader("🚀 Setup Bulk Deployment")
num_servers = st.number_input("Number of Servers", min_value=1, max_value=50, value=1, step=1)

server_list = []

st.markdown("### 🌍 Select Details for Each Server:")

for i in range(int(num_servers)):
    st.markdown(f"#### 🖥️ Server #{i+1}")
    
    col_host, col_cont, col_country, col_city = st.columns([2, 2, 2, 2])
    
    with col_host:
        h_name = st.text_input("Hostname", value=f"server-alma8-{i+1}", key=f"host_{i}")
        
    with col_cont:
        selected_cont = st.selectbox(
            "Continent",
            options=list(LOCATIONS_DATA.keys()),
            key=f"cont_{i}"
        )
        
    with col_country:
        country_options = list(LOCATIONS_DATA[selected_cont].keys())
        selected_country = st.selectbox(
            "Country",
            options=country_options,
            key=f"country_{i}"
        )
        
    with col_city:
        city_dict = LOCATIONS_DATA[selected_cont][selected_country]
        selected_city_name = st.selectbox(
            "City / State",
            options=list(city_dict.keys()),
            key=f"city_{i}"
        )
        location_code = city_dict[selected_city_name]

    # Custom Code override option if needed
    custom_code = st.text_input(
        f"Selected Code: ({location_code}) — [Type custom code here if needed]:", 
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
if st.button("🔥 Execute Livewire Bulk Creation", type="primary"):
    if not csrf_token or not cookie_str:
        st.error("❌ يرجى إدخال X-CSRF-TOKEN و Cookie أولاً من الـ Sidebar!")
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-CSRF-TOKEN": csrf_token,
            "X-Livewire": "true",
            "Content-Type": "application/json",
            "Accept": "text/html, application/xhtml+xml",
            "Cookie": cookie_str,
            "Origin": "https://cloudcenmax.com",
            "Referer": "https://cloudcenmax.com/deploy"
        }

        progress = st.progress(0)
        status_box = st.container()
        
        for idx, srv in enumerate(server_list):
            payload = {
                "_token": csrf_token,
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
                                        "continent": srv["continent"],
                                        "country": srv["country"],
                                        "city": srv["city"],
                                        "location": srv["location"],
                                        "os": "almalinux-8.10",
                                        "plan": "4vcpu-8gb-80gb",
                                        "password": default_password,
                                        "root_password": default_password
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
                        f"✅ Created **{srv['hostname']}** | "
                        f"Location: **{srv['continent']} -> {srv['country']} -> {srv['city']} ({srv['location']})**"
                    )
                else:
                    status_box.error(f"❌ Failed **{srv['hostname']}**: HTTP {res.status_code} - {res.text[:200]}")
            except Exception as e:
                status_box.error(f"❌ Connection Error on **{srv['hostname']}**: {str(e)}")

            progress.progress((idx + 1) / len(server_list))
            
        st.balloons()
