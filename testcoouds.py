import streamlit as st
import requests

st.set_page_config(page_title="CloudCenmax Inspector & Deployer", layout="wide")

st.title("⚡ CloudCenmax API Debugger & Deployer")

st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("API Key", type="password")
base_url = st.sidebar.text_input("Base URL", value="https://cloudcenmax.com")

if api_key:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Lista dyal Endpoints l-mo7tamala f CloudCenmax
    test_endpoints = [
        "/api/v1/locations",
        "/api/v1/catalog/locations",
        "/api/v1/servers",
        "/api/locations",
        "/api/v1/plans",
        "/api/v1/os",
        "/api/v1/user"
    ]
    
    if st.sidebar.button("🔍 Scan Working Endpoints"):
        st.subheader("📡 Endpoint Diagnostics Results:")
        found_any = False
        
        for ep in test_endpoints:
            full_url = f"{base_url.rstrip('/')}{ep}"
            try:
                res = requests.get(full_url, headers=headers, timeout=5)
                if res.status_code != 404:
                    st.success(f"✅ **FOUND ({res.status_code})**: `{full_url}`")
                    st.json(res.json() if res.headers.get('content-type', '').startswith('application/json') else res.text)
                    found_any = True
                else:
                    st.error(f"❌ **404**: `{full_url}`")
            except Exception as e:
                st.warning(f"⚠️ Error testing `{full_url}`: {e}")
                
        if not found_any:
            st.info("💡 **نصيحة:** إذا ظهرت جميع المسارات 404، افتح F12 (Network tab) في المتصفح عند إنشاء سيرفر يدوي لمعرفة المسار الحقيقي الذي تستخدمه الواجهة.")
