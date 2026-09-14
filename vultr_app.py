import base64
import json
import os
import time
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. إعدادات الصفحة والتصاميم
# ==========================================
st.set_page_config(
    page_title="Vultr Multi-Account Manager — 4 Plan Types",
    page_icon="🖥️",
    layout="wide"
)

ACCOUNTS_FILE = "vultr_accounts.json"
DEFAULT_ROOT_PASSWORD = "qRdkWWKIhbb9q6Nmwi3mfrt"

USER_DATA_SCRIPT = f"""#!/bin/bash
echo 'root:{DEFAULT_ROOT_PASSWORD}' | chpasswd
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
systemctl restart sshd
"""
USER_DATA_B64 = base64.b64encode(USER_DATA_SCRIPT.encode("utf-8")).decode("utf-8")

# ==========================================
# 🔒 نظام LOGIN (Authentication)
# ==========================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin12345")

    st.title("🔒 Login to Vultr Manager")
    user_pass = st.text_input("Enter Access Password:", type="password")
    
    if st.button("Login", type="primary"):
        if user_pass == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("✅ Logged in successfully!")
            st.rerun()
        else:
            st.error("❌ Invalid password!")
    return False

if not check_password():
    st.stop()

# ==========================================
# 2. وظائف إدارة الحسابات (مع الـ Persistent Cache)
# ==========================================
def load_accounts():
    accounts = {}
    if "VULTR_ACCOUNTS" in st.secrets:
        try:
            accounts.update(json.loads(st.secrets["VULTR_ACCOUNTS"]))
        except Exception:
            pass

    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accounts.update(json.load(f))
        except Exception:
            pass
            
    return accounts

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
# 3. وظائف API Vultr والتحقق من حالة الحساب
# ==========================================
def check_account_health(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.vultr.com/v2/account", headers=headers, proxies=proxies, timeout=12)
        if res.status_code == 200:
            acc_info = res.json().get("account", {})
            return True, "ACTIVE", acc_info
        elif res.status_code == 403:
            return False, "SUSPENDED_OR_FORBIDDEN", "⚠️ Account is Suspended, Locked, or Unauthorized (403 Forbidden)"
        elif res.status_code == 401:
            return False, "INVALID_API_KEY", "❌ Invalid API Key (401 Unauthorized)"
        else:
            return False, "ERROR", f"⚠️ Vultr Error Code {res.status_code}: {res.text}"
    except Exception as e:
        return False, "CONNECTION_ERROR", f"❌ Connection Error: {str(e)}"

def get_all_instances(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get("https://api.vultr.com/v2/instances", headers=headers, proxies=proxies, timeout=12)
        if res.status_code == 200:
            return True, res.json().get("instances", []), None
        elif res.status_code == 403:
            return False, [], "⚠️ Account Status: SUSPENDED / LOCKED (403 Forbidden)"
        elif res.status_code == 401:
            return False, [], "❌ Account Status: INVALID API KEY (401 Unauthorized)"
        else:
            return False, [], f"⚠️ Error {res.status_code}: {res.text}"
    except Exception as e:
        return False, [], f"❌ Network/Proxy Error: {str(e)}"

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

def get_vultr_plans(api_key, proxies):
    """Fetch all normal Cloud/Compute plans."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(
            "https://api.vultr.com/v2/plans",
            headers=headers,
            proxies=proxies,
            timeout=15
        )
        if res.status_code == 200:
            plans = res.json().get("plans", [])
            return sorted(plans, key=lambda x: x.get("monthly_cost", 0) or 0)
    except Exception:
        pass
    return []


def get_vultr_bare_metal_plans(api_key, proxies):
    """Fetch Bare Metal plans."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(
            "https://api.vultr.com/v2/bare-metals/plans",
            headers=headers,
            proxies=proxies,
            timeout=15
        )
        if res.status_code == 200:
            data = res.json()
            plans = data.get("plans", data.get("bare_metal_plans", []))
            return sorted(plans, key=lambda x: x.get("monthly_cost", 0) or 0)
    except Exception:
        pass
    return []


PLAN_CATEGORIES = {
    "Shared CPU": {
        "prefixes": ("vc2-",),
        "description": "Shared CPU / regular Cloud Compute"
    },
    "Dedicated CPU": {
        "prefixes": ("vdc-", "vhf-", "vhp-", "voc-"),
        "description": "Dedicated / High Frequency / High Performance CPU plans"
    },
    "Cloud GPU": {
        "prefixes": ("vcg-",),
        "description": "Cloud GPU instances"
    },
    "Bare Metal": {
        "prefixes": ("vbm-",),
        "description": "Single-tenant physical servers"
    },
}


def get_plan_category(plan):
    """Classify Vultr plans using their documented family prefixes/types."""
    plan_id = str(plan.get("id", "")).lower()
    ptype = str(plan.get("type", "")).lower()

    if plan_id.startswith("vbm-") or ptype == "vbm":
        return "Bare Metal"
    if plan_id.startswith("vcg-") or ptype == "vcg":
        return "Cloud GPU"
    if plan_id.startswith("vc2-") or ptype == "vc2":
        return "Shared CPU"
    if plan_id.startswith(("vdc-", "vhf-", "vhp-", "voc-")):
        return "Dedicated CPU"

    if any(x in ptype for x in ("gpu", "vcg")):
        return "Cloud GPU"
    if any(x in ptype for x in ("bare", "vbm")):
        return "Bare Metal"
    if ptype in ("vdc", "vhf", "vhp", "voc", "dedicated"):
        return "Dedicated CPU"

    return None


def get_plans_for_category(api_key, proxies, category):
    if category == "Bare Metal":
        plans = get_vultr_bare_metal_plans(api_key, proxies)
    else:
        plans = get_vultr_plans(api_key, proxies)

    return [p for p in plans if get_plan_category(p) == category]


def get_vultr_regions(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(
            "https://api.vultr.com/v2/regions",
            headers=headers,
            proxies=proxies,
            timeout=15
        )
        if res.status_code == 200:
            return sorted(
                res.json().get("regions", []),
                key=lambda x: x.get("city", "")
            )
    except Exception:
        pass
    return []


def get_regions_for_plan(regions, plan):
    """Use the plan's location list when supplied by the API."""
    locations = plan.get("locations")

    if isinstance(locations, list) and locations:
        location_ids = {str(x) for x in locations}
        filtered = [
            r for r in regions
            if str(r.get("id")) in location_ids
        ]
        if filtered:
            return sorted(filtered, key=lambda x: x.get("city", ""))

    # If the API does not include location metadata, show the full region list.
    return sorted(regions, key=lambda x: x.get("city", ""))


def attach_dedicated_ip(api_key, instance_id, region_code, proxies):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "region": region_code,
        "ip_type": "v4",
        "label": f"dedicated-ip-{instance_id}"
    }
    try:
        res = requests.post("https://api.vultr.com/v2/reserved-ips", headers=headers, json=payload, proxies=proxies, timeout=12)
        if res.status_code in [200, 201]:
            reserved_ip_data = res.json().get("reserved_ip", {})
            reserved_ip_id = reserved_ip_data.get("id")
            subnet = reserved_ip_data.get("subnet")

            attach_payload = {"instance_id": instance_id}
            att_res = requests.post(f"https://api.vultr.com/v2/reserved-ips/{reserved_ip_id}/attach", headers=headers, json=attach_payload, proxies=proxies, timeout=12)
            if att_res.status_code in [200, 202]:
                return True, subnet
    except Exception:
        pass
    return False, None

def wait_for_ip_and_ipv6(api_key, instance_id, proxies, max_retries=20):
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

def deploy_single_server(counter, code, os_id, plan_id, need_dedicated_ip, current_api_key, current_proxies):
    hostname = f"vultr-server-{counter}"
    headers = {
        "Authorization": f"Bearer {current_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "region": code,
        "plan": plan_id,
        "os_id": os_id,
        "user_scheme": "root",
        "password": DEFAULT_ROOT_PASSWORD,
        "user_data": USER_DATA_B64,
        "hostname": hostname,
        "label": hostname,
        "backups": "disabled",
        "enable_ipv6": True
    }
    
    try:
        res = requests.post("https://api.vultr.com/v2/instances", headers=headers, json=payload, proxies=current_proxies, timeout=15)
        if res.status_code == 202:
            inst_id = res.json().get("instance", {}).get("id")
            ip, _ = wait_for_ip_and_ipv6(current_api_key, inst_id, current_proxies)
            
            extra_ip_str = ""
            if need_dedicated_ip:
                ok_ip, extra_ip = attach_dedicated_ip(current_api_key, inst_id, code, current_proxies)
                if ok_ip and extra_ip:
                    extra_ip_str = f" | Dedicated_IP: {extra_ip}"

            formatted = f"{ip},22,root,{DEFAULT_ROOT_PASSWORD}{extra_ip_str}"
            return True, formatted, None
        else:
            return False, None, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, None, str(e)

def deploy_single_bare_metal(counter, code, os_id, plan_id, current_api_key, current_proxies):
    """Create one Vultr Bare Metal server."""
    hostname = f"vultr-baremetal-{counter}"
    headers = {
        "Authorization": f"Bearer {current_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "region": code,
        "plan": plan_id,
        "os_id": os_id,
        "user_data": USER_DATA_B64,
        "hostname": hostname,
        "label": hostname,
        "enable_ipv6": True
    }

    try:
        res = requests.post(
            "https://api.vultr.com/v2/bare-metals",
            headers=headers,
            json=payload,
            proxies=current_proxies,
            timeout=20
        )

        if res.status_code in [200, 202]:
            data = res.json()
            bm = data.get("bare_metal", data.get("baremetal", data))
            inst_id = bm.get("id")

            if not inst_id:
                return False, None, f"API returned no Bare Metal ID: {res.text}"

            for _ in range(30):
                try:
                    check = requests.get(
                        f"https://api.vultr.com/v2/bare-metals/{inst_id}",
                        headers=headers,
                        proxies=current_proxies,
                        timeout=12
                    )
                    if check.status_code == 200:
                        current = check.json().get(
                            "bare_metal",
                            check.json().get("baremetal", {})
                        )
                        ip = current.get("main_ip", "")
                        if ip and ip != "0.0.0.0":
                            password = current.get("default_password") or DEFAULT_ROOT_PASSWORD
                            return True, f"{ip},22,root,{password}", None
                except Exception:
                    pass
                time.sleep(3)

            return False, None, "Bare Metal created, but public IP was not available before timeout."

        return False, None, f"HTTP {res.status_code}: {res.text}"

    except Exception as e:
        return False, None, str(e)


def get_all_bare_metals(api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(
            "https://api.vultr.com/v2/bare-metals",
            headers=headers,
            proxies=proxies,
            timeout=15
        )
        if res.status_code == 200:
            data = res.json()
            return True, data.get("bare_metals", data.get("baremetal", [])), None
        if res.status_code == 403:
            return False, [], "Bare Metal access forbidden (403)."
        if res.status_code == 401:
            return False, [], "Invalid API Key (401 Unauthorized)"
        return False, [], f"Error {res.status_code}: {res.text}"
    except Exception as e:
        return False, [], str(e)


def delete_single_bare_metal(inst_id, api_key, proxies):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.delete(
            f"https://api.vultr.com/v2/bare-metals/{inst_id}",
            headers=headers,
            proxies=proxies,
            timeout=15
        )
        if res.status_code in [200, 202, 204]:
            return True, inst_id
        return False, inst_id
    except Exception:
        return False, inst_id


def delete_single_server(inst_id, current_api_key, current_proxies):
    headers = {"Authorization": f"Bearer {current_api_key}"}
    try:
        res = requests.delete(f"https://api.vultr.com/v2/instances/{inst_id}", headers=headers, proxies=current_proxies, timeout=12)
        if res.status_code == 204:
            return True, inst_id
        return False, inst_id
    except Exception:
        return False, inst_id

# ==========================================
# 4. الواجهة والSidebar
# ==========================================
accounts = load_accounts()

st.sidebar.title("🎮 Account Management")

if st.sidebar.button("🚪 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

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

if not accounts:
    st.warning("⚠️ No Vultr accounts found. Please add an account using the left sidebar.")
    st.stop()

selected_acc_name = st.sidebar.selectbox("Select Active Account:", list(accounts.keys()))
active_acc = accounts[selected_acc_name]
current_api_key = active_acc["api_key"]
current_proxy_str = active_acc["proxy"]
current_proxies = parse_proxy(current_proxy_str)

if st.sidebar.button("🔍 Test Account Status"):
    ok, code, msg = check_account_health(current_api_key, current_proxies)
    if ok:
        st.sidebar.success(f"✅ Account OK! Balance: ${msg.get('balance')} | Pending Charges: ${msg.get('pending_charges')}")
    else:
        st.sidebar.error(f"❌ {msg}")

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

is_healthy, status_code_acc, acc_details = check_account_health(current_api_key, current_proxies)

if not is_healthy:
    st.error(f"🚨 **ACCOUNT ALERT [{selected_acc_name}]:** {acc_details}")

tab1, tab2, tab3 = st.tabs(["📊 Active Instances", "🚀 Deploy Servers", "🗑️ Delete Servers"])

# --- TAB 1: عرض السيرفرات النشطة ---
with tab1:
    st.subheader("Active Instances")

    if st.button("🔄 Refresh Instances"):
        st.rerun()

    success, cloud_instances, err_msg = get_all_instances(
        current_api_key, current_proxies
    )
    bm_success, bare_metals, bm_err = get_all_bare_metals(
        current_api_key, current_proxies
    )

    if not success:
        st.error(f"🚨 Failed to load Cloud instances: {err_msg}")
    if not bm_success:
        st.warning(f"⚠️ Failed to load Bare Metal instances: {bm_err}")

    table_data = []

    if success:
        for inst in cloud_instances:
            table_data.append({
                "Type": "Cloud",
                "ID": inst.get("id"),
                "IPv4 Address": inst.get("main_ip", "N/A"),
                "IPv6 Address": inst.get("v6_main_ip", "N/A"),
                "Status": inst.get("status"),
                "Region": inst.get("region"),
                "Label": inst.get("label", "N/A"),
                "RAM": inst.get("ram"),
                "vCPU": inst.get("vcpu")
            })

    if bm_success:
        for inst in bare_metals:
            table_data.append({
                "Type": "Bare Metal",
                "ID": inst.get("id"),
                "IPv4 Address": inst.get("main_ip", "N/A"),
                "IPv6 Address": inst.get("v6_main_ip", "N/A"),
                "Status": inst.get("status"),
                "Region": inst.get("region"),
                "Label": inst.get("label", "N/A"),
                "RAM": inst.get("ram"),
                "vCPU": inst.get("cpu_count")
            })

    if table_data:
        st.dataframe(table_data, use_container_width=True)
    else:
        st.info("No active instances found in this account.")

# --- TAB 2: إنشاء سيرفرات جديدة ---
with tab2:
    st.subheader("Deploy New Servers")

    if not is_healthy:
        st.warning(
            "⚠️ You cannot deploy new servers because the selected account "
            "has errors or is suspended."
        )
    else:
        plan_type = st.radio(
            "🖥️ Server Type",
            ["Shared CPU", "Dedicated CPU", "Cloud GPU", "Bare Metal"],
            horizontal=True
        )

        st.caption(PLAN_CATEGORIES[plan_type]["description"])

        is_bare_metal = plan_type == "Bare Metal"

        os_id, os_name = get_centos_os_id(
            current_api_key, current_proxies
        )

        if not os_id:
            st.error(
                "Could not fetch the selected CentOS OS ID. "
                "Check API Key/Proxy and OS availability."
            )
        else:
            st.success(
                f"Target OS: **{os_name}** (ID: `{os_id}`)"
            )

            plans_list = get_plans_for_category(
                current_api_key,
                current_proxies,
                plan_type
            )
            regions_list = get_vultr_regions(
                current_api_key,
                current_proxies
            )

            if not plans_list:
                st.error(
                    f"No {plan_type} plans found or the API returned no plans."
                )
            elif not regions_list:
                st.error("No Vultr regions were returned by the API.")
            else:
                def plan_label(p):
                    pid = p.get("id", "N/A")
                    ram = p.get("ram", p.get("memory", "N/A"))
                    vcpu = p.get("vcpu_count", p.get("cpu_count", "N/A"))
                    disk = p.get("disk", "N/A")
                    monthly = p.get("monthly_cost", "N/A")

                    extra = ""
                    if p.get("gpu_type"):
                        extra = f" | GPU: {p.get('gpu_type')}"
                    elif p.get("cpu_model"):
                        extra = f" | CPU: {p.get('cpu_model')}"

                    return (
                        f"🔥 {pid} — {ram}MB RAM | "
                        f"{vcpu} CPU | Disk: {disk} | "
                        f"${monthly}/mo{extra}"
                    )

                plan_options = {
                    plan_label(p): p for p in plans_list
                }

                selected_plan_label = st.selectbox(
                    f"⚙️ Select {plan_type} Plan:",
                    options=list(plan_options.keys()),
                    index=0
                )
                selected_plan = plan_options[selected_plan_label]
                selected_plan_id = selected_plan.get("id")

                compatible_regions = get_regions_for_plan(
                    regions_list, selected_plan
                )

                region_options = {
                    f"{r.get('city')} ({r.get('country')}) [{r.get('id')}]":
                    r.get("id")
                    for r in compatible_regions
                }

                selected_region_labels = st.multiselect(
                    "🌍 Select Target Regions:",
                    list(region_options.keys()),
                    help=(
                        "Regions are loaded dynamically. If Vultr returns "
                        "location data for the selected plan, only compatible "
                        "regions are displayed."
                    )
                )

                server_count = st.number_input(
                    "Total Number of Servers:",
                    min_value=1,
                    max_value=50,
                    value=1
                )

                need_dedicated_ip = False
                if not is_bare_metal:
                    need_dedicated_ip = st.checkbox(
                        "📌 Attach Additional Dedicated Public IPv4 (+ $3/mo approx)",
                        value=False
                    )

                if st.button("🚀 Start Deployment", type="primary"):
                    if not selected_region_labels:
                        st.error("Please select at least one region.")
                    else:
                        selected_codes = [
                            region_options[label]
                            for label in selected_region_labels
                        ]

                        num_regions = len(selected_codes)
                        base_per = server_count // num_regions
                        remainder = server_count % num_regions

                        status_box = st.empty()
                        progress_bar = st.progress(0)

                        tasks = []
                        counter = 0

                        for idx, code in enumerate(selected_codes):
                            count_for_reg = (
                                base_per + (1 if idx < remainder else 0)
                            )
                            for _ in range(count_for_reg):
                                counter += 1
                                tasks.append((counter, code))

                        results = []
                        completed_count = 0

                        status_box.info(
                            f"⚡ Deploying {server_count} server(s) "
                            f"using {plan_type} / {selected_plan_id} in parallel..."
                        )

                        with ThreadPoolExecutor(
                            max_workers=min(10, server_count)
                        ) as executor:
                            futures = []

                            for c, reg in tasks:
                                if is_bare_metal:
                                    futures.append(
                                        executor.submit(
                                            deploy_single_bare_metal,
                                            c,
                                            reg,
                                            os_id,
                                            selected_plan_id,
                                            current_api_key,
                                            current_proxies
                                        )
                                    )
                                else:
                                    futures.append(
                                        executor.submit(
                                            deploy_single_server,
                                            c,
                                            reg,
                                            os_id,
                                            selected_plan_id,
                                            need_dedicated_ip,
                                            current_api_key,
                                            current_proxies
                                        )
                                    )

                            for future in as_completed(futures):
                                success_dep, formatted_res, err = future.result()
                                completed_count += 1
                                progress_bar.progress(
                                    completed_count / server_count
                                )

                                if success_dep and formatted_res:
                                    results.append(formatted_res)

                                    output_file = (
                                        "vultr_bare_metal_servers.txt"
                                        if is_bare_metal
                                        else "vultr_servers.txt"
                                    )

                                    with open(
                                        output_file,
                                        "a",
                                        encoding="utf-8"
                                    ) as f_out:
                                        f_out.write(formatted_res + "\n")
                                else:
                                    st.error(f"Deployment Error: {err}")

                        status_box.success("🎉 Deployment Complete!")

                        st.text_area(
                            "Created Servers List (ipv4,port,user,pass):",
                            value="\n".join(results),
                            height=180
                        )

# --- TAB 3: حذف السيرفرات ---
with tab3:
    st.subheader("Delete Servers")

    delete_scope = st.radio(
        "Resource Type:",
        ["Cloud Instances", "Bare Metal", "Both"],
        horizontal=True
    )

    if delete_scope in ["Cloud Instances", "Both"]:
        cloud_ok, cloud_instances, cloud_err = get_all_instances(
            current_api_key, current_proxies
        )
    else:
        cloud_ok, cloud_instances, cloud_err = True, [], None

    if delete_scope in ["Bare Metal", "Both"]:
        bm_ok, bare_metals, bm_err = get_all_bare_metals(
            current_api_key, current_proxies
        )
    else:
        bm_ok, bare_metals, bm_err = True, [], None

    if not cloud_ok:
        st.error(f"Cloud list error: {cloud_err}")
    if not bm_ok:
        st.error(f"Bare Metal list error: {bm_err}")

    combined = []

    if cloud_ok:
        for inst in cloud_instances:
            combined.append({
                "resource_type": "Cloud",
                "id": inst.get("id"),
                "ip": inst.get("main_ip", "N/A"),
                "label": inst.get("label", "N/A"),
                "region": inst.get("region", "N/A")
            })

    if bm_ok:
        for inst in bare_metals:
            combined.append({
                "resource_type": "Bare Metal",
                "id": inst.get("id"),
                "ip": inst.get("main_ip", "N/A"),
                "label": inst.get("label", "N/A"),
                "region": inst.get("region", "N/A")
            })

    if not combined:
        st.info("No servers found.")
    else:
        if st.button("🔄 Reload Server List"):
            st.rerun()

        st.markdown("---")
        selected = {}

        with st.form("delete_servers_form"):
            st.write("Select the servers you want to delete:")

            for inst in combined:
                key = f"delete_{inst['resource_type']}_{inst['id']}"
                selected[key] = st.checkbox(
                    f"🖥️ {inst['resource_type']} | "
                    f"**{inst['label']}** | "
                    f"IP: `{inst['ip']}` | "
                    f"Region: `{inst['region']}`",
                    key=key
                )

            st.markdown("---")
            submit_delete = st.form_submit_button(
                "🗑️ Delete Selected Servers",
                type="primary"
            )

        if submit_delete:
            targets = [
                inst for inst in combined
                if selected.get(
                    f"delete_{inst['resource_type']}_{inst['id']}",
                    False
                )
            ]

            if not targets:
                st.warning("Please select at least one server.")
            else:
                status_del = st.empty()
                status_del.info(
                    f"⚡ Deleting {len(targets)} server(s) in parallel..."
                )

                success_count = 0

                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_map = {}

                    for inst in targets:
                        if inst["resource_type"] == "Bare Metal":
                            future = executor.submit(
                                delete_single_bare_metal,
                                inst["id"],
                                current_api_key,
                                current_proxies
                            )
                        else:
                            future = executor.submit(
                                delete_single_server,
                                inst["id"],
                                current_api_key,
                                current_proxies
                            )

                        future_map[future] = inst

                    for future in as_completed(future_map):
                        inst = future_map[future]
                        ok_del, _ = future.result()

                        if ok_del:
                            st.success(
                                f"✅ Deleted {inst['resource_type']}: {inst['ip']}"
                            )
                            success_count += 1
                        else:
                            st.error(
                                f"❌ Failed to delete "
                                f"{inst['resource_type']}: {inst['ip']}"
                            )

                status_del.success(
                    f"Process finished! Total deleted: {success_count}"
                )
                time.sleep(1)
                st.rerun()

