import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Bulk Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax API Bulk Resource Deployer")
st.markdown("إنشاء السيرفرات بالـ SKU المناسب مع معالجة خطأ 500 والتحقق من الرصيد.")

BASE_URL = "https://cloudcenmax.com/api/v1"

# --- Sidebar Authentication ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password", help="ضع مفتاح ck_your_api_key هنا")
root_password = st.sidebar.text_input("Root Password", value="qRdkWWKIhbb9q6Nmwi3mfrt", type="password")

# --- Check Account Balance ---
def check_account_balance(key):
    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "Accept": "application/json"
    }
    try:
        res = requests.get(f"{BASE_URL}/account", headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", {})
            balance = data.get("balance", {}).get("amount", 0)
            return balance
    except Exception:
        pass
    return None

if api_key:
    user_balance = check_account_balance(api_key)
    if user_balance is not None:
        st.sidebar.metric("Current Balance", f"${user_balance:.2f}")
        if user_balance <= 0:
            st.sidebar.warning("⚠️ رصيدك 0$! السيرفر قد يرجع خطأ 500 أو 402 إذا لم يكن هناك رصيد كافي.")

# --- Fetch Catalog Data Dynamic ---
@st.cache_data(ttl=120)
def fetch_catalog(key):
    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "Accept": "application/json"
    }
    all_items = []
    page = 1
    
    while True:
        try:
            res = requests.get(f"{BASE_URL}/catalog?page={page}", headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                all_items.extend(items)
                if data.get("links", {}).get("next") is None:
                    break
                page += 1
            else:
                break
        except Exception:
            break
            
    return all_items

catalog_items = []
if api_key:
    with st.spinner("جاري جلب الـ Catalog..."):
        catalog_items = fetch_catalog(api_key)

if catalog_items:
    st.sidebar.success(f"✅ تم جلب {len(catalog_items)} خيار!")

# --- Parse Catalog Structure ---
structured_catalog = {}
for item in catalog_items:
    specs = item.get("specs", {})
    region = specs.get("region", "Other")
    country = specs.get("country", "Unknown")
    city = specs.get("city", "Unknown")
    
    if region not in structured_catalog:
        structured_catalog[region] = {}
    if country not in structured_catalog[region]:
        structured_catalog[region][country] = {}
    if city not in structured_catalog[region][country]:
        structured_catalog[region][country][city] = []
        
    structured_catalog[region][country][city].append(item)

# --- Deployment Form ---
st.subheader("🚀 Bulk Deployment Configuration")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=50, value=1, step=1)

server_list = []

if not structured_catalog:
    st.info("💡 أدخل الـ API Key أولاً لعرض الخيارات.")
else:
    for i in range(int(num_servers)):
        st.markdown(f"#### 🖥️ Server #{i+1}")
        
        col_host, col_reg, col_country, col_city, col_sku = st.columns([2, 2, 2, 2, 3])
        
        with col_host:
            h_name = st.text_input("Server Name", value=f"server-vm-{i+1}", key=f"name_{i}")
            
        with col_reg:
            reg_options = list(structured_catalog.keys())
            selected_reg = st.selectbox("Region", options=reg_options, key=f"reg_{i}")
            
        with col_country:
            country_options = list(structured_catalog[selected_reg].keys())
            selected_country = st.selectbox("Country", options=country_options, key=f"country_{i}")
            
        with col_city:
            city_options = list(structured_catalog[selected_reg][selected_country].keys())
            selected_city = st.selectbox("City", options=city_options, key=f"city_{i}")
            
        with col_sku:
            available_skus = structured_catalog[selected_reg][selected_country][selected_city]
            sku_labels = {f"{item['name']} ({item['code']})": item['code'] for item in available_skus}
            selected_sku_label = st.selectbox("SKU Plan", options=list(sku_labels.keys()), key=f"sku_{i}")
            selected_sku_code = sku_labels[selected_sku_label]

        server_list.append({
            "name": h_name,
            "sku": selected_sku_code
        })
        st.divider()

# --- Execution ---
if st.button("🔥 Deploy All Resources Now", type="primary"):
    if not api_key:
        st.error("❌ أدخل الـ API Key أولاً!")
    else:
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        progress = st.progress(0)
        status_box = st.container()
        logs_and_errors = []

        for idx, srv in enumerate(server_list):
            # تجربة إرسال الـ Payload مع options وبدونها إذا رجع 500
            payload_with_options = {
                "name": srv["name"],
                "sku": srv["sku"],
                "options": {
                    "image": "almalinux-8.10",
                    "os": "almalinux-8.10",
                    "password": root_password
                }
            }
            
            payload_minimal = {
                "name": srv["name"],
                "sku": srv["sku"]
            }

            try:
                # المحاولة الأولى بـ Options
                res = requests.post(f"{BASE_URL}/resources", json=payload_with_options, headers=headers, timeout=15)
                
                # إذا رجع 500، نجرب Payload بدون Options
                if res.status_code == 500:
                    res = requests.post(f"{BASE_URL}/resources", json=payload_minimal, headers=headers, timeout=15)

                if res.status_code in [200, 201]:
                    res_data = res.json().get("data", {})
                    server_id = res_data.get("id", "N/A")
                    status_box.success(f"✅ Created **{srv['name']}** (ID: `{server_id}`) | SKU: `{srv['sku']}`")
                elif res.status_code == 402:
                    status_box.error(f"💳 Payment Required: الرصيد غير كافي لشراء **{srv['name']}**.")
                    logs_and_errors.append({"name": srv["name"], "status_code": 402, "response": res.text})
                else:
                    status_box.error(f"❌ Failed **{srv['name']}**: HTTP Status {res.status_code}")
                    logs_and_errors.append({
                        "name": srv["name"],
                        "status_code": res.status_code,
                        "response": res.text
                    })
            except Exception as e:
                status_box.error(f"❌ Error on **{srv['name']}**: {str(e)}")
                logs_and_errors.append({"name": srv["name"], "status_code": "EXC", "response": str(e)})

            progress.progress((idx + 1) / len(server_list))

        if logs_and_errors:
            st.markdown("---")
            st.subheader("🚨 Error Details")
            for err in logs_and_errors:
                with st.expander(f"Details: {err['name']} (Status: {err['status_code']})"):
                    st.code(err["response"], language="json" if "{" in err["response"] else "html")
        else:
            st.balloons()
