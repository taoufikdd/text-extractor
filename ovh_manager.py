import streamlit as st
import ovh
import time

st.set_page_config(
    page_title="OVHcloud Public Cloud Manager",
    page_icon="☁️",
    layout="wide",
)

st.title("☁️ OVHcloud Public Cloud Manager")
st.caption("Single-instance deployment and basic management for normal infrastructure administration.")

# -----------------------------
# OVH API client
# -----------------------------
def get_client(endpoint, application_key, application_secret, consumer_key):
    return ovh.Client(
        endpoint=endpoint,
        application_key=application_key.strip(),
        application_secret=application_secret.strip(),
        consumer_key=consumer_key.strip(),
    )

def api_call(client, method, path, **kwargs):
    return getattr(client, method)(path, **kwargs)

# -----------------------------
# Sidebar: credentials
# -----------------------------
with st.sidebar:
    st.header("OVHcloud API")

    endpoint = st.selectbox(
        "Endpoint",
        ["ovh-eu", "ovh-ca"],
        index=0,
        help="Use the endpoint matching your OVHcloud account.",
    )

    application_key = st.text_input("Application Key", type="password")
    application_secret = st.text_input("Application Secret", type="password")
    consumer_key = st.text_input("Consumer Key", type="password")

    connect = st.button("Connect", type="primary", use_container_width=True)

if connect:
    if not all([application_key, application_secret, consumer_key]):
        st.error("Enter Application Key, Application Secret and Consumer Key.")
        st.stop()

    try:
        client = get_client(
            endpoint,
            application_key,
            application_secret,
            consumer_key,
        )

        projects = client.get("/cloud/project")
        st.session_state["ovh_client"] = client
        st.session_state["projects"] = projects
        st.success(f"Connected. {len(projects)} Public Cloud project(s) found.")
    except Exception as e:
        st.error(f"Connection failed: {e}")

client = st.session_state.get("ovh_client")
projects = st.session_state.get("projects", [])

if not client:
    st.info("Enter your OVHcloud API credentials in the sidebar and click Connect.")
    st.stop()

if not projects:
    st.warning("No Public Cloud project was returned by the API.")
    st.stop()

# -----------------------------
# Select project
# -----------------------------
project = st.selectbox(
    "Public Cloud Project",
    projects,
    format_func=lambda x: str(x),
)

# -----------------------------
# Load project configuration
# -----------------------------
@st.cache_data(ttl=120)
def load_config(endpoint, application_key, application_secret, consumer_key, project_id):
    c = get_client(
        endpoint,
        application_key,
        application_secret,
        consumer_key,
    )

    regions = c.get(f"/cloud/project/{project_id}/region")
    flavors = c.get(f"/cloud/project/{project_id}/flavor")
    images = c.get(f"/cloud/project/{project_id}/image")
    sshkeys = c.get(f"/cloud/project/{project_id}/sshkey")

    return regions, flavors, images, sshkeys

try:
    regions, flavors, images, sshkeys = load_config(
        endpoint,
        application_key,
        application_secret,
        consumer_key,
        project,
    )
except Exception as e:
    st.error(f"Could not load project configuration: {e}")
    st.stop()

# -----------------------------
# Normalize API objects
# -----------------------------
def label_region(x):
    return f"{x.get('name', x.get('region', 'unknown'))}"

def label_flavor(x):
    name = x.get("name", x.get("id", "unknown"))
    vcpu = x.get("vcpus", x.get("vcore", "?"))
    ram = x.get("ram", "?")
    return f"{name} | {vcpu} vCPU | {ram} MB"

def label_image(x):
    name = x.get("name", x.get("id", "unknown"))
    version = x.get("version", "")
    return f"{name} {version}".strip()

def label_ssh(x):
    return x.get("name", x.get("id", "unknown"))

region_names = [label_region(x) for x in regions]
flavor_names = [label_flavor(x) for x in flavors]
image_names = [label_image(x) for x in images]
ssh_names = [label_ssh(x) for x in sshkeys]

if not region_names or not flavor_names or not image_names:
    st.error("OVHcloud returned incomplete region/flavor/image data.")
    st.stop()

region_by_name = {label_region(x): x for x in regions}
flavor_by_name = {label_flavor(x): x for x in flavors}
image_by_name = {label_image(x): x for x in images}
ssh_by_name = {label_ssh(x): x for x in sshkeys}

# -----------------------------
# Create instance
# -----------------------------
st.subheader("🚀 Create Instance")

c1, c2 = st.columns(2)

with c1:
    selected_region = st.selectbox("Region", region_names)
    selected_flavor = st.selectbox("Flavor", flavor_names)

with c2:
    selected_image = st.selectbox("Operating System / Image", image_names)
    selected_ssh = st.selectbox(
        "SSH Key",
        ssh_names if ssh_names else ["No SSH key available"],
    )

instance_name = st.text_input(
    "Instance Name",
    value="ovh-server-01",
)

billing_period = st.selectbox(
    "Billing Period",
    ["hourly", "monthly"],
)

create_btn = st.button(
    "Create Instance",
    type="primary",
    use_container_width=True,
)

if create_btn:
    try:
        region_obj = region_by_name[selected_region]
        flavor_obj = flavor_by_name[selected_flavor]
        image_obj = image_by_name[selected_image]

        region = region_obj.get("name") or region_obj.get("region")
        flavor_id = flavor_obj.get("id") or flavor_obj.get("name")
        image_id = image_obj.get("id")

        if not region or not flavor_id or not image_id:
            st.error("Could not determine region/flavor/image identifiers.")
            st.stop()

        if not ssh_names:
            st.error("An SSH key is required for a normal Linux instance.")
            st.stop()

        ssh_obj = ssh_by_name[selected_ssh]
        ssh_name = ssh_obj.get("name")

        payload = {
            "billingPeriod": billing_period,
            "bootFrom": {
                "imageId": image_id,
            },
            "flavor": {
                "id": flavor_id,
            },
            "name": instance_name.strip(),
            "network": {
                "public": True,
            },
            "sshKey": {
                "name": ssh_name,
            },
        }

        with st.spinner("Creating instance..."):
            result = client.post(
                f"/cloud/project/{project}/region/{region}/instance",
                **payload,
            )

        st.success("Instance creation request submitted.")
        st.json(result)

        time.sleep(2)
        st.rerun()

    except Exception as e:
        st.error(f"Creation failed: {e}")

# -----------------------------
# Server list
# -----------------------------
st.divider()
st.subheader("🖥️ Instances")

try:
    instances = client.get(f"/cloud/project/{project}/instance")
except Exception as e:
    st.error(f"Could not load instances: {e}")
    st.stop()

if not instances:
    st.info("No instances found.")
else:
    for inst in instances:
        iid = inst.get("id")
        name = inst.get("name", "Unnamed")
        region = inst.get("region", "")
        status = inst.get("status", "")
        ip = inst.get("ipAddresses") or inst.get("ipAddresses", [])

        with st.container(border=True):
            a, b, c, d = st.columns([2, 1, 1, 1])

            with a:
                st.markdown(f"**{name}**")
                st.caption(f"ID: {iid}")

            with b:
                st.write(f"Region: {region}")

            with c:
                st.write(f"Status: {status}")

            with d:
                if st.button("🗑️ Delete", key=f"delete_{iid}"):
                    try:
                        client.delete(
                            f"/cloud/project/{project}/region/{region}/instance/{iid}"
                        )
                        st.success(f"Deleted {name}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

            if ip:
                st.write("IP:", ip)

st.caption(
    "This manager uses OVHcloud Public Cloud APIs. It intentionally does not configure SMTP, "
    "bulk-mailing, or port-unblocking behavior."
)
