import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="MD5 Extractor & Merger", layout="wide")

st.title("⚡ MD5 Hash Extractor & Merger")
st.write("رفع ملفات CSV ضخمة لاستخراج أعمدة الـ MD5 (Status) وجمعها كاملة فـ ملف نصي واحد.")

uploaded_files = st.file_uploader(
    "اختار ولا جر ملفات CSV هنا (يمكن اختيار عدة ملفات ضخمة)", 
    type=["csv"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"تم اختيار {len(uploaded_files)} ملف(ات). اضغط على الزر لتحضير الملف الموحد.")
    
    if st.button("🚀 استخراج وجمع الـ MD5 Hash"):
        all_md5_hashes = set()  # set كيحيد التكرار تلقائياً وكيقتصد الذاكرة
        total_rows = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"جاري معالجة: {uploaded_file.name} ...")
            
            try:
                # القراءة بـ Chunks مفيدة بزاف للملفات الكبيرة باش الـ RAM ما يعمرش
                chunk_size = 100000  # قراءة 100 ألف سطر فكل دفعة
                for chunk in pd.read_csv(uploaded_file, chunksize=chunk_size, low_memory=False, dtype=str):
                    
                    # البحث على عمود Status أو MD5
                    target_col = None
                    for col in chunk.columns:
                        clean_col = str(col).strip().lower()
                        if clean_col in ['status', 'md5']:
                            target_col = col
                            break
                    
                    if target_col:
                        # استخراج القيم، مسح الفراغات، وتصفية الصفوف الخاوية
                        hashes = chunk[target_col].dropna().str.strip()
                        # تصفية القيم غير الفارغة
                        hashes = hashes[hashes != ""]
                        
                        total_rows += len(hashes)
                        all_md5_hashes.update(hashes)
                    else:
                        st.error(f"لم يتم العثور على عمود 'Status' أو 'MD5' في الملف {uploaded_file.name}")
                        break
                        
            except Exception as e:
                st.error(f"خطأ أثناء معالجة الملف {uploaded_file.name}: {e}")
            
            # تحديث شريط التقدم
            progress_bar.progress((idx + 1) / len(uploaded_files))
        
        status_text.text("تمت المعالجة بنجاح!")
        
        st.success(f"✅ تم استخراج {len(all_md5_hashes):,} MD5 فريد (Unique) من أصل {total_rows:,} مجموع السطور.")
        
        # تحويل النتيجة لملف نصي (سطر لكل MD5)
        output_data = "\n".join(all_md5_hashes)
        
        st.download_button(
            label="📥 تحميل الملف الموحد (all_md5_list.txt)",
            data=output_data,
            file_name="all_md5_list.txt",
            mime="text/plain"
        )