"""
webscraper.py

This module provides functions that take article links as input and scrape
full article content from each link. It compiles the results into a dictionary
mapping URLs to extracted article data.
"""

import json
from urllib.parse import urlparse

import requests
from newspaper import Article
from readability import Document
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsScraper/1.0)"
}

# Publishers whose article pages turn away scrapers but who publish AMP
# copies served by Google's AMP cache. Those copies are fetched instead; the
# stored URL stays the publisher's.
AMP_CACHE_HOSTS = {"thehill.com"}


def fetch_url_for(url):
    """Where to download `url` from: its AMP cache copy for AMP_CACHE_HOSTS,
    otherwise the URL itself."""
    parts = urlparse(url)
    if parts.netloc not in AMP_CACHE_HOSTS:
        return url
    cache_host = parts.netloc.replace("-", "--").replace(".", "-")
    return f"https://{cache_host}.cdn.ampproject.org/c/s/{parts.netloc}{parts.path.rstrip('/')}/amp/"

# ------------------------------------------------------------
# Basic HTML fetcher
# ------------------------------------------------------------

def fetch(url):
    """Download raw HTML from a URL with error handling."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[Fetch Error] {url}: {e}")
        return None

# ------------------------------------------------------------
# Bylines
# ------------------------------------------------------------

def _is_article_type(node):
    kinds = node.get("@type") or []
    kinds = kinds if isinstance(kinds, list) else [kinds]
    return any("Article" in str(k) or "Posting" in str(k) for k in kinds)


def authors_from_metadata(html):
    """The article's authors as its page declares them for search engines
    (JSON-LD "author" on the NewsArticle), or [] if it doesn't. More
    reliable than newspaper3k's guesses, which pick up job titles and bio
    sentences, and miss Fox, the Post, UPI, The Hill and The Independent."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    found, fallback = [], []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            stack = [json.loads(script.string or "")]
        except ValueError:
            continue
        while stack:
            node = stack.pop(0)
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                if "author" in node:
                    authors = node["author"] if isinstance(node["author"], list) else [node["author"]]
                    names = [a.get("name") if isinstance(a, dict) else a for a in authors]
                    # Only the article's own: pages also describe videos
                    # and related stories, each with its author.
                    (found if _is_article_type(node) else fallback).extend(
                        n for n in names if isinstance(n, str) and n.strip()
                    )
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    names = found or fallback
    return list(dict.fromkeys(" ".join(n.split()) for n in names))

# ------------------------------------------------------------
# Article extraction logic
# ------------------------------------------------------------

def extract_article(url):
    """
    Extract article content from a URL.
    Uses newspaper3k first, then readability as fallback.
    Returns a dictionary with article metadata.
    """
    download_url = fetch_url_for(url)

    # Try newspaper3k first
    try:
        article = Article(download_url)
        article.download()
        article.parse()

        return {
            "title": article.title,
            "text": article.text,
            "authors": authors_from_metadata(article.html) or article.authors,
            "publish_date": article.publish_date,
            "url": url
        }
    except Exception:
        pass  # Fall back to readability

    # Fallback: readability-lxml
    html = fetch(download_url)
    if not html:
        return None

    try:
        doc = Document(html)
        soup = BeautifulSoup(doc.summary(), "lxml")
        text = soup.get_text(separator="\n")

        return {
            "title": doc.title(),
            "text": text,
            "authors": authors_from_metadata(html),
            "publish_date": None,
            "url": url
        }
    except Exception as e:
        print(f"[Parse Error] {url}: {e}")
        return None

# ------------------------------------------------------------
# Batch scraping
# ------------------------------------------------------------

def scrape_articles(url_list):
    """
    Given a list of article URLs, scrape each one and return
    a dictionary mapping URL → article data.
    """
    results = {}

    for url in url_list:
        print(f"Scraping: {url}")
        article_data = extract_article(url)

        if article_data:
            results[url] = article_data
        else:
            print(f"  Failed to extract: {url}")

    return results

# ------------------------------------------------------------
# Optional: scrape grouped by source
# ------------------------------------------------------------

def scrape_articles_by_source(source_dict):
    """
    Accepts a dictionary like:
        { "NBC": [url1, url2], "CBS": [url3, url4] }

    Returns:
        { "NBC": {url1: {...}, url2: {...}}, "CBS": {...} }
    """
    all_results = {}

    for source, urls in source_dict.items():
        print(f"\n=== Scraping articles from {source} ===")
        all_results[source] = scrape_articles(urls)

    return all_results


# ------------------------------------------------------------
# Example usage (manual testing)
# ------------------------------------------------------------
if __name__ == "__main__":
    from backend.pipeline.rss_scraper import get_all_top_story_links
    test_links = get_all_top_story_links()
    data = scrape_articles_by_source(test_links)
    print(data)