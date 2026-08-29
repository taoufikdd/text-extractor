import streamlit as st
import ovh
import time

st.set_page_config(page_title="OVH Cloud Deployer", page_icon="⚡")

st.title("⚡ إنشاء سيرفر OVH تلقائياً")

# -----------------------------
# 1. إدخال المفاتيح فقط
# -----------------------------
with st.sidebar:
    st.header("🔑 مفاتيح OVH API")
    endpoint = st.selectbox("Endpoint", ["ovh-eu", "ovh-ca"], index=0)
    app_key = st.text_input("Application Key", type="password")
    app_secret = st.text_input("Application Secret", type="password")
    consumer_key = st.text_input("Consumer Key", type="password")

st.info("أدخل المفاتيح في القائمة الجانبية ثم اضغط على الزر لإنشاء السيرفر فوراً.")

# -----------------------------
# 2. زر الإنشاء التلقائي
# -----------------------------
if st.button("🚀 إنشاء السيرفر الآن", type="primary", use_container_width=True):
    if not all([app_key, app_secret, consumer_key]):
        st.error("الرجاء إدخال جميع مفاتيح API أولاً!")
        st.stop()

    try:
        with st.spinner("جاري الاتصال بـ OVH..."):
            # إنشاء عميل الاتصال
            client = ovh.Client(
                endpoint=endpoint,
                application_key=app_key.strip(),
                application_secret=app_secret.strip(),
                consumer_key=consumer_key.strip(),
            )

            # 1. جلب أول مشروع متوفر في الحساب
            projects = client.get("/cloud/project")
            if not projects:
                st.error("لم يتم العثور على أي مشروع Public Cloud في هذا الحساب.")
                st.stop()
            
            project_id = projects[0] # اختيار أول مشروع تلقائياً

            # 2. جلب SSH Key متوفر (أو الاعتماد على المفتاح الأول)
            ssh_keys = client.get(f"/cloud/project/{project_id}/sshkey")
            if not ssh_keys:
                st.error("لا يوجد SSH Key مسجل في حسابك. يرجى إضافة SSH Key في لوحة OVH أولاً.")
                st.stop()
            
            ssh_key_id = ssh_keys[0]["id"]

            # 3. جلب الأحجام والأنظمة المتوفرة واختيار الافتراضي
            flavors = client.get(f"/cloud/project/{project_id}/flavor", region="GRA7")
            images = client.get(f"/cloud/project/{project_id}/image", region="GRA7")

            # اختيار أول Flavor و Image مناسبة (يمكنك تحديد الاسم بوضوح)
            flavor_id = flavors[0]["id"] # أو ابحث عن نوع معين مثل b2-7
            image_id = images[0]["id"]   # أو ابحث عن Ubuntu 22.04 مثلاً

            # 4. إرسال أمر إنشاء السيرفر
            payload = {
                "name": "auto-created-server",
                "region": "GRA7", # يمكنك تغيير المنطقة هنا (مثلاً GRA7 أو SBG5)
                "flavorId": flavor_id,
                "imageId": image_id,
                "sshKeyId": ssh_key_id,
                "monthlyBilling": False # False = بالفرنك/الساعة (Hourly)
            }

            res = client.post(f"/cloud/project/{project_id}/instance", **payload)

        st.success("✅ تم إرسال أمر إنشاء السيرفر بنجاح!")
        st.json(res)

    except Exception as e:
        st.error(f"حدث خطأ أثناء الإنشاء: {e}")
