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
            .stApp, [data-testid="stMainBlockContainer"] {
                background-color: #ffffff !important;
                color: #1c1e21 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #f8f9fa !important;
                border-right: 1px solid #e9ecef;
            }
            h1, h2, h3, h4, h5, h6, p, label, .stCaption {
                color: #1c1e21 !important;
            }
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
            span[data-baseweb="tag"] {
                background-color: #e9ecef !important;
                color: #1c1e21 !important;
            }
            [data-testid="stDataFrame"], 
            [data-testid="stDataFrame"] > div, 
            [data-testid="stDataFrame"] canvas,
            [data-testid="stDataFrame"] iframe {
                background-color: #ffffff !important;
            }
            [data-testid="stDataFrame"] * {
                color: #1c1e21 !important;
            }
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
    save_json(get_user_data_file("admin"), {"api_keys": [], "sub1_names": {}, "account_groups": {}})

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

user_data = load_json(USER_DATA_FILE, {"api_keys": [], "sub1_names": {}, "account_groups": {}})

if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = user_data.get("api_keys", [])

if "sub1_names" not in st.session_state:
    st.session_state["sub1_names"] = user_data.get("sub1_names", {})

if "account_groups" not in st.session_state:
    st.session_state["account_groups"] = user_data.get("account_groups", {})

# ==========================================
# ⚙️ 5. Sidebar (الإعدادات والتحكم)
# ==========================================
st.sidebar.title(f"👤 User: **{current_user.capitalize()}**")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True, key="sb_refresh"):
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
    st.session_state.pop("account_groups", None)
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

# --- إدارة المفاتيح والمجموعات محمية بالكود 123 ---
st.sidebar.subheader("🔑 Add / Manage API Keys & Groups")
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
                "sub1_names": st.session_state["sub1_names"],
                "account_groups": st.session_state["account_groups"]
            })
            st.sidebar.success("Key Added!")
            st.rerun()

    if st.session_state["api_keys"]:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📁 Account Groups")
        
        all_account_names = [acc.get("name") for acc in st.session_state["api_keys"]]
        
        group_name = st.sidebar.text_input("Group Name (e.g. Group 1):")
        selected_accs_for_group = st.sidebar.multiselect("Select Accounts for Group:", options=all_account_names)
        
        if st.sidebar.button("💾 Save / Update Group"):
            if group_name.strip() and selected_accs_for_group:
                st.session_state["account_groups"][group_name.strip()] = selected_accs_for_group
                save_json(USER_DATA_FILE, {
                    "api_keys": st.session_state["api_keys"],
                    "sub1_names": st.session_state["sub1_names"],
                    "account_groups": st.session_state["account_groups"]
                })
                st.sidebar.success(f"Group '{group_name}' Saved!")
                st.rerun()

        if st.session_state["account_groups"]:
            for g_name, g_accs in list(st.session_state["account_groups"].items()):
                g_col1, g_col2 = st.sidebar.columns([3, 1])
                g_col1.write(f"📂 **{g_name}** ({len(g_accs)} accs)")
                if g_col2.button("❌", key=f"del_g_{g_name}"):
                    st.session_state["account_groups"].pop(g_name)
                    save_json(USER_DATA_FILE, {
                        "api_keys": st.session_state["api_keys"],
                        "sub1_names": st.session_state["sub1_names"],
                        "account_groups": st.session_state["account_groups"]
                    })
                    st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.subheader("📋 Active Keys")
        for idx, acc in enumerate(list(st.session_state["api_keys"])):
            col1, col2 = st.sidebar.columns([3, 1])
            k = acc.get("key", "")
            masked_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "API Key"
            col1.write(f"**{acc.get('name', 'Account')}**\n`{masked_key}`")
            if col2.button("❌", key=f"del_{idx}"):
                removed_acc = st.session_state["api_keys"].pop(idx)
                # Remove from groups if exists
                for g_name, g_accs in st.session_state["account_groups"].items():
                    if removed_acc.get("name") in g_accs:
                        g_accs.remove(removed_acc.get("name"))
                
                save_json(USER_DATA_FILE, {
                    "api_keys": st.session_state["api_keys"],
                    "sub1_names": st.session_state["sub1_names"],
                    "account_groups": st.session_state["account_groups"]
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
                            "sub1_names": st.session_state["sub1_names"],
                            "account_groups": st.session_state["account_groups"]
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
                        "sub1_names": st.session_state["sub1_names"],
                        "account_groups": st.session_state["account_groups"]
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

    # ==========================================
    # 🔍 خيارات الفلترة والمجموعات (Filter Options & Group Selector)
    # ==========================================
    st.markdown("---")
    st.subheader("🔍 Filter Data & Select Group")
    
    group_col, f_col1, f_col2 = st.columns([3, 3, 3])
    
    # اختيار المجموعة
    with group_col:
        group_options = ["All Accounts"] + list(st.session_state["account_groups"].keys())
        selected_group = st.selectbox("📂 Select Group:", options=group_options)

    # تطبيق فلتر المجموعة أولاً
    filtered_df = df.copy()
    if selected_group != "All Accounts":
        allowed_accounts = st.session_state["account_groups"].get(selected_group, [])
        filtered_df = filtered_df[filtered_df["Account"].isin(allowed_accounts)]
    
    with f_col1:
        filter_type = st.selectbox(
            "Filter By:",
            ["All", "Offer Name / ID", "Sub1 ID", "Sub1 Name"]
        )

    with f_col2:
        if filter_type == "Offer Name / ID":
            unique_offers = sorted(filtered_df["Offer Name"].unique())
            selected_offer = st.multiselect("Select Offers:", options=unique_offers, default=unique_offers)
            if selected_offer:
                filtered_df = filtered_df[filtered_df["Offer Name"].isin(selected_offer)]
        
        elif filter_type == "Sub1 ID":
            unique_sub1_ids = sorted(filtered_df["Sub1 ID"].unique())
            selected_sub1_ids = st.multiselect("Select Sub1 IDs:", options=unique_sub1_ids, default=unique_sub1_ids)
            if selected_sub1_ids:
                filtered_df = filtered_df[filtered_df["Sub1 ID"].isin(selected_sub1_ids)]
                
        elif filter_type == "Sub1 Name":
            unique_sub1_names = sorted(filtered_df["Sub1 Name"].unique())
            selected_sub1_names = st.multiselect("Select Sub1 Names:", options=unique_sub1_names, default=unique_sub1_names)
            if selected_sub1_names:
                filtered_df = filtered_df[filtered_df["Sub1 Name"].isin(selected_sub1_names)]

    # حساب المجاميع بناءً على البيانات المفلترة فقط
    total_rev = filtered_df["Revenue ($)"].sum() if not filtered_df.empty else 0.0
    total_conv = filtered_df["Conversions"].sum() if not filtered_df.empty else 0
    total_clicks = filtered_df["Clicks"].sum() if not filtered_df.empty else 0

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🖱️ Total Clicks", f"{total_clicks:,}")

    st.markdown("---")
    
    # زر Refresh Data
    perf_col1, perf_col2 = st.columns([8, 2])
    with perf_col1:
        st.subheader("📊 Performance Details")
    with perf_col2:
        if st.button("🔄 Refresh Data", type="primary", key="perf_refresh", use_container_width=True):
            st.rerun()

    all_columns = ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name", "Clicks", "Conversions", "Revenue ($)"]
    selected_columns = st.multiselect(
        "👁️ Select Columns to Display:",
        options=all_columns,
        default=all_columns
    )

    if selected_columns:
        if not filtered_df.empty:
            group_keys = [col for col in selected_columns if col in ["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name"]]
            num_metrics = [col for col in selected_columns if col in ["Clicks", "Conversions", "Revenue ($)"]]

            if group_keys and num_metrics:
                display_df = filtered_df.groupby(group_keys, as_index=False)[num_metrics].sum()
                display_df = display_df[selected_columns]
            else:
                display_df = filtered_df[selected_columns]

            format_dict = {"Revenue ($)": "${:,.2f}"} if "Revenue ($)" in selected_columns else {}
            st.dataframe(
                display_df.style.format(format_dict),
                use_container_width=True
            )
        else:
            st.info("لا توجد بيانات للمجموعة أو الفلتر المحدد.")
    else:
        st.warning("اختر عموداً واحداً على الأقل للعرض.")
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أرباح للفترة المحددة. تفقد قسم التشخيص:")
        with st.expander("🔍 Debugging Info", expanded=True):
            st.json(all_debug_info)
