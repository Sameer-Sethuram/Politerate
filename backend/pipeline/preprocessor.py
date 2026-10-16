"""
preprocessor.py

Prepares scraped article text for the summarizer pipeline:
- Cleans and normalizes text
- Validates article quality
- Splits title from body
- Truncates to model token limit (`text`, for clustering and summarizing),
  keeping the whole article as well (`full_text`, stored, shown and analyzed)
"""

import json
import re
import unicodedata
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 200
# `text` is cut to BART's input window (about 4,000 characters). Clustering
# was tuned on it and summaries are budgeted by its length, so both keep
# using the cut text.
MAX_TOKENS = 1024
# `full_text` is the whole article: what's stored, shown and analyzed. Capped
# (about 20,000 characters, ~3,300 words) for pages like live blogs that run
# far longer than any article, since analysis time grows with length.
FULL_TEXT_MAX_TOKENS = 5000

_BOILERPLATE = re.compile(
    r"(subscribe|sign[\s-]?up|log[\s-]?in|already a (subscriber|member)|"
    r"create (an? )?account|newsletter|click here|read more|continue reading|"
    r"share (this|on)|follow us|all rights reserved|copyright \d{4}|"
    r"terms of (use|service)|privacy policy|cookie(s)?|advertisement|"
    r"skip to (content|main)|you('ve)? reached your|free article|"
    r"get unlimited access|support (our|independent) journalism|"
    r"this article (is|was) (originally )?published|contributed to this report|"
    # AP's notice on wire stories, and Fox's market-data footer
    r"may not be published, broadcast|quotes displayed in real[\s-]?time|market data provided by)",
    re.IGNORECASE,
)

# Photo credits like "(AP Photo/J. Scott Applewhite)" or "(Kevin Dietsch/Getty Images)"
_PHOTO_CREDIT = re.compile(r"\s*\([^()]{0,80}\b(?:Photo|Getty Images|Pool)\b[^()]{0,80}\)")

# Lines shorter than this (in words) that aren't mid-paragraph get dropped
_MIN_LINE_WORDS = 5

# Bylines kept per article; more is a list scraped from a page section, not
# the article's authors.
MAX_AUTHORS = 4
_MAX_AUTHOR_WORDS = 5
_MAX_AUTHOR_CHARS = 60
# What newspaper3k picks up around bylines that isn't a name: page
# furniture, job titles, and the rest of a bio ("Politics Reporter",
# "Based In Washington", "Read Full Bio").
_NOT_A_NAME = re.compile(
    r"(\d|@|https?:|\b(share|facebook|twitter|email|icon|close|follow|subscribe|"
    r"sign up|click|image|photo|getty|updated|published|read more|more stories|bio|"
    r"based in|reporter|correspondent|editor|writer|producer|contributor|columnist|"
    r"analyst|anchor|host)\b)",
    re.IGNORECASE,
)
# "Casey Wooten Is A Breaking News Editor For ...": newspaper3k takes bios
# for bylines; the name is the part before "is a".
_BIO = re.compile(r"^(.+?)\s+is\s+an?\s+", re.IGNORECASE)
# Several authors in one byline: "A, B and C", "A & B", "A | B".
_BYLINE_SEPARATORS = re.compile(r"\s*,\s*|\s+and\s+|\s*&\s*|\s*\|\s*", re.IGNORECASE)
# A wire service credited after the reporter: "BECKY BOHRER Associated Press".
_TRAILING_AGENCY = re.compile(r"^(.+?)\s+((?:The\s+)?Associated Press|Reuters|AFP)$", re.IGNORECASE)
# Outlets' long names, by the short label they go by here, for spotting an
# outlet crediting itself ("The Christian Science Monitor" on CS Monitor).
_OUTLET_LONG_NAMES = {
    "csmonitor": "christiansciencemonitor",
    "nypost": "newyorkpost",
    "upi": "unitedpressinternational",
}


def _is_all_caps(line: str) -> bool:
    """ALL-CAPS lines are inline link teasers / promos ("CLICK HERE TO GET THE
    FOX NEWS APP", "TRUMP SAYS HE WILL ..."), never article prose."""
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.8


def _strip_boilerplate_lines(text: str) -> str:
    """Remove lines that are standalone boilerplate (short or matching known patterns)."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        word_count = len(stripped.split())
        if word_count < _MIN_LINE_WORDS and _BOILERPLATE.search(stripped):
            continue
        if _BOILERPLATE.search(stripped) and stripped.endswith((".", "→", "»", "›")):
            continue
        if _is_all_caps(stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = unicodedata.normalize("NFKC", text)

    # Strip common scraper artifacts: bracketed image captions, URLs inline
    text = re.sub(r"\[(\d+|image|photo|video|gallery|caption)[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", "", text)
    text = _PHOTO_CREDIT.sub("", text)

    text = _strip_boilerplate_lines(text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^[ \t]+|[ \t]+$", "", text, flags=re.MULTILINE)

    return text.strip()


def _outlet_key(name: str) -> str:
    return re.sub(r"\b(the|news|newshour|staff)\b|[^a-z]", "", name.lower())


def _is_outlet(name: str, source: str) -> bool:
    """True for a byline that's the outlet itself ("Abc News" on ABC, "Al
    Jazeera Staff"): the site shows the outlet next to the byline anyway."""
    key, outlet = _outlet_key(name), _outlet_key(source or "")
    return bool(key) and key in (outlet, _OUTLET_LONG_NAMES.get(outlet))


def _proper_case(name: str) -> str:
    """ALL-CAPS words in names title-cased ("BECKY BOHRER"); short ones
    like "AP" or "CNN" are left as they are."""
    return " ".join(w.capitalize() if w.isupper() and len(w) > 3 else w for w in name.split())


def clean_authors(authors, source: str = "") -> list[str]:
    """The article's authors, from the page's metadata or newspaper3k's
    guesses (a list, or the JSON list the download cache stores): bylines
    split into one name each, with job titles, bios, page furniture and the
    outlet crediting itself left out."""
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except ValueError:
            authors = [authors]
    if not isinstance(authors, list):
        return []

    candidates = []
    for raw in authors:
        byline = " ".join(str(raw).split())
        bio = _BIO.match(byline)
        if bio:
            byline = bio.group(1)
        for part in _BYLINE_SEPARATORS.split(byline):
            agency = _TRAILING_AGENCY.match(part)
            candidates.extend(agency.groups() if agency else [part])

    names: list[str] = []
    for candidate in candidates:
        name = _proper_case(candidate.strip(" ,;|-–—."))
        if not name or len(name) > _MAX_AUTHOR_CHARS or len(name.split()) > _MAX_AUTHOR_WORDS:
            continue
        if _NOT_A_NAME.search(name) or _is_outlet(name, source):
            continue
        if name.lower() not in {n.lower() for n in names}:
            names.append(name)

    # A lone first name next to the full one ("Kathryn", "Kathryn Watson").
    names = [
        n for n in names
        if " " in n or not any(m.lower().startswith(n.lower() + " ") for m in names)
    ]
    return names[:MAX_AUTHORS]


def validate_article(article: dict) -> tuple[bool, str]:
    url = article.get("url", "unknown")

    if not article.get("text"):
        logger.warning(f"{url}: empty or missing text")
        return False, "empty text"

    text = article["text"]
    if len(text) < MIN_TEXT_LENGTH:
        logger.warning(f"{url}: text too short ({len(text)} chars)")
        return False, f"text too short ({len(text)} chars)"

    return True, ""


def split_title_body(text: str, title: str) -> tuple[str, str]:
    if not title or not text:
        return "", text

    text_lower = text.lower()
    title_lower = title.lower().strip()

    title_words = title_lower.split()
    text_start = text_lower[:200].lower()

    first_sentence_match = re.match(r"^[^.!?]*", text_start)
    if first_sentence_match:
        first_sentence = first_sentence_match.group(0).strip()

        if title_lower in first_sentence or all(w in first_sentence for w in title_words if len(w) > 4):
            text = re.sub(r"^[^.!?]*[.!?]\s*", "", text, count=1).lstrip()

    return title, text


def truncate_to_length(text: str, max_tokens: int = MAX_TOKENS) -> str:
    if not text:
        return text

    rough_chars_per_token = 4
    char_limit = max_tokens * rough_chars_per_token

    if len(text) <= char_limit:
        return text

    truncated = text[:char_limit]

    last_period = truncated.rfind(".")
    last_newline = truncated.rfind("\n")

    cutoff = max(last_period, last_newline)
    if cutoff > char_limit * 0.7:
        return truncated[:cutoff + 1].strip()

    return truncated.strip() + "..."


def preprocess_single(article: dict) -> dict | None:
    url = article.get("url", "unknown")

    try:
        is_valid, reason = validate_article(article)
        if not is_valid:
            return None
    except Exception as e:
        logger.error(f"{url}: {type(e).__name__}: {str(e)[:50]}")
        return None

    try:
        cleaned_text = clean_text(article["text"])
    except Exception as e:
        logger.error(f"{url}: clean_text failed - {type(e).__name__}: {str(e)[:50]}")
        return None

    raw_title = article.get("title", "")
    if not raw_title:
        logger.warning(f"{url}: missing title, using 'Untitled'")
        raw_title = "Untitled"

    title, body = split_title_body(cleaned_text, raw_title)

    truncated_body = truncate_to_length(body)
    full_body = truncate_to_length(body, FULL_TEXT_MAX_TOKENS)

    prepended_text = f"{title}. {truncated_body}" if title else truncated_body

    return {
        "title": title,
        "text": prepended_text,
        "full_text": f"{title}. {full_body}" if title else full_body,
        "url": url,
        "source": article.get("source", "unknown"),
        "authors": clean_authors(article.get("authors"), article.get("source", "")),
        "region": article.get("region"),
        "category": article.get("category"),
        "policy": article.get("policy", False),
        "original_text_length": len(article["text"]),
        "processed_text_length": len(prepended_text)
    }


def preprocess_batch(articles: list[dict]) -> list[dict]:
    logger.info(f"Starting preprocessing: {len(articles)} articles")

    processed = []
    for article in articles:
        result = preprocess_single(article)
        if result is not None:
            processed.append(result)

    logger.info(f"Preprocessing complete: {len(processed)}/{len(articles)} articles processed")
    return processed


if __name__ == "__main__":
    test_articles = [
        {
            "title": "President Signs New Climate Bill",
            "text": "President Signs New Climate Bill Congress passed the landmark climate legislation on Tuesday, marking a historic shift in environmental policy. The bill aims to reduce carbon emissions by 50% by 2030. Industry leaders have expressed mixed reactions, with renewable energy companies praising the move while fossil fuel companies warn of economic impacts. The legislation includes provisions for solar and wind energy incentives, electric vehicle tax credits, and funding for climate research.",
            "url": "https://example.com/climate-bill",
            "source": "TestSource"
        },
        {
            "title": "Too Short",
            "text": "This is less than 200 characters of text for testing purposes.",
            "url": "https://example.com/short",
            "source": "TestSource"
        },
        {
            "url": "https://example.com/no-text",
            "source": "TestSource"
        },
        {
            "title": "",
            "text": "A" * 300,
            "url": "https://example.com/no-title",
            "source": "TestSource"
        }
    ]

    print("\n=== Preprocessor Test ===")
    results = preprocess_batch(test_articles)
    print(f"\nProcessed {len(results)} articles:")
    for r in results:
        print(f"  - {r['title']} ({r['processed_text_length']} chars)")

