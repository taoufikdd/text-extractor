import json
import os
import requests
import pandas as pd
from datetime import date
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. إعداد الصفحة والتحديث التلقائي (كل 30 ثانية)
# ==========================================
st.set_page_config(
    page_title="Simple Revenue Tracker",
    page_icon="💰",
    layout="wide"
)

# تحديث تلقائي كل 30 ثانية
st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

CONFIG_FILE = "api_keys.json"

# ==========================================
# 💾 2. حفظ وقراءة الـ API Keys
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
# ⚙️ 3. Sidebar: إدخال الـ API Key فقط
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
        # إخفاء جزء من الـ Key للأمان
        masked_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "API Key"
        col1.write(f"Key {idx+1}: `{masked_key}`")
        if col2.button("❌", key=f"del_{idx}"):
            st.session_state["api_keys"].pop(idx)
            save_keys(st.session_state["api_keys"])
            st.rerun()

# ==========================================
# 🌐 4. دالة جلب الـ Revenue بالـ API Key فقط
# ==========================================
def get_revenue_by_key(api_key, s_date, e_date):
    headers = {
        "x-eflow-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "from": s_date.strftime("%Y-%m-%d"),
        "to": e_date.strftime("%Y-%m-%d"),
        "timezone_id": 80,
        "currency_id": "USD",
        "query": {
            "day_breakdown": False,
            "group_by": ["sub1"],
            "filters": []
        }
    }

    # المسارات المحتملة لـ Everflow
    endpoints = [
        "https://api.eflow.team/v1/networks/reporting/sub1",
        "https://api.eflow.team/v1/affiliates/reporting/sub1",
        "https://api.eflow.team/v1/networks/reporting/custom",
        "https://api.eflow.team/v1/affiliates/reporting/custom",
        "https://api.eflow.team/v1/networks/reporting/entity",
        "https://api.eflow.team/v1/affiliates/reporting/entity"
    ]

    for url in endpoints:
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                table = data.get("table", [])
                results = []
                for row in table:
                    cols = row.get("columns", [])
                    rep = row.get("reporting", {})
                    
                    sub1 = "N/A"
                    if cols:
                        sub1 = str(cols[0].get("id", cols[0].get("label", "N/A"))).strip()
                    
                    revenue = float(rep.get("payout", rep.get("revenue", 0.0)))
                    conversions = int(rep.get("conversions", rep.get("total_conversions", 0)))
                    clicks = int(rep.get("clicks", 0))

                    results.append({
                        "Sub1": sub1,
                        "Clicks": clicks,
                        "Conversions": conversions,
                        "Revenue ($)": revenue
                    })
                return results
        except Exception:
            continue
    return None

# ==========================================
# 📊 5. الشاشة الرئيسية (عرض الأرباح)
# ==========================================
st.title("💵 Live Revenue Tracker")

all_data = []

if not st.session_state["api_keys"]:
    st.info("👈 أضف الـ **API Key** في القائمة الجانبية (Sidebar) للبدء.")
else:
    for idx, key in enumerate(st.session_state["api_keys"]):
        res = get_revenue_by_key(key, start_date, end_date)
        if res:
            for item in res:
                item["Key ID"] = f"Key #{idx+1}"
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
    st.subheader("📊 Breakdown by Sub1 / Revenue")
    st.dataframe(
        df[["Key ID", "Sub1", "Clicks", "Conversions", "Revenue ($)"]].style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أي أرباح في هذا التاريخ أو الـ API Key غير صحيح.")
