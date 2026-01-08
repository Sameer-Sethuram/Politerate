# Uses RSS feeds to scrape links from different news websites, will feed into webscraper.py for article extraction
# Use current date and time, as well as whether the article is top story or not to be the condition for extracting the link from RSS feed

import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re

# Only include TOP STORY feeds — not category feeds
RSS_FEEDS = {
    # "AP": "https://apnews.com/rss",
    "NPR": "https://news.google.com/rss/search?q=when:24h+allinurl:npr.org&hl=en-US&gl=US&ceid=US:en",  # NPR Top Stories
    # "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "Fox": "https://moxie.foxnews.com/google-publisher/politics.xml",  # Fox Top Stories
    # "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "NBC": "https://feeds.nbcnews.com/nbcnews/public/news",  # NBC Top Stories
    # "ABC": "https://abcnews.go.com/abcnews/topstories",
    "NYPost - Politics": "https://nypost.com/feed/",  # NYPost Politics News
    "NYPost - US News": "https://nypost.com/us-news/feed/",  # NYPost US News
    "CBS": "https://www.cbsnews.com/latest/rss/politics",  # CBS Top Stories
    "AP": "https://news.google.com/rss/search?q=when:24h+allinurl:apnews.com&hl=en-US&gl=US&ceid=US:en" # AP US stories
}

def parse_date(entry):
    """
    Convert RSS 'published' or 'updated' fields into a timezone-aware datetime.
    Returns None if no valid date is found.
    """
    if "published" in entry:
        try:
            return parsedate_to_datetime(entry.published)
        except:
            pass

    if "updated" in entry:
        try:
            return parsedate_to_datetime(entry.updated)
        except:
            pass

    return None


def is_today(dt):
    """
    Check if a datetime is from the current day (UTC-normalized).
    """
    if dt is None:
        return False

    now = datetime.now().date()
    return dt.astimezone().date() == now

def is_video_url(url: str) -> bool:
    if "/video/" in url:
        return True
    if "/shorts/" in url:
        return True
    if re.search(r"/\d+$", url):  # ends with /123456789
        return True
    return False


def fetch_rss_feed(url):
    feed = feedparser.parse(url)
    articles = []

    for entry in feed.entries:
        link = entry.link

        # Skip video URLs
        if is_video_url(link):
            continue

        pub_date = parse_date(entry)
        if not is_today(pub_date):
            continue

        articles.append({
            "title": entry.title,
            "link": link,
            "published": pub_date.isoformat() if pub_date else None,
            "summary": entry.get("summary")
        })

    return articles


def get_all_top_story_links():
    """
    Fetch all RSS feeds and return only today's top-story links.
    """
    all_links = {}

    for name, url in RSS_FEEDS.items():
        print(f"Fetching RSS for {name}...")
        entries = fetch_rss_feed(url)
        links = [entry["link"] for entry in entries]
        all_links[name] = links

    return all_links

def nice_print_links(links_dict):
    for name, links in links_dict.items():
        print(f"\n{name} - {len(links)} links:")
        for link in links:
            print(f"  {link}")

if __name__ == "__main__":
    data = get_all_top_story_links()
    nice_print_links(data)