"""
rss_link_scraper.py

Fetches top-story article links from multiple news outlets using RSS feeds.
Filters out videos, podcasts, and (for non–Google News feeds) articles not
published today. Returns a dictionary mapping source → list of URLs.
"""

import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# RSS FEEDS (Top Stories Only)
# ------------------------------------------------------------

RSS_FEEDS = {
    "Fox": "https://moxie.foxnews.com/google-publisher/politics.xml",
    "NBC": "https://feeds.nbcnews.com/nbcnews/public/news",
    "NYPost - Politics": "https://nypost.com/feed/",
    "NYPost - US News": "https://nypost.com/us-news/feed/",
    "CBS": "https://www.cbsnews.com/latest/rss/politics",
    "ABC": "https://abcnews.go.com/abcnews/politicsheadlines",
    "Guardian": "https://www.theguardian.com/us-news/us-politics/rss"
}

# ------------------------------------------------------------
# Date Parsing
# ------------------------------------------------------------

def parse_date(entry):
    for field in ("published", "updated"):
        if field in entry:
            try:
                return parsedate_to_datetime(entry[field])
            except:
                pass
    return None

def is_today(dt):
    if dt is None:
        return False
    today = datetime.now().date()
    return dt.astimezone().date() == today

# ------------------------------------------------------------
# URL Filtering
# ------------------------------------------------------------

def is_video_url(url):
    return (
        "/video/" in url or
        "/shorts/" in url or
        re.search(r"/\d+$", url) is not None
    )

def is_podcast_url(url):
    return "/programs/" in url or "/podcasts/" in url

def is_google_news_entry(entry):
    return entry.get("id", "").startswith("tag:news.google.com")

# ------------------------------------------------------------
# RSS Fetching
# ------------------------------------------------------------

def fetch_rss_feed(url):
    feed = feedparser.parse(url)
    articles = []
    seen = set()

    for entry in feed.entries:
        raw_link = entry.link

        # 1. Resolve Google News redirect FIRST
        link = raw_link

        # 2. Filter podcasts AFTER redirect
        if is_podcast_url(link):
            continue

        # 3. Filter videos
        if is_video_url(link):
            continue

        # 4. Detect Google News entry
        gnews = is_google_news_entry(entry)

        # 5. Apply date filtering ONLY to non-Google News
        if not gnews:
            pub_date = parse_date(entry)
            if not is_today(pub_date):
                continue

        # 6. Deduplicate on FINAL URL
        if link in seen:
            continue
        seen.add(link)

        # 7. Append
        articles.append({
            "title": entry.title,
            "link": link,
            "published": entry.get("published"),
            "summary": entry.get("summary")
        })

    return articles

# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def get_all_top_story_links():
    all_links = {}
    for name, url in RSS_FEEDS.items():
        print(f"Fetching RSS for {name}...")
        entries = fetch_rss_feed(url)
        all_links[name] = [entry["link"] for entry in entries]
    return all_links

def nice_print_links(links_dict):
    for name, links in links_dict.items():
        print(f"\n{name} - {len(links)} links:")
        for link in links:
            print(f"  {link}")

# ------------------------------------------------------------
# Manual test
# ------------------------------------------------------------

if __name__ == "__main__":
    data = get_all_top_story_links()
    nice_print_links(data)