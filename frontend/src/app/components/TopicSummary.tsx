import { SectionLabel } from "./shared";
import { safeUrl, sanitizeHtml } from "../sanitize";

export interface TopicDetail {
  text: string;
  html?: string;
  source: string;
  url?: string;
  also_reported_by?: string[];
}

export interface DetailedSummary {
  overview: string;
  overview_html?: string;
  details: TopicDetail[];
}

export interface DefinedTerm {
  term: string;
  definition: string;
}

export function KeyTermChips({ terms }: { terms: DefinedTerm[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {terms.map(t => (
        <span
          key={t.term}
          title={t.definition}
          className="cursor-help inline-flex px-2 py-0.5 rounded-sm text-sm font-medium bg-secondary text-secondary-foreground border border-border"
        >
          {t.term}
        </span>
      ))}
    </div>
  );
}

// <mark> is styled globally (globals.css), for both themes.
const MARK_CLASSES = "";

/** Glossary-highlighted HTML from the backend when present, else plain text. */
function RichText({ html, text, className }: { html?: string; text: string; className: string }) {
  return html
    ? <p className={className} dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }} />
    : <p className={className}>{text}</p>;
}

/**
 * A topic's in-depth summary: a fused overview of every outlet's account,
 * then the distinct facts the outlets reported, each credited to its source.
 * Clusters saved before detailed summaries existed fall back to the brief.
 */
export function TopicSummary({
  detailed,
  fallbackHtml,
}: {
  detailed?: DetailedSummary | null;
  fallbackHtml: string;
}) {
  if (!detailed?.overview) {
    return (
      <div
        className={`text-lg text-foreground leading-relaxed ${MARK_CLASSES}`}
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(fallbackHtml) }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <SectionLabel>Overview</SectionLabel>
        <RichText
          html={detailed.overview_html}
          text={detailed.overview}
          className={`text-lg text-foreground leading-relaxed ${MARK_CLASSES}`}
        />
      </div>

      {detailed.details.length > 0 && (
        <div>
          <SectionLabel>Key details by outlet</SectionLabel>
          <ul className="space-y-4">
            {detailed.details.map((d, i) => (
              <li key={i} className="flex gap-3">
                <span
                  className="mt-3 h-1.5 w-1.5 rounded-full shrink-0"
                  style={{ background: "var(--accent)" }}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <RichText
                    html={d.html}
                    text={d.text}
                    className={`text-lg text-foreground leading-relaxed ${MARK_CLASSES}`}
                  />
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    Reported by{" "}
                    {safeUrl(d.url) ? (
                      <a
                        href={safeUrl(d.url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold link"
                      >
                        {d.source}
                      </a>
                    ) : (
                      <strong>{d.source}</strong>
                    )}
                    {d.also_reported_by?.length ? ` · also ${d.also_reported_by.join(", ")}` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
