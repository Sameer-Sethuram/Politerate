import { Link } from "react-router";
import { SourceBadge, SectionLabel, getTopicIcon } from "./shared";

export interface BriefSection {
  cluster_id: string;
  headline: string;
  bullets: string[];
  article_count: number;
}

export interface DailySummary {
  sections: BriefSection[];
  cluster_count: number;
  total_articles: number;
  source_count: number;
  source_links: Array<{ source: string; url: string }>;
}

export function StatPill({ value, label }: { value: number; label: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-secondary text-secondary-foreground text-sm"
      style={{ fontFamily: "var(--font-data)" }}
    >
      <strong>{value}</strong>&nbsp;{label}
    </span>
  );
}

const HEADLINE_STYLE = {
  fontFamily: "var(--font-display)",
  fontWeight: 600,
  fontSize: "1.3rem",
  lineHeight: 1.3,
} as const;

/**
 * The bulleted brief. Headlines link to today's topic page by default; the
 * Archive passes `onHeadlineClick` instead, since topic pages only exist for
 * today's clusters.
 */
export function DailyBriefCard({
  data,
  title = "Today's Political Brief",
  onHeadlineClick,
}: {
  data: DailySummary;
  title?: string;
  onHeadlineClick?: (clusterId: string) => void;
}) {
  return (
    <article className="bg-card border border-border rounded p-6 sm:p-8 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-4 pb-5 mb-5 border-b border-border">
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "1.85rem",
            lineHeight: 1.2,
          }}
        >
          {title}
        </h2>
        <div className="flex flex-wrap gap-2">
          <StatPill value={data.cluster_count} label="topics" />
          <StatPill value={data.total_articles} label="articles" />
          <StatPill value={data.source_count} label="sources" />
        </div>
      </header>

      <div className="space-y-7 mb-6">
        {data.sections.map(s => {
          const headline = s.headline.length > 110 ? s.headline.slice(0, 110) + "…" : s.headline;
          return (
            <section key={s.cluster_id}>
              <h3 className="flex items-start gap-2.5 mb-2">
                <span className="text-xl leading-none mt-1 shrink-0">{getTopicIcon(s.bullets.join(" "))}</span>
                {onHeadlineClick ? (
                  <button
                    onClick={() => onHeadlineClick(s.cluster_id)}
                    className="text-left hover:underline decoration-[var(--accent)] underline-offset-2"
                    style={HEADLINE_STYLE}
                  >
                    {headline}
                  </button>
                ) : (
                  <Link
                    to={`/cluster/${encodeURIComponent(s.cluster_id)}`}
                    className="hover:underline decoration-[var(--accent)] underline-offset-2"
                    style={HEADLINE_STYLE}
                  >
                    {headline}
                  </Link>
                )}
              </h3>
              <ul className="list-disc pl-8 sm:pl-12 space-y-2 text-lg text-foreground leading-relaxed marker:text-muted-foreground">
                {s.bullets.map((b, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: b }} />
                ))}
              </ul>
            </section>
          );
        })}
      </div>

      {data.source_links?.length > 0 && (
        <div className="pt-4 border-t border-border space-y-2">
          <SectionLabel>Sources</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {data.source_links.map((s, i) => (
              <SourceBadge key={i} source={s.source} url={s.url} />
            ))}
          </div>
        </div>
      )}
    </article>
  );
}
