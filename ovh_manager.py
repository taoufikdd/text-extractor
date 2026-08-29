import streamlit as st
import requests
import time
import socket

# ---------------------------------------------------------
# Page Config & Custom Modern Dark Theme
# ---------------------------------------------------------
st.set_page_config(page_title="Multi-Cloud Server Manager", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    /* Dark Theme Core */
    .stApp {
        background-color: #0B0F19;
        color: #F9FAFB;
    }
    
    /* Inputs Styling */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #1F2937 !important;
        border-color: #374151 !important;
        color: #F9FAFB !important;
        border-radius: 8px !important;
    }
    
    /* Primary Buttons */
    .stButton>button {
        background-color: #2563EB;
        color: #FFFFFF;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
    }
    
    /* Textarea output styling */
    textarea {
        background-color: #111827 !important;
        color: #10B981 !important;
        font-family: 'Courier New', Courier, monospace !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
    }

    /* Container Cards */
    .css-1r6slb0, .e1f1d6gn1 {
        background-color: #111827;
        border: 1px solid #1F2937;
        padding: 20px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

UPCLOUD_API = "https://api.upcloud.com/1.3"

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def upcloud_req(token, endpoint, method="GET", payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{UPCLOUD_API}{endpoint}"
    if method == "POST":
        res = requests.post(url, headers=headers, json=payload)
    elif method == "DELETE":
        res = requests.delete(url, headers=headers)
    else:
        res = requests.get(url, headers=headers)
    
    if not res.ok:
        raise Exception(f"UpCloud API Error ({res.status_code}): {res.text}")
    return res.json() if res.text else {}

def check_ssh_port(ip, port=22, timeout=3):
    """
    Checks if SSH Port (22) is actually OPEN and responding.
    Returns True ONLY when the server is ready.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, int(port)))
        sock.close()
        return result == 0
    except:
        return False

# ---------------------------------------------------------
# UI App
# ---------------------------------------------------------
st.title("⚡ Server Deployer & Manager")
st.caption("Auto-verification & clean export format")

# Sidebar Configuration / Authentication
st.sidebar.header("🔑 Provider Settings")
provider = st.sidebar.selectbox("Select Cloud Provider", ["UpCloud", "OVHcloud"])

if provider == "UpCloud":
    api_token = st.sidebar.text_input("UpCloud API Token", type="password")
    
    if api_token:
        if "upcloud_auth" not in st.session_state:
            try:
                upcloud_req(api_token, "/account")
                st.session_state["upcloud_auth"] = True
                st.sidebar.success("UpCloud Connected!")
            except Exception as e:
                st.session_state["upcloud_auth"] = False
                st.sidebar.error(f"Auth Failed: {e}")

    if st.session_state.get("upcloud_auth"):
        # Load UpCloud resources
        @st.cache_data(ttl=300)
        def fetch_upcloud_resources(token):
            zones = upcloud_req(token, "/zone").get("zones", {}).get("zone", [])
            plans = upcloud_req(token, "/plan").get("plans", {}).get("plan", [])
            templates = upcloud_req(token, "/storage/template").get("storages", {}).get("storage", [])
            
            os_list = [
                t for t in templates 
                if any(k in t.get("title", "").lower() for k in ["ubuntu", "alma", "centos", "debian"])
            ]
            return zones, plans, os_list

        try:
            zones, plans, os_list = fetch_upcloud_resources(api_token)
            
            st.subheader("🚀 Deploy UpCloud Instance")
            col1, col2 = st.columns(2)
            
            with col1:
                selected_os = st.selectbox("Operating System", os_list, format_func=lambda x: x['title'])
                selected_plan = st.selectbox("Hardware Plan", plans, format_func=lambda x: f"{x['name']} ({x['core_number']} vCPU / {x['memory_amount']}MB RAM)")
                selected_zones = st.multiselect("Regions / Zones", [z['id'] for z in zones], default=[zones[0]['id']] if zones else [])

            with col2:
                srv_count = st.number_input("Total Servers Count", min_value=1, max_value=50, value=1)
                prefix = st.text_input("Hostname Prefix", value="alma-server")
                disk_size = st.number_input("Disk Size (GB)", min_value=10, value=60)
                password = st.text_input("Root Password", type="password", value="qRdkWWKIhbb9q6Nmwi3mfrt")

            if st.button("⚡ Launch & Extract Verified List"):
                if not selected_zones:
                    st.error("Please select at least one region.")
                elif len(password) < 10:
                    st.error("Password must be at least 10 characters.")
                else:
                    progress = st.empty()
                    created_servers = []
                    log_messages = []

                    for i in range(srv_count):
                        zone = selected_zones[i % len(selected_zones)]
                        hostname = f"{prefix}-{str(i+1).zfill(2)}"
                        
                        payload = {
                            "server": {
                                "zone": zone,
                                "title": hostname,
                                "hostname": hostname,
                                "plan": selected_plan["name"],
                                "metadata": "yes",
                                "storage_devices": {
                                    "storage_device": [{
                                        "action": "clone",
                                        "storage": selected_os["uuid"],
                                        "title": f"{hostname}-disk",
                                        "size": disk_size,
                                        "tier": "standard" if selected_plan["name"].startswith("DEV-") else "maxiops"
                                    }]
                                }
                            }
                        }
                        
                        try:
                            res = upcloud_req(api_token, "/server", method="POST", payload=payload)
                            s_uuid = res.get("server", {}).get("uuid")
                            created_servers.append(s_uuid)
                            log_messages.append(f"✅ Created {hostname} ({zone}) -> {s_uuid}")
                        except Exception as err:
                            log_messages.append(f"❌ Failed {hostname}: {err}")
                        
                        progress.code("\n".join(log_messages))
                        time.sleep(0.5)

                    # ---------------------------------------------------------
                    # SSH Checking & Filtering (ONLY GOOD SERVERS)
                    # ---------------------------------------------------------
                    st.info("⏳ Waiting for servers to initialize and Port 22 (SSH) to become ACTIVE...")
                    
                    good_servers = []
                    status_placeholder = st.empty()

                    for idx, s_uuid in enumerate(created_servers):
                        status_placeholder.text(f"Checking server {idx+1}/{len(created_servers)}...")
                        active_ip = None
                        
                        # Retries to catch Public IP and check Port 22 readiness
                        for attempt in range(20):
                            time.sleep(5)
                            try:
                                details = upcloud_req(api_token, f"/server/{s_uuid}").get("server", {})
                                ips = details.get("ip_addresses", {}).get("ip_address", [])
                                pub_ip = next((ip["address"] for ip in ips if ip.get("access") == "public" and ":" not in ip.get("address")), None)
                                
                                if pub_ip:
                                    # Verify Port 22 SSH Connection is live
                                    if check_ssh_port(pub_ip):
                                        active_ip = pub_ip
                                        break
                            except:
                                pass
                        
                        if active_ip:
                            # Append directly in exact string format
                            good_servers.append(f"{active_ip},22,root,{password}")

                    status_placeholder.empty()

                    # Render Section like image mockup
                    st.markdown("---")
                    st.subheader("🖥️ قائمة السيرفرات الجاهزة وتنسيق البيانات (Format)")
                    
                    if good_servers:
                        st.success("إبنجاح تم إنشاء و فحص جميع السيرفرات!")
                        formatted_output = "\n".join(good_servers)
                        
                        st.markdown("**:موحد Format نسخ كل السيرفرات بـ**")
                        st.caption("جاهزة للنسخ المباشر:")
                        st.text_area("", value=formatted_output, height=180)
                    else:
                        st.error("لم يتم التأكد من جاهزية Port 22 للسيرفرات. المرجو المحاولة لاحقاً.")

        except Exception as e:
            st.error(f"Configuration error: {e}")

elif provider == "OVHcloud":
    st.sidebar.subheader("OVH Credentials")
    ovh_endpoint = st.sidebar.selectbox("Endpoint", ["ovh-eu", "ovh-us", "ca-ovh"])
    app_key = st.sidebar.text_input("Application Key", type="password")
    app_secret = st.sidebar.text_input("Application Secret", type="password")
    consumer_key = st.sidebar.text_input("Consumer Key", type="password")
    
    if st.sidebar.button("Connect OVH"):
        st.info("Ensure Application Key, Secret & Consumer Key are correctly generated for OVH API.")
