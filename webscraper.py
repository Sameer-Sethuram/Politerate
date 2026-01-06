### This python script will be used to scrape data from a website and save it to a CSV file.

import requests
from requests.exceptions import RequestException

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsScraper/1.0)"
}

def fetch(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except RequestException as e:
        print(f"Fetch error for {url}: {e}")
        return None
    
from newspaper import Article
from readability import Document
from bs4 import BeautifulSoup

def extract_article(url):
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
    except:
        # Fallback using readability
        html = fetch(url)
        if not html:
            return None
        
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
    
from urllib.parse import urljoin
from bs4 import BeautifulSoup

def parse_homepage_generic(html, link_selector, base_url):
    soup = BeautifulSoup(html, "lxml")
    links = set()

    for tag in soup.select(link_selector):
        href = tag.get("href")
        if not href:
            continue

        # Convert relative URLs to absolute
        full_url = urljoin(base_url, href)

        # Optionally skip obviously bad links (javascript:, mailto:, etc.)
        if full_url.startswith("http"):
            links.add(full_url)

    return list(links)

NEWS_SITES = {
    "AP": {
        "url": "https://apnews.com",
        "selector": "a[data-key='card-headline']"
    },
    "NPR": {
        "url": "https://www.npr.org",
        "selector": "h3.title a"
    },
    "Reuters": {
        "url": "https://www.reuters.com",
        "selector": "a.story-title, a.media-story-card__heading__link"
    },
    "Fox": {
        "url": "https://www.foxnews.com",
        "selector": "h2.title a"
    }
}

def get_top_story_links(site_config):
    html = fetch(site_config["url"])
    if not html:
        return []
    return parse_homepage_generic(html, site_config["selector"], site_config["url"])

def scrape_site(name, config):
    print(f"\nScraping {name}...")
    links = get_top_story_links(config)
    print(f"  Found {len(links)} raw links for {name}")
    if not links:
        print(f"  No links found for {name} with selector: {config['selector']}")
        return []

    articles = []
    for link in links[:10]:  # limit to top 10
        print(f"  Extracting: {link}")
        article = extract_article(link)
        if article:
            articles.append(article)

    print(f"  Finished {name}: {len(articles)} articles extracted")
    return articles


def scrape_all_sites():
    all_articles = {}

    for name, config in NEWS_SITES.items():
        articles = scrape_site(name, config)
        all_articles[name] = articles

    return all_articles

if __name__ == "__main__":
    data = scrape_all_sites()
    print(data)