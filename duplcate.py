import streamlit as st

st.set_page_config(page_title="Email Cleaner & Deduplicator", layout="wide")

st.title("📧 Email Cleaner & Deduplicator")
st.write("Uploadi les fichiers `.txt` dyalak bach t-filtri les emails ghir li jdad bla duplicate.")

col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("1. Fichier 1 (Emails Asliya / Base)", type=["txt"])

with col2:
    file2 = st.file_uploader("2. Fichier 2 (Emails li ghadyin n-filtriw)", type=["txt"])

if file1 and file2:
    if st.button("Start Processing 🚀", type="primary"):
        with st.spinner("Processing emails..."):
            # 1. Read Fichier 1 and convert to set for O(1) fast lookup
            # Processing line by line to handle large files efficiently
            emails_base = set()
            for line in file1:
                email = line.decode("utf-8", errors="ignore").strip().lower()
                if email:
                    emails_base.add(email)

            # 2. Process Fichier 2: Remove duplicates & remove emails present in Fichier 1
            result_emails = []
            seen_in_file2 = set()

            for line in file2:
                email = line.decode("utf-8", errors="ignore").strip().lower()
                if email and (email not in emails_base) and (email not in seen_in_file2):
                    seen_in_file2.add(email)
                    result_emails.append(email)

            # 3. Format the final output string
            result_text = "\n".join(result_emails)

        st.success(f"Done! Cleaned emails count: **{len(result_emails):,}**")

        # Display result & Download button
        col_res1, col_res2 = st.columns([2, 1])

        with col_res1:
            st.text_area("Result (Fichier 3):", value=result_text, height=300)

        with col_res2:
            st.write("### Download Result")
            st.download_button(
                label="📥 Download Fichier 3 (.txt)",
                data=result_text,
                file_name="clean_emails_result.txt",
                mime="text/plain"
            )