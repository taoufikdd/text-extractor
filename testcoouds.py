import streamlit as st
import requests
import json

st.set_page_config(page_title="CloudCenmax Debugger & Deployer", layout="wide", page_icon="⚡")

st.title("⚡ CloudCenmax API Deployer & Diagnostic Tool")

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

# --- Configuration Section ---
st.subheader("🛠️ Deployment & Header Diagnostic")

col1, col2 = st.columns(2)
with col1:
    server_name = st.text_input("Server Name", value="server-test")
    
with col2:
    header_auth_type = st.selectbox(
        "Select Auth Header Format", 
        ["Bearer Token (Standard)", "X-API-Key Header", "Plain Token (No Bearer)"]
    )

if structured_catalog:
    col_reg, col_country, col_city, col_sku = st.columns([2, 2, 2, 3])
    with col_reg:
        selected_reg = st.selectbox("Region", sorted(list(structured_catalog.keys())))
    with col_country:
        selected_country = st.selectbox("Country", sorted(list(structured_catalog[selected_reg].keys())))
    with col_city:
        selected_city = st.selectbox("City", sorted(list(structured_catalog[selected_reg][selected_country].keys())))
    with col_sku:
        available_skus = structured_catalog[selected_reg][selected_country][selected_city]
        sku_map = {f"{item['name']} [{item['code']}]": item['code'] for item in available_skus}
        selected_sku_label = st.selectbox("SKU Plan", list(sku_map.keys()))
        selected_sku_code = sku_map[selected_sku_label]

    st.divider()

    if st.button("🚀 Execute Deployment Request", type="primary"):
        clean_key = api_key.strip()
        
        # تجهيز الهيدرز حسب الاختيار
        if header_auth_type == "Bearer Token (Standard)":
            headers = {"Authorization": f"Bearer {clean_key}", "Accept": "application/json", "Content-Type": "application/json"}
        elif header_auth_type == "X-API-Key Header":
            headers = {"X-API-Key": clean_key, "Accept": "application/json", "Content-Type": "application/json"}
        else:
            headers = {"Authorization": clean_key, "Accept": "application/json", "Content-Type": "application/json"}

        # تجربة Payload الخفيف المعياري
        payload = {
            "name": server_name.strip(),
            "sku": selected_sku_code,
            "options": {}
        }

        st.info("Sending Request...")
        try:
            res = requests.post(f"{BASE_URL}/resources", json=payload, headers=headers, timeout=15)
            
            st.write(f"**HTTP Response Code:** `{res.status_code}`")
            
            if res.status_code in [200, 201]:
                st.success("✅ Order Provisioned Successfully!")
                st.json(res.json())
            else:
                st.error(f"❌ Returned Error Code {res.status_code}")
                st.write("**Full Response Raw Output:**")
                st.code(res.text, language="json" if "{" in res.text else "text")

        except Exception as e:
            st.error(f"Exception Error: {str(e)}")
