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

st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

CONFIG_FILE = "affiliate_config.json"

# ==========================================
# 🔒 2. نظام الدخول متعدد الرتب (Admin / User)
# ==========================================
def check_login():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["role"] = None

    if st.session_state["authenticated"]:
        return True

    # كلمات السر (يمكن تغييرها هنا أو عبر Streamlit Secrets)
    ADMIN_PASS = st.secrets.get("ADMIN_PASSWORD", "admin12345")
    USER_PASS = st.secrets.get("USER_PASSWORD", "user12345")

    st.title("🔒 Login to Affiliate Tracker")
    user_pass = st.text_input("Enter Access Password:", type="password")
    
    if st.button("Login", type="primary"):
        if user_pass == ADMIN_PASS:
            st.session_state["authenticated"] = True
            st.session_state["role"] = "admin"
            st.success("✅ Logged in as ADMIN")
            st.rerun()
        elif user_pass == USER_PASS:
            st.session_state["authenticated"] = True
            st.session_state["role"] = "user"
            st.success("✅ Logged in as USER")
            st.rerun()
        else:
            st.error("❌ Invalid password!")
    return False

if not check_login():
    st.stop()

# ==========================================
# 💾 3. إدارة التخزين الدائم (Permanent Cache)
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

    if "sub1_mapping" in st.secrets:
        config["sub1_mapping"].update(dict(st.secrets["sub1_mapping"]))
    if "sponsors" in st.secrets:
        config["sponsors"] = list(st.secrets["sponsors"])
        
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
# ⚙️ 4. Sidebar: التحكم والخيارات حسب الرتبة
# ==========================================
user_role = st.session_state.get("role", "user")
st.sidebar.title("⚙️ Control Panel")
st.sidebar.info(f"👤 Logged in as: **{user_role.upper()}**")

if st.sidebar.button("🚪 Logout"):
    st.session_state["authenticated"] = False
    st.session_state["role"] = None
    st.rerun()

st.sidebar.markdown("---")

# --- أ) اختيار التاريخ (متاح للجميع) ---
st.sidebar.subheader("📅 Date Range")
col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("From", date.today())
end_date = col_d2.date_input("To", date.today())

st.sidebar.markdown("---")

# --- ب) خصائص الأدمن فقط (إضافة وتعديل) ---
if user_role == "admin":
    st.sidebar.subheader("👤 Sub1 / Publisher Mapping")
    with st.sidebar.expander("➕ Add / Edit Sub1 Mapping"):
        new_sub1_id = st.text_input("Sub1 ID (e.g. 101):")
        new_user_name = st.text_input("Person Name (e.g. Amine):")
        if st.button("Save Sub1 Mapping"):
            if new_sub1_id and new_user_name:
                st.session_state["sub1_mapping"][new_sub1_id.strip()] = new_user_name.strip()
                save_config()
                st.success(f"Saved: Sub1 `{new_sub1_id}` ➡️ **{new_user_name}**")
                st.rerun()
            else:
                st.error("Fill both ID and Name.")

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
                save_config()
                st.success(f"Added {s_name}!")
                st.rerun()
            else:
                st.error("Please fill all Sponsor fields.")

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
# 📊 6. العرض الرئيسي للبيانات (Dashboard)
# ==========================================
st.title("🚀 Real-Time Affiliate Revenue Tracker")

all_reports = []

if not st.session_state["sponsors"]:
    st.info("💡 **No active sponsors found.** Admin needs to configure APIs in the sidebar.")
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

    rev_col = "Revenue ($)" if "Revenue ($)" in df.columns else "revenue"
    conv_col = "Conversions" if "Conversions" in df.columns else "conversions"

    total_rev = df[rev_col].sum() if rev_col in df.columns else 0.0
    total_conv = df[conv_col].sum() if conv_col in df.columns else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🔄 Real-Time Status", "Active (Every 30s)")

    st.markdown("---")

    # --- جدول الأرباح مقسم حسب الشخص (آمن ضد KeyError) ---
    st.subheader("👥 Revenue by Person (Grouped)")
    cols_to_sum = [c for c in ["Conversions", "Revenue ($)", "conversions", "revenue"] if c in df.columns]
    
    if "Person Name" in df.columns and cols_to_sum:
        person_df = df.groupby("Person Name")[cols_to_sum].sum().reset_index()
        rename_dict = {"conversions": "Conversions", "revenue": "Revenue ($)"}
        person_df = person_df.rename(columns=rename_dict)
        
        sort_col = "Revenue ($)" if "Revenue ($)" in person_df.columns else cols_to_sum[0]
        person_df = person_df.sort_values(by=sort_col, ascending=False)
        st.dataframe(person_df, use_container_width=True)

    st.subheader("📊 Detailed Real-Time Breakdown")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("No data retrieved for the selected date range.")
