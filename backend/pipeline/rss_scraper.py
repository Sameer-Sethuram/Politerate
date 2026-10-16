"""
rss_link_scraper.py

Fetches top-story article links from multiple news outlets using RSS feeds.
Filters out videos, podcasts, and (for non–Google News feeds) articles not
published today. Each link is tagged with its region: "us" (U.S. news) or
"world" (world news).

Outlets without a usable RSS feed are read through Google News RSS search
(news.google.com/rss/search?q=site:<domain>), whose links are resolved back
to the publisher's own URL before scraping.
"""

import json
import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote, urlparse

import feedparser
import requests

from backend.config import TIMEZONE, site_now

# ------------------------------------------------------------
# RSS FEEDS (Top Stories Only)
# ------------------------------------------------------------

US = "us"
WORLD = "world"
# Mixed feeds: articles whose URL section names no region (sports, odd
# news...) are skipped. See region_from_url.
BY_SECTION = "by_section"

# Categories. Political news is the site's core. Health, tech and business
# articles are clustered with everything else but only go on to credibility
# analysis and summarizing if their story is widely covered or about policy
# (summarizer.gate_genre_topics).
POLITICS = "politics"
HEALTH = "health"
TECH = "tech"
BUSINESS = "business"


def google_news_feed(domain: str) -> str:
    """Google News RSS search for one outlet's last day of articles."""
    query = quote(f"site:{domain} when:1d")
    return f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@dataclass(frozen=True)
class Feed:
    source: str  # outlet label shown in the app
    # US or WORLD: the region for articles whose URL section doesn't say
    # (an article's URL section wins, so a world feed's /us-news/ story is
    # U.S. news). BY_SECTION: only articles whose URL section says.
    region: str
    url: str
    # The category for articles whose URL section doesn't say (an article's
    # URL section wins, so a politics feed's /business/ story is business).
    category: str = POLITICS
    # A policy subsection (e.g. The Hill's /policy/healthcare/): its articles
    # count as policy news.
    policy: bool = False


# Checked 2026-10-13. Not included because their article pages reject every
# scraper request (401/403 bot checks), even when found through Google News:
# AP News, Reuters, Politico.
FEEDS = [
    # --- Original outlets ---
    Feed("Fox", US, "https://moxie.foxnews.com/google-publisher/politics.xml"),
    Feed("Fox", WORLD, "https://moxie.foxnews.com/google-publisher/world.xml"),
    Feed("NBC", US, "https://feeds.nbcnews.com/nbcnews/public/politics"),
    Feed("NBC", WORLD, "https://feeds.nbcnews.com/nbcnews/public/world"),
    Feed("NY Post", US, "https://nypost.com/politics/feed/"),
    Feed("NY Post", US, "https://nypost.com/us-news/feed/"),
    Feed("NY Post", WORLD, "https://nypost.com/world-news/feed/"),
    Feed("CBS", US, "https://www.cbsnews.com/latest/rss/politics"),
    Feed("CBS", WORLD, "https://www.cbsnews.com/latest/rss/world"),
    Feed("ABC", US, "https://abcnews.com/abcnews/politicsheadlines"),
    Feed("ABC", WORLD, "https://abcnews.com/abcnews/internationalheadlines"),
    Feed("Guardian", US, "https://www.theguardian.com/us-news/us-politics/rss"),
    Feed("Guardian", WORLD, "https://www.theguardian.com/world/rss"),
    # Wire service, replacing AP (no official feed). Mixed feed; only its
    # Top_News/US and Top_News/World-News sections are kept.
    Feed("UPI", BY_SECTION, "https://rss.upi.com/news/top_news.rss"),

    # --- Expanded coverage ---
    # Center / mainstream
    # Article pages are bot-blocked; scraper.py fetches them via Google's AMP cache.
    Feed("The Hill", US, "https://thehill.com/feed/"),
    Feed("The Hill", WORLD, "https://thehill.com/policy/international/feed/"),
    Feed("CS Monitor", US, "https://rss.csmonitor.com/feeds/usa"),
    Feed("CS Monitor", WORLD, "https://rss.csmonitor.com/feeds/world"),
    Feed("PBS NewsHour", US, "https://www.pbs.org/newshour/feeds/rss/politics"),
    Feed("PBS NewsHour", WORLD, "https://www.pbs.org/newshour/feeds/rss/world"),
    Feed("BBC", US, "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
    Feed("BBC", WORLD, "https://feeds.bbci.co.uk/news/world/rss.xml"),
    Feed("Deseret News", US, "https://www.deseret.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"),
    # International outlet; its URLs carry no region, so all of it counts as world news.
    Feed("Al Jazeera", WORLD, "https://www.aljazeera.com/xml/rss/all.xml"),
    # Center-left
    Feed("NPR", US, "https://feeds.npr.org/1014/rss.xml"),
    Feed("NPR", WORLD, "https://feeds.npr.org/1004/rss.xml"),
    Feed("The Independent", US, "https://www.independent.co.uk/news/world/americas/us-politics/rss"),
    Feed("The Independent", WORLD, "https://www.independent.co.uk/news/world/rss"),
    # CNN stopped publishing RSS in 2024. Site-wide Google News results; only
    # its /politics/, /us/ and /world/ sections are kept. (Google News can't
    # search one section, so CNN has no health, tech or business feeds.)
    Feed("CNN", BY_SECTION, google_news_feed("cnn.com")),

    # --- Health, tech and business (checked 2026-10-15) ---
    # Not included: UPI's health and science feeds and CS Monitor's tech feed
    # (nothing new since 2025), CS Monitor's economy feed (404), The Hill's
    # finance feed (empty), Deseret's business feed (mostly sports and faith).
    Feed("Fox", US, "https://moxie.foxnews.com/google-publisher/health.xml", HEALTH),
    Feed("Fox", US, "https://moxie.foxnews.com/google-publisher/tech.xml", TECH),
    # Fox Business, labelled Fox so one company's two sites count as one outlet.
    Feed("Fox", US, "https://moxie.foxbusiness.com/google-publisher/latest.xml", BUSINESS),
    Feed("NBC", US, "https://feeds.nbcnews.com/nbcnews/public/health", HEALTH),
    Feed("NBC", US, "https://feeds.nbcnews.com/nbcnews/public/tech", TECH),
    Feed("NBC", US, "https://feeds.nbcnews.com/nbcnews/public/business", BUSINESS),
    Feed("NY Post", US, "https://nypost.com/health/feed/", HEALTH),
    Feed("NY Post", US, "https://nypost.com/tech/feed/", TECH),
    Feed("NY Post", US, "https://nypost.com/business/feed/", BUSINESS),
    Feed("CBS", US, "https://www.cbsnews.com/latest/rss/health", HEALTH),
    Feed("CBS", US, "https://www.cbsnews.com/latest/rss/technology", TECH),
    Feed("CBS", US, "https://www.cbsnews.com/latest/rss/moneywatch", BUSINESS),
    Feed("ABC", US, "https://abcnews.com/abcnews/healthheadlines", HEALTH),
    Feed("ABC", US, "https://abcnews.com/abcnews/technologyheadlines", TECH),
    Feed("ABC", US, "https://abcnews.com/abcnews/moneyheadlines", BUSINESS),
    Feed("Guardian", WORLD, "https://www.theguardian.com/society/health/rss", HEALTH),
    Feed("Guardian", US, "https://www.theguardian.com/us-news/healthcare/rss", HEALTH, policy=True),
    Feed("Guardian", US, "https://www.theguardian.com/us/technology/rss", TECH),
    Feed("Guardian", US, "https://www.theguardian.com/us/business/rss", BUSINESS),
    Feed("UPI", BY_SECTION, "https://rss.upi.com/news/business_news.rss", BUSINESS),
    Feed("The Hill", US, "https://thehill.com/policy/healthcare/feed/", HEALTH, policy=True),
    Feed("The Hill", US, "https://thehill.com/policy/technology/feed/", TECH, policy=True),
    Feed("The Hill", US, "https://thehill.com/business/feed/", BUSINESS),
    Feed("PBS NewsHour", US, "https://www.pbs.org/newshour/feeds/rss/health", HEALTH),
    Feed("PBS NewsHour", US, "https://www.pbs.org/newshour/feeds/rss/economy", BUSINESS),
    Feed("BBC", WORLD, "https://feeds.bbci.co.uk/news/health/rss.xml", HEALTH),
    Feed("BBC", WORLD, "https://feeds.bbci.co.uk/news/technology/rss.xml", TECH),
    Feed("BBC", WORLD, "https://feeds.bbci.co.uk/news/business/rss.xml", BUSINESS),
    Feed("NPR", US, "https://feeds.npr.org/1128/rss.xml", HEALTH),
    Feed("NPR", US, "https://feeds.npr.org/1027/rss.xml", HEALTH, policy=True),  # Healthcare
    Feed("NPR", US, "https://feeds.npr.org/1019/rss.xml", TECH),
    Feed("NPR", US, "https://feeds.npr.org/1006/rss.xml", BUSINESS),
    Feed("NPR", US, "https://feeds.npr.org/1017/rss.xml", BUSINESS),  # Economy
    Feed("The Independent", WORLD, "https://www.independent.co.uk/news/health/rss", HEALTH),
    Feed("The Independent", WORLD, "https://www.independent.co.uk/tech/rss", TECH),
    Feed("The Independent", WORLD, "https://www.independent.co.uk/news/business/rss", BUSINESS),
]

# URL sections that mark an article's region, checked in order.
_REGION_SECTIONS = [
    (re.compile(r"/(us-politics|us-news|us|politics|nation|national)/", re.IGNORECASE), US),
    (re.compile(r"/(world|world-news|international|uk-news)/", re.IGNORECASE), WORLD),
]
# Outlets whose sections mean something else, checked before _REGION_SECTIONS.
_REGION_SECTIONS_BY_HOST = {
    # U.S. politics is under /us-news/; /politics/ is UK politics.
    "theguardian.com": [(re.compile(r"/politics/"), WORLD)],
    # U.S. news is filed under /news/world/americas/ (about four in five of
    # its articles there are U.S. stories); UK news under /news/uk/.
    "independent.co.uk": [(re.compile(r"/news/uk/"), WORLD), (re.compile(r"/news/world/americas/"), US)],
}


def region_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    for pattern, region in _REGION_SECTIONS_BY_HOST.get(host, []) + _REGION_SECTIONS:
        if pattern.search(parsed.path):
            return region
    return None


# URL sections that mark an article's category, checked in order (so The
# Hill's /policy/healthcare/ is health). Sections naming none (CBS's /news/,
# BBC's /news/articles/...) leave the feed's category.
_CATEGORY_SECTIONS = [
    (re.compile(r"/(health|healthcare|health_news|wellness)/", re.IGNORECASE), HEALTH),
    (re.compile(r"/(tech|technology)/", re.IGNORECASE), TECH),
    (re.compile(r"/(business|economy|moneywatch|money|markets|personal-finance)/", re.IGNORECASE), BUSINESS),
    (re.compile(r"/(politics|us-politics|homenews)/", re.IGNORECASE), POLITICS),
]
_POLICY_SECTION = re.compile(r"/(policy|politics)/", re.IGNORECASE)


def category_from_url(url: str) -> Optional[str]:
    path = urlparse(url).path
    for pattern, category in _CATEGORY_SECTIONS:
        if pattern.search(path):
            return category
    return None


def is_policy_url(url: str) -> bool:
    return bool(_POLICY_SECTION.search(urlparse(url).path))

# ------------------------------------------------------------
# Google News link resolution
# ------------------------------------------------------------

# Google News RSS links point at news.google.com/rss/articles/<id>, not the
# publisher. Resolving one takes two requests (the article page carries a
# signature; the batchexecute endpoint trades it for the real URL), so
# results are cached for the life of the process and resolutions per feed
# are capped.
MAX_GOOGLE_NEWS_ENTRIES = 50
_GOOGLE_NEWS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
}
_google_news_urls: dict[str, Optional[str]] = {}
_google_news_session = requests.Session()
# Google News lists some stories under more than one host for the same page.
_CANONICAL_HOSTS = {"edition.cnn.com": "www.cnn.com"}


def resolve_google_news_url(link: str) -> Optional[str]:
    """Publisher URL for a Google News article link, or None if it can't be
    resolved."""
    if link in _google_news_urls:
        return _google_news_urls[link]
    url = None
    try:
        article_id = urlparse(link).path.rsplit("/", 1)[-1]
        page = _google_news_session.get(
            f"https://news.google.com/rss/articles/{article_id}",
            headers=_GOOGLE_NEWS_HEADERS, timeout=15,
        )
        signature = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        timestamp = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if signature and timestamp:
            request = json.dumps([
                "garturlreq",
                [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None,
                  None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                article_id, int(timestamp.group(1)), signature.group(1),
            ])
            response = _google_news_session.post(
                "https://news.google.com/_/DotsSplashUi/data/batchexecute",
                headers={**_GOOGLE_NEWS_HEADERS,
                         "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                data={"f.req": json.dumps([[["Fbv4je", request, None, "generic"]]])},
                timeout=15,
            )
            for line in response.text.splitlines():
                if line.startswith('[["wrb.fr"'):
                    url = json.loads(json.loads(line)[0][2])[1]
                    break
        if url:
            parts = urlparse(url)
            if parts.netloc in _CANONICAL_HOSTS:
                url = parts._replace(netloc=_CANONICAL_HOSTS[parts.netloc]).geturl()
    except Exception as e:
        print(f"[Google News] could not resolve {link[:80]}: {e}")
    if len(_google_news_urls) > 5000:
        _google_news_urls.clear()
    _google_news_urls[link] = url
    return url

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
    """Published today on the site's clock. On the server's own clock (UTC)
    the day turned over at 8 p.m. Eastern, and the evening's runs kept only
    articles published after that."""
    if dt is None:
        return False
    return dt.astimezone(TIMEZONE).date() == site_now().date()

# ------------------------------------------------------------
# URL Filtering
# ------------------------------------------------------------

def is_video_url(url):
    return (
        "/video/" in url or
        "/videos/" in url or
        "/shorts/" in url or
        re.search(r"/\d+$", url) is not None
    )

def is_podcast_url(url):
    return "/programs/" in url or "/podcasts/" in url or "/audio/" in url

def is_google_news_entry(entry):
    # Older Google News feeds used tag: ids; current ones only show in the link.
    return (
        entry.get("id", "").startswith("tag:news.google.com")
        or urlparse(entry.get("link", "")).netloc == "news.google.com"
    )

# ------------------------------------------------------------
# RSS Fetching
# ------------------------------------------------------------

# feedparser.parse(url) downloads with no timeout, so one feed that stops
# responding would hang the hourly run (and every run after it) forever.
FEED_TIMEOUT_SECONDS = 15


def download_feed(url):
    """The parsed feed at `url`, or an empty one if it can't be fetched in
    time. Sent with feedparser's own User-Agent, as when it downloaded."""
    try:
        response = requests.get(
            url, headers={"User-Agent": feedparser.USER_AGENT}, timeout=FEED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[RSS] could not fetch {url[:80]}: {e}")
        return feedparser.parse(b"")
    # Its headers carry the charset, which feedparser decodes with.
    headers = {k.lower(): v for k, v in response.headers.items()}
    return feedparser.parse(response.content, response_headers=headers)


def fetch_rss_feed(url, region=US, category=POLITICS, policy=False):
    feed = download_feed(url)
    articles = []
    seen = set()
    google_news_resolved = 0

    for entry in feed.entries:
        gnews = is_google_news_entry(entry)

        # 1. Resolve Google News redirect FIRST
        link = entry.link
        if gnews:
            if google_news_resolved >= MAX_GOOGLE_NEWS_ENTRIES:
                continue
            google_news_resolved += 1
            link = resolve_google_news_url(link)
            if not link:
                continue

        # Links end up in the site's pages, where a javascript: one would
        # run when clicked.
        if urlparse(link).scheme not in ("http", "https"):
            continue

        # 2. Filter podcasts AFTER redirect
        if is_podcast_url(link):
            continue

        # 3. Filter videos
        if is_video_url(link):
            continue

        # 4. Region: the URL section's if it names one, else the feed's
        #    (mixed feeds skip articles whose section doesn't say)
        article_region = region_from_url(link) or (region if region != BY_SECTION else None)
        if article_region is None:
            continue

        # 5. Apply date filtering ONLY to non-Google News (its search is
        #    already limited to the last day)
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
            "region": article_region,
            "category": category_from_url(link) or category,
            "policy": policy or is_policy_url(link),
            "published": entry.get("published"),
            "summary": entry.get("summary")
        })

    return articles

# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def get_feed_links() -> tuple[dict[str, list[str]], dict[str, dict]]:
    """Today's links from every feed: ({source: [urls]},
    {url: {"region", "category", "policy"}}).

    A URL listed by several feeds with no section in its URL to decide (e.g.
    BBC's U.S. & Canada and World feeds, or CBS's politics and health feeds)
    counts as U.S. news over world news, and political news over health,
    tech or business; it's policy news if any listing says so.
    """
    links_by_source: dict[str, list[str]] = {}
    meta_by_url: dict[str, dict] = {}
    for feed in FEEDS:
        print(f"Fetching RSS for {feed.source} ({feed.category}, {feed.region})...")
        urls = links_by_source.setdefault(feed.source, [])
        for entry in fetch_rss_feed(feed.url, feed.region, feed.category, feed.policy):
            link = entry["link"]
            meta = meta_by_url.get(link)
            if meta is None:
                urls.append(link)
                meta_by_url[link] = {k: entry[k] for k in ("region", "category", "policy")}
                continue
            if entry["region"] == US:
                meta["region"] = US
            if entry["category"] == POLITICS:
                meta["category"] = POLITICS
            meta["policy"] = meta["policy"] or entry["policy"]
    return links_by_source, meta_by_url

def get_all_top_story_links():
    return get_feed_links()[0]

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
