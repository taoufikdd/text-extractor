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
# 🌐 4. دالة جلب البيانات المباشرة
# ==========================================
def get_affiliate_revenue(api_key, s_date, e_date):
    headers = {
        "x-eflow-api-key": api_key.strip(),
        "Content-Type": "application/json"
    }

    # Payload متوافق مع Everflow Affiliate API
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

    # قائمة روابط Everflow المخصصة للـ Affiliates
    endpoints = [
        "https://api.eflow.team/v1/affiliates/reporting/custom",
        "https://api.eflow.team/v1/affiliates/reporting/entity",
        "https://api.eflow.team/v1/affiliates/reporting/offers",
        "https://api.eflow.team/v1/networks/reporting/custom"
    ]

    for url in endpoints:
        try:
            # إذا كان الرابط الخاص بالـ Offers نغير الـ group_by إلى offer
            current_payload = payload.copy()
            if "offers" in url:
                current_payload["query"]["group_by"] = ["offer"]

            res = requests.post(url, headers=headers, json=current_payload, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                table = data.get("table", [])
                results = []
                
                for row in table:
                    cols = row.get("columns", [])
                    rep = row.get("reporting", {})
                    
                    label_val = "All / Direct"
                    if cols:
                        label_val = str(cols[0].get("label", cols[0].get("id", "N/A"))).strip()
                    
                    revenue = float(rep.get("payout", rep.get("revenue", 0.0)))
                    conversions = int(rep.get("conversions", rep.get("total_conversions", 0)))
                    clicks = int(rep.get("clicks", 0))

                    if revenue > 0 or conversions > 0 or clicks > 0:
                        results.append({
                            "Label / Sub1": label_val,
                            "Clicks": clicks,
                            "Conversions": conversions,
                            "Revenue ($)": revenue
                        })
                
                if results:
                    return results

        except Exception:
            continue

    # محاولة أخير عبر GET Summary API إذا فشل الـ POST
    try:
        summary_url = f"https://api.eflow.team/v1/affiliates/reporting/summary?from={s_date.strftime('%Y-%m-%d')}&to={e_date.strftime('%Y-%m-%d')}"
        res = requests.get(summary_url, headers=headers, timeout=10)
        if res.status_code == 200:
            rep = res.json().get("reporting", {})
            revenue = float(rep.get("payout", rep.get("revenue", 0.0)))
            conversions = int(rep.get("conversions", 0))
            clicks = int(rep.get("clicks", 0))
            if revenue > 0 or conversions > 0 or clicks > 0:
                return [{
                    "Label / Sub1": "Total Summary",
                    "Clicks": clicks,
                    "Conversions": conversions,
                    "Revenue ($)": revenue
                }]
    except Exception:
        pass

    return None

# ==========================================
# 📊 5. العرض
# ==========================================
st.title("💵 Live Revenue Tracker")

all_data = []

if not st.session_state["api_keys"]:
    st.info("👈 أضف الـ **API Key** في القائمة الجانبية (Sidebar) للبدء.")
else:
    for idx, key in enumerate(st.session_state["api_keys"]):
        res = get_affiliate_revenue(key, start_date, end_date)
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
    st.subheader("📊 Breakdown Detail")
    st.dataframe(
        df[["Key ID", "Label / Sub1", "Clicks", "Conversions", "Revenue ($)"]].style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أي أرباح في هذا التاريخ أو الـ API Key غير صحيح.")
