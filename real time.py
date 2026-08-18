import json
import os
import requests
import pandas as pd
from datetime import date
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. إعداد الصفحة والتحديث التلقائي
# ==========================================
st.set_page_config(
    page_title="Live Revenue Tracker",
    page_icon="💰",
    layout="wide"
)

st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

CONFIG_FILE = "api_keys.json"

# ==========================================
# 💾 2. إدارة الـ API Keys
# ==========================================
def load_keys():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_keys(keys_list):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(keys_list, f, indent=4)

if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = load_keys()

# ==========================================
# ⚙️ 3. Sidebar
# ==========================================
st.sidebar.title("⚙️ Config")

st.sidebar.subheader("📅 Date")
today = date.today()
start_date = st.sidebar.date_input("From", today)
end_date = st.sidebar.date_input("To", today)

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Add API Key")

new_key = st.sidebar.text_input("Enter API Key:", type="password")
if st.sidebar.button("➕ Add Key"):
    if new_key.strip():
        if new_key.strip() not in st.session_state["api_keys"]:
            st.session_state["api_keys"].append(new_key.strip())
            save_keys(st.session_state["api_keys"])
            st.sidebar.success("Key Added!")
            st.rerun()

if st.session_state["api_keys"]:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Active Keys")
    for idx, k in enumerate(list(st.session_state["api_keys"])):
        col1, col2 = st.sidebar.columns([3, 1])
        masked_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "API Key"
        col1.write(f"Key {idx+1}: `{masked_key}`")
        if col2.button("❌", key=f"del_{idx}"):
            st.session_state["api_keys"].pop(idx)
            save_keys(st.session_state["api_keys"])
            st.rerun()

# ==========================================
# 🌐 4. دالة الاختبار التشخيصية (Debug Fetcher)
# ==========================================
def test_and_fetch_everflow(api_key, s_date, e_date):
    clean_key = api_key.strip()
    
    # رأس الطلب المعتمد
    headers = {
        "x-eflow-api-key": clean_key,
        "Content-Type": "application/json"
    }

    # الهيكل القياسي لطلبات Everflow Affiliates
    payload = {
        "from": s_date.strftime("%Y-%m-%d"),
        "to": e_date.strftime("%Y-%m-%d"),
        "timezone_id": 54,
        "currency_id": "USD",
        "query": {
            "day_breakdown": False,
            "group_by": ["sub1"],
            "filters": []
        }
    }

    # اختبار أفضل 2 مسارات مخصصة للـ Affiliates
    endpoints = [
        "https://api.eflow.team/v1/affiliates/reporting/custom",
        "https://api.eflow.team/v1/affiliates/reporting/offers"
    ]

    debug_logs = []
    
    for url in endpoints:
        # إذا كان المسار يستعلم عن العروض نغير المجموعات إلى offer
        curr_payload = payload.copy()
        if "offers" in url:
            curr_payload["query"]["group_by"] = ["offer"]

        try:
            res = requests.post(url, headers=headers, json=curr_payload, timeout=10)
            
            # تسجيل الاستجابة للـ Debug
            log_entry = {
                "url": url,
                "status_code": res.status_code,
                "response_text": res.text[:300]
            }
            debug_logs.append(log_entry)

            if res.status_code == 200:
                data = res.json()
                table = data.get("table", [])
                results = []
                for row in table:
                    cols = row.get("columns", [])
                    rep = row.get("reporting", {})
                    
                    label = "General"
                    if cols:
                        label = str(cols[0].get("label", cols[0].get("id", "N/A"))).strip()
                    
                    revenue = float(rep.get("payout", rep.get("revenue", 0.0)))
                    conversions = int(rep.get("conversions", rep.get("total_conversions", 0)))
                    clicks = int(rep.get("clicks", 0))

                    results.append({
                        "Item": label,
                        "Clicks": clicks,
                        "Conversions": conversions,
                        "Revenue ($)": revenue
                    })
                return results, debug_logs
        except Exception as e:
            debug_logs.append({"url": url, "error": str(e)})

    return None, debug_logs

# ==========================================
# 📊 5. الشاشة الرئيسية
# ==========================================
st.title("💵 Live Revenue Tracker")

all_data = []
all_debug_info = []

if not st.session_state["api_keys"]:
    st.info("👈 أضف الـ **API Key** في القائمة الجانبية (Sidebar) للبدء.")
else:
    for idx, key in enumerate(st.session_state["api_keys"]):
        res, logs = test_and_fetch_everflow(key, start_date, end_date)
        all_debug_info.append({"key_index": idx + 1, "logs": logs})
        if res:
            for item in res:
                item["Key"] = f"Account #{idx+1}"
                all_data.append(item)

if all_data:
    df = pd.DataFrame(all_data)
    
    total_rev = df["Revenue ($)"].sum()
    total_conv = df["Conversions"].sum()
    total_clicks = df["Clicks"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🖱️ Total Clicks", f"{total_clicks:,}")

    st.markdown("---")
    st.subheader("📊 Performance Details")
    st.dataframe(
        df[["Key", "Item", "Clicks", "Conversions", "Revenue ($)"]].style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم جلب أي أرباح. تفقد قسم التشخيص (Debugging) أسفله لمعرفة الاستجابة:")
        
        # قسم طباعة أخطاء الاستجابة لمعرفة السبب بدقة
        with st.expander("🔍 Debugging Info (استجابة الـ API الحقيقية)", expanded=True):
            st.json(all_debug_info)
