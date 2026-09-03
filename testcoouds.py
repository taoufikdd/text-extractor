import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Bulk Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax API Resource Deployer")

BASE_URL = "https://cloudcenmax.com/api/v1"

# --- Sidebar Authentication ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("CloudCenmax API Key", type="password")

# --- Fetch Catalog ---
@st.cache_data(ttl=120)
def fetch_catalog(key):
    headers = {"Authorization": f"Bearer {key.strip()}", "Accept": "application/json"}
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

# --- Deployment Form ---
st.subheader("🚀 Bulk Deployment Configuration")
num_servers = st.number_input("Number of Servers to Create", min_value=1, max_value=50, value=1, step=1)

server_list = []

if structured_catalog:
    for i in range(int(num_servers)):
        st.markdown(f"#### 🖥️ Server #{i+1}")
        col_host, col_reg, col_country, col_city, col_sku = st.columns([2, 2, 2, 2, 3])
        
        with col_host:
            h_name = st.text_input("Server Name", value=f"server-{i+1}", key=f"name_{i}")
        with col_reg:
            selected_reg = st.selectbox("Region", sorted(list(structured_catalog.keys())), key=f"reg_{i}")
        with col_country:
            selected_country = st.selectbox("Country", sorted(list(structured_catalog[selected_reg].keys())), key=f"country_{i}")
        with col_city:
            selected_city = st.selectbox("City", sorted(list(structured_catalog[selected_reg][selected_country].keys())), key=f"city_{i}")
        with col_sku:
            available_skus = structured_catalog[selected_reg][selected_country][selected_city]
            sku_map = {f"{item['name']} [{item['code']}]": item['code'] for item in available_skus}
            selected_sku_label = st.selectbox("SKU Plan", list(sku_map.keys()), key=f"sku_{i}")
            selected_sku_code = sku_map[selected_sku_label]

        # خيارات إضافية تجريبية للـ Options
        st.caption("🔧 Optional Options Payload Customization:")
        include_os = st.checkbox("Include Default OS Image (AlmaLinux 8) in Options", value=True, key=f"os_chk_{i}")

        options_payload = {}
        if include_os:
            options_payload = {
                "image": "almalinux-8",
                "os": "almalinux-8"
            }

        server_list.append({
            "name": h_name.strip(),
            "sku": selected_sku_code,
            "options": options_payload
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
            payload = {
                "name": srv["name"],
                "sku": srv["sku"],
                "options": srv["options"]
            }

            try:
                res = requests.post(f"{BASE_URL}/resources", json=payload, headers=headers, timeout=15)

                if res.status_code in [200, 201]:
                    res_data = res.json().get("data", {})
                    server_id = res_data.get("id", "N/A")
                    status_box.success(f"✅ Created **{srv['name']}** (ID: `{server_id}`) | SKU: `{srv['sku']}`")
                elif res.status_code in [401, 403]:
                    status_box.error(f"🚫 Permission Error ({res.status_code}): الـ API Key قد يكون Read-Only أو يفتقر لصلاحية الكتابة (Write Permission).")
                    logs_and_errors.append({"name": srv["name"], "status_code": res.status_code, "response": res.text})
                else:
                    status_box.error(f"❌ Failed **{srv['name']}**: HTTP Status {res.status_code}")
                    logs_and_errors.append({
                        "name": srv["name"],
                        "status_code": res.status_code,
                        "payload_sent": payload,
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
                    st.write("**Payload Sent:**")
                    st.json(err.get("payload_sent", {}))
                    st.write("**Response:**")
                    st.code(err["response"], language="json")
