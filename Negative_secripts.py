import re
import time
import io
import xml.etree.ElementTree as ET
import urllib.parse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="Advanced Text Extractor Tool",
    page_icon="📝",
    layout="wide"
)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})

# --- القائمة الجانبية لاختيار نوع الاستخراج ---
st.sidebar.header("⚙️ Extraction Settings")
extraction_mode = st.sidebar.radio(
    "Choose Output Format:",
    ("Clean Text Only", "Text with Domains & Links")
)

def has_domain_or_link(text):
    """التحقق من وجود رابط أو دومين داخل النص"""
    pattern = r'(https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b)'
    return bool(re.search(pattern, text))

def is_valid_html_url(url):
    url_lower = url.lower()
    bad_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.gz', '.png', '.jpg', '.jpeg', '.mp4']
    if any(url_lower.endswith(ext) or ext in url_lower for ext in bad_exts):
        return False
    bad_domains = ['bing.com', 'yahoo.com', 'duckduckgo.com', 'google.com', 'yimg.com', 'youtube.com', 'facebook.com']
    if any(domain in url_lower for domain in bad_domains):
        return False
    return True

def clean_text_strictly(raw_text, mode, force_dear_prefix=False):
    clean_lines = []
    preserve_links = (mode == "Text with Domains & Links")
    
    for line in raw_text.splitlines():
        line_str = line.strip()
        if len(line_str) < 30:
            continue
        if any(kw in line_str.lower() for kw in ['javascript', 'function(', 'var ', 'const ', 'document.', '{', '}', '<', '>', '==']):
            continue

        if preserve_links:
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—:/\?%&=#@\_]', '', line_str)
        else:
            line_str = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b', '', line_str)
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—]', '', line_str)

        sanitized_line = ' '.join(sanitized_line.split())
        if len(sanitized_line) > 25:
            clean_lines.append(sanitized_line)
            
    if not clean_lines:
        return None
        
    full_text = '\n'.join(clean_lines[:50])

    # إذا اشترطنا تبدأ بـ Dear
    if force_dear_prefix and not re.match(r'^(dear|hi|hello|greetings)\b', full_text, re.IGNORECASE):
        return None

    # إذا كان وضع الروابط مفعلاً، نتحقق أن النص يحتوي فعلياً على رابط/دومين
    if preserve_links and not has_domain_or_link(full_text):
        return None

    return full_text

def extract_content_from_url(url, mode, force_dear=False):
    try:
        res = session.get(url, timeout=8)
        if res.status_code != 200 or 'text/html' not in res.headers.get('Content-Type', '').lower():
            return None
            
        soup = BeautifulSoup(res.text, 'html.parser')
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript", "svg", "iframe", "button"]):
            tag.decompose()
            
        if mode == "Text with Domains & Links":
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http'):
                    a.replace_with(f" {a.get_text()} ({href}) ")

        paragraphs = soup.find_all('p')
        raw_text = "\n".join([p.get_text() for p in paragraphs]) if paragraphs else soup.get_text(separator='\n')
        
        return clean_text_strictly(raw_text, mode, force_dear_prefix=force_dear)
    except Exception:
        return None

def search_ddg_lite(query, max_results=20):
    links = []
    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = {'q': query}
        res = session.post(url, data=data, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a', class_='result-snippet'):
                href = a.get('href', '')
                if href.startswith('//'):
                    href = 'https:' + href
                if href.startswith('http') and is_valid_html_url(href) and href not in links:
                    links.append(href)
                    if len(links) >= max_results:
                        break
    except Exception:
        pass
    return links

def search_google_news_rss(query, max_results=10):
    links = []
    try:
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        res = session.get(rss_url, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall('.//item'):
                link = item.find('link').text if item.find('link') is not None else None
                if link and is_valid_html_url(link):
                    links.append(link)
                    if len(links) >= max_results:
                        break
    except Exception:
        pass
    return links

def fetch_wikimedia_family(domain, query, target_count, mode, force_dear=False):
    results = []
    try:
        search_url = f"https://en.{domain}.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&srlimit={target_count*2}&format=json"
        res = session.get(search_url, timeout=8)
        if res.status_code == 200:
            items = res.json().get('query', {}).get('search', [])
            for item in items:
                if len(results) >= target_count:
                    break
                pid = item.get('pageid')
                if not pid:
                    continue
                content_url = f"https://en.{domain}.org/w/api.php?action=query&prop=extracts&explaintext=1&pageids={pid}&format=json"
                c_res = session.get(content_url, timeout=8)
                if c_res.status_code == 200:
                    pages = c_res.json().get('query', {}).get('pages', {})
                    pdata = pages.get(str(pid), {})
                    raw_extract = pdata.get('extract', '')
                    cleaned = clean_text_strictly(raw_extract, mode, force_dear_prefix=force_dear)
                    if cleaned:
                        results.append(cleaned)
                time.sleep(0.1)
    except Exception:
        pass
    return results

def fetch_arxiv_abstracts(query, target_count, mode, force_dear=False):
    results = []
    try:
        url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={target_count}"
        res = session.get(url, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                summary = entry.find('atom:summary', ns)
                if summary is not None and summary.text:
                    cleaned = clean_text_strictly(summary.text, mode, force_dear_prefix=force_dear)
                    if cleaned:
                        results.append(cleaned)
    except Exception:
        pass
    return results

def extract_queries_from_sample_text(sample_text):
    """استخراج استعلامات بحث ذكية من نص عينة متكامل"""
    queries = []
    first_line = sample_text.splitlines()[0] if sample_text else ""
    
    # التقاط البدايات الترحيبية مثل Dear Students, Dear Families...
    dear_match = re.search(r'(dear\s+[a-zA-Z0-9\s,]+)', first_line, re.IGNORECASE)
    if dear_match:
        queries.append(f'"{dear_match.group(1).strip()}" handbook letter')
        queries.append(f'"{dear_match.group(1).strip()}" website')
    
    # البحث عن الكلمات العالية الأهمية
    words = re.findall(r'\b[a-zA-Z]{5,}\b', sample_text.lower())
    common = {'students', 'families', 'school', 'handbook', 'education', 'learning', 'welcome', 'principal'}
    matched_words = [w for w in words if w in common]
    
    if matched_words:
        queries.append("Dear " + " ".join(list(set(matched_words))[:3]) + " website")
    
    queries.extend([
        '"Dear Students and Families" handbook',
        '"Dear Parents and Students" letter website',
        '"Welcome to our school" "http"',
        '"Sincerely" "Principal" handbook website'
    ])
    return list(dict.fromkeys(queries))

# --- واجهة المستخدم (Streamlit UI) ---

st.title("🚀 Advanced Web Text Extractor")

input_type = st.radio("Choose Search Method:", ("Keywords Mode", "Similar Text Reference Mode"))

force_dear_option = False
if input_type == "Keywords Mode":
    keywords_input = st.text_input("Enter Keywords (comma separated):", placeholder="e.g. dear Brian, dear Students")
    force_dear_option = st.checkbox("Force texts to start with 'Dear / Hi / Hello'", value=False)
else:
    sample_text_input = st.text_area("Paste Reference Text Here:", height=200, placeholder="Paste example letter/text here...")
    force_dear_option = st.checkbox("Require generated texts to start with 'Dear' (Like sample)", value=True)

target_count = st.number_input("Number of texts to extract:", min_value=1, max_value=200, value=20, step=5)

submitted = st.button("Start Extraction ⚡")

if submitted:
    search_queries = []
    
    if input_type == "Keywords Mode":
        keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
        if not keywords:
            st.error("Please enter at least one keyword.")
            st.stop()
        for kw in keywords:
            search_queries.append(kw)
            search_queries.append(f'"{kw}" website')
            search_queries.append(f'letter "{kw}"')
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
            
        status_box.info(f"⏳ Searching sources for query: **'{q}'**...")
        
        # 1. DuckDuckGo Lite
        urls = search_ddg_lite(q, max_results=15)
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

        # 2. Google News
        if len(all_results) < target_count:
            news_urls = search_google_news_rss(q, max_results=10)
            for url in news_urls:
                if len(all_results) >= target_count:
                    break
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                res_data = extract_content_from_url(url, extraction_mode, force_dear=force_dear_option)
                if res_data:
                    all_results.append(res_data)

        # 3. Wikibooks / Wikiquote
        if len(all_results) < target_count:
            for wiki_dom in ["wikibooks", "wikiquote"]:
                if len(all_results) >= target_count:
                    break
                w_texts = fetch_wikimedia_family(wiki_dom, q, 5, extraction_mode, force_dear=force_dear_option)
                for wt in w_texts:
                    if len(all_results) >= target_count:
                        break
                    all_results.append(wt)

        # 4. ArXiv Abstracts
        if len(all_results) < target_count:
            ar_texts = fetch_arxiv_abstracts(q, 5, extraction_mode, force_dear=force_dear_option)
            for at in ar_texts:
                if len(all_results) >= target_count:
                    break
                all_results.append(at)

        progress_bar.progress((idx + 1) / total_q)

    status_box.success(f"🎉 Process Complete! Total matching texts collected: **{len(all_results)}**")
    
    # المعاينة
    st.subheader("📋 Extracted Results Preview:")
    if not all_results:
        st.warning("No matching results found for these criteria. Try unchecking strict options or using broader keywords.")
    else:
        for res in all_results[:10]:
            st.text_area("Result Preview", value=res, height=180)
        
        # تجهيز ملف Negative.txt
        file_content = "\n\n__SEP__\n\n".join(all_results)
        st.download_button(
            label="📥 Download Negative.txt",
            data=file_content,
            file_name="Negative.txt",
            mime="text/plain"
        )
