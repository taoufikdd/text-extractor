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
    page_title="Text Extractor Tool",
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

def clean_text_strictly(raw_text, mode):
    clean_lines = []
    preserve_links = (mode == "Text with Domains & Links")
    
    for line in raw_text.splitlines():
        line_str = line.strip()
        if len(line_str) < 30:
            continue
        if any(kw in line_str.lower() for kw in ['javascript', 'function(', 'var ', 'const ', 'document.', '{', '}', '<', '>', '==']):
            continue

        if preserve_links:
            # الاحتفاظ بالروابط والدومينات الطبيعية داخل النص
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—:/\?%&=#@\_]', '', line_str)
        else:
            # مسح الروابط والدومينات تماماً من داخل النص
            line_str = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}\b', '', line_str)
            sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—]', '', line_str)

        sanitized_line = ' '.join(sanitized_line.split())
        
        if len(sanitized_line) > 25:
            clean_lines.append(sanitized_line)
            
    if not clean_lines:
        return None
        
    full_text = '\n'.join(clean_lines[:50])

    # إذا كان وضع الروابط مفعلاً، نتحقق أن النص يحتوي فعلياً على رابط/دومين وإلا نرفضه
    if preserve_links and not has_domain_or_link(full_text):
        return None

    return full_text

def extract_content_from_url(url, mode):
    try:
        res = session.get(url, timeout=8)
        if res.status_code != 200 or 'text/html' not in res.headers.get('Content-Type', '').lower():
            return None
            
        soup = BeautifulSoup(res.text, 'html.parser')
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript", "svg", "iframe", "button"]):
            tag.decompose()
            
        # تحويل عناوين الروابط HTML إلى نصوص ظاهرة تحتوي على الرابط نفسه
        if mode == "Text with Domains & Links":
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http'):
                    a.replace_with(f" {a.get_text()} ({href}) ")

        paragraphs = soup.find_all('p')
        raw_text = "\n".join([p.get_text() for p in paragraphs]) if paragraphs else soup.get_text(separator='\n')
        
        return clean_text_strictly(raw_text, mode)
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

def fetch_wikimedia_family(domain, query, target_count, mode):
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
                    cleaned = clean_text_strictly(raw_extract, mode)
                    if cleaned:
                        results.append(cleaned)
                time.sleep(0.1)
    except Exception:
        pass
    return results

def fetch_arxiv_abstracts(query, target_count, mode):
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
                    cleaned = clean_text_strictly(summary.text, mode)
                    if cleaned:
                        results.append(cleaned)
    except Exception:
        pass
    return results

def fetch_wiki_random_article(mode):
    try:
        url = "https://en.wikipedia.org/w/api.php?action=query&generator=random&grnnamespace=0&prop=extracts&explaintext=1&grnlimit=1&format=json"
        res = session.get(url, timeout=8)
        if res.status_code == 200:
            pages = res.json().get('query', {}).get('pages', {})
            for pid, pdata in pages.items():
                raw_extract = pdata.get('extract', '')
                return clean_text_strictly(raw_extract, mode)
    except Exception:
        pass
    return None

def generate_similar_queries(original_kw):
    clean_kw = re.sub(r'^(dear|hi|hello|mr|mrs|ms)\s+', '', original_kw, flags=re.IGNORECASE).strip()
    variations = [
        original_kw,
        clean_kw,
        f"letter {clean_kw}",
        f"about {clean_kw}",
        f"website {clean_kw}",
        f"official site {clean_kw}",
        "personal letter email website",
        "english prose text links"
    ]
    return list(dict.fromkeys([v for v in variations if v]))

# --- واجهة المستخدم (Streamlit UI) ---

st.title("🚀 Web Text Extractor Tool")
st.markdown("Extract pure, clean English text for your keywords automatically.")

with st.form("extractor_form"):
    keywords_input = st.text_input("Enter Keywords (comma separated):", placeholder="e.g. dear Brian, dear Olivia")
    target_count = st.number_input("Number of texts per keyword:", min_value=1, max_value=200, value=20, step=5)
    enable_extended = st.checkbox("Enable Extended Sources (Google News, Wikibooks, ArXiv)", value=True)
    
    submitted = st.form_submit_button("Start Extraction ⚡")

if submitted:
    keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
    if not keywords:
        st.error("Please enter at least one valid keyword.")
    else:
        status_box = st.empty()
        progress_bar = st.progress(0)
        
        all_results = []
        total_keywords = len(keywords)
        
        for idx, kw in enumerate(keywords):
            status_box.info(f"⏳ Extracting texts for: **'{kw}'**...")
            saved_for_kw = 0
            visited_urls = set()
            similar_queries = generate_similar_queries(kw)
            
            # DDG
            for current_query in similar_queries:
                if saved_for_kw >= target_count:
                    break
                urls = search_ddg_lite(current_query, target_count - saved_for_kw)
                for url in urls:
                    if saved_for_kw >= target_count:
                        break
                    if url in visited_urls:
                        continue
                    visited_urls.add(url)
                    res_data = extract_content_from_url(url, extraction_mode)
                    if res_data:
                        all_results.append(res_data)
                        saved_for_kw += 1
                    time.sleep(0.1)

            # Extended - Google News
            if enable_extended and saved_for_kw < target_count:
                news_urls = search_google_news_rss(kw, target_count - saved_for_kw)
                for url in news_urls:
                    if saved_for_kw >= target_count:
                        break
                    if url in visited_urls:
                        continue
                    visited_urls.add(url)
                    res_data = extract_content_from_url(url, extraction_mode)
                    if res_data:
                        all_results.append(res_data)
                        saved_for_kw += 1

            # Extended - Wikimedia
            if enable_extended and saved_for_kw < target_count:
                for domain in ["wikibooks", "wikiquote"]:
                    if saved_for_kw >= target_count:
                        break
                    w_texts = fetch_wikimedia_family(domain, kw, target_count - saved_for_kw, extraction_mode)
                    for wt in w_texts:
                        if saved_for_kw >= target_count:
                            break
                        all_results.append(wt)
                        saved_for_kw += 1

            # Extended - ArXiv
            if enable_extended and saved_for_kw < target_count:
                arxiv_texts = fetch_arxiv_abstracts(kw, target_count - saved_for_kw, extraction_mode)
                for at in arxiv_texts:
                    if saved_for_kw >= target_count:
                        break
                    all_results.append(at)
                    saved_for_kw += 1

            # Wiki
            if saved_for_kw < target_count:
                wiki_texts = fetch_wikimedia_family("wikipedia", kw, target_count - saved_for_kw, extraction_mode)
                for wt in wiki_texts:
                    if saved_for_kw >= target_count:
                        break
                    all_results.append(wt)
                    saved_for_kw += 1

            # Fallback - Random Wiki
            if saved_for_kw < target_count:
                retry_count = 0
                while saved_for_kw < target_count and retry_count < 50:
                    r_text = fetch_wiki_random_article(extraction_mode)
                    if r_text:
                        all_results.append(r_text)
                        saved_for_kw += 1
                    else:
                        retry_count += 1
                    time.sleep(0.1)

            progress_bar.progress((idx + 1) / total_keywords)

        status_box.success(f"🎉 Extraction Completed! Total items collected: **{len(all_results)}**")
        
        # عرض النتائج مباشرة داخل الصفحة
        st.subheader("📋 Extracted Output Preview:")
        for res in all_results[:10]:
            st.text_area("Result Preview", value=res, height=150)
        
        # تجهيز ملف Negative.txt للتنزيل المباشر
        file_content = "\n\n__SEP__\n\n".join(all_results)
        
        st.download_button(
            label="📥 Download Negative.txt",
            data=file_content,
            file_name="Negative.txt",
            mime="text/plain"
        )
