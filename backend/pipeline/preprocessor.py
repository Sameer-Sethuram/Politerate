"""
preprocessor.py

Prepares scraped article text for the summarizer pipeline:
- Cleans and normalizes text
- Validates article quality
- Splits title from body
- Truncates to model token limit
"""

import re
import unicodedata
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 200
MAX_TOKENS = 1024


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    text = re.sub(r"^[ \t]+|[ \t]+$", "", text, flags=re.MULTILINE)

    text = unicodedata.normalize("NFKC", text)

    return text.strip()


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

    prepended_text = f"{title}. {truncated_body}" if title else truncated_body

    return {
        "title": title,
        "text": prepended_text,
        "url": url,
        "source": article.get("source", "unknown"),
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

