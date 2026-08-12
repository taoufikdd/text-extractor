import re
import time
import urllib.parse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st

st.set_page_config(
    page_title="Advanced Text Extractor Tool",
    page_icon="📝",
    layout="wide"
)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
})

st.sidebar.header("⚙️ Extraction Settings")
extraction_mode = st.sidebar.radio(
    "Choose Output Format:",
    ("Text with Domains & Links", "Clean Text Only")
)

def has_domain_or_link(text):
    pattern = r'(https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b)'
    return bool(re.search(pattern, text))

def is_valid_html_url(url):
    url_lower = url.lower()
    bad_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.gz', '.png', '.jpg', '.jpeg', '.mp4']
    if any(url_lower.endswith(ext) or ext in url_lower for ext in bad_exts):
        return False
    bad_domains = ['bing.com', 'yahoo.com', 'duckduckgo.com', 'google.com', 'yimg.com', 'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']
    if any(domain in url_lower for domain in bad_domains):
        return False
    return True

def clean_text_strictly(raw_text, mode, force_dear_prefix=False):
    clean_lines = []
    preserve_links = (mode == "Text with Domains & Links")
    
    for line in raw_text.splitlines():
        line_str = line.strip()
        if len(line_str) < 20:
            continue
        if any(kw in line_str.lower() for kw in ['javascript', 'function(', 'var ', 'const ', 'document.', '{', '}', '<', '>', '==']):
            continue

        if preserve_links:
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—:/\?%&=#@\_]', '', line_str)
        else:
            line_str = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b', '', line_str)
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—]', '', line_str)

        sanitized_line = ' '.join(sanitized_line.split())
        if len(sanitized_line) > 15:
            clean_lines.append(sanitized_line)
            
    if not clean_lines:
        return None
        
    full_text = '\n'.join(clean_lines[:50])

    if force_dear_prefix:
        first_part = full_text[:150].lower()
        if not any(w in first_part for w in ['dear', 'hi', 'hello', 'greetings', 'welcome']):
            return None

    if preserve_links and not has_domain_or_link(full_text):
        return None

    return full_text

def extract_content_from_url(url, mode, force_dear=False):
    try:
        res = session.get(url, timeout=6)
        if res.status_code != 200 or 'text/html' not in res.headers.get('Content-Type', '').lower():
            return None
            
        soup = BeautifulSoup(res.text, 'html.parser')
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript", "svg", "iframe", "button"]):
            tag.decompose()
            
        if mode == "Text with Domains & Links":
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http') and not any(bd in href for bd in ['facebook', 'twitter', 'instagram']):
                    a.replace_with(f" {a.get_text()} ({href}) ")

        paragraphs = soup.find_all('p')
        raw_text = "\n".join([p.get_text() for p in paragraphs]) if paragraphs else soup.get_text(separator='\n')
        
        return clean_text_strictly(raw_text, mode, force_dear_prefix=force_dear)
    except Exception:
        return None

def search_ddg_html(query, max_results=15):
    links = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        res = session.get(url, timeout=7)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a', class_='result__url'):
                href = a.get('href', '').strip()
                if href.startswith('//'):
                    href = 'https:' + href
                elif href.startswith('/l/?uddg='):
                    href = urllib.parse.unquote(href.split('/l/?uddg=')[1].split('&')[0])
                
                if href.startswith('http') and is_valid_html_url(href) and href not in links:
                    links.append(href)
                    if len(links) >= max_results:
                        break
    except Exception:
        pass
    return links

def extract_queries_from_sample_text(sample_text):
    queries = []
    if "dear" in sample_text.lower():
        queries.append('dear students handbook website')
        queries.append('dear parents elementary school letter')
        queries.append('welcome to our school principal letter')
    
    queries.extend([
        'school handbook principal letter website',
        'elementary school student handbook dear parents',
        'school principal welcoming letter website'
    ])
    return list(dict.fromkeys(queries))

# --- UI Streamlit ---

st.title("🚀 Advanced Web Text Extractor")

input_type = st.radio("Choose Search Method:", ("Keywords Mode", "Similar Text Reference Mode"))

force_dear_option = False
if input_type == "Keywords Mode":
    keywords_input = st.text_input("Enter Keywords (comma separated):", placeholder="e.g. dear Brian, dear Students")
    force_dear_option = st.checkbox("Require text to contain 'Dear / Hi / Welcome' near start", value=False)
else:
    sample_text_input = st.text_area("Paste Reference Text Here:", height=180, placeholder="Paste example letter/text here...")
    force_dear_option = st.checkbox("Require texts to contain greeting (Dear/Welcome) like sample", value=False)

target_count = st.number_input("Number of texts to extract:", min_value=1, max_value=200, value=10, step=5)

submitted = st.button("Start Extraction ⚡")

if submitted:
    search_queries = []
    
    if input_type == "Keywords Mode":
        keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
        if not keywords:
            st.error("Please enter at least one keyword.")
            st.stop()
        for kw in keywords:
            search_queries.append(f'{kw} website')
            search_queries.append(f'{kw} letter')
    else:
        if not sample_text_input.strip():
            st.error("Please paste a reference text first.")
            st.stop()
        search_queries = extract_queries_from_sample_text(sample_text_input)

    status_box = st.empty()
    progress_bar = st.progress(0)
    all_results = []
    visited_urls = set()
    
    total_q = len(search_queries)
    
    for idx, q in enumerate(search_queries):
        if len(all_results) >= target_count:
            break
            
        status_box.info(f"⏳ Searching web for: **'{q}'**...")
        
        urls = search_ddg_html(q, max_results=15)
        
        for url in urls:
            if len(all_results) >= target_count:
                break
            if url in visited_urls:
                continue
            visited_urls.add(url)
            
            res_data = extract_content_from_url(url, extraction_mode, force_dear=force_dear_option)
            if res_data:
                all_results.append(res_data)
            time.sleep(0.1)

        progress_bar.progress((idx + 1) / total_q)

    status_box.success(f"🎉 Process Complete! Total matching texts collected: **{len(all_results)}**")
    
    st.subheader("📋 Extracted Results Preview:")
    if not all_results:
        st.warning("No matching results found. Try unchecking the 'Require text to contain Dear/Welcome' checkbox.")
    else:
        for res in all_results[:10]:
            st.text_area("Result Preview", value=res, height=180)
        
        file_content = "\n\n__SEP__\n\n".join(all_results)
        st.download_button(
            label="📥 Download Negative.txt",
            data=file_content,
            file_name="Negative.txt",
            mime="text/plain"
        )
