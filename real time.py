import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Analytics Dashboard", layout="wide")

# --- DATABASE / MAPPING SESSION ---
if "mapping" not in st.session_state:
    # Format: {"Sponsor_A": {"31": "kaoutar", "32": "youssef"}}
    st.session_state.mapping = {
        "Sponsor_A": {"31": "kaoutar"},
        "Sponsor_B": {"42": "Campaign_Beta"}
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None

# --- AUTHENTICATION ---
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

st.sidebar.title(f"👤 Role: {st.session_state.role.upper()}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.toast("Data refreshed successfully!", icon="✅")

# --- RAW DATA MOCK (Data li jaya mn les Sponsors) ---
today = datetime.date.today()
raw_data = pd.DataFrame([
    {"date": today, "sponsor": "Sponsor_A", "sub1": "31", "clicks": 150, "leads": 12, "conversions": 5, "revenue": 120.50, "mailer": "Omar", "offer": "Offer_X"},
    {"date": today, "sponsor": "Sponsor_A", "sub1": "35", "clicks": 80, "leads": 4, "conversions": 1, "revenue": 30.00, "mailer": "Omar", "offer": "Offer_X"},
    {"date": today, "sponsor": "Sponsor_B", "sub1": "42", "clicks": 300, "leads": 45, "conversions": 18, "revenue": 450.00, "mailer": "Alex", "offer": "Offer_Y"},
    {"date": today, "sponsor": "Sponsor_B", "sub1": "99", "clicks": 50, "leads": 2, "conversions": 0, "revenue": 0.00, "mailer": "Alex", "offer": "Offer_Z"},
])

# --- ADMIN PANEL: AUTOMATIC SUB1 DETECTION BY SPONSOR ---
if st.session_state.role == "admin":
    with st.expander("🛠️ Admin Panel: Gérer Name Mapping par Sponsor", expanded=True):
        # 1. Khtar l-Sponsor
        sponsors_list = raw_data["sponsor"].unique().tolist()
        selected_sponsor = st.selectbox("📌 Choisir Sponsor", sponsors_list)
        
        # 2. Extract Sub1 IDs d dak l-Sponsor
        available_sub1s = raw_data[raw_data["sponsor"] == selected_sponsor]["sub1"].unique().tolist()
        
        st.write(f"**Les Sub1 IDs détectés pour {selected_sponsor}:**")
        
        # Formulaire باش t-smi ghir li bghiti
        with st.form("mapping_form"):
            updated_names = {}
            current_sponsor_map = st.session_state.mapping.get(selected_sponsor, {})
            
            for sub_id in sorted(available_sub1s):
                existing_name = current_sponsor_map.get(str(sub_id), "")
                updated_names[str(sub_id)] = st.text_input(
                    label=f"Sub1 ID: {sub_id}",
                    value=existing_name,
                    placeholder="Khallih khawi ila ma-bghitish t-smih",
                    key=f"input_{selected_sponsor}_{sub_id}"
                )
            
            if st.form_submit_button("💾 Enregistrer Mapping"):
                # Sauvegarder les noms non-vides
                if selected_sponsor not in st.session_state.mapping:
                    st.session_state.mapping[selected_sponsor] = {}
                
                for s_id, name in updated_names.items():
                    if name.strip():
                        st.session_state.mapping[selected_sponsor][s_id] = name.strip()
                    elif s_id in st.session_state.mapping[selected_sponsor]:
                        del st.session_state.mapping[selected_sponsor][s_id]
                
                st.success(f"Mapping pour {selected_sponsor} enregistré avec succès!")

# --- DASHBOARD LOGIC ---
st.title("📊 Performance Dashboard")

# Format Sub1 Name: ila fih smiya kaytla3 ID - Smiya, ila ma-fihsh kaytla3 ghir ID
def format_sub1(row):
    sp = row["sponsor"]
    s_id = str(row["sub1"])
    custom_name = st.session_state.mapping.get(sp, {}).get(s_id, "")
    if custom_name:
        return f"{s_id} - {custom_name}"
    return s_id

raw_data["Sub1_Formatted"] = raw_data.apply(format_sub1, axis=1)

# Filters
date_range = st.date_input("📅 Date Range", value=(today, today), max_value=today)

col_f1, col_f2 = st.columns(2)
with col_f1:
    selected_metrics = st.multiselect("👁️ Metrics", ["clicks", "leads", "conversions", "revenue"], default=["clicks", "leads", "revenue"])
with col_f2:
    group_by = st.multiselect("🔍 Group By", ["sponsor", "mailer", "offer", "Sub1_Formatted"], default=["sponsor", "Sub1_Formatted"])

# Filter Date
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = raw_data[(raw_data["date"] >= start_date) & (raw_data["date"] <= end_date)]
else:
    filtered_df = raw_data

# Display
if group_by and selected_metrics:
    final_df = filtered_df.groupby(group_by)[selected_metrics].sum().reset_index()
    st.dataframe(final_df, use_container_width=True)
else:
    st.dataframe(filtered_df, use_container_width=True)
