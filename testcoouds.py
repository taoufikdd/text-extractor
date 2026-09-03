import streamlit as st
import requests

# Set page layout
st.set_page_config(page_title="CloudCenmax Server Deployer", layout="wide", page_icon="☁️")

st.title("⚡ CloudCenmax Bulk Server Deployment")
st.markdown("قم بإدخال الـ **API Key** للاتصال وجلب المناطق المتاحة وإنشاء السيرفرات دفعة واحدة.")

# Configuration Constants
PLAN_SPEC = {
    "name": "4 vCPU / 8 GB RAM / 80 GB Disk",
    "vcpu": 4,
    "ram_mb": 8192,
    "disk_gb": 80,
    "plan_id": "standard-4vcpu-8gb"  # Replace with actual plan ID from CloudCenmax API
}
OS_IMAGE = "almalinux-8.10-x64"      # Replace with actual image slug from CloudCenmax API

# --- Sidebar: API Key & Fetch Regions ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="أدخل مفتاح الـ API الخاص بك هنا")

BASE_URL = "https://cloudcenmax.com/api/v1"  # Update base URL if API docs specify another endpoint

@st.cache_data(ttl=300)
def fetch_regions(token):
    """ Fetch available regions/locations from CloudCenmax API """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        # Standard endpoint for fetching locations
        response = requests.get(f"{BASE_URL}/regions", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Expecting list of regions, adapt key mapping as per actual API response structure
            return {r.get("name", r.get("id")): r["id"] for r in data.get("regions", data)}
        else:
            st.sidebar.error(f"Failed to fetch regions: {response.status_code}")
            return {}
    except Exception as e:
        st.sidebar.error(f"Error connecting to API: {str(e)}")
        return {}

regions_dict = {}
if api_key:
    if st.sidebar.button("🔄 Fetch / Refresh Regions"):
        st.cache_data.clear()
    regions_dict = fetch_regions(api_key)
    if regions_dict:
        st.sidebar.success(f"Loaded {len(regions_dict)} regions successfully!")

# --- Main Configuration & Deployment ---
st.subheader("📋 Server Specifications (Fixed)")
col_spec1, col_spec2, col_spec3, col_spec4 = st.columns(4)
col_spec1.metric("CPU", "4 vCPU")
col_spec2.metric("RAM", "8192 MB (8 GB)")
col_spec3.metric("Disk", "80 GB")
col_spec4.metric("OS Image", "AlmaLinux 8.10 64bit")

st.divider()

st.subheader("🚀 Bulk Creation Setup")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=20, value=2, step=1)

server_configs = []

if not regions_dict:
    st.warning("⚠️ Enter a valid API Key in the sidebar to fetch available regions before creating servers.")
else:
    region_names = list(regions_dict.keys())
    
    st.markdown("### Select Region for Each Server:")
    
    # Generate dynamic inputs per server
    for i in range(int(num_servers)):
        col1, col2 = st.columns([2, 3])
        with col1:
            hostname = st.text_input(f"Server #{i+1} Hostname", value=f"server-alma8-{i+1}", key=f"host_{i}")
        with col2:
            selected_region_name = st.selectbox(
                f"Server #{i+1} Region", 
                options=region_names, 
                key=f"region_{i}"
            )
        
        server_configs.append({
            "hostname": hostname,
            "region_id": regions_dict[selected_region_name],
            "region_name": selected_region_name
        })

    st.divider()

    # --- Deploy Button ---
    if st.button("🔥 Deploy All Servers Now", type="primary"):
        if not api_key:
            st.error("Please provide an API Key!")
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            progress_bar = st.progress(0)
            status_container = st.container()
            
            created_count = 0
            for idx, config in enumerate(server_configs):
                payload = {
                    "hostname": config["hostname"],
                    "region": config["region_id"],
                    "plan": PLAN_SPEC["plan_id"],
                    "image": OS_IMAGE,
                    "vcpus": PLAN_SPEC["vcpu"],
                    "ram": PLAN_SPEC["ram_mb"],
                    "disk": PLAN_SPEC["disk_gb"]
                }
                
                try:
                    # Endpoint for server creation
                    res = requests.post(f"{BASE_URL}/servers", json=payload, headers=headers, timeout=15)
                    
                    if res.status_code in [200, 201]:
                        created_count += 1
                        server_info = res.json()
                        status_container.success(
                            f"✅ **{config['hostname']}** created successfully in **{config['region_name']}**! "
                            f"(ID: {server_info.get('id', 'N/A')})"
                        )
                    else:
                        status_container.error(
                            f"❌ Failed to create **{config['hostname']}**: Status {res.status_code} - {res.text}"
                        )
                except Exception as ex:
                    status_container.error(f"❌ Error deploying **{config['hostname']}**: {str(ex)}")
                
                # Update progress bar
                progress_bar.progress((idx + 1) / len(server_configs))
            
            if created_count == len(server_configs):
                st.balloons()
                st.success(f"🎉 All {created_count} servers created successfully!")