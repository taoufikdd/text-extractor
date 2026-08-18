import streamlit as st
import pandas as pd
import datetime
import requests

st.set_page_config(page_title="Analytics Dashboard", layout="wide")

# --- SESSION STATES ---
if "sponsors_config" not in st.session_state:
    # Key: Sponsor Name, Value: {"api_url": ..., "api_key": ...}
    st.session_state.sponsors_config = {}

if "sub1_mapping" not in st.session_state:
    # Key: Sponsor Name, Value: {Sub1_ID: Custom_Name}
    st.session_state.sub1_mapping = {}

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

# --- SIDEBAR ---
st.sidebar.title(f"👤 Role: {st.session_state.role.upper()}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Real-Time Data"):
    st.cache_data.clear()
    st.toast("Data updated in real-time!", icon="✅")

# --- FUNCTION: FETCH REAL-TIME DATA FROM SPONSOR API ---
@st.cache_data(ttl=60) # Caches data for 60 seconds for performance
def fetch_sponsor_data(api_url, api_key=""):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Assurer l-return kay-koon DataFrame
            return pd.DataFrame(data)
        else:
            st.error(f"Erreur API: Status {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Impossible de connecter à l'API: {e}")
        return pd.DataFrame()

# --- ADMIN PANEL ---
if st.session_state.role == "admin":
    with st.expander("➕ 1. Ajouter un Nouveau Sponsor (API Setup)", expanded=False):
        c1, c2, c3 = st.columns(3)
        sp_name = c1.text_input("Sponsor Name (ex: HasTraff)")
        sp_url = c2.text_input("API Endpoint URL")
        sp_key = c3.text_input("API Key / Token (Optional)", type="password")
        
        if st.button("Enregistrer Sponsor"):
            if sp_name and sp_url:
                st.session_state.sponsors_config[sp_name] = {"api_url": sp_url, "api_key": sp_key}
                st.success(f"Sponsor '{sp_name}' ajouté avec succès!")
                st.rerun()
            else:
                st.warning("Veuillez remplir le nom et l'URL d'API.")

# --- FETCH ALL SPONSORS DATA IN REAL-TIME ---
all_data_frames = []

for sponsor_name, config in st.session_state.sponsors_config.items():
    df_sp = fetch_sponsor_data(config["api_url"], config["api_key"])
    if not df_sp.empty:
        df_sp["sponsor"] = sponsor_name
        all_data_frames.append(df_sp)

if all_data_frames:
    realtime_df = pd.concat(all_data_frames, ignore_index=True)
else:
    # Template khawi f-halat ma-zal ma-tzad hta sponsor
    realtime_df = pd.DataFrame(columns=["date", "sponsor", "sub1", "clicks", "leads", "conversions", "revenue", "mailer", "offer"])

# --- ADMIN SUB1 NAMING SECTION ---
if st.session_state.role == "admin" and not realtime_df.empty:
    with st.expander("🏷️ 2. Gérer Name Mapping des Sub1s", expanded=True):
        active_sponsors = list(st.session_state.sponsors_config.keys())
        selected_sp = st.selectbox("Choisir Sponsor pour Mapping", active_sponsors)
        
        sp_df = realtime_df[realtime_df["sponsor"] == selected_sp]
        
        if not sp_df.empty and "sub1" in sp_df.columns:
            detected_sub1s = sp_df["sub1"].unique().tolist()
            
            with st.form("sub1_mapping_form"):
                st.write(f"**Sub1 IDs détectés en temps réel pour {selected_sp}:**")
                updated_names = {}
                current_map = st.session_state.sub1_mapping.get(selected_sp, {})
                
                for s_id in sorted(detected_sub1s):
                    existing = current_map.get(str(s_id), "")
                    updated_names[str(s_id)] = st.text_input(
                        f"Sub1 ID: {s_id}", 
                        value=existing,
                        placeholder="Khallih khawi باش ybqa ghir l-ID"
                    )
                
                if st.form_submit_button("Sauvegarder Mapping"):
                    if selected_sp not in st.session_state.sub1_mapping:
                        st.session_state.sub1_mapping[selected_sp] = {}
                    
                    for s_id, name in updated_names.items():
                        if name.strip():
                            st.session_state.sub1_mapping[selected_sp][str(s_id)] = name.strip()
                        elif str(s_id) in st.session_state.sub1_mapping[selected_sp]:
                            del st.session_state.sub1_mapping[selected_sp][str(s_id)]
                    st.success("Mapping mis à jour!")
                    st.rerun()

# --- DASHBOARD (ADMIN + USER) ---
st.title("📊 Performance Dashboard (Real-Time)")

if realtime_df.empty:
    st.info("💡 Aucun sponsor configuré ou aucune donnée reçue. L'Admin doit ajouter un Sponsor et son API URL.")
else:
    # Apply Sub1 Formatted Name
    def format_sub1(row):
        sp = row["sponsor"]
        s_id = str(row["sub1"])
        custom_name = st.session_state.sub1_mapping.get(sp, {}).get(s_id, "")
        return f"{s_id} - {custom_name}" if custom_name else s_id

    realtime_df["Sub1_Formatted"] = realtime_df.apply(format_sub1, axis=1)

    # Date Convert & Filters
    if "date" in realtime_df.columns:
        realtime_df["date"] = pd.to_datetime(realtime_df["date"]).dt.date
    
    today = datetime.date.today()
    date_range = st.date_input("📅 Date Range", value=(today, today), max_value=today)

    col_f1, col_f2 = st.columns(2)
    
    # Available metrics in dataframe
    numeric_cols = [c for c in ["clicks", "leads", "conversions", "revenue"] if c in realtime_df.columns]
    groupable_cols = [c for c in ["sponsor", "mailer", "offer", "Sub1_Formatted"] if c in realtime_df.columns]

    with col_f1:
        selected_metrics = st.multiselect("👁️ Metrics", numeric_cols, default=numeric_cols)
    with col_f2:
        group_by = st.multiselect("🔍 Group By", groupable_cols, default=[c for c in ["sponsor", "Sub1_Formatted"] if c in groupable_cols])

    # Filter Data by Date
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
        filtered_df = realtime_df[(realtime_df["date"] >= start_d) & (realtime_df["date"] <= end_d)]
    else:
        filtered_df = realtime_df

    # Display Table
    if group_by and selected_metrics:
        final_df = filtered_df.groupby(group_by)[selected_metrics].sum().reset_index()
        st.dataframe(final_df, use_container_width=True)
    else:
        st.dataframe(filtered_df, use_container_width=True)
