import streamlit as st
import ovh
import time
import random
import string
import os

# استخدام paramiko أو cryptography إذا توفرت لتوليد SSH Key تلقائياً
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    crypto_available = True
except ImportError:
    crypto_available = False

st.set_page_config(
    page_title="OVHcloud Deployer",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ OVHcloud Multi-Server Deployer")

# توليد كلمة سر تلقائية
def generate_default_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "P@ss_" + "".join(random.choices(chars, k=10))

# توليد SSH Key مؤقت تلقائي لمنع خطأ OVH
def generate_ssh_key_pair():
    if crypto_available:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = key.public_key().public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
        return public_key
    return None

PAUSE_DELAY = 5

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
# Safe Format Maps
# -----------------------------
region_list = [r.get("name") or r.get("region") if isinstance(r, dict) else str(r) for r in regions]

flavor_map = {
    f"{f.get('name', 'Unknown')} | {f.get('vcpus', '?')} vCPU | {f.get('ram', '?')}MB": f 
    for f in flavors if isinstance(f, dict)
}

image_map = {
    i.get("name", i.get("id", "Unknown")): i 
    for i in images if isinstance(i, dict)
}

ssh_map = {
    s.get("name", s.get("id", "Unknown")): s 
    for s in sshkeys if isinstance(s, dict)
}

# -----------------------------
# Deployment Form
# -----------------------------
st.subheader("🚀 إعدادات الإنشاء المتعدد")

col1, col2 = st.columns(2)

with col1:
    selected_region = st.selectbox("Region (المنطقة)", region_list if region_list else ["US-EAST-VA"])
    selected_flavor = st.selectbox("Flavor (المواصفات)", list(flavor_map.keys()))
    base_name = st.text_input("Prefix Name", value="server")
    
    if "def_pass" not in st.session_state:
        st.session_state["def_pass"] = generate_default_password()
        
    custom_password = st.text_input("Password للسيرفرات", value=st.session_state["def_pass"])

with col2:
    selected_image = st.selectbox("Operating System (النظام)", list(image_map.keys()))
    
    # القائمة تعرض SSH Keys المتاحة
    selected_ssh = st.selectbox("SSH Key (ضروري لـ OVH)", list(ssh_map.keys()) if ssh_map else ["إنشاء SSH Key تلقائياً"])
    billing_period = st.selectbox("Billing", ["hourly", "monthly"])
    os_user = st.text_input("اسم المستخدم (Username)", value="ubuntu")

st.divider()

num_servers = st.number_input("عدد السيرفرات (Number of servers)", min_value=1, max_value=20, value=1)

create_btn = st.button("🚀 بدء إنشاء السيرفرات", type="primary", use_container_width=True)

if create_btn:
    flv_obj = flavor_map[selected_flavor]
    img_obj = image_map[selected_image]

    flavor_id = flv_obj.get("id")
    image_id = img_obj.get("id")

    # التعامل مع الـ SSH Key
    ssh_key_id = None
    if ssh_map and selected_ssh in ssh_map:
        ssh_key_id = ssh_map[selected_ssh].get("id")
    else:
        # إذا لم يكن هناك SSH Key أو اختار إنشاء تلقائي
        try:
            auto_pub_key = generate_ssh_key_pair()
            if auto_pub_key:
                new_key = client.post(f"/cloud/project/{project}/sshkey", 
                                      name=f"auto-key-{int(time.time())}", 
                                      publicKey=auto_pub_key)
                ssh_key_id = new_key.get("id")
                st.info(f"تم إنشاء SSH Key تلقائي لحسابك بنجاح لتفادي رفض OVH.")
        except Exception as ssh_err:
            st.warning(f"ملاحظة حول SSH Key: {ssh_err}")

    # Script إعداد كلمة المرور والدخول عبر SSH
    user_data_script = f"""#cloud-config
chpasswd:
  list: |
    {os_user}:{custom_password}
    root:{custom_password}
  expire: False
ssh_pwauth: True
"""

    payload_base = {
        "region": selected_region,
        "flavorId": flavor_id,
        "imageId": image_id,
        "monthlyBilling": billing_period == "monthly",
        "userData": user_data_script,
    }

    if ssh_key_id:
        payload_base["sshKeyId"] = ssh_key_id

    created_servers = []
    progress_bar = st.progress(0)
    
    for i in range(int(num_servers)):
        srv_name = f"{base_name}-0{i+1}" if num_servers > 1 else base_name
        payload = payload_base.copy()
        payload["name"] = srv_name

        try:
            res = client.post(f"/cloud/project/{project}/instance", **payload)
            created_servers.append(res)
            st.success(f"✅ تم إرسال طلب إنشاء {srv_name} بنجاح!")
        except Exception as e:
            st.error(f"❌ خطأ في إنشاء {srv_name}: {e}")

        progress_bar.progress((i + 1) / int(num_servers))

        if i < num_servers - 1:
            time.sleep(PAUSE_DELAY)

    st.balloons()
    st.session_state["last_created_pass"] = custom_password
    st.session_state["last_created_user"] = os_user

# -----------------------------
# List Active Instances & Format Output
# -----------------------------
st.divider()
st.subheader("🖥️ قائمة السيرفرات الجاهزة وتنسيق البيانات (Format)")

try:
    instances = client.get(f"/cloud/project/{project}/instance")
    if not instances:
        st.info("لا توجد سيرفرات حالياً.")
    else:
        formatted_list = []
        saved_pass = st.session_state.get("last_created_pass", custom_password)
        saved_user = st.session_state.get("last_created_user", "ubuntu")

        for inst in instances:
            iid = inst.get("id")
            name = inst.get("name")
            status = inst.get("status")
            reg = inst.get("region")
            ip_addresses = inst.get("ipAddresses", [])

            public_ip = "جاري الجلب..."
            for ip_info in ip_addresses:
                if isinstance(ip_info, dict) and ip_info.get("type") == "public":
                    public_ip = ip_info.get("ip")
                    break
                elif isinstance(ip_info, dict) and "ip" in ip_info:
                    public_ip = ip_info.get("ip")

            formatted_entry = f"{public_ip} | {saved_user} | {saved_pass}"
            formatted_list.append(formatted_entry)

            with st.container(border=True):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                with col_a:
                    st.write(f"**{name}** (`{iid}`)")
                    st.code(formatted_entry, language="text")
                with col_b:
                    st.write(f"Region: {reg} | Status: **{status}**")
                with col_c:
                    if st.button("🗑️ مسح", key=f"del_{iid}"):
                        client.delete(f"/cloud/project/{project}/instance/{iid}")
                        st.success(f"تم مسح {name}")
                        time.sleep(1)
                        st.rerun()

        st.subheader("📋 نسخ كل السيرفرات بـ Format موحد:")
        st.text_area(
            "جاهزة للنسخ المباشر:",
            value="\n".join(formatted_list),
            height=150
        )

except Exception as e:
    st.error(f"تعذر جلب السيرفرات: {e}")
