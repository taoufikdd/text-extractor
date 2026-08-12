import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
import streamlit as st

# استيراد googlesearch
try:
    from googlesearch import search as google_search
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

st.set_page_config(
    page_title="Advanced Web Text Extractor Tool",
    page_icon="📝",
    layout="wide"
)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
})

st.sidebar.header("⚙️ Extraction Settings")

# 1. إضافة اختيار محرك البحث
search_engine_choice = st.sidebar.radio(
    "Choose Search Engine:",
    ("Google (Primary)", "Auto (Google + DuckDuckGo Fallback)", "DuckDuckGo Only")
)

extraction_mode = st.sidebar.radio(
    "Choose Output Format:",
    ("Text with Domains & Links", "Clean Text Only")
)

def is_valid_html_url(url):
    url_lower = url.lower()
    bad_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.gz', '.png', '.jpg', '.jpeg', '.mp4']
    if any(url_lower.endswith(ext) or ext in url_lower for ext in bad_exts):
        return False
    bad_domains = ['google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com', 'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']
    if any(domain in url_lower for domain in bad_domains):
        return False
    return True

def clean_text_strictly(raw_text, mode):
    clean_lines = []
    preserve_links = (mode == "Text with Domains & Links")
    
    for line in raw_text.splitlines():
        line_str = line.strip()
        if len(line_str) < 15:
            continue
        if any(kw in line_str.lower() for kw in ['javascript', 'function(', 'var ', 'const ', 'document.', '{', '}', '<', '>', '==']):
            continue

        if preserve_links:
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—:/\?%&=#@\_]', '', line_str)
        else:
            line_str = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b', '', line_str)
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—]', '', line_str)

        sanitized_line = ' '.join(sanitized_line.split())
        if len(sanitized_line) > 10:
            clean_lines.append(sanitized_line)
            
    if not clean_lines:
        return None
        
    full_text = '\n'.join(clean_lines[:40])
    return full_text

def extract_content_from_url(url, mode):
    try:
        res = session.get(url, timeout=6)
        if res.status_code != 200 or 'text/html' not in res.headers.get('Content-Type', '').lower():
            return None
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        if mode == "Text with Domains & Links":
            for a in soup.find_all('a', href=True):
                href = a['href']
                anchor_text = a.get_text().strip()
                if href.startswith('http') and not any(bd in href for bd in ['facebook', 'twitter', 'instagram']):
                    a.replace_with(f" {anchor_text} ({href}) ")

        for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript", "svg", "iframe", "button"]):
            tag.decompose()

        paragraphs = soup.find_all(['p', 'div', 'article'])
        raw_text = "\n".join([p.get_text() for p in paragraphs]) if paragraphs else soup.get_text(separator='\n')
        
        return clean_text_strictly(raw_text, mode)
    except Exception:
        return None

# --- محركات البحث ---

def search_google(query, max_results=10):
    """البحث المباشر عبر Google"""
    links = []
    if not HAS_GOOGLE:
        return links
    try:
        for url in google_search(query, num_results=max_results, lang="en"):
            if is_valid_html_url(url) and url not in links:
                links.append(url)
    except Exception:
        pass
    return links

def search_ddg_html(query, max_results=15):
    """البحث عبر DuckDuckGo"""
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

def fetch_search_results(query, engine_setting, max_results=10):
    """دالة توجيه البحث على حسب الاختيار"""
    urls = []
    if engine_setting == "Google (Primary)":
        urls = search_google(query, max_results)
    elif engine_setting == "DuckDuckGo Only":
        urls = search_ddg_html(query, max_results)
    else: # Auto (Google + Fallback)
        urls = search_google(query, max_results)
        if not urls: # إذا Google عطى 0 نتائج بسباب البلوك، كيدوز لـ DDG
            urls = search_ddg_html(query, max_results)
    return urls

def extract_queries_from_sample_text(sample_text):
    queries = []
    clean_sample = sample_text.strip()
    
    if len(clean_sample) < 40:
        queries.append(f'{clean_sample}')
        queries.append(f'{clean_sample} website')
        queries.append(f'{clean_sample} school')
    else:
        lines = [l.strip() for l in clean_sample.splitlines() if len(l.strip()) > 10]
        if lines:
            queries.append(f'"{lines[0][:30]}"')
            queries.append(lines[0][:40])

    queries.extend([
        'dear students school handbook',
        'dear parents elementary school',
        'welcome students principal letter'
    ])
    return list(dict.fromkeys(queries))

# --- UI Streamlit ---

st.title("🚀 Advanced Web Text Extractor")

input_type = st.radio("Choose Search Method:", ("Keywords Mode", "Similar Text Reference Mode"))

if input_type == "Keywords Mode":
    keywords_input = st.text_input("Enter Keywords (comma separated):", placeholder="e.g. dear Brian, dear Students")
else:
    sample_text_input = st.text_area("Paste Reference Text Here:", height=150, placeholder="Paste example letter/text here...")

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
            search_queries.append(f'{kw}')
            search_queries.append(f'{kw} website')
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
            
        status_box.info(f"⏳ Searching ({search_engine_choice}) for: **'{q}'**...")
        
        urls = fetch_search_results(q, search_engine_choice, max_results=10)
        
        for url in urls:
            if len(all_results) >= target_count:
                break
            if url in visited_urls:
                continue
            visited_urls.add(url)
            
            res_data = extract_content_from_url(url, extraction_mode)
            if res_data:
                all_results.append(res_data)
            time.sleep(0.3)

        progress_bar.progress((idx + 1) / total_q)

    status_box.success(f"🎉 Process Complete! Total matching texts collected: **{len(all_results)}**")
    
    st.subheader("📋 Extracted Results Preview:")
    if not all_results:
        st.warning("No matching results found. Try broader keywords or change search engine.")
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
