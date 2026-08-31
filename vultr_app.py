import streamlit as st
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION CONSTANTS ---
DEFAULT_ROOT_PASSWORD = "qRdkWWKIhbb9q6Nmwi3mfrt"
PLAN_ID = "vc2-1c-1gb"  # Standard $5/mo instance plan
DEFAULT_OS_ID = 215     # Ubuntu 22.04 LTS x64

# Base64 encoded user_data script (Optional startup script)
USER_DATA_B64 = ""

st.set_page_config(
    page_title="Vultr Deployer Pro",
    page_icon="🚀",
    layout="wide"
)

# --- HELPER FUNCTIONS ---

def parse_proxies(proxy_text):
    """Parses a newline-separated string of proxies into requests format."""
    proxies = []
    lines = proxy_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_str = f"http://{user}:{pwd}@{ip}:{port}"
            proxies.append({
                "http": proxy_str,
                "https": proxy_str
            })
        elif len(parts) == 2:
            ip, port = parts
            proxy_str = f"http://{ip}:{port}"
            proxies.append({
                "http": proxy_str,
                "https": proxy_str
            })
    return proxies


def get_proxy_for_thread(index, proxy_list):
    """Returns a proxy from the list based on round-robin indexing."""
    if not proxy_list:
        return None
    return proxy_list[index % len(proxy_list)]


def parse_api_keys(keys_text):
    """Parses newline-separated API keys."""
    return [k.strip() for k in keys_text.strip().split("\n") if k.strip()]


def wait_for_ip_and_ipv6(api_key, instance_id, proxies, max_retries=20):
    """Polls the Vultr API until an IPv4 address is assigned."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"https://api.vultr.com/v2/instances/{instance_id}"
    for _ in range(max_retries):
        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            if res.status_code == 200:
                inst_data = res.json().get("instance", {})
                main_ip = inst_data.get("main_ip", "")
                v6_main_ip = inst_data.get("v6_main_ip", "")
                
                if main_ip and main_ip != "0.0.0.0":
                    return main_ip, v6_main_ip
        except Exception:
            pass
        time.sleep(3)
    return "0.0.0.0", ""


def deploy_single_server(counter, code, os_id, current_api_key, current_proxies):
    """Deploys a single Vultr instance and returns formatted string with IPv4 only."""
    hostname = f"vultr-server-{counter}"
    headers = {
        "Authorization": f"Bearer {current_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "region": code,
        "plan": PLAN_ID,
        "os_id": os_id,
        "user_scheme": "root",
        "password": DEFAULT_ROOT_PASSWORD,
        "user_data": USER_DATA_B64,
        "hostname": hostname,
        "label": hostname,
        "backups": "disabled",
        "enable_ipv6": True  # IPv6 enabled on deployment
    }
    
    try:
        res = requests.post(
            "https://api.vultr.com/v2/instances",
            headers=headers,
            json=payload,
            proxies=current_proxies,
            timeout=15
        )
        if res.status_code == 202:
            inst_id = res.json().get("instance", {}).get("id")
            ip, _ = wait_for_ip_and_ipv6(current_api_key, inst_id, current_proxies)
            # Standard Output format (IPv4 only)
            formatted = f"{ip},22,root,{DEFAULT_ROOT_PASSWORD}"
            return True, formatted, None
        else:
            return False, None, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, None, str(e)


def fetch_instances_for_key(api_key, proxies=None):
    """Fetches list of active instances for a given API key."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(
            "https://api.vultr.com/v2/instances",
            headers=headers,
            proxies=proxies,
            timeout=10
        )
        if res.status_code == 200:
            return res.json().get("instances", [])
    except Exception:
        pass
    return []


# --- MAIN APP LAYOUT ---

st.title("⚡ Vultr Server Deployment Manager")

tab1, tab2 = st.tabs(["📋 Active Instances", "🚀 Start Deployment"])

# ==========================================
# TAB 1: ACTIVE INSTANCES
# ==========================================
with tab1:
    st.header("Manage Existing Instances")
    api_keys_input_tab1 = st.text_area(
        "Enter Vultr API Key(s) (One per line):",
        height=100,
        key="tab1_keys"
    )
    
    if st.button("Fetch Active Instances", key="btn_fetch"):
        keys = parse_api_keys(api_keys_input_tab1)
        if not keys:
            st.error("Please provide at least one API key.")
        else:
            all_instances = []
            with st.spinner("Fetching active instances..."):
                for key in keys:
                    instances = fetch_instances_for_key(key)
                    all_instances.extend(instances)
            
            if all_instances:
                st.success(f"Found {len(all_instances)} total instance(s).")
                display_data = []
                for inst in all_instances:
                    display_data.append({
                        "ID": inst.get("id"),
                        "Label": inst.get("label"),
                        "Region": inst.get("region"),
                        "IPv4": inst.get("main_ip"),
                        "IPv6": inst.get("v6_main_ip", "N/A"),
                        "Status": inst.get("status"),
                        "Power": inst.get("power_status"),
                        "OS": inst.get("os")
                    })
                st.dataframe(display_data, use_container_width=True)
            else:
                st.info("No active instances found or invalid API key(s).")


# ==========================================
# TAB 2: START DEPLOYMENT
# ==========================================
with tab2:
    st.header("Deploy New Vultr Instances")
    
    col1, col2 = st.columns(2)
    
    with col1:
        api_keys_text = st.text_area(
            "API Keys (One per line):",
            height=120,
            key="tab2_keys"
        )
        proxies_text = st.text_area(
            "Proxies (Optional - ip:port or ip:port:user:pass):",
            height=120,
            key="tab2_proxies"
        )
        
    with col2:
        locations_input = st.text_input(
            "Region Code(s) (comma separated, e.g., ewr, lax, fra):",
            value="ewr"
        )
        os_id_input = st.number_input(
            "OS ID:",
            value=DEFAULT_OS_ID,
            step=1
        )
        count_per_loc = st.number_input(
            "Servers per Region:",
            min_value=1,
            max_value=100,
            value=1
        )
        max_workers = st.slider(
            "Concurrent Threads:",
            min_value=1,
            max_value=20,
            value=5
        )

    if st.button("Start Deployment 🚀", key="btn_deploy"):
        api_keys = parse_api_keys(api_keys_text)
        proxies = parse_proxies(proxies_text)
        locations = [loc.strip() for loc in locations_input.split(",") if loc.strip()]
        
        if not api_keys:
            st.error("Please enter at least one Vultr API Key.")
        elif not locations:
            st.error("Please enter at least one region code.")
        else:
            # Build list of deployment tasks
            tasks = []
            counter = 1
            for loc in locations:
                for _ in range(count_per_loc):
                    # Round-robin API key selection
                    key = api_keys[(counter - 1) % len(api_keys)]
                    proxy = get_proxy_for_thread(counter - 1, proxies)
                    tasks.append((counter, loc, os_id_input, key, proxy))
                    counter += 1
            
            st.info(f"Starting deployment of {len(tasks)} server(s)...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            failed_count = 0
            completed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        deploy_single_server,
                        counter=t[0],
                        code=t[1],
                        os_id=t[2],
                        current_api_key=t[3],
                        current_proxies=t[4]
                    ): t for t in tasks
                }
                
                for future in as_completed(futures):
                    completed += 1
                    success, formatted_str, err = future.result()
                    
                    if success:
                        results.append(formatted_str)
                    else:
                        failed_count += 1
                        st.error(f"Deployment failed: {err}")
                    
                    progress = completed / len(tasks)
                    progress_bar.progress(progress)
                    status_text.text(f"Processed {completed}/{len(tasks)} tasks...")
            
            st.success("Deployment Process Finished!")
            
            if results:
                st.subheader("Created Servers List")
                # Clean Output List (IPv4 only)
                servers_text = "\n".join(results)
                
                st.text_area(
                    "Created Servers List (ip,port,user,pass):",
                    value=servers_text,
                    height=200
                )
                
                # Option to download list as txt file
                st.download_button(
                    label="Download vultr_servers.txt 📥",
                    data=servers_text,
                    file_name="vultr_servers.txt",
                    mime="text/plain"
                )
            
            if failed_count > 0:
                st.warning(f"{failed_count} deployment(s) failed. Check details above.")
