import base64
import json
import os
import random
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
import streamlit as st

# ==========================================
# 1. إعدادات الصفحة والتصاميم
# ==========================================
st.set_page_config(
    page_title="Vultr Multi-Account Manager",
    page_icon="🖥️",
    layout="wide"
)

ACCOUNTS_FILE = "vultr_accounts.json"
PLAN_ID = "vc2-2c-4gb"
DEFAULT_ROOT_PASSWORD = "qRdkWWKIhbb9q6Nmwi3mfrt"

USER_DATA_SCRIPT = f"""#!/bin/bash
echo 'root:{DEFAULT_ROOT_PASSWORD}' | chpasswd
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
systemctl restart sshd
"""
USER_DATA_B64 = base64.b64encode(USER_DATA_SCRIPT.encode("utf-8")).decode("utf-8")

# ==========================================
# 2. وظائف إدارة الحسابات (JSON)
# ==========================================
def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=4)

def parse_proxy(proxy_str):
    if not proxy_str or not proxy_str.strip():
        return None
    clean_str = proxy_str.strip()
    parts = clean_str.split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        p_url = f"http://{user}:{pwd}@{ip}:{port}"
        return {"http": p_url, "https": p_url}
    elif len(parts) == 2:
        ip, port = parts
        p_url = f"http://{ip}:{port}"
        return {"http": p_url, "https": p_url}
    return None

def test_proxy_connection(proxies):
    if not proxies:
        return True, "Direct Connection (No Proxy)"
    try:
        res = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=8)
        if res.status_code == 200:
            return True, res.json().get("ip")
    except Exception as e:
        return False, str(e)
    return False, "Unknown Error"

# ==========================================
# 3. وظائف API Vultr
# ==========================================
def get_all_instances(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.vultr.com/v2/instances", headers=headers, proxies=proxies, timeout=12)
        if res.status_code == 200:
            return res.json().get("instances", [])
    except Exception:
        pass
    return []

def get_centos_os_id(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.vultr.com/v2/os", headers=headers, proxies=proxies, timeout=12)
        if res.status_code == 200:
            os_list = res.json().get("os", [])
            for os_item in os_list:
                name = os_item.get("name", "")
                if "centos 9" in name.lower() or "stream 9" in name.lower():
                    return os_item.get("id"), name
            for os_item in os_list:
                if "centos" in os_item.get("name", "").lower():
                    return os_item.get("id"), os_item.get("name")
    except Exception:
        pass
    return None, None

def get_vultr_regions(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.vultr.com/v2/regions", headers=headers, proxies=proxies, timeout=12)
        if res.status_code == 200:
            regions_data = res.json().get("regions", [])
            return sorted(regions_data, key=lambda x: x.get("city", ""))
    except Exception:
        pass
    return []

def wait_for_ip(api_key, instance_id, proxies, max_retries=20):
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"https://api.vultr.com/v2/instances/{instance_id}"
    for _ in range(max_retries):
        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            if res.status_code == 200:
                main_ip = res.json().get("instance", {}).get("main_ip", "")
                if main_ip and main_ip != "0.0.0.0":
                    return main_ip
        except Exception:
            pass
        time.sleep(3)
    return "0.0.0.0"

# ==========================================
# 4. الواجهة والSidebar
# ==========================================
accounts = load_accounts()

st.sidebar.title("🎮 Account Management")

# إضافة حساب جديد
with st.sidebar.expander("➕ Add New Vultr Account"):
    acc_name = st.text_input("Account Label (e.g. Acc_1)")
    acc_key = st.text_input("API Key", type="password")
    acc_proxy = st.text_input("Proxy (IP:PORT or IP:PORT:USER:PASS)", placeholder="1.2.3.4:8080:user:pass")
    
    if st.button("Save Account"):
        if acc_name and acc_key:
            accounts[acc_name] = {
                "api_key": acc_key.strip(),
                "proxy": acc_proxy.strip()
            }
            save_accounts(accounts)
            st.sidebar.success(f"Account '{acc_name}' saved!")
            st.rerun()
        else:
            st.sidebar.error("Name and API Key are required.")

# اختيار الحساب الحالي
if not accounts:
    st.warning("⚠️ No Vultr accounts found. Please add an account using the left sidebar.")
    st.stop()

selected_acc_name = st.sidebar.selectbox("Select Active Account:", list(accounts.keys()))
active_acc = accounts[selected_acc_name]
current_api_key = active_acc["api_key"]
current_proxy_str = active_acc["proxy"]
current_proxies = parse_proxy(current_proxy_str)

# إمكانية حذف الحساب المحدد
if st.sidebar.button("🗑️ Delete Selected Account"):
    del accounts[selected_acc_name]
    save_accounts(accounts)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write("**Active Proxy Info:**")
if current_proxy_str:
    ok, ip_or_err = test_proxy_connection(current_proxies)
    if ok:
        st.sidebar.success(f"✅ Connected via IP: {ip_or_err}")
    else:
        st.sidebar.error(f"❌ Proxy Error: {ip_or_err}")
else:
    st.sidebar.info("🌐 Direct Connection (No Proxy)")

# ==========================================
# 5. الواجهة الرئيسية للعمليات
# ==========================================
st.title(f"🖥️ Vultr Manager — [{selected_acc_name}]")

tab1, tab2, tab3 = st.tabs(["📊 Active Instances", "🚀 Deploy Servers", "🗑️ Delete Servers"])

# --- TAB 1: عرض السيرفرات النشطة ---
with tab1:
    st.subheader("Active Instances")
    if st.button("🔄 Refresh Instances"):
        st.rerun()
        
    instances = get_all_instances(current_api_key, current_proxies)
    if instances:
        table_data = []
        for inst in instances:
            table_data.append({
                "ID": inst.get("id"),
                "IP Address": inst.get("main_ip", "N/A"),
                "Status": inst.get("status"),
                "Region": inst.get("region"),
                "Label": inst.get("label", "N/A"),
                "RAM": inst.get("ram"),
                "vCPU": inst.get("vcpu")
            })
        st.dataframe(table_data, use_container_width=True)
    else:
        st.info("No active instances found or failed to connect.")

# --- TAB 2: إنشاء سيرفرات جديدة ---
with tab2:
    st.subheader("Deploy New Servers")
    
    os_id, os_name = get_centos_os_id(current_api_key, current_proxies)
    if not os_id:
        st.error("Could not fetch CentOS OS ID. Check API Key/Proxy.")
    else:
        st.success(f"Target OS: **{os_name}** (ID: `{os_id}`)")
        
        regions_list = get_vultr_regions(current_api_key, current_proxies)
        region_options = {f"{r.get('city')} ({r.get('country')}) [{r.get('id')}]": r.get('id') for r in regions_list}
        
        selected_region_labels = st.multiselect("Select Target Regions:", list(region_options.keys()))
        server_count = st.number_input("Total Number of Servers:", min_value=1, max_value=50, value=1)
        
        if st.button("🚀 Start Deployment"):
            if not selected_region_labels:
                st.error("Please select at least one region.")
            else:
                selected_codes = [region_options[lbl] for lbl in selected_region_labels]
                num_regions = len(selected_codes)
                base_per = server_count // num_regions
                remainder = server_count % num_regions
                
                status_box = st.empty()
                progress_bar = st.progress(0)
                
                results = []
                counter = 0
                
                for idx, code in enumerate(selected_codes):
                    count_for_reg = base_per + (1 if idx < remainder else 0)
                    for _ in range(count_for_reg):
                        counter += 1
                        hostname = f"vultr-server-{counter}"
                        status_box.info(f"⏳ Creating server {counter}/{server_count} in region **{code}**...")
                        
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
                            "backups": "disabled"
                        }
                        
                        try:
                            res = requests.post("https://api.vultr.com/v2/instances", headers=headers, json=payload, proxies=current_proxies, timeout=15)
                            if res.status_code == 202:
                                inst_id = res.json().get("instance", {}).get("id")
                                ip = wait_for_ip(current_api_key, inst_id, current_proxies)
                                formatted = f"{ip},22,root,{DEFAULT_ROOT_PASSWORD}"
                                results.append(formatted)
                                
                                with open("vultr_servers.txt", "a", encoding="utf-8") as f_out:
                                    f_out.write(formatted + "\n")
                            else:
                                st.error(f"Failed to create server: {res.text}")
                        except Exception as e:
                            st.error(f"Error: {e}")
                        
                        progress_bar.progress(counter / server_count)
                
                status_box.success("🎉 Deployment Complete!")
                st.text_area("Created Servers List (ip,port,user,pass):", value="\n".join(results), height=150)

# --- TAB 3: حذف السيرفرات ---
with tab3:
    st.subheader("Delete Instances")
    del_mode = st.radio("Delete Option:", [
        "☑️ Checkbox Selection (Select & Delete)", 
        "📝 Paste Specific IPs", 
        "🔥 DANGER: Wipe ALL Instances"
    ])
    
    # 1. تحديد السيرفرات بواسطة Checkbox مع أزرار التحكم بالكل
    if del_mode == "☑️ Checkbox Selection (Select & Delete)":
        
        # حفظ السيرفرات في Session State لمنع التعتيم وإعادة التحديث المتكرر
        if f"cached_instances_{selected_acc_name}" not in st.session_state or st.button("🔄 Reload Server List"):
            st.session_state[f"cached_instances_{selected_acc_name}"] = get_all_instances(current_api_key, current_proxies)
            
        instances = st.session_state[f"cached_instances_{selected_acc_name}"]
        
        if not instances:
            st.info("No active instances found in this account.")
        else:
            # أزرار تحديد / إلغاء تحديد الكل
            col_btn1, col_btn2, _ = st.columns([1, 1, 3])
            with col_btn1:
                if st.button("✅ Select All"):
                    for inst in instances:
                        st.session_state[f"form_chk_{inst.get('id')}"] = True
                    st.rerun()
            with col_btn2:
                if st.button("❌ Unselect All"):
                    for inst in instances:
                        st.session_state[f"form_chk_{inst.get('id')}"] = False
                    st.rerun()

            st.markdown("---")

            with st.form("delete_servers_form"):
                st.write("Select the servers you want to delete:")
                
                checkbox_states = {}
                for inst in instances:
                    inst_id = inst.get("id")
                    ip = inst.get("main_ip", "N/A")
                    label = inst.get("label", "N/A")
                    region = inst.get("region", "N/A")
                    
                    chk_key = f"form_chk_{inst_id}"
                    if chk_key not in st.session_state:
                        st.session_state[chk_key] = False

                    checkbox_states[inst_id] = (
                        st.checkbox(
                            f"🖥️ **{label}** | IP: `{ip}` | Region: `{region}`", 
                            key=chk_key
                        ),
                        ip
                    )
                
                st.markdown("---")
                submit_delete = st.form_submit_button("🗑️ Delete Selected Servers", type="primary")
            
            if submit_delete:
                selected_to_delete = [(inst_id, ip) for inst_id, (is_checked, ip) in checkbox_states.items() if is_checked]
                
                if not selected_to_delete:
                    st.warning("Please select at least one server to delete.")
                else:
                    headers = {"Authorization": f"Bearer {current_api_key}"}
                    success_count = 0
                    
                    for inst_id, ip in selected_to_delete:
                        res = requests.delete(f"https://api.vultr.com/v2/instances/{inst_id}", headers=headers, proxies=current_proxies)
                        if res.status_code == 204:
                            st.success(f"✅ Deleted server: {ip}")
                            success_count += 1
                        else:
                            st.error(f"❌ Failed to delete server: {ip}")
                    
                    st.success(f"Process finished! Total deleted: {success_count}")
                    # إعادة تحديث القائمة المخزنة بعد الحذف
                    st.session_state[f"cached_instances_{selected_acc_name}"] = get_all_instances(current_api_key, current_proxies)
                    time.sleep(1)
                    st.rerun()

    # 2. خيار كتابة IPs يدوياً
    elif del_mode == "📝 Paste Specific IPs":
        ips_input = st.text_area("Enter IP addresses (one per line or comma separated):")
        if st.button("🗑️ Delete Specified Servers"):
            raw_ips = [ip.strip().split(",")[0] for line in ips_input.splitlines() for ip in line.split(",") if ip.strip()]
            if not raw_ips:
                st.error("Please enter at least one IP.")
            else:
                instances = get_all_instances(current_api_key, current_proxies)
                ip_to_id = {inst.get("main_ip"): inst.get("id") for inst in instances if inst.get("main_ip")}
                
                headers = {"Authorization": f"Bearer {current_api_key}"}
                success_count = 0
                for target_ip in raw_ips:
                    if target_ip in ip_to_id:
                        inst_id = ip_to_id[target_ip]
                        res = requests.delete(f"https://api.vultr.com/v2/instances/{inst_id}", headers=headers, proxies=current_proxies)
                        if res.status_code == 204:
                            st.success(f"Deleted IP: {target_ip}")
                            success_count += 1
                        else:
                            st.error(f"Failed to delete {target_ip}")
                    else:
                        st.warning(f"IP {target_ip} not found in active servers.")
                st.info(f"Process complete. Deleted {success_count} server(s).")
                
    # 3. خيار مسح الحساب بالكامل
    else:
        st.error("⚠️ WARNING: This will permanently delete ALL instances in the selected account!")
        confirm_code = st.text_input("Type 'DELETE ALL' to confirm:")
        if st.button("🔥 WIPE ALL SERVERS NOW"):
            if confirm_code == "DELETE ALL":
                instances = get_all_instances(current_api_key, current_proxies)
                headers = {"Authorization": f"Bearer {current_api_key}"}
                deleted = 0
                for inst in instances:
                    inst_id = inst.get("id")
                    res = requests.delete(f"https://api.vultr.com/v2/instances/{inst_id}", headers=headers, proxies=current_proxies)
                    if res.status_code == 204:
                        deleted += 1
                st.success(f"Total Wiped: {deleted} instances.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Confirmation text mismatch.")
