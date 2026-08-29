import streamlit as st
import ovh
import time
import random
import string

st.set_page_config(
    page_title="OVHcloud Deployer",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ OVHcloud Multi-Server Deployer")

# دالة لتوليد كلمة سر قوية افتراضية
def generate_default_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "P@ss_" + "".join(random.choices(chars, k=10))

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
region_list = []
for r in regions:
    if isinstance(r, dict):
        region_list.append(r.get("name") or r.get("region") or str(r))
    else:
        region_list.append(str(r))

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
    selected_region = st.selectbox("Region (المنطقة)", region_list if region_list else ["GRA7"])
    selected_flavor = st.selectbox("Flavor (المواصفات)", list(flavor_map.keys()))
    base_name = st.text_input("Prefix Name", value="server")
    
    if "def_pass" not in st.session_state:
        st.session_state["def_pass"] = generate_default_password()
        
    custom_password = st.text_input("Password للسيرفرات (افتراضي مجهز)", value=st.session_state["def_pass"])

with col2:
    selected_image = st.selectbox("Operating System (النظام)", list(image_map.keys()))
    selected_ssh = st.selectbox("SSH Key (اختياري)", ["بدون SSH Key"] + list(ssh_map.keys()))
    billing_period = st.selectbox("Billing", ["hourly", "monthly"])
    os_user = st.text_input("اسم المستخدم (Username)", value="ubuntu")

st.divider()

c3, c4 = st.columns(2)
with c3:
    num_servers = st.number_input("عدد السيرفرات (Number of servers)", min_value=1, max_value=20, value=1)
with c4:
    # القيمة الافتراضية 5 ثواني وهي الوقت المثالي لـ OVH Cloud
    pause_sec = st.number_input(
        "المدة الزمنية بين كل سيرفر وسيرفر (افتراضي مثالي: 5 ثواني)",
        min_value=0, 
        max_value=60, 
        value=5,
        help="5 ثواني هي أفضل مدة لضمان عدم رفض الطلبات المتتالية من طرف OVH"
    )

create_btn = st.button("🚀 بدء إنشاء السيرفرات", type="primary", use_container_width=True)

if create_btn:
    flv_obj = flavor_map[selected_flavor]
    img_obj = image_map[selected_image]

    flavor_id = flv_obj.get("id")
    image_id = img_obj.get("id")
    
    # Cloud-Init script
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

    if selected_ssh != "بدون SSH Key" and selected_ssh in ssh_map:
        payload_base["sshKeyId"] = ssh_map[selected_ssh].get("id")

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

        if i < num_servers - 1 and pause_sec > 0:
            st.write(f"⏳ الانتظار لمدة {pause_sec} ثواني قبل السيرفر القادم...")
            time.sleep(pause_sec)

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
