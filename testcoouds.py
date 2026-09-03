import streamlit as st
import requests

st.set_page_config(page_title="CloudCenmax Bulk Deployer & Manager", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Bulk Deployer & Manager")

BASE_URL = "https://cloudcenmax.com/api/v1"

# --- Sidebar Authentication ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password")

def get_headers(key):
    return {
        "Authorization": f"Bearer {key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

# --- Helper API Functions ---
def check_account_balance(key):
    try:
        res = requests.get(f"{BASE_URL}/account", headers=get_headers(key), timeout=8)
        if res.status_code == 200:
            return res.json().get("data", {}).get("balance", {}).get("amount", 0)
    except Exception:
        pass
    return None

def fetch_user_resources(key):
    all_resources = []
    page = 1
    while True:
        try:
            res = requests.get(f"{BASE_URL}/resources?page={page}", headers=get_headers(key), timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                all_resources.extend(items)
                if not data.get("links", {}).get("next"):
                    break
                page += 1
            else:
                break
        except Exception:
            break
    return all_resources

def action_resource(key, resource_id, action_type):
    try:
        if action_type == "delete":
            res = requests.delete(f"{BASE_URL}/resources/{resource_id}", headers=get_headers(key), timeout=10)
        else:
            res = requests.post(f"{BASE_URL}/resources/{resource_id}/{action_type}", headers=get_headers(key), timeout=10)
        return res.status_code in [200, 202, 204]
    except Exception:
        return False

if api_key:
    user_balance = check_account_balance(api_key)
    if user_balance is not None:
        st.sidebar.metric("Current Balance", f"${user_balance:.2f}")

# ==========================================
# SECTION 1: BULK DEPLOYMENT (PART DE CREATION)
# ==========================================
st.subheader("🚀 Bulk Deployment Configuration")

@st.cache_data(ttl=120)
def fetch_catalog(key):
    all_items = []
    page = 1
    while True:
        try:
            res = requests.get(f"{BASE_URL}/catalog?page={page}", headers=get_headers(key), timeout=10)
            if res.status_code == 200:
                data = res.json()
                all_items.extend(data.get("data", []))
                if not data.get("links", {}).get("next"):
                    break
                page += 1
            else:
                break
        except Exception:
            break
    return all_items

catalog_items = []
if api_key:
    catalog_items = fetch_catalog(api_key)

structured_catalog = {}
for item in catalog_items:
    if item.get("module") and item.get("module") != "vm":
        continue
    specs = item.get("specs", {})
    region = specs.get("region", "Other")
    country = specs.get("country", "Unknown")
    city = specs.get("city", "Unknown")
    sku_code = item.get("code")
    if sku_code:
        structured_catalog.setdefault(region, {}).setdefault(country, {}).setdefault(city, []).append({
            "code": sku_code,
            "name": item.get("name", sku_code)
        })

num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=50, value=1, step=1)
server_list = []

if structured_catalog:
    for i in range(int(num_servers)):
        st.markdown(f"#### 🖥️ Server #{i+1}")
        col_host, col_reg, col_country, col_city, col_sku = st.columns([2, 2, 2, 2, 3])
        
        with col_host:
            h_name = st.text_input("Server Name", value=f"server-{i+1}", key=f"d_name_{i}")
        with col_reg:
            selected_reg = st.selectbox("Region", sorted(list(structured_catalog.keys())), key=f"d_reg_{i}")
        with col_country:
            selected_country = st.selectbox("Country", sorted(list(structured_catalog[selected_reg].keys())), key=f"d_country_{i}")
        with col_city:
            selected_city = st.selectbox("City", sorted(list(structured_catalog[selected_reg][selected_country].keys())), key=f"d_city_{i}")
        with col_sku:
            available_skus = structured_catalog[selected_reg][selected_country][selected_city]
            sku_map = {f"{item['name']} [{item['code']}]": item['code'] for item in available_skus}
            selected_sku_label = st.selectbox("SKU Plan", list(sku_map.keys()), key=f"d_sku_{i}")
            selected_sku_code = sku_map[selected_sku_label]

        server_list.append({"name": h_name.strip(), "sku": selected_sku_code})

    if st.button("🔥 Deploy All Resources Now", type="primary"):
        if not api_key:
            st.error("❌ أدخل الـ API Key أولاً!")
        else:
            progress = st.progress(0)
            status_box = st.container()

            for idx, srv in enumerate(server_list):
                payload = {"name": srv["name"], "sku": srv["sku"], "options": {}}
                try:
                    res = requests.post(f"{BASE_URL}/resources", json=payload, headers=get_headers(api_key), timeout=15)
                    if res.status_code in [200, 201]:
                        res_data = res.json().get("data", {})
                        status_box.success(f"✅ Created **{srv['name']}** (ID: `{res_data.get('id', 'N/A')}`)")
                    else:
                        status_box.error(f"❌ Failed **{srv['name']}**: HTTP {res.status_code} | {res.text}")
                except Exception as e:
                    status_box.error(f"❌ Exception on **{srv['name']}**: {str(e)}")

                progress.progress((idx + 1) / len(server_list))

st.markdown("---")

# ==========================================
# SECTION 2: SERVER LIST & MANAGEMENT TABLE
# ==========================================
st.subheader("Server List & Management")

if "selected_servers" not in st.session_state:
    st.session_state.selected_servers = set()

# Control Options Bar
ctrl_col1, ctrl_col2 = st.columns([3, 1])
with ctrl_col1:
    show_terminated = st.checkbox("Show Terminated / Deleted Servers", value=False)
with ctrl_col2:
    if st.button("🔄 Fetch Server List", use_container_width=True):
        st.rerun()

if api_key:
    raw_servers = fetch_user_resources(api_key)
    
    # Filter Terminated Servers if unchecked
    servers = []
    for s in raw_servers:
        st_val = str(s.get("status", "")).lower()
        if not show_terminated and st_val in ["terminated", "deleted", "destroying"]:
            continue
        servers.append(s)

    if not servers:
        st.info("No active servers loaded.")
    else:
        # Batch Action Bar
        col_sel_count, col_b1, col_b2, col_b3, col_b4 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
        
        selected_count = len(st.session_state.selected_servers)
        col_sel_count.markdown(f"### **{selected_count} selected**")

        with col_b1:
            if st.button("Start Selected", use_container_width=True):
                for srv_id in list(st.session_state.selected_servers):
                    action_resource(api_key, srv_id, "start")
                st.success("Start signal sent!")
                st.rerun()

        with col_b2:
            if st.button("Restart Selected", use_container_width=True):
                for srv_id in list(st.session_state.selected_servers):
                    action_resource(api_key, srv_id, "restart")
                st.success("Restart signal sent!")
                st.rerun()

        with col_b3:
            if st.button("Stop Selected", use_container_width=True):
                for srv_id in list(st.session_state.selected_servers):
                    action_resource(api_key, srv_id, "stop")
                st.success("Stop signal sent!")
                st.rerun()

        with col_b4:
            if st.button("Delete Selected", type="primary", use_container_width=True):
                for srv_id in list(st.session_state.selected_servers):
                    action_resource(api_key, srv_id, "delete")
                st.session_state.selected_servers.clear()
                st.success("Delete signal sent!")
                st.rerun()

        st.markdown("---")

        # Table Header
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7, h_col8 = st.columns([0.5, 2, 1.5, 1.5, 2.5, 1.5, 2, 1.5])
        
        # Select All Checkbox logic
        all_ids = {s.get("id") for s in servers if s.get("id")}
        select_all = h_col1.checkbox("", key="chk_select_all")
        if select_all:
            st.session_state.selected_servers = set(all_ids)

        h_col2.write("**Hostname**")
        h_col3.write("**Region**")
        h_col4.write("**IPv4**")
        h_col5.write("**Plan**")
        h_col6.write("**Status**")
        h_col7.write("**SSH**")
        h_col8.write("**Actions**")
        
        st.divider()

        # Table Rows
        for srv in servers:
            srv_id = srv.get("id")
            name = srv.get("name", "N/A")
            
            # Region parsing
            specs = srv.get("specs", {})
            if isinstance(specs, dict):
                region = specs.get("region", srv.get("region", "N/A"))
            else:
                region = srv.get("region", "N/A")

            # IP parsing
            ip = srv.get("ip") or srv.get("main_ip") or "N/A"

            # Plan / SKU parsing (Fixing JSON object display issue)
            sku_raw = srv.get("sku") or srv.get("plan")
            if isinstance(sku_raw, dict):
                plan_display = sku_raw.get("code") or sku_raw.get("name") or "N/A"
            elif isinstance(sku_raw, str):
                plan_display = sku_raw
            else:
                plan_display = "N/A"

            status = str(srv.get("status", "unknown")).lower()
            ssh_cmd = f"ssh root@{ip}" if ip != "N/A" else "N/A"

            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.5, 2, 1.5, 1.5, 2.5, 1.5, 2, 1.5])

            # Selection Checkbox
            is_checked = c1.checkbox("", key=f"chk_{srv_id}", value=(srv_id in st.session_state.selected_servers))
            if is_checked:
                st.session_state.selected_servers.add(srv_id)
            else:
                st.session_state.selected_servers.discard(srv_id)

            c2.write(f"**{name}**")
            c3.write(region)
            c4.code(ip, language="text")
            c5.write(plan_display)
            
            # Status Badges
            if status in ["active", "running"]:
                c6.markdown("🟢 `ACTIVE`")
            elif status in ["stopped", "off"]:
                c6.markdown("🔴 `STOPPED`")
            elif status in ["terminated", "deleted"]:
                c6.markdown("🟠 `TERMINATED`")
            else:
                c6.markdown(f"🟡 `{status.upper()}`")

            c7.code(ssh_cmd, language="bash")

            # Inline Action Buttons
            btn_col1, btn_col2 = c8.columns(2)
            with btn_col1:
                if st.button("⏹️", key=f"btn_stop_{srv_id}", help="Stop Server"):
                    action_resource(api_key, srv_id, "stop")
                    st.rerun()
            with btn_col2:
                if st.button("🗑️", key=f"btn_del_{srv_id}", help="Delete Server"):
                    action_resource(api_key, srv_id, "delete")
                    st.rerun()

else:
    st.warning("Please enter your API Key in the sidebar.")
