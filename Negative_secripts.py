import email
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from bs4 import BeautifulSoup

import streamlit as st

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(
    page_title="Multi-Source Unstoppable Extractor",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Multi-Source Text Extractor")
st.write(
    "Extract clean texts directly into the browser with a 1-click Copy button."
)

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
})


# ==========================================
# 2. Helper Functions
# ==========================================
def is_valid_html_url(url):
  url_lower = url.lower()
  bad_exts = [
      ".pdf",
      ".doc",
      ".docx",
      ".xls",
      ".xlsx",
      ".ppt",
      ".pptx",
      ".zip",
      ".gz",
      ".png",
      ".jpg",
      ".jpeg",
      ".mp4",
  ]
  if any(url_lower.endswith(ext) or ext in url_lower for ext in bad_exts):
    return False
  bad_domains = [
      "bing.com",
      "yahoo.com",
      "duckduckgo.com",
      "google.com",
      "yimg.com",
      "youtube.com",
      "facebook.com",
  ]
  if any(domain in url_lower for domain in bad_domains):
    return False
  return True


def clean_text_strictly(raw_text):
  clean_lines = []
  for line in raw_text.splitlines():
    line_str = line.strip()

    if len(line_str) < 30:
      continue
    if any(
        kw in line_str.lower()
        for kw in [
            "javascript",
            "function(",
            "var ",
            "const ",
            "document.",
            "{",
            "}",
            "<",
            ">",
            "==",
        ]
    ):
      continue

    sanitized_line = re.sub(r'[^a-zA-Z0-9\s.,!?\'"\-\–\—]', "", line_str)
    sanitized_line = " ".join(sanitized_line.split())

    if len(sanitized_line) > 25:
      clean_lines.append(sanitized_line)

  if clean_lines:
    return "\n".join(clean_lines[:50])
  return None


def extract_clean_text_from_url(url):
  try:
    res = session.get(url, timeout=8)
    if res.status_code != 200 or "text/html" not in res.headers.get(
        "Content-Type", ""
    ).lower():
      return None

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup([
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "form",
        "aside",
        "noscript",
        "svg",
        "iframe",
        "button",
    ]):
      tag.decompose()

    paragraphs = soup.find_all("p")
    raw_text = (
        "\n".join([p.get_text() for p in paragraphs])
        if paragraphs
        else soup.get_text(separator="\n")
    )

    return clean_text_strictly(raw_text)
  except Exception:
    return None


def search_ddg_lite(query, max_results=20):
  links = []
  try:
    url = "https://lite.duckduckgo.com/lite/"
    data = {"q": query}
    res = session.post(url, data=data, timeout=8)
    if res.status_code == 200:
      soup = BeautifulSoup(res.text, "html.parser")
      for a in soup.find_all("a", class_="result-snippet"):
        href = a.get("href", "")
        if href.startswith("//"):
          href = "https:" + href
        if (
            href.startswith("http")
            and is_valid_html_url(href)
            and href not in links
        ):
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
      for item in root.findall(".//item"):
        link = (
            item.find("link").text if item.find("link") is not None else None
        )
        if link and is_valid_html_url(link):
          links.append(link)
          if len(links) >= max_results:
            break
  except Exception:
    pass
  return links


def fetch_wikimedia_family(domain, query, target_count):
  texts = []
  try:
    search_url = f"https://en.{domain}.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&srlimit={target_count*2}&format=json"
    res = session.get(search_url, timeout=8)
    if res.status_code == 200:
      items = res.json().get("query", {}).get("search", [])
      for item in items:
        if len(texts) >= target_count:
          break
        pid = item.get("pageid")
        if not pid:
          continue
        content_url = f"https://en.{domain}.org/w/api.php?action=query&prop=extracts&explaintext=1&pageids={pid}&format=json"
        c_res = session.get(content_url, timeout=8)
        if c_res.status_code == 200:
          pages = c_res.json().get("query", {}).get("pages", {})
          pdata = pages.get(str(pid), {})
          raw_extract = pdata.get("extract", "")
          cleaned = clean_text_strictly(raw_extract)
          if cleaned:
            texts.append(cleaned)
        time.sleep(0.1)
  except Exception:
    pass
  return texts


def fetch_arxiv_abstracts(query, target_count):
  texts = []
  try:
    url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={target_count}"
    res = session.get(url, timeout=8)
    if res.status_code == 200:
      root = ET.fromstring(res.content)
      ns = {"atom": "http://www.w3.org/2005/Atom"}
      for entry in root.findall("atom:entry", ns):
        summary = entry.find("atom:summary", ns)
        if summary is not None and summary.text:
          cleaned = clean_text_strictly(summary.text)
          if cleaned:
            texts.append(cleaned)
  except Exception:
    pass
  return texts


def fetch_wiki_random_article():
  try:
    url = "https://en.wikipedia.org/w/api.php?action=query&generator=random&grnnamespace=0&prop=extracts&explaintext=1&grnlimit=1&format=json"
    res = session.get(url, timeout=8)
    if res.status_code == 200:
      pages = res.json().get("query", {}).get("pages", {})
      for pid, pdata in pages.items():
        raw_extract = pdata.get("extract", "")
        return clean_text_strictly(raw_extract)
  except Exception:
    pass
  return None


def generate_similar_queries(original_kw):
  clean_kw = re.sub(
      r"^(dear|hi|hello|mr|mrs|ms)\s+", "", original_kw, flags=re.IGNORECASE
  ).strip()
  variations = [
      original_kw,
      clean_kw,
      f"letter {clean_kw}",
      f"about {clean_kw}",
      f"story {clean_kw}",
      f"history of {clean_kw}",
      "personal letter email",
      "english prose text essay",
  ]
  return list(dict.fromkeys([v for v in variations if v]))


# ==========================================
# 3. Streamlit User Interface
# ==========================================
col1, col2 = st.columns(2)

with col1:
  user_input = st.text_input(
      "Keywords (comma separated):",
      placeholder="e.g. artificial intelligence, space exploration",
  )
  target_count = st.number_input(
      "Results per keyword:", min_value=1, max_value=100, value=10, step=1
  )

with col2:
  enable_extended = st.checkbox(
      "Enable Extended Sources (News, Wikibooks, ArXiv)", value=True
  )

st.markdown("---")

# ==========================================
# 4. Process & Output
# ==========================================
if st.button("🚀 Start Extraction", type="primary"):
  keywords = [kw.strip() for kw in user_input.split(",") if kw.strip()]

  if not keywords:
    st.error("Please enter at least one keyword.")
  else:
    status_box = st.empty()
    progress_bar = st.progress(0)

    extracted_results = []
    total_expected = len(keywords) * target_count
    current_total = 0

    for kw in keywords:
      status_box.info(f"Processing Keyword: '{kw}'...")

      saved_for_kw = 0
      visited_urls = set()
      similar_queries = generate_similar_queries(kw)

      # 1. DDG Search
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

          text = extract_clean_text_from_url(url)
          if text:
            extracted_results.append(text)
            saved_for_kw += 1
            current_total += 1
            progress_bar.progress(min(current_total / total_expected, 1.0))
            status_box.info(
                f"Extracted: {current_total}/{total_expected} texts..."
            )
          time.sleep(0.1)

      # 2. Google News RSS
      if enable_extended and saved_for_kw < target_count:
        news_urls = search_google_news_rss(kw, target_count - saved_for_kw)
        for url in news_urls:
          if saved_for_kw >= target_count:
            break
          if url in visited_urls:
            continue
          visited_urls.add(url)
          text = extract_clean_text_from_url(url)
          if text:
            extracted_results.append(text)
            saved_for_kw += 1
            current_total += 1
            progress_bar.progress(min(current_total / total_expected, 1.0))
            status_box.info(
                f"Extracted: {current_total}/{total_expected} texts..."
            )
          time.sleep(0.1)

      # 3. Wikibooks / Wikiquote
      if enable_extended and saved_for_kw < target_count:
        for domain in ["wikibooks", "wikiquote"]:
          if saved_for_kw >= target_count:
            break
          w_texts = fetch_wikimedia_family(
              domain, kw, target_count - saved_for_kw
          )
          for wt in w_texts:
            if saved_for_kw >= target_count:
              break
            extracted_results.append(wt)
            saved_for_kw += 1
            current_total += 1
            progress_bar.progress(min(current_total / total_expected, 1.0))

      # 4. ArXiv
      if enable_extended and saved_for_kw < target_count:
        arxiv_texts = fetch_arxiv_abstracts(kw, target_count - saved_for_kw)
        for at in arxiv_texts:
          if saved_for_kw >= target_count:
            break
          extracted_results.append(at)
          saved_for_kw += 1
          current_total += 1
          progress_bar.progress(min(current_total / total_expected, 1.0))

      # 5. Wikipedia
      if saved_for_kw < target_count:
        wiki_texts = fetch_wikimedia_family(
            "wikipedia", kw, target_count - saved_for_kw
        )
        for wt in wiki_texts:
          if saved_for_kw >= target_count:
            break
          extracted_results.append(wt)
          saved_for_kw += 1
          current_total += 1
          progress_bar.progress(min(current_total / total_expected, 1.0))

      # 6. Fallback
      if saved_for_kw < target_count:
        retry_count = 0
        while saved_for_kw < target_count and retry_count < 20:
          r_text = fetch_wiki_random_article()
          if r_text:
            extracted_results.append(r_text)
            saved_for_kw += 1
            current_total += 1
            progress_bar.progress(min(current_total / total_expected, 1.0))
          else:
            retry_count += 1
          time.sleep(0.1)

    progress_bar.progress(1.0)
    status_box.success(
        f"✅ Finished! Successfully extracted {len(extracted_results)} text(s)."
    )

    # Output Block
    final_output = "\n\n__SEP__\n\n".join(extracted_results)
    st.subheader("📋 Output Results")
    st.caption(
        "Click the Copy button on the top-right corner of the code block:"
    )
    st.code(final_output, language="text")
