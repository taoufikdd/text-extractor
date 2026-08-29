import streamlit as st
import ovh
import time
import random
import string
import subprocess

st.set_page_config(
    page_title="OVHcloud Deployer Fix",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ OVHcloud Multi-Server Deployer")

def generate_default_password():
    chars = string.ascii_letters + string.digits
    return "P@ss" + "".join(random.choices(chars, k=8)) + "!"

PAUSE_DELAY = 5

def get_or_create_ssh_key(client, project_id):
    try:
        keys = client.get(f"/cloud/project/{project_id}/sshkey")
        if keys:
            return keys[0].get("id")
        
        res = subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", "/tmp/ovh_tmp_key"],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            with open("/tmp/ovh_tmp_key.pub", "r") as f:
                pub_key = f.read().strip()
            
            new_k = client.post(
                f"/cloud/project/{project_id}/sshkey",
                name=f"auto-key-{random.randint(1000,9999)}",
                publicKey=pub_key
            )
            return new_k.get("id")
    except Exception:
        pass
    return None

# -----------------------------
# Sidebar: Credentials
# -----------------------------
with st.sidebar:
    st.header("🔑 مفاتيح OVH API")

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
    st.info("أدخل المفاتيح في القائمة الجانبية واضغط Connect.")
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

# -----------------------------
# Mapping Logic
# -----------------------------
region_list = [r.get("name") or r.get("region") if isinstance(r, dict) else str(r) for r in regions]

flavor_map = {}
for f in flavors:
    if isinstance(f, dict):
        ram_gb = round(f.get("ram", 0) / 1024, 1) if f.get("ram") else "?"
        label = f"{f.get('name', 'Unknown')} | {f.get('vcpus', '?')} vCPU | {ram_gb} GB"
        flavor_map[label] = f

image_map = {
    i.get("name", i.get("id", "Unknown")): i 
    for i in images if isinstance(i, dict)
}

ssh_map = {
    s.get("name", s.get("id", "Unknown")): s 
    for s in sshkeys if isinstance(s, dict)
}

# -----------------------------
# Form
# -----------------------------
st.subheader("🚀 إعدادات الإنشاء المتعدد")

col1, col2 = st.columns(2)

with col1:
    selected_region = st.selectbox("Region", region_list if region_list else ["US-EAST-VA"])
    selected_flavor = st.selectbox("Flavor", list(flavor_map.keys()))
    base_name = st.text_input("Prefix Name", value="server")
    
    if "def_pass" not in st.session_state:
        st.session_state["def_pass"] = generate_default_password()
        
    custom_password = st.text_input("Password", value=st.session_state["def_pass"])

with col2:
    selected_image = st.selectbox("Operating System", list(image_map.keys()))
    ssh_options = ["تلقائي (Auto Detect)"] + list(ssh_map.keys())
    selected_ssh = st.selectbox("SSH Key", ssh_options)
    billing_period = st.selectbox("Billing", ["hourly", "monthly"])
    os_user = st.text_input("Username", value="ubuntu")

st.divider()

num_servers = st.number_input("عدد السيرفرات", min_value=1, max_value=20, value=1)
create_btn = st.button("🚀 بدء إنشاء السيرفرات", type="primary", use_container_width=True)

# -----------------------------
# Execution
# -----------------------------
if create_btn:
    flv_obj = flavor_map[selected_flavor]
    img_obj = image_map[selected_image]

    flavor_id = flv_obj.get("id")
    image_id = img_obj.get("id")

    target_ssh_id = None
    if selected_ssh != "تلقائي (Auto Detect)" and selected_ssh in ssh_map:
        target_ssh_id = ssh_map[selected_ssh].get("id")
    else:
        target_ssh_id = get_or_create_ssh_key(client, project)

    cloud_init = f"""#cloud-config
password: {custom_password}
chpasswd: {{ expire: False }}
ssh_pwauth: True
"""

    progress_bar = st.progress(0)
    
    for i in range(int(num_servers)):
        srv_name = f"{base_name}-0{i+1}" if num_servers > 1 else base_name
        
        payload = {
            "name": srv_name,
            "region": selected_region,
            "flavorId": flavor_id,
            "imageId": image_id,
            "monthlyBilling": True if billing_period == "monthly" else False,
            "userData": cloud_init
        }
        if target_ssh_id:
            payload["sshKeyId"] = target_ssh_id

        try:
            res = client.post(f"/cloud/project/{project}/instance", **payload)
            st.success(f"✅ تم إرسال طلب إنشاء {srv_name} بنجاح!")
        except Exception as e:
            st.error(f"❌ خطأ من OVH: {e}")

        progress_bar.progress((i + 1) / int(num_servers))

        if i < num_servers - 1:
            time.sleep(PAUSE_DELAY)

    st.balloons()
