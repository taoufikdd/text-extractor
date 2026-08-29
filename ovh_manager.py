import streamlit as st
import ovh
import time

st.set_page_config(
    page_title="OVHcloud Deployer",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ OVHcloud Multi-Server Deployer")

# -----------------------------
# Sidebar: Credentials
# -----------------------------
with st.sidebar:
    st.header("🔑 مفاتيح OVH API")

    # إضافة ovh-us واختيارها كـ افتراضية
    endpoint = st.selectbox(
        "Endpoint",
        ["ovh-us", "ovh-eu", "ovh-ca"],
        index=0,
        key="endpoint_input"
    )

    application_key = st.text_input("Application Key", type="password", key="ak")
    application_secret = st.text_input("Application Secret", type="password", key="as")
    consumer_key = st.text_input("Consumer Key", type="password", key="ck")

    connect = st.button("Connect", type="primary", use_container_width=True)

if connect:
    if not all([application_key, application_secret, consumer_key]):
        st.error("الرجاء إدخال جميع المفاتيح أولاً!")
        st.stop()

    try:
        client = ovh.Client(
            endpoint=endpoint,
            application_key=application_key.strip(),
            application_secret=application_secret.strip(),
            consumer_key=consumer_key.strip(),
        )
        projects = client.get("/cloud/project")
        st.session_state["connected"] = True
        st.session_state["projects"] = projects
        st.success(f"تم الاتصال بنجاح. تم العثور على {len(projects)} مشروع.")
    except Exception as e:
        st.session_state["connected"] = False
        st.error(f"فشل الاتصال: {e}")

if not st.session_state.get("connected"):
    st.info("أدخل المفاتيح في القائمة الجانبية واضغط Connect (تأكد من اختيار ovh-us).")
    st.stop()

projects = st.session_state.get("projects", [])
if not projects:
    st.warning("لم يتم العثور على أي مشروع Public Cloud.")
    st.stop()

client = ovh.Client(
    endpoint=st.session_state["endpoint_input"],
    application_key=st.session_state["ak"],
    application_secret=st.session_state["as"],
    consumer_key=st.session_state["ck"],
)

# -----------------------------
# Select Project
# -----------------------------
project = st.selectbox("Public Cloud Project", projects)

# -----------------------------
# Load Project Config
# -----------------------------
@st.cache_data(ttl=300)
def load_config(endpoint_val, ak, _as, ck, project_id):
    c = ovh.Client(
        endpoint=endpoint_val,
        application_key=ak,
        application_secret=_as,
        consumer_key=ck,
    )
    regions = c.get(f"/cloud/project/{project_id}/region")
    flavors = c.get(f"/cloud/project/{project_id}/flavor")
    images = c.get(f"/cloud/project/{project_id}/image")
    sshkeys = c.get(f"/cloud/project/{project_id}/sshkey")
    return regions, flavors, images, sshkeys

try:
    regions, flavors, images, sshkeys = load_config(
        st.session_state["endpoint_input"],
        st.session_state["ak"],
        st.session_state["as"],
        st.session_state["ck"],
        project,
    )
except Exception as e:
    st.error(f"تعذر جلب إعدادات المشروع: {e}")
    st.stop()

# Format maps
region_map = {r.get("name", r.get("region")): r for r in regions}
flavor_map = {f"{f.get('name')} | {f.get('vcpus', '?')} vCPU | {f.get('ram', '?')}MB": f for f in flavors}
image_map = {i.get("name", i.get("id")): i for i in images}
ssh_map = {s.get("name", s.get("id")): s for s in sshkeys}

# -----------------------------
# Deployment Form
# -----------------------------
st.subheader("🚀 إعدادات الإنشاء المتعدد")

col1, col2 = st.columns(2)

with col1:
    selected_region = st.selectbox("Region (المنطقة)", list(region_map.keys()))
    selected_flavor = st.selectbox("Flavor (المواصفات)", list(flavor_map.keys()))
    base_name = st.text_input("Prefix Name", value="server")

with col2:
    selected_image = st.selectbox("Operating System (النظام)", list(image_map.keys()))
    selected_ssh = st.selectbox("SSH Key", list(ssh_map.keys()) if ssh_map else ["No SSH key"])
    billing_period = st.selectbox("Billing", ["hourly", "monthly"])

st.divider()

c3, c4 = st.columns(2)
with c3:
    num_servers = st.number_input("عدد السيرفرات (Number of servers)", min_value=1, max_value=20, value=1)
with c4:
    pause_sec = st.number_input("المدة الزمنية بين كل سيرفر وسيرفر (بالثواني)", min_value=0, max_value=60, value=2)

create_btn = st.button("🚀 بدء إنشاء السيرفرات", type="primary", use_container_width=True)

if create_btn:
    if not ssh_map:
        st.error("خاصك تكون ضايف SSH Key فـ لوحة OVH قبل ما تكرّيي السيرفر.")
        st.stop()

    reg_obj = region_map[selected_region]
    flv_obj = flavor_map[selected_flavor]
    img_obj = image_map[selected_image]
    ssh_obj = ssh_map[selected_ssh]

    region_code = reg_obj.get("name") or reg_obj.get("region")
    flavor_id = flv_obj.get("id")
    image_id = img_obj.get("id")
    ssh_id = ssh_obj.get("id")

    progress_bar = st.progress(0)
    
    for i in range(int(num_servers)):
        srv_name = f"{base_name}-0{i+1}" if num_servers > 1 else base_name
        
        payload = {
            "name": srv_name,
            "region": region_code,
            "flavorId": flavor_id,
            "imageId": image_id,
            "sshKeyId": ssh_id,
            "monthlyBilling": billing_period == "monthly",
        }

        try:
            res = client.post(f"/cloud/project/{project}/instance", **payload)
            st.success(f"✅ تم إرسال طلب إنشاء {srv_name} بنجاح!")
        except Exception as e:
            st.error(f"❌ خطأ في إنشاء {srv_name}: {e}")

        # Update progress
        progress_bar.progress((i + 1) / int(num_servers))

        # Pause delay if not the last server
        if i < num_servers - 1 and pause_sec > 0:
            st.write(f"⏳ الانتظار لمدة {pause_sec} ثواني قبل السيرفر القادم...")
            time.sleep(pause_sec)

    st.balloons()

# -----------------------------
# List Active Instances
# -----------------------------
st.divider()
st.subheader("🖥️ قائمة السيرفرات الحالية")

try:
    instances = client.get(f"/cloud/project/{project}/instance")
    if not instances:
        st.info("لا توجد سيرفرات حالياً.")
    else:
        for inst in instances:
            iid = inst.get("id")
            name = inst.get("name")
            status = inst.get("status")
            reg = inst.get("region")
            
            with st.container(border=True):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                with col_a:
                    st.write(f"**{name}** (`{iid}`)")
                with col_b:
                    st.write(f"Region: {reg} | Status: **{status}**")
                with col_c:
                    if st.button("🗑️ مسح", key=f"del_{iid}"):
                        client.delete(f"/cloud/project/{project}/instance/{iid}")
                        st.success(f"تم مسح {name}")
                        time.sleep(1)
                        st.rerun()
except Exception as e:
    st.error(f"تعذر جلب السيرفرات: {e}")
