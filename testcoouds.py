import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="CloudCenmax Manager", layout="wide", page_icon="⚡")

st.title("Server List & Management")

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

# API Call Functions
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
    # action_type: start, stop, restart, delete
    try:
        if action_type == "delete":
            res = requests.delete(f"{BASE_URL}/resources/{resource_id}", headers=get_headers(key), timeout=10)
        else:
            res = requests.post(f"{BASE_URL}/resources/{resource_id}/{action_type}", headers=get_headers(key), timeout=10)
        return res.status_code in [200, 202, 204]
    except Exception:
        return False

# --- Top Actions Bar ---
col_top_left, col_top_right = st.columns([3, 1])
with col_top_right:
    fetch_btn = st.button("🔄 Fetch Server List", type="secondary", use_container_width=True)

if api_key:
    servers = fetch_user_resources(api_key)
    
    if not servers:
        st.info("No servers loaded. Connect API and fetch servers.")
    else:
        # إدارة حالة الاختيارات (State Management for Selection)
        if "selected_servers" not in st.session_state:
            st.session_state.selected_servers = set()

        # Batch Actions Bar
        col_sel_count, col_b1, col_b2, col_b3, col_b4 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
        
        selected_count = len(st.session_state.selected_servers)
        col_sel_count.markdown(f"### **{selected_count} selected**")

        with col_b1:
            if st.button("Start Selected", use_container_width=True):
                for srv_id in st.session_state.selected_servers:
                    action_resource(api_key, srv_id, "start")
                st.success("Start signal sent!")
                st.rerun()

        with col_b2:
            if st.button("Restart Selected", use_container_width=True):
                for srv_id in st.session_state.selected_servers:
                    action_resource(api_key, srv_id, "restart")
                st.success("Restart signal sent!")
                st.rerun()

        with col_b3:
            if st.button("Stop Selected", use_container_width=True):
                for srv_id in st.session_state.selected_servers:
                    action_resource(api_key, srv_id, "stop")
                st.success("Stop signal sent!")
                st.rerun()

        with col_b4:
            if st.button("Delete Selected", type="primary", use_container_width=True):
                for srv_id in st.session_state.selected_servers:
                    action_resource(api_key, srv_id, "delete")
                st.session_state.selected_servers.clear()
                st.success("Delete signal sent!")
                st.rerun()

        st.markdown("---")

        # Header Row (Table Structure)
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7, h_col8 = st.columns([0.5, 2, 1.5, 1.5, 2, 1.5, 2, 2])
        h_col1.write("☑️")
        h_col2.write("**Hostname**")
        h_col3.write("**Region**")
        h_col4.write("**IPv4**")
        h_col5.write("**Plan**")
        h_col6.write("**Status**")
        h_col7.write("**SSH**")
        h_col8.write("**Actions**")
        
        st.divider()

        # Data Rows
        for srv in servers:
            srv_id = srv.get("id")
            name = srv.get("name", "N/A")
            specs = srv.get("specs", {})
            region = specs.get("region", srv.get("region", "N/A"))
            ip = srv.get("ip", srv.get("main_ip", "N/A"))
            plan = srv.get("sku", "N/A")
            status = str(srv.get("status", "unknown")).lower()
            ssh_cmd = f"ssh root@{ip}" if ip != "N/A" else "N/A"

            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.5, 2, 1.5, 1.5, 2, 1.5, 2, 2])

            # Checkbox Selection
            is_checked = c1.checkbox("", key=f"chk_{srv_id}", value=(srv_id in st.session_state.selected_servers))
            if is_checked:
                st.session_state.selected_servers.add(srv_id)
            else:
                st.session_state.selected_servers.discard(srv_id)

            c2.write(f"**{name}**")
            c3.write(region)
            c4.code(ip, language="text")
            c5.write(plan)
            
            # Status Badge
            if status in ["active", "running"]:
                c6.markdown("🟢 `ACTIVE`")
            elif status in ["stopped", "off"]:
                c6.markdown("🔴 `STOPPED`")
            else:
                c6.markdown(f"🟡 `{status.upper()}`")

            c7.code(ssh_cmd, language="bash")

            # Inline Quick Actions
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
