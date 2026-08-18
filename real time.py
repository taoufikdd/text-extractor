import json
import os
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

CONFIG_FILE = "api_keys.json"
OFFER_NAMES_FILE = "offer_names.json"
SUB1_NAMES_FILE = "sub1_names.json"

# ==========================================
# 💾 2. إدارة البيانات والتخزين المحلي
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

if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = load_json(CONFIG_FILE, [])

if "offer_names" not in st.session_state:
    st.session_state["offer_names"] = load_json(OFFER_NAMES_FILE, {})

if "sub1_names" not in st.session_state:
    st.session_state["sub1_names"] = load_json(SUB1_NAMES_FILE, {})

# ==========================================
# ⚙️ 3. Sidebar (الإعدادات والتسميات)
# ==========================================
st.sidebar.title("⚙️ Config")

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
st.sidebar.subheader("🔑 Add API Key")
new_key = st.sidebar.text_input("Enter API Key:", type="password")
if st.sidebar.button("➕ Add Key"):
    if new_key.strip():
        if new_key.strip() not in st.session_state["api_keys"]:
            st.session_state["api_keys"].append(new_key.strip())
            save_json(CONFIG_FILE, st.session_state["api_keys"])
            st.sidebar.success("Key Added!")
            st.rerun()

if st.session_state["api_keys"]:
    st.sidebar.subheader("📋 Active Keys")
    for idx, k in enumerate(list(st.session_state["api_keys"])):
        col1, col2 = st.sidebar.columns([3, 1])
        masked_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "API Key"
        col1.write(f"Key {idx+1}: `{masked_key}`")
        if col2.button("❌", key=f"del_{idx}"):
            st.session_state["api_keys"].pop(idx)
            save_json(CONFIG_FILE, st.session_state["api_keys"])
            st.rerun()

# --- تسمية الـ Offers و Sub1 يدوياً وفي Sidebar ---
if st.session_state["api_keys"]:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏷️ Offer Custom Names")
    if st.session_state["offer_names"]:
        for oid in sorted(st.session_state["offer_names"].keys()):
            cur_o = st.session_state["offer_names"].get(oid, "")
            new_o = st.sidebar.text_input(f"Offer {oid}:", value=cur_o, key=f"o_{oid}")
            if new_o != cur_o:
                st.session_state["offer_names"][oid] = new_o
                save_json(OFFER_NAMES_FILE, st.session_state["offer_names"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 Sub1 (User) Custom Names")
    if st.session_state["sub1_names"]:
        for sid in sorted(st.session_state["sub1_names"].keys()):
            cur_s = st.session_state["sub1_names"].get(sid, "")
            new_s = st.sidebar.text_input(f"Sub1 [{sid}]:", value=cur_s, key=f"s_{sid}")
            if new_s != cur_s:
                st.session_state["sub1_names"][sid] = new_s
                save_json(SUB1_NAMES_FILE, st.session_state["sub1_names"])

# ==========================================
# 🌐 4. دالة جلب البيانات (Offer + Sub1)
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

    # طلب التقرير مجمع بـ Offer و Sub1
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

                # استخراج المعطيات من الأعمدة المرجعة
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

                # حفظ الـ IDs تلقائياً إذا كانت جديدة لتظهر في القائمة الجانبية
                if offer_id and offer_id not in st.session_state["offer_names"]:
                    st.session_state["offer_names"][offer_id] = offer_label
                    save_json(OFFER_NAMES_FILE, st.session_state["offer_names"])

                if sub1_id and sub1_id not in st.session_state["sub1_names"]:
                    st.session_state["sub1_names"][sub1_id] = sub1_id
                    save_json(SUB1_NAMES_FILE, st.session_state["sub1_names"])

                # جلب الأسماء المخصصة
                custom_offer_name = st.session_state["offer_names"].get(offer_id, offer_label)
                custom_sub1_name = st.session_state["sub1_names"].get(sub1_id, sub1_id)

                payout = float(rep.get("payout", rep.get("revenue", 0.0)))
                conversions = int(rep.get("cv", rep.get("conversions", 0)))
                clicks = int(rep.get("total_click", rep.get("clicks", 0)))

                results.append({
                    "Offer ID": offer_id,
                    "Offer Name": custom_offer_name,
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
# 📊 5. العرض الرئيسي
# ==========================================
st.title("💵 Live Revenue Tracker")
st.caption(f"📅 Selected Range: **{start_date}** to **{end_date}**")

all_data = []
all_debug_info = []

if not st.session_state["api_keys"]:
    st.info("👈 أضف الـ **API Key** في القائمة الجانبية (Sidebar) للبدء.")
else:
    for idx, key in enumerate(st.session_state["api_keys"]):
        res, logs = fetch_everflow_data(key, start_date, end_date)
        all_debug_info.append({"key_index": idx + 1, "logs": logs})
        if res:
            for item in res:
                item["Account"] = f"Account #{idx+1}"
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
        df[["Account", "Offer ID", "Offer Name", "Sub1 ID", "Sub1 Name", "Clicks", "Conversions", "Revenue ($)"]].style.format({"Revenue ($)": "${:,.2f}"}),
        use_container_width=True
    )
else:
    if st.session_state["api_keys"]:
        st.warning("لم يتم العثور على أرباح للفترة المحددة. تفقد قسم التشخيص:")
        with st.expander("🔍 Debugging Info", expanded=True):
            st.json(all_debug_info)
