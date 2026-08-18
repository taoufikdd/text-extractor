import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. إعدادات الصفحة والـ Auto-Refresh
# ==========================================
st.set_page_config(
    page_title="Affiliate Real-Time Tracker",
    page_icon="💰",
    layout="wide"
)

# تحديث تلقائي للصفحة كل 30 ثانية (30000 millisecond) لضمان Real-time
count = st_autorefresh(interval=30000, limit=1000, key="realtime_counter")

st.title("🚀 Real-Time Affiliate Revenue Tracker")

# ==========================================
# 2. إعداد الحفظ المحلي والـ Session State
# ==========================================
if "sub1_mapping" not in st.session_state:
    # مثال افتراضي لـ Mapping: "SUB1_ID": "اسم الشخص"
    st.session_state["sub1_mapping"] = {
        "101": "Amine",
        "102": "Youssef",
        "103": "Simo"
    }

if "sponsors" not in st.session_state:
    # قائمة الـ Sponsors مع الـ API Keys
    st.session_state["sponsors"] = []

# ==========================================
# 3. Sidebar: التحكم فـ Date و Mapping و Sponsors
# ==========================================
st.sidebar.title("⚙️ Control Panel")

# --- أ) اختيار التاريخ ---
st.sidebar.subheader("📅 Date Range")
col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("From", date.today())
end_date = col_d2.date_input("To", date.today())

st.sidebar.markdown("---")

# --- ب) إدارة Sub1/Publisher ID (ربط ID بالإسم) ---
st.sidebar.subheader("👤 Sub1 / Publisher Mapping")
with st.sidebar.expander("➕ Add / Edit Sub1 Mapping"):
    new_sub1_id = st.text_input("Sub1 ID (e.g. 101):")
    new_user_name = st.text_input("Person Name (e.g. Amine):")
    if st.button("Save Sub1 Mapping"):
        if new_sub1_id and new_user_name:
            st.session_state["sub1_mapping"][new_sub1_id.strip()] = new_user_name.strip()
            st.success(f"Linked Sub1 `{new_sub1_id}` ➡️ **{new_user_name}**")
        else:
            st.error("Fill both ID and Name.")

st.sidebar.markdown("---")

# --- ج) إدارة الـ Sponsors و API Keys ---
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
            st.success(f"Added {s_name}!")
        else:
            st.error("Please fill all Sponsor fields.")

# ==========================================
# 4. دالة جلب البيانات من الـ API (Generic API Fetcher)
# ==========================================
def fetch_sponsor_data(sponsor, s_date, e_date):
    """
    دالة موحدة لطلب المعطيات من API. 
    ملاحظة: يمكنك تعديل params أو headers بحسب معايير كل Sponsor.
    """
    headers = {
        "Authorization": f"Bearer {sponsor['api_key']}",
        "Accept": "application/json"
    }
    
    params = {
        "start_date": str(s_date),
        "end_date": str(e_date),
        "group_by": "sub1"  # أغلب شبكات الأفلييت كتقبل جلب التقارير مقسمة بـ sub1
    }
    
    try:
        response = requests.get(sponsor["endpoint"], headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"⚠️ {sponsor['name']} returned HTTP {response.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ Connection error with {sponsor['name']}: {str(e)}")
        return None

# ==========================================
# 5. معالجة وتجميع البيانات فـ Real Time
# ==========================================
all_reports = []

# حقل تجريبي إذا لم تكن قد أضفت API حقيقية بعد (Mock Data Demo)
if not st.session_state["sponsors"]:
    st.info("💡 **Demo Mode Active:** Add your Sponsors and API Keys in the left sidebar.")
    # بيانات وهمية للعرض فقط
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
    # جلب البيانات الحقيقية من جميع الـ APIs المضافة
    for sp in st.session_state["sponsors"]:
        raw_data = fetch_sponsor_data(sp, start_date, end_date)
        if raw_data:
            # هنا كتقاد الـ Parsing على حساب Structure ديال JSON لي كايراجع ليك الـ Sponsor
            # افتراض أن النتيجة قائمة من الأغراض (List of Dicts):
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

# ==========================================
# 6. عرض البيانات والـ Dashboard
# ==========================================
if all_reports:
    df = pd.DataFrame(all_reports)

    # --- Metrics / Cards العلوية ---
    total_rev = df["Revenue ($)"].sum() if "Revenue ($)" in df.columns else df["revenue"].sum()
    total_conv = df["Conversions"].sum() if "Conversions" in df.columns else df["conversions"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"${total_rev:,.2f}")
    col2.metric("🎯 Total Conversions", f"{total_conv:,}")
    col3.metric("🔄 Auto-Refresh Status", "Active (Every 30s)")

    st.markdown("---")

    # --- جدول الأرباح حسب الشخص (Person Summary) ---
    st.subheader("👥 Revenue by Person (Grouped)")
    if "Person Name" in df.columns:
        person_df = df.groupby("Person Name")[["Conversions", "Revenue ($)"]].sum().reset_index()
        person_df = person_df.sort_values(by="Revenue ($)", ascending=False)
        st.dataframe(person_df, use_container_width=True)

    # --- الجدول التفصيلي الكامل (Detailed Real-time Table) ---
    st.subheader("📊 Detailed Real-Time Breakdown")
    st.dataframe(df, use_container_width=True)

else:
    st.warning("No data retrieved for the selected date range or configuration.")