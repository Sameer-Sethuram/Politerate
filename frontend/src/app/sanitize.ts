import DOMPurify from "dompurify";

/**
 * Summaries arrive as HTML: escaped text plus the glossary's
 * <span class="politerate-term" title data-term> tooltips. The server
 * escapes scraped text before adding those, but topics and archived days
 * saved before it did hold raw article text, so whatever is rendered with
 * dangerouslySetInnerHTML goes through here first: only those spans (and
 * harmless inline formatting) survive, with no URLs, styles or handlers.
 */
const ALLOWED_TAGS = ["span", "mark", "b", "strong", "i", "em", "br"];
const ALLOWED_ATTR = ["class", "title", "data-term"];

export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR, ALLOW_DATA_ATTR: false });
}

/** `url` if it's a web address, else undefined, so a stored
 *  "javascript:" link can't run code when clicked. */
export function safeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? url : undefined;
  } catch {
    return undefined;
  }
}
