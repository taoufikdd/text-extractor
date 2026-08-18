import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Analytics Dashboard", layout="wide")

# --- INITIALIZATION D DATA (MOCK / DATABASE) ---
if "mapping" not in st.session_state:
    # Mapping dyal Sub1 ID -> Name (Sponsor / Mailer / Offer)
    st.session_state.mapping = {
        "31": {"name": "Campaign_Alpha", "sponsor": "Sponsor_A"},
        "42": {"name": "Campaign_Beta", "sponsor": "Sponsor_B"}
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None

# --- SYSTEM D LOGIN ---
def login():
    st.title("🔐 Se connecter")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.rerun()
        elif username == "user" and password == "user123":
            st.session_state.logged_in = True
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Username aw Password ghalt!")

if not st.session_state.logged_in:
    login()
    st.stop()

# Sidebar L-Logout w Refresh
st.sidebar.title(f"👤 Role: {st.session_state.role.upper()}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

# --- REFRESH BUTTON ---
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.toast("Data refreshed successfully!", icon="✅")

# --- SECTION ADMIN: MANAGEMENT D SUB1 & SPONSORS ---
if st.session_state.role == "admin":
    with st.expander("🛠️ Admin Panel: Ajouter / Modifier Sub1 Mapping"):
        col1, col2, col3 = st.columns(3)
        sub1_id = col1.text_input("Sub1 ID (ex: 31)")
        sub1_name = col2.text_input("Name / Mailer")
        sponsor = col3.text_input("Sponsor Name")
        
        if st.button("Save Mapping"):
            if sub1_id and sub1_name:
                st.session_state.mapping[sub1_id] = {"name": sub1_name, "sponsor": sponsor}
                st.success(f"Sub1 ID {sub1_id} saved successfully!")
            else:
                st.warning("3ammar Sub1 ID w Name!")

    # Display Current Mapping Table
    st.write("**Current Mappings:**")
    st.json(st.session_state.mapping)

# --- SECTION DASHBOARD (ADMIN + USER) ---
st.title("📊 Performance Dashboard")

# 1. Date Filter (Default = Today)
today = datetime.date.today()
date_range = st.date_input(
    "📅 Select Date Range",
    value=(today, today),
    max_value=today
)

# Dummy Data (F-real code, hna kat-fetchi mn API dyal Sponsor)
raw_data = pd.DataFrame([
    {"date": today, "sub1": "31", "clicks": 150, "leads": 12, "conversions": 5, "revenue": 120.50, "mailer": "Omar", "offer": "Offer_X"},
    {"date": today, "sub1": "42", "clicks": 300, "leads": 45, "conversions": 18, "revenue": 450.00, "mailer": "Alex", "offer": "Offer_Y"},
])

# Process Sub1 Name Mapping
def apply_mapping(row):
    sub1_info = st.session_state.mapping.get(str(row["sub1"]), {"name": "Unknown", "sponsor": "Unknown"})
    return f"{row['sub1']} - {sub1_info['name']}"

raw_data["Sub1_Formatted"] = raw_data.apply(apply_mapping, axis=1)

# 2. Dynamic Metric Selection & Filters
col_f1, col_f2 = st.columns(2)

with col_f1:
    selected_metrics = st.multiselect(
        "👁️ Choose Metrics to Display",
        options=["clicks", "leads", "conversions", "revenue"],
        default=["clicks", "leads", "revenue"]
    )

with col_f2:
    group_by = st.multiselect(
        "🔍 Filter / Group By",
        options=["mailer", "offer", "Sub1_Formatted"],
        default=["mailer", "Sub1_Formatted"]
    )

# Filter Data by Date
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = raw_data[(raw_data["date"] >= start_date) & (raw_data["date"] <= end_date)]
else:
    filtered_df = raw_data

# 3. Aggregation & Table Display
if group_by and selected_metrics:
    final_df = filtered_df.groupby(group_by)[selected_metrics].sum().reset_index()
    st.dataframe(final_df, use_container_width=True)
else:
    st.dataframe(filtered_df, use_container_width=True)
