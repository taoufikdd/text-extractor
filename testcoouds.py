import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Manager & Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax Manager & Bulk Deployer")

BASE_URL = "https://cloudcenmax.com/api/v1"

# --- Sidebar Authentication ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password")

# --- Helper Functions ---
def get_headers(key):
    return {
        "Authorization": f"Bearer {key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

# 1. جلب رصيد الحساب
def check_account_balance(key):
    try:
        res = requests.get(f"{BASE_URL}/account", headers=get_headers(key), timeout=8)
        if res.status_code == 200:
            return res.json().get("data", {}).get("balance", {}).get("amount", 0)
    except Exception:
        pass
    return None

if api_key:
    user_balance = check_account_balance(api_key)
    if user_balance is not None:
        st.sidebar.metric("Current Balance", f"${user_balance:.2f}")

# 2. جلب جميع السيرفرات الحالية (Fetch Existing Servers)
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

# 3. إيقاف سيرفر (Stop / Power Off)
def stop_resource(key, resource_id):
    try:
        res = requests.post(f"{BASE_URL}/resources/{resource_id}/stop", headers=get_headers(key), timeout=10)
        return res.status_code in [200, 202], res.text
    except Exception as e:
        return False, str(e)

# 4. حذف سيرفر (Delete / Terminate)
def delete_resource(key, resource_id):
    try:
        res = requests.delete(f"{BASE_URL}/resources/{resource_id}", headers=get_headers(key), timeout=10)
        return res.status_code in [200, 202, 204], res.text
    except Exception as e:
        return False, str(e)

# --- Navigation Tabs ---
tab_manage, tab_deploy = st.tabs(["🖥️ Manage Existing Servers", "🚀 Bulk Deploy New Servers"])

# ==========================================
# TAB 1: SERVER MANAGEMENT & STATUS
# ==========================================
with tab_manage:
    st.subheader("📋 Active & Created Servers")
    
    if st.button("🔄 Refresh Servers List", type="secondary"):
        st.cache_data.clear()

    if api_key:
        with st.spinner("Fetching servers from CloudCenmax..."):
            servers = fetch_user_resources(api_key)
        
        if not servers:
            st.info("لا توجد أي سيرفرات حالية في هذا الحساب.")
        else:
            st.write(f"إجمالي السيرفرات المجلوبة: **{len(servers)}**")
            
            # خيار التحديد الجماعي
            st.markdown("---")
            col_a, col_b = st.columns(2)
            
            # عرض السيرفرات في جدول منظم
            for srv in servers:
                srv_id = srv.get("id")
                srv_name = srv.get("name", "N/A")
                srv_status = str(srv.get("status", "unknown")).lower()
                srv_ip = srv.get("ip", srv.get("main_ip", "N/A"))
                srv_sku = srv.get("sku", "N/A")
                
                # تنسيق الـ Badges حسب الحالة
                if srv_status in ["active", "running"]:
                    status_badge = f"🟢 **{srv_status.upper()}**"
                elif srv_status in ["pending", "creating", "processing"]:
                    status_badge = f"🟡 **{srv_status.upper()}**"
                elif srv_status in ["stopped", "off"]:
                    status_badge = f"🟠 **{srv_status.upper()}**"
                else:
                    status_badge = f"🔴 **{srv_status.upper()}**"
                
                with st.expander(f"🖥️ **{srv_name}** | IP: `{srv_ip}` | Status: {srv_status.upper()}"):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    
                    with c1:
                        st.write(f"**Resource ID:** `{srv_id}`")
                        st.write(f"**SKU:** `{srv_sku}`")
                        st.write(f"**Status:** {status_badge}")
                        st.write(f"**IP Address:** `{srv_ip}`")
                    
                    with c2:
                        if st.button(f"⏹️ Stop Server", key=f"stop_{srv_id}"):
                            success, msg = stop_resource(api_key, srv_id)
                            if success:
                                st.success(f"تم إرسال أمر الإيقاف للسيرفر {srv_name}!")
                            else:
                                st.error(f"فشل الإيقاف: {msg}")
                                
                    with c3:
                        if st.button(f"🗑️ Delete Server", key=f"del_{srv_id}", type="primary"):
                            success, msg = delete_resource(api_key, srv_id)
                            if success:
                                st.success(f"تم حذف السيرفر {srv_name} بنجاح!")
                            else:
                                st.error(f"فشل الحذف: {msg}")
    else:
        st.warning("⚠️ يرجى أدخال الـ API Key أولاً في القائمة الجانبية (Sidebar).")


# ==========================================
# TAB 2: BULK DEPLOYMENT
# ==========================================
with tab_deploy:
    st.subheader("🚀 Deploy New Virtual Machines")

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

            server_list.append({"name": h_name.strip(), "sku": selected_sku_code, "options": {}})
            st.divider()

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
