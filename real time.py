import json
import os
import hashlib
import requests
import re
import time
import pandas as pd
from datetime import date, timedelta
import streamlit as st

# ==========================================
# 1. إعداد الصفحة (بدون Autorefresh تلقائي)
# ==========================================
st.set_page_config(
    page_title="Live Revenue Tracker",
    page_icon="💰",
    layout="wide"
)

USERS_FILE = "users.json"

# ==========================================
# 🎨 التحكم في المظهر (Dark / Light Theme)
# ==========================================
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

if st.session_state["theme"] == "light":
    st.markdown("""
        <style>
            .stApp, [data-testid="stMainBlockContainer"] { background-color: #ffffff !important; color: #1c1e21 !important; }
            [data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #e9ecef; }
            h1, h2, h3, h4, h5, h6, p, label, .stCaption { color: #1c1e21 !important; }
            div[data-baseweb="input"], div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, input {
                background-color: #ffffff !important; color: #1c1e21 !important; border-color: #ced4da !important;
            }
            .stButton > button { background-color: #ffffff !important; color: #1c1e21 !important; border: 1px solid #ced4da !important; }
            [data-testid="stDataFrame"], [data-testid="stDataFrame"] * { background-color: #ffffff !important; color: #1c1e21 !important; }
            [data-testid="stMetricValue"] { color: #0d6efd !important; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .stApp { background-color: #0e1117 !important; color: #ffffff !important; }
            [data-testid="stSidebar"] { background-color: #161b22 !important; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 💾 2. دالّات إدارة البيانات والملفات
# ==========================================
def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_data_file(username):
    return f"data_{username}.json"

# ==========================================
# 🔐 3. نظام تسجيل الدخول
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

users_db = load_json(USERS_FILE, {})

if not users_db:
    default_admin_pass = "admin"
    users_db["admin"] = hash_password(default_admin_pass)
    save_json(USERS_FILE, users_db)
    save_json(get_user_data_file("admin"), {"api_keys": [], "sub1_names": {}})

if not st.session_state["authenticated"]:
    t_col1, t_col2 = st.columns([8, 2])
    with t_col2:
        if st.session_state["theme"] == "dark":
            if st.button("☀️ Light Mode"):
                st.session_state["theme"] = "light"
                st.rerun()
        else:
            if st.button("🌙 Dark Mode"):
                st.session_state["theme"] = "dark"
                st.rerun()

    st.title("🔐 Authentication Required")
    st.subheader("Login to your dashboard")
    
    login_user = st.text_input("Username", key="l_user").strip().lower()
    login_pass = st.text_input("Password", type="password", key="l_pass")
    
    if st.button("Login", type="primary", key="btn_login"):
        if login_user in users_db and users_db[login_user] == hash_password(login_pass):
            st.session_state["authenticated"] = True
            st.session_state["username"] = login_user
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid Username or Password!")

    st.stop()

# ==========================================
# 📂 4. تحميل بيانات المستخدم الحالي
# ==========================================
current_user = st.session_state["username"]
USER_DATA_FILE = get_user_data_file(current_user)
user_data = load_json(USER_DATA_FILE, {"api_keys": [], "sub1_names": {}})

if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = user_data.get("api_keys", [])

if "sub1_names" not in st.session_state:
    st.session_state["sub1_names"] = user_data.get("sub1_names", {})

# ==========================================
# ⚙️ 5. Sidebar
# ==========================================
st.sidebar.title(f"👤 User: **{current_user.capitalize()}**")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True, key="sb_refresh"):
    st.cache_data.clear()
    st.rerun()

if st.session_state["theme"] == "dark":
    if st.sidebar.button("☀️ Light Mode", use_container_width=True):
        st.session_state["theme"] = "light"
        st.rerun()
else:
    if st.sidebar.button("🌙 Dark Mode", use_container_width=True):
        st.session_state["theme"] = "dark"
        st.rerun()

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.session_state.pop("api_keys", None)
    st.session_state.pop("sub1_names", None)
    st.rerun()

st.sidebar.markdown("---")

# --- تحديد التاريخ ---
st.sidebar.subheader("📅 Date Selection")
date_option = st.sidebar.selectbox(
    "Choose Range:",
    ["Today", "Yesterday", "Last 7 Days", "Custom Range"]
)

today = date.today()

if date_option == "Today":
    start_date = today
    end_date = today
elif date_option == "Yesterday":
    start_date = today - timedelta(days=1)
    end_date = today - timedelta(days=1)
elif date_option == "Last 7 Days":
    start_date = today - timedelta(days=6)
    end_date = today
else:
    start_date = st.sidebar.date_input("From", today)
    end_date = st.sidebar.date_input("To", today)

st.sidebar.markdown("---")

# --- إدارة المفاتيح ---
st.sidebar.subheader("🔑 Add / Manage API Keys")
api_pin_code = st.sidebar.text_input("Enter Passcode to Manage Keys:", type="password", key="api_pin_input")

if api_pin_code == "123":
    st.sidebar.success("Access Granted!")
    acc_name = st.sidebar.text_input("Account Name (e.g. Main Acc):")
    new_key = st.sidebar.text_input("Enter API Key:", type="password")

    if st.sidebar.button("➕ Add Key"):
        if new_key.strip():
            final_name = acc_name.strip() if acc_name.strip() else f"Account #{len(st.session_state['api_keys']) + 1}"
            st.session_state["api_keys"].append({"name": final_name, "key": new_key.strip()})
            save_json(USER_DATA_FILE, {
                "api_keys": st.session_state["api_keys"],
                "sub1_names": st.session_state["sub1_names"]
            })
            st.sidebar.success("Key Added!")
            st.rerun()

    if st.session_state["api_keys"]:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📋 Active Keys")
        for idx, acc in enumerate(list(st.session_state["api_keys"])):
            col1, col2 = st.sidebar.columns([3, 1])
            k = acc.get("key", "")
            masked_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "API Key"
            col1.write(f"**{acc.get('name', 'Account')}**\n`{masked_key}`")
            if col2.button("❌", key=f"del_{idx}"):
                st.session_state["api_keys"].pop(idx)
                save_json(USER_DATA_FILE, {
                    "api_keys": st.session_state["api_keys"],
                    "sub1_names": st.session_state["sub1_names"]
                })
                st.rerun()

elif api_pin_code != "":
    st.sidebar.error("Incorrect Passcode!")
else:
    if st.session_state["api_keys"]:
        st.sidebar.info(f"🔒 {len(st.session_state['api_keys'])} Active Account(s) Loaded.")

# ==========================================
# 🌐 6. دالة جلب البيانات المحسنة ضد 429
# ==========================================
@st.cache_data(ttl=600, show_spinner="Fetching data from Everflow...")
def fetch_everflow_data(api_key, s_date, e_date):
    clean_key = api_key.strip()
    from_str = s_date.strftime("%Y-%m-%d")
    to_str = e_date.strftime("%Y-%m-%d")

    headers = {
        "x-eflow-api-key": clean_key,
        "Content-Type": "application/json"
    }

    url = "https://api.eflow.team/v1/affiliates/reporting/entity/table"

    # Payload خفيف بدون استهلاك زائد لـ BigQuery
    payload = {
        "from": from_str,
        "to": to_str,
        "timezone_id": 54,
        "currency_id": "USD",
        "columns": [
            {"column": "offer"},
            {"column": "sub1"}
        ]
    }

    debug_logs = []
    max_retries = 3

    # محاولات إعادة الاتصال عند ظهور 429 (Retry Mechanism)
    for attempt in range(max_retries):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)

            debug_logs.append({
                "attempt": attempt + 1,
                "status_code": res.status_code,
                "response_text": res.text[:300]
            })

            if res.status_code == 200:
                data = res.json()
                results = []

                table_data = data.get("table", [])
                for row in table_data:
                    cols = row.get("columns", [])
                    rep = row.get("reporting", {})

                    offer_id = ""
                    offer_label = ""
                    sub1_id = ""

                    for c in cols:
                        col_type = c.get("column_type", c.get("id", ""))
                        if col_type == "offer":
                            offer_id = str(c.get("id", ""))
                            offer_label = c.get("label", offer_id)
                        elif col_type == "sub1":
                            sub1_id = str(c.get("id", c.get("label", "")))

                    if not offer_id and len(cols) > 0:
                        offer_id = str(cols[0].get("id", ""))
                        offer_label = cols[0].get("label", offer_id)
                    if not sub1_id and len(cols) > 1:
                        sub1_id = str(cols[1].get("id", cols[1].get("label", "")))

                    custom_sub1_name = st.session_state.get("sub1_names", {}).get(sub1_id, sub1_id)

                    payout = float(rep.get("payout", rep.get("revenue", 0.0)))
                    conversions = int(rep.get("cv", rep.get("conversions", 0)))
                    clicks = int(rep.get("total_click", rep.get("clicks", 0)))

                    results.append({
                        "Account": "",
                        "Offer ID": offer_id,
                        "Offer Name": offer_label,
                        "Sub1 ID": sub1_id,
                        "Sub1 Name": custom_sub1_name,
                        "Clicks": clicks,
                        "Conversions": conversions,
                        "Revenue ($)": payout
                    })

                if results:
                    return results, debug_logs
                break

            elif res.status_code == 429:
                # انتظر ثانيتين أو 4 ثواني قبل إعادة الطلب لتجاوز الـ Rate Limit
                time.sleep(2 * (attempt + 1))
            else:
                break

        except Exception as e:
            debug_logs.append({"attempt": attempt + 1, "error": str(e)})

    return None, debug_logs

# ==========================================
# 📊 7. العرض الرئيسي
# ==========================================
st.title("💵 Live Revenue Tracker")
st.caption(f"👤 Logged in as: **{current_user}** | 📅 Selected Range: **{start_date}** to **{end_date}**")

all_data = []
all_debug_info = []

if not st.session_state["api_keys"]:
    st.info("👈 أدخل Passcode `123` في القائمة الجانبية لإضافة API Keys والحسابات.")
else:
    for idx, acc in enumerate(st.session_state["api_keys"]):
        res, logs = fetch_everflow_data(acc.get("key", ""), start_date, end_date)
        all_debug_info.append({"account_name": acc.get("name"), "logs": logs})
        if res:
            for item in res:
                item["Account"] = acc.get("name", f"Account #{idx+1}")
                sub1_id = item["Sub1 ID"]
                item["Sub1 Name"] = st.session_state["sub1_names"].get(sub1_id, item["Sub1 Name"])
                all_data.append(item)

if all_data:
    df = pd.DataFrame(all_data)

    st.markdown("---")
    st.subheader("🔍 Filter Data")
    
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        filter_type = st.selectbox("Filter By:", ["All", "Offer Name / ID", "Sub1 ID", "Sub1 Name"])

    filtered_df = df.copy()

    with f_col2:
        if filter_type == "Offer Name / ID":
            unique_offers = sorted(df["Offer Name"].unique())
            selected_offer = st.multiselect("Select Offers:", options=unique_offers, default=unique_offers)
            if selected_offer:
                filtered_df = filtered_df[filtered_df["Offer Name"].isin(selected_offer)]
        elif filter_type == "Sub1 ID":
            unique_sub1_ids = sorted(df["Sub1 ID"].unique())
            selected_sub1_ids = st.multiselect("Select Sub1 IDs:", options=unique_sub1_ids, default=unique_sub1_ids)
            if selected_sub1_ids:
                filtered_df = filtered_df[filtered_df["Sub1 ID"].isin(selected_sub1_ids)]
        elif filter_type == "Sub1 Name":
            unique_sub1_names = sorted(df["Sub1 Name"].unique())
            selected_sub1_names = st.multiselect("Select Sub1 Names:", options=unique_sub1_names, default=unique_sub1_names)
            if selected_sub1_names:
                filtered_df = filtered_df[filtered_df["Sub1 Name"].isin(selected_sub1_names)]

    total_rev = filtered_df["Revenue ($)"].sum()
    total_conv = filtered_df["Conversions"].sum()
    total_clicks = filtered_df["Clicks"].sum()

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🖱️ Total Clicks", f"{total_clicks:,}")

    st.markdown("---")
    
    perf_col1, perf_col2 = st.columns([8, 2])
    with perf_col1:
        search_term = st.text_input("🔍 Quick Search:", placeholder="Search offer name, sub1, account...", label_visibility="collapsed").strip()
    with perf_col2:
        if st.button("🔄 Refresh Data", type="primary", key="perf_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if search_term:
        try:
            safe_term = re.escape(search_term)
            search_mask = filtered_df.astype(str).apply(lambda row: row.str.contains(safe_term, case=False, na=False)).any(axis=1)
            filtered_df = filtered_df[search_mask]
        except Exception:
            pass

    all_columns = ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name", "Clicks", "Conversions", "Revenue ($)"]
    selected_columns = st.multiselect("👁️ Select Columns to Display:", options=all_columns, default=all_columns)

    if selected_columns:
        group_keys = [col for col in selected_columns if col in ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name"]]
        num_metrics = [col for col in selected_columns if col in ["Clicks", "Conversions", "Revenue ($)"]]

        if group_keys and num_metrics:
            display_df = filtered_df.groupby(group_keys, as_index=False)[num_metrics].sum()
            display_df = display_df[selected_columns]
        else:
            display_df = filtered_df[selected_columns]

        format_dict = {"Revenue ($)": "${:,.2f}"} if "Revenue ($)" in selected_columns else {}
        st.dataframe(display_df.style.format(format_dict), use_container_width=True)
    else:
        st.warning("اختر عموداً واحداً على الأقل للعرض.")
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أرباح للفترة المحددة أو هناك تعارض مع Limit. تفقد التشخيص:")
        with st.expander("🔍 Debugging Info", expanded=True):
            st.json(all_debug_info)
