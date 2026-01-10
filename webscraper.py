"""
webscraper.py

This module provides functions that take article links as input and scrape
full article content from each link. It compiles the results into a dictionary
mapping URLs to extracted article data.
"""

import requests
from newspaper import Article
from readability import Document
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsScraper/1.0)"
}

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
# Article extraction logic
# ------------------------------------------------------------

def extract_article(url):
    """
    Extract article content from a URL.
    Uses newspaper3k first, then readability as fallback.
    Returns a dictionary with article metadata.
    """
    # Try newspaper3k first
    try:
        article = Article(url)
        article.download()
        article.parse()

        return {
            "title": article.title,
            "text": article.text,
            "authors": article.authors,
            "publish_date": article.publish_date,
            "url": url
        }
    except Exception:
        pass  # Fall back to readability

    # Fallback: readability-lxml
    html = fetch(url)
    if not html:
        return None

    try:
        doc = Document(html)
        soup = BeautifulSoup(doc.summary(), "lxml")
        text = soup.get_text(separator="\n")

        return {
            "title": doc.title(),
            "text": text,
            "authors": [],
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
    test_links = [
        "https://apnews.com/article/iran-protests-us-israel-war-nuclear-economy-c867cd53c99585cc5e0cd98eafe95d16"
    ]
    data = scrape_articles(test_links)
    print(data)