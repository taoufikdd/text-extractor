import streamlit as st
import requests

st.set_page_config(page_title="CloudCenmax Livewire Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Deployer (Livewire Engine)")
st.markdown("يقوم هذا السكريبت بإرسال طلبات المباشرة إلى Livewire Component لإنشاء السيرفرات دفعة واحدة.")

# --- Livewire & Session Credentials ---
st.sidebar.header("🔑 Session & Tokens")
st.sidebar.info("احصل على هذه البيانات من Network Tab (Headers) عند الضغط على زر Create/Deploy في الموقع.")

csrf_token = st.sidebar.text_input("X-CSRF-TOKEN", type="password", help="قيمة X-CSRF-TOKEN من Request Headers")
cookie_str = st.sidebar.text_input("Cookie Header", type="password", help="قيمة Cookie كاملة من Request Headers")

# Component Fingerprint / Snapshots required by Livewire 3
st.sidebar.subheader("🧩 Livewire Snapshots / Payload Data")
component_name = st.sidebar.text_input("Component Name", value="deploy-cloud-server")
fingerprint_snapshot = st.sidebar.text_area("Snapshot JSON (إذا كان مطلوباً)", value='{}')

LIVEWIRE_URL = "https://cloudcenmax.com/livewire/update"

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
num_servers = st.number_input("Number of Servers", min_value=1, max_value=20, value=2, step=1)

server_list = []
for i in range(int(num_servers)):
    c1, c2 = st.columns([2, 3])
    with c1:
        h_name = st.text_input(f"Server #{i+1} Hostname", value=f"server-alma8-{i+1}", key=f"host_{i}")
    with c2:
        # Static or custom location inputs based on site options
        r_code = st.text_input(f"Server #{i+1} Region / Location Code", value="san-juan", key=f"loc_{i}")
    server_list.append({"hostname": h_name, "location": r_code})

st.divider()

# --- Execution ---
if st.button("🔥 Execute Livewire Bulk Creation", type="primary"):
    if not csrf_token or not cookie_str:
        st.error("❌ يرجى إدخال X-CSRF-TOKEN و Cookie أولاً!")
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
        
        for idx, srv in enumerate(server_list):
            # Livewire v3 payload structure
            payload = {
                "_token": csrf_token,
                "components": [
                    {
                        "snapshot": fingerprint_snapshot if fingerprint_snapshot != '{}' else '{"memo":{"name":"' + component_name + '"}}',
                        "updates": {},
                        "calls": [
                            {
                                "path": "",
                                "method": "deploy",
                                "params": [
                                    {
                                        "hostname": srv["hostname"],
                                        "location": srv["location"],
                                        "os": "almalinux-8.10",
                                        "plan": "4vcpu-8gb-80gb"
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
                    st.success(f"✅ Success sending request for **{srv['hostname']}** ({srv['location']})")
                else:
                    st.error(f"❌ Failed for **{srv['hostname']}**: Status {res.status_code} - {res.text[:200]}")
            except Exception as e:
                st.error(f"❌ Connection error on **{srv['hostname']}**: {str(e)}")

            progress.progress((idx + 1) / len(server_list))
