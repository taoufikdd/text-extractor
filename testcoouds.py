import streamlit as st
import requests

st.set_page_config(page_title="CloudCenmax Server Deployer", layout="wide", page_icon="☁️")

st.title("⚡ CloudCenmax Bulk Server Deployment")
st.markdown("قم بإدخال الـ **API Key** للاتصال وجلب المناطق المتاحة وإنشاء السيرفرات دفعة واحدة.")

# Fixed System Specifications
PLAN_SPEC = {
    "name": "4 vCPU / 8 GB RAM / 80 GB Disk",
    "vcpu": 4,
    "ram_mb": 8192,
    "disk_gb": 80,
    "sku": "vm.o.11.100"  # Default CloudCenmax SKU pattern
}
OS_IMAGE = "almalinux-8.10"

# --- Sidebar Configuration ---
st.sidebar.header("🔑 Authentication & Settings")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="أدخل مفتاح API الخاص بك")

# Endpoint configuration (Default CloudCenmax API v1 Base URL)
base_url = st.sidebar.text_input("API Base URL", value="https://cloudcenmax.com/api/v1")

def get_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Key": token,
        "Content-Type": "application/json"
    }

@st.cache_data(ttl=300)
def fetch_regions(token, url):
    """ Fetch available locations with dynamic fallback endpoints """
    headers = get_headers(token)
    
    # Endpoints to check sequentially based on CloudCenmax structure
    endpoints = [
        f"{url}/catalog/locations",
        f"{url}/locations",
        f"{url}/regions"
    ]
    
    last_error = ""
    for ep in endpoints:
        try:
            res = requests.get(ep, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("locations", data.get("data", data if isinstance(data, list) else []))
                
                regions = {}
                for item in items:
                    if isinstance(item, dict):
                        # Extract name and location ID/slug
                        name = item.get("name") or item.get("city") or item.get("country") or item.get("id")
                        code = item.get("slug") or item.get("code") or item.get("id")
                        if name and code:
                            regions[f"{name} ({code})"] = code
                    elif isinstance(item, str):
                        regions[item] = item
                
                if regions:
                    return regions, None
            else:
                last_error = f"Status {res.status_code} from {ep}"
        except Exception as e:
            last_error = str(e)

    return {}, last_error

regions_dict = {}
if api_key:
    if st.sidebar.button("🔄 Fetch / Refresh Regions"):
        st.cache_data.clear()
    
    regions_dict, err = fetch_regions(api_key, base_url.rstrip('/'))
    if regions_dict:
        st.sidebar.success(f"✅ Loaded {len(regions_dict)} regions successfully!")
    elif err:
        st.sidebar.error(f"❌ Failed to fetch regions: {err}")

# --- Fixed Specs Display ---
st.subheader("📋 Server Specifications (Fixed)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("CPU", "4 vCPU")
col2.metric("RAM", "8192 MB (8 GB)")
col3.metric("Disk", "80 GB")
col4.metric("OS Image", "AlmaLinux 8.10 64bit")

st.divider()

# --- Bulk Deploy Form ---
st.subheader("🚀 Bulk Creation Setup")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=20, value=2, step=1)

server_configs = []

if not regions_dict:
    st.warning("⚠️ Enter a valid API Key in the sidebar to fetch available regions before creating servers.")
else:
    region_names = list(regions_dict.keys())
    
    st.markdown("### Select Region for Each Server:")
    for i in range(int(num_servers)):
        c1, c2 = st.columns([2, 3])
        with c1:
            hostname = st.text_input(f"Server #{i+1} Hostname", value=f"server-alma8-{i+1}", key=f"host_{i}")
        with c2:
            selected_region_name = st.selectbox(f"Server #{i+1} Region", options=region_names, key=f"region_{i}")
        
        server_configs.append({
            "hostname": hostname,
            "region_id": regions_dict[selected_region_name],
            "region_name": selected_region_name
        })

    st.divider()

    # --- Execution ---
    if st.button("🔥 Deploy All Servers Now", type="primary"):
        if not api_key:
            st.error("Please provide an API Key!")
        else:
            headers = get_headers(api_key)
            progress_bar = st.progress(0)
            status_container = st.container()
            
            deploy_url = f"{base_url.rstrip('/')}/resources/deploy"
            
            created_count = 0
            for idx, config in enumerate(server_configs):
                payload = {
                    "name": config["hostname"],
                    "location": config["region_id"],
                    "region": config["region_id"],
                    "template": OS_IMAGE,
                    "sku": PLAN_SPEC["sku"],
                    "vcpus": PLAN_SPEC["vcpu"],
                    "ram": PLAN_SPEC["ram_mb"],
                    "disk": PLAN_SPEC["disk_gb"]
                }
                
                try:
                    res = requests.post(deploy_url, json=payload, headers=headers, timeout=15)
                    
                    if res.status_code in [200, 201, 202]:
                        created_count += 1
                        info = res.json()
                        server_id = info.get("id") or info.get("server_id") or "Success"
                        status_container.success(f"✅ **{config['hostname']}** created in **{config['region_name']}**! (ID: {server_id})")
                    else:
                        status_container.error(f"❌ Failed **{config['hostname']}**: HTTP {res.status_code} - {res.text}")
                except Exception as ex:
                    status_container.error(f"❌ Error deploying **{config['hostname']}**: {str(ex)}")
                
                progress_bar.progress((idx + 1) / len(server_configs))
            
            if created_count == len(server_configs):
                st.balloons()
                st.success(f"🎉 Successfully created {created_count} servers!")
