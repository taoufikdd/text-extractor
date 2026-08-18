import json
import os
import hashlib
import requests
import pandas as pd
from datetime import date, timedelta
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

USERS_FILE = "users.json"

# ==========================================
# 🎨 التحكم في المظهر (Dark / Light Theme)
# ==========================================
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

if st.session_state["theme"] == "light":
    st.markdown("""
        <style>
            /* خلفية الصفحة والـ Sidebar */
            .stApp, [data-testid="stMainBlockContainer"] {
                background-color: #ffffff !important;
                color: #1c1e21 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #f8f9fa !important;
                border-right: 1px solid #e9ecef;
            }
            
            /* النصوص الرئيسية */
            h1, h2, h3, h4, h5, h6, p, label, .stCaption {
                color: #1c1e21 !important;
            }

            /* إصلاح الخانات والـ SelectBox */
            div[data-baseweb="input"], 
            div[data-baseweb="input"] > div,
            div[data-baseweb="select"] > div,
            input {
                background-color: #ffffff !important;
                color: #1c1e21 !important;
                border-color: #ced4da !important;
            }
            
            div[data-baseweb="input"]:focus-within {
                border-color: #0d6efd !important;
            }

            /* إصلاح الأزرار (Logout / Light Mode / Buttons) */
            .stButton > button {
                background-color: #ffffff !important;
                color: #1c1e21 !important;
                border: 1px solid #ced4da !important;
                box-shadow: none !important;
            }
            .stButton > button:hover {
                background-color: #f8f9fa !important;
                border-color: #adb5bd !important;
                color: #000000 !important;
            }

            /* إصلاح الـ Multiselect Tags */
            span[data-baseweb="tag"] {
                background-color: #e9ecef !important;
                color: #1c1e21 !important;
            }

            /* إصلاح الجدول بالكامل (DataFrame / Table) */
            [data-testid="stDataFrame"], 
            [data-testid="stDataFrame"] > div, 
            [data-testid="stDataFrame"] canvas,
            [data-testid="stDataFrame"] iframe {
                background-color: #ffffff !important;
            }

            /* فرض اللون الأبيض لنصوص الجدول وعناصره */
            [data-testid="stDataFrame"] * {
                color: #1c1e21 !important;
            }
            
            /* Metric Cards */
            [data-testid="stMetricValue"] {
                color: #0d6efd !important;
            }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .stApp {
                background-color: #0e1117 !important;
                color: #ffffff !important;
            }
            [data-testid="stSidebar"] {
                background-color: #161b22 !important;
            }
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
# 🔐 3. نظام تسجيل الدخول مع Admin تلقائي
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
    
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Create Account"])

    with tab1:
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

    with tab2:
        st.subheader("Create a new account")
        new_user = st.text_input("Choose Username", key="reg_user").strip().lower()
        new_pass = st.text_input("Choose Password", type="password", key="reg_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="reg_confirm")

        if st.button("Register", key="btn_reg"):
            if not new_user or not new_pass or not confirm_pass:
                st.warning("Please fill in all fields.")
            elif new_user in users_db:
                st.error("Username already exists! Choose another one.")
            elif new_pass != confirm_pass:
                st.error("Passwords do not match!")
            else:
                users_db[new_user] = hash_password(new_pass)
                save_json(USERS_FILE, users_db)

                user_file = get_user_data_file(new_user)
                save_json(user_file, {"api_keys": [], "sub1_names": {}})

                st.success("Account created successfully! Go to Login tab.")

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
# ⚙️ 5. Sidebar (الإعدادات والتحكم)
# ==========================================
st.sidebar.title(f"👤 User: **{current_user.capitalize()}**")

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

# --- إدارة المفاتيح محمية بالكود 123 ---
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

# --- قسم تخصيص أسماء Sub1 محمي بالكود 123 ---
if st.session_state["api_keys"]:
    st.sidebar.markdown("---")
    with st.sidebar.expander("👤 Sub1 Custom Names", expanded=False):
        sub1_pin_code = st.text_input("Enter Passcode to Edit:", type="password", key="sub1_pin_input")
        
        if sub1_pin_code == "123":
            st.success("Access Granted!")
            if st.session_state["sub1_names"]:
                for sid in sorted(st.session_state["sub1_names"].keys()):
                    cur_s = st.session_state["sub1_names"].get(sid, "")
                    new_s = st.text_input(f"Sub1 [{sid}]:", value=cur_s, key=f"s_{sid}")
                    if new_s != cur_s:
                        st.session_state["sub1_names"][sid] = new_s
                        save_json(USER_DATA_FILE, {
                            "api_keys": st.session_state["api_keys"],
                            "sub1_names": st.session_state["sub1_names"]
                        })
            else:
                st.info("No Sub1 IDs fetched yet.")
        elif sub1_pin_code != "":
            st.error("Incorrect Passcode!")

# ==========================================
# 🌐 6. دالة جلب البيانات (Everflow API)
# ==========================================
def fetch_everflow_data(api_key, s_date, e_date):
    clean_key = api_key.strip()
    from_str = s_date.strftime("%Y-%m-%d")
    to_str = e_date.strftime("%Y-%m-%d")

    headers = {
        "x-eflow-api-key": clean_key,
        "Content-Type": "application/json"
    }

    url = "https://api.eflow.team/v1/affiliates/reporting/entity/table"

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

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)

        debug_logs.append({
            "method": "POST",
            "url": url,
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

                if sub1_id and sub1_id not in st.session_state["sub1_names"]:
                    st.session_state["sub1_names"][sub1_id] = sub1_id
                    save_json(USER_DATA_FILE, {
                        "api_keys": st.session_state["api_keys"],
                        "sub1_names": st.session_state["sub1_names"]
                    })

                custom_sub1_name = st.session_state["sub1_names"].get(sub1_id, sub1_id)

                payout = float(rep.get("payout", rep.get("revenue", 0.0)))
                conversions = int(rep.get("cv", rep.get("conversions", 0)))
                clicks = int(rep.get("total_click", rep.get("clicks", 0)))

                results.append({
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

    except Exception as e:
        debug_logs.append({"url": url, "error": str(e)})

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

    all_columns = ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name", "Clicks", "Conversions", "Revenue ($)"]
    selected_columns = st.multiselect(
        "👁️ Select Columns to Display:",
        options=all_columns,
        default=all_columns
    )

    if selected_columns:
        group_keys = [col for col in selected_columns if col in ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name"]]
        num_metrics = [col for col in selected_columns if col in ["Clicks", "Conversions", "Revenue ($)"]]

        if group_keys and num_metrics:
            display_df = df.groupby(group_keys, as_index=False)[num_metrics].sum()
            display_df = display_df[selected_columns]
        else:
            display_df = df[selected_columns]

        # استعمال st.dataframe المباشر مع استهداف الـ CSS لفرض اللون الأبيض
        format_dict = {"Revenue ($)": "${:,.2f}"} if "Revenue ($)" in selected_columns else {}
        st.dataframe(
            display_df.style.format(format_dict),
            use_container_width=True
        )
    else:
        st.warning("اختر عموداً واحداً على الأقل للعرض.")
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أرباح للفترة المحددة. تفقد قسم التشخيص:")
        with st.expander("🔍 Debugging Info", expanded=True):
            st.json(all_debug_info)
