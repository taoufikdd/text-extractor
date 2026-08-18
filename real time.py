import json
import os
import requests
import pandas as pd
from datetime import date
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. إعدادات الصفحة والـ Auto-Refresh
# ==========================================
st.set_page_config(
    page_title="Affiliate Revenue Tracker",
    page_icon="💰",
    layout="wide"
)

# تحديث تلقائي كل 30 ثانية
st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

CONFIG_FILE = "affiliate_config.json"

# ==========================================
# 💾 2. إدارة التخزين
# ==========================================
def load_config():
    config = {"sub1_mapping": {}, "sponsors": []}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                config["sub1_mapping"].update(saved_data.get("sub1_mapping", {}))
                config["sponsors"] = saved_data.get("sponsors", [])
        except Exception:
            pass
    return config

def save_config():
    data = {
        "sub1_mapping": st.session_state["sub1_mapping"],
        "sponsors": st.session_state["sponsors"]
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

if "config_loaded" not in st.session_state:
    loaded_cfg = load_config()
    st.session_state["sub1_mapping"] = loaded_cfg["sub1_mapping"]
    st.session_state["sponsors"] = loaded_cfg["sponsors"]
    st.session_state["config_loaded"] = True

# ==========================================
# ⚙️ 3. Sidebar: الإعدادات والمدخلات
# ==========================================
st.sidebar.title("⚙️ Control Panel")

st.sidebar.subheader("📅 Date Range")
col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("From", date.today())
end_date = col_d2.date_input("To", date.today())

st.sidebar.markdown("---")

st.sidebar.subheader("👤 Sub1 / Person Mapping")
with st.sidebar.expander("➕ Add / Edit Sub1 Mapping"):
    new_sub1_id = st.text_input("Sub1 ID (e.g. 31):")
    new_user_name = st.text_input("Person Name (e.g. kaoutar):")
    if st.button("Save Mapping"):
        if new_sub1_id and new_user_name:
            st.session_state["sub1_mapping"][new_sub1_id.strip()] = new_user_name.strip()
            save_config()
            st.success("Saved!")
            st.rerun()

if st.session_state["sub1_mapping"]:
    with st.sidebar.expander("📋 Current Mappings"):
        for sid, sname in list(st.session_state["sub1_mapping"].items()):
            col_m1, col_m2 = st.sidebar.columns([3, 1])
            col_m1.write(f"**{sid}** : {sname}")
            if col_m2.button("❌", key=f"del_map_{sid}"):
                del st.session_state["sub1_mapping"][sid]
                save_config()
                st.rerun()

st.sidebar.markdown("---")

st.sidebar.subheader("🔌 Sponsor API Setup")
with st.sidebar.expander("➕ Add Sponsor API"):
    s_name = st.text_input("Sponsor Name:")
    s_api_key = st.text_input("API Key:", type="password")
    s_domain = st.text_input("Domain (Default: api.eflow.team):", value="api.eflow.team")
    
    if st.button("Add Sponsor"):
        if s_name and s_api_key:
            st.session_state["sponsors"].append({
                "name": s_name.strip(),
                "api_key": s_api_key.strip(),
                "domain": s_domain.strip()
            })
            save_config()
            st.success("Sponsor Added!")
            st.rerun()

if st.session_state["sponsors"]:
    with st.sidebar.expander("🏢 Active Sponsors"):
        for idx, sp in enumerate(list(st.session_state["sponsors"])):
            col_sp1, col_sp2 = st.sidebar.columns([3, 1])
            col_sp1.write(f"**{sp['name']}**")
            if col_sp2.button("❌", key=f"del_sp_{idx}"):
                st.session_state["sponsors"].pop(idx)
                save_config()
                st.rerun()

# ==========================================
# 🌐 4. دالة جلب الأرباح (Direct API Fetcher)
# ==========================================
def fetch_revenue(sponsor, s_date, e_date):
    api_key = sponsor.get("api_key", "").strip()
    domain = sponsor.get("domain", "api.eflow.team").strip()
    
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    if "everflow.io" in domain:
        domain = domain.replace("everflow.io", "eflow.team")

    headers = {
        "x-eflow-api-key": api_key,
        "Content-Type": "application/json"
    }

    # تجريب مسار الـ Summary ومسار الـ Sub1
    endpoints = [
        f"https://{domain}/v1/networks/reporting/sub1",
        f"https://{domain}/v1/affiliates/reporting/sub1",
        f"https://{domain}/v1/networks/reporting/custom",
        f"https://{domain}/v1/affiliates/reporting/custom"
    ]

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
                    
                    sub1_id = "N/A"
                    if cols:
                        sub1_id = str(cols[0].get("id", cols[0].get("label", "N/A"))).strip()
                    
                    # قراءة الأرباح سواء من payout أو revenue
                    payout = float(rep.get("payout", rep.get("revenue", 0.0)))
                    conversions = int(rep.get("conversions", rep.get("total_conversions", 0)))
                    
                    results.append({
                        "sub1": sub1_id,
                        "conversions": conversions,
                        "revenue": payout
                    })
                return results
        except Exception:
            continue
    return None

# ==========================================
# 📊 5. الشاشة الرئيسية (عرض الربح فقط)
# ==========================================
st.title("💰 Real-Time Revenue Dashboard")

records = []

if st.session_state["sponsors"]:
    for sp in st.session_state["sponsors"]:
        res = fetch_revenue(sp, start_date, end_date)
        if res:
            for item in res:
                s_id = item["sub1"]
                name = st.session_state["sub1_mapping"].get(s_id, "Unknown / Not Set")
                records.append({
                    "Sponsor": sp["name"],
                    "Sub1 ID": s_id,
                    "Person": name,
                    "Conversions": item["conversions"],
                    "Revenue ($)": item["revenue"]
                })

if records:
    df = pd.DataFrame(records)
    
    # 1. البطاقة الرئيسية لمجموع الأرباح
    total_rev = df["Revenue ($)"].sum()
    total_conv = df["Conversions"].sum()
    
    c1, c2 = st.columns(2)
    c1.metric("💵 Total Revenue", f"${total_rev:,.2f}")
    c2.metric("🎯 Total Conversions", f"{total_conv:,}")

    st.markdown("---")

    # 2. جدول الأرباح صافي حسب الأشخاص
    st.subheader("👤 Revenue by Person")
    person_df = df.groupby("Person")[["Conversions", "Revenue ($)"]].sum().reset_index()
    person_df = person_df.sort_values(by="Revenue ($)", ascending=False)
    
    st.dataframe(
        person_df.style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )

    # 3. التفاصيل الكاملة
    st.subheader("📋 Breakdown Detail")
    st.dataframe(
        df.style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )
else:
    st.info("No revenue data found for selected date range.")
