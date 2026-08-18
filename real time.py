import base64
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
    page_title="Affiliate Real-Time Tracker",
    page_icon="💰",
    layout="wide"
)

# تحديث تلقائي للصفحة كل 30 ثانية (Real-time)
count = st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

CONFIG_FILE = "affiliate_config.json"

# ==========================================
# 🔒 2. نظام تسجيل الدخول (Login System)
# ==========================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    # كلمة السر الافتراضية أو المحددة فـ Streamlit Secrets
    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin12345")

    st.title("🔒 Login to Affiliate Tracker")
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
# 💾 3. إدارة التخزين الدائم (Permanent Cache)
# ==========================================
def load_config():
    """تحميل البيانات المحفوظة فـ الملف المحلي وفي Secrets"""
    config = {
        "sub1_mapping": {
            "101": "Amine",
            "102": "Youssef",
            "103": "Simo"
        },
        "sponsors": []
    }
    
    # 1. القراءة من ملف التخزين المحلي إلا كان كاين
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                config["sub1_mapping"].update(saved_data.get("sub1_mapping", {}))
                config["sponsors"] = saved_data.get("sponsors", [])
        except Exception:
            pass

    # 2. القراءة من Streamlit Secrets (Fallback دائم فـ Cloud)
    if "sub1_mapping" in st.secrets:
        config["sub1_mapping"].update(dict(st.secrets["sub1_mapping"]))
    if "sponsors" in st.secrets:
        config["sponsors"] = list(st.secrets["sponsors"])
        
    return config

def save_config():
    """حفظ التعديلات فـ ملف JSON دائم"""
    data = {
        "sub1_mapping": st.session_state["sub1_mapping"],
        "sponsors": st.session_state["sponsors"]
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# تحميل الإعدادات فـ Session State أول مرة
if "config_loaded" not in st.session_state:
    loaded_cfg = load_config()
    st.session_state["sub1_mapping"] = loaded_cfg["sub1_mapping"]
    st.session_state["sponsors"] = loaded_cfg["sponsors"]
    st.session_state["config_loaded"] = True

# ==========================================
# ⚙️ 4. Sidebar: التحكم والخيارات
# ==========================================
st.sidebar.title("⚙️ Control Panel")

# زر الخروج
if st.sidebar.button("🚪 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- أ) اختيار التاريخ ---
st.sidebar.subheader("📅 Date Range")
col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("From", date.today())
end_date = col_d2.date_input("To", date.today())

st.sidebar.markdown("---")

# --- ب) إضافة وترتيب Sub1 Mapping (ID -> Name) ---
st.sidebar.subheader("👤 Sub1 / Publisher Mapping")
with st.sidebar.expander("➕ Add / Edit Sub1 Mapping"):
    new_sub1_id = st.text_input("Sub1 ID (e.g. 101):")
    new_user_name = st.text_input("Person Name (e.g. Amine):")
    if st.button("Save Sub1 Mapping"):
        if new_sub1_id and new_user_name:
            st.session_state["sub1_mapping"][new_sub1_id.strip()] = new_user_name.strip()
            save_config()  # حفظ دائم
            st.success(f"Saved: Sub1 `{new_sub1_id}` ➡️ **{new_user_name}**")
            st.rerun()
        else:
            st.error("Fill both ID and Name.")

# عرض الـ Mappings الحالية مع إمكانية الحذف
if st.session_state["sub1_mapping"]:
    with st.sidebar.expander("📋 Current Mappings"):
        for sid, sname in list(st.session_state["sub1_mapping"].items()):
            col_m1, col_m2 = st.columns([3, 1])
            col_m1.write(f"**{sid}** : {sname}")
            if col_m2.button("❌", key=f"del_map_{sid}"):
                del st.session_state["sub1_mapping"][sid]
                save_config()
                st.rerun()

st.sidebar.markdown("---")

# --- ج) إضافة الـ Sponsors و API Keys ---
st.sidebar.subheader("🔌 Sponsor API Setup")
with st.sidebar.expander("➕ Add Sponsor API"):
    s_name = st.text_input("Sponsor Name (e.g. Sponsor_A):")
    s_api_key = st.text_input("API Key / Token:", type="password")
    s_endpoint = st.text_input("API Endpoint URL:", placeholder="https://api.sponsor.com/v1/reports")
    
    if st.button("Add Sponsor"):
        if s_name and s_api_key and s_endpoint:
            st.session_state["sponsors"].append({
                "name": s_name.strip(),
                "api_key": s_api_key.strip(),
                "endpoint": s_endpoint.strip()
            })
            save_config()  # حفظ دائم
            st.success(f"Added {s_name}!")
            st.rerun()
        else:
            st.error("Please fill all Sponsor fields.")

# عرض الـ Sponsors المضافة مع إمكانية الحذف
if st.session_state["sponsors"]:
    with st.sidebar.expander("🏢 Active Sponsors"):
        for idx, sp in enumerate(list(st.session_state["sponsors"])):
            col_sp1, col_sp2 = st.columns([3, 1])
            col_sp1.write(f"**{sp['name']}**")
            if col_sp2.button("❌", key=f"del_sp_{idx}"):
                st.session_state["sponsors"].pop(idx)
                save_config()
                st.rerun()

# ==========================================
# 🌐 5. دالة جلب البيانات من الـ APIs
# ==========================================
def fetch_sponsor_data(sponsor, s_date, e_date):
    headers = {
        "Authorization": f"Bearer {sponsor['api_key']}",
        "Accept": "application/json"
    }
    params = {
        "start_date": str(s_date),
        "end_date": str(e_date),
        "group_by": "sub1"
    }
    try:
        response = requests.get(sponsor["endpoint"], headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

# ==========================================
# 📊 6. العرض الرئيسي للبيانات (Real-Time Dashboard)
# ==========================================
st.title("🚀 Real-Time Affiliate Revenue Tracker")

all_reports = []

if not st.session_state["sponsors"]:
    st.info("💡 **Demo Mode:** Add your Sponsors and API Keys in the left sidebar to start tracking live data.")
    dummy_raw = [
        {"sponsor": "Sponsor_Alpha", "sub1": "101", "clicks": 140, "conversions": 12, "revenue": 150.50},
        {"sponsor": "Sponsor_Alpha", "sub1": "102", "clicks": 85, "conversions": 5, "revenue": 62.00},
        {"sponsor": "Sponsor_Beta", "sub1": "101", "clicks": 210, "conversions": 22, "revenue": 310.00},
        {"sponsor": "Sponsor_Beta", "sub1": "103", "clicks": 45, "conversions": 2, "revenue": 25.00},
    ]
    for row in dummy_raw:
        sub_id = str(row["sub1"])
        person_name = st.session_state["sub1_mapping"].get(sub_id, "Unknown / Not Set")
        row["Person Name"] = person_name
        all_reports.append(row)
else:
    for sp in st.session_state["sponsors"]:
        raw_data = fetch_sponsor_data(sp, start_date, end_date)
        if raw_data:
            items = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
            for item in items:
                sub_id = str(item.get("sub1", item.get("sub_id", "N/A")))
                person_name = st.session_state["sub1_mapping"].get(sub_id, "Unknown / Not Set")
                
                all_reports.append({
                    "Sponsor": sp["name"],
                    "Sub1 ID": sub_id,
                    "Person Name": person_name,
                    "Clicks": item.get("clicks", 0),
                    "Conversions": item.get("conversions", 0),
                    "Revenue ($)": float(item.get("revenue", item.get("payout", 0.0)))
                })

if all_reports:
    df = pd.DataFrame(all_reports)

    total_rev = df["Revenue ($)"].sum() if "Revenue ($)" in df.columns else df["revenue"].sum()
    total_conv = df["Conversions"].sum() if "Conversions" in df.columns else df["conversions"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🔄 Auto-Refresh Status", "Active (Every 30s)")

    st.markdown("---")

    st.subheader("👥 Revenue by Person (Grouped)")
    if "Person Name" in df.columns:
        person_df = df.groupby("Person Name")[["Conversions", "Revenue ($)"]].sum().reset_index()
        person_df = person_df.sort_values(by="Revenue ($)", ascending=False)
        st.dataframe(person_df, use_container_width=True)

    st.subheader("📊 Detailed Real-Time Breakdown")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("No data retrieved for the selected date range.")
