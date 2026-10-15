import type { CSSProperties, MouseEvent } from "react";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";
import { REGIONS, Region, RegionIcon, SourceBadge, SectionLabel } from "./shared";
import { GenreWeights, TopicTags, primaryTag, tagStyle, topicTags } from "./topicTags";

export interface BriefSection {
  cluster_id: string;
  headline: string;
  bullets: string[];
  article_count: number;
  // Missing on briefs built before regions existed; those count as U.S. news.
  region?: Region;
  // Missing on older briefs.
  outlet_count?: number;
  category?: string;
  relevance?: number;
  genre_weights?: Partial<GenreWeights> | null;
}

export interface DailySummary {
  sections: BriefSection[];
  cluster_count: number;
  total_articles: number;
  source_count: number;
  source_links: Array<{ source: string; url: string }>;
  last_updated?: string;
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

// ─── Bento layout ─────────────────────────────────────────────────────────────

type TileSize = "hero" | "tall" | "wide" | "small";

interface TileSpan {
  c: number;   // columns on the twelve-column grid
  r: number;   // rows on the twelve-column grid
  c2: number;  // columns on the two-column grid
  size: TileSize;
}

/** Rows for `rest` tiles after the lead block, as column spans: rows of
 *  four, then three, then two, never one tile alone. */
function restRows(rest: number): number[][] {
  const rows: number[][] = [];
  while (rest > 0) {
    const count = rest === 2 ? 2 : rest === 3 || rest === 5 ? 3 : 4;
    rows.push(Array(count).fill(12 / count));
    rest -= count;
  }
  return rows;
}

/**
 * Spans for `n` tiles, most relevant first, that fill every row of the
 * twelve-column grid: the lead story takes the left half for two rows with
 * the next stories beside it (four small tiles, or fewer bigger ones), then
 * rows of four, three or two.
 */
export function bentoSpans(n: number): TileSpan[] {
  if (n <= 0) return [];
  let spans: Array<[number, number]>;
  if (n === 1) spans = [[12, 1]];
  else if (n === 2) spans = [[7, 2], [5, 2]];
  else if (n === 3) spans = [[6, 2], [6, 1], [6, 1]];
  // A lead block of five unless that leaves a lone tile after it.
  else if (n === 4 || n === 6) spans = [[6, 2], [6, 1], [3, 1], [3, 1]];
  else spans = [[6, 2], [3, 1], [3, 1], [3, 1], [3, 1]];
  for (const row of restRows(n - spans.length)) spans.push(...row.map(c => [c, 1] as [number, number]));

  // Two-column grid: the lead story spans both, the rest one each, and a
  // leftover last tile spans both.
  return spans.map(([c, r], i) => ({
    c,
    r,
    c2: i === 0 || (i === n - 1 && (n - 1) % 2 === 1) ? 2 : 1,
    size: i === 0 && n > 1 ? "hero" : r === 2 ? "tall" : c >= 6 ? "wide" : "small",
  }));
}

// What each tile size shows: the lead story its key points, the rest their
// headline and top point. Points are clamped to two lines so rows stay
// short; headlines never are.
const TILE: Record<TileSize, { bullets: number; headline: string; lift: number }> = {
  hero:  { bullets: 4, headline: "clamp(1.35rem, 2.4cqi, 1.8rem)", lift: 1.01 },
  tall:  { bullets: 2, headline: "1.25rem", lift: 1.02 },
  wide:  { bullets: 1, headline: "1.2rem",  lift: 1.02 },
  small: { bullets: 1, headline: "1.1rem",  lift: 1.03 },
};

function BriefTile({
  section,
  span,
  href,
  onSelect,
}: {
  section: BriefSection;
  span: TileSpan;
  href: string;
  onSelect?: (clusterId: string) => void;
}) {
  const t = TILE[span.size];
  const tags = topicTags(section.category, section.region, section.genre_weights);
  const outlets = section.outlet_count;
  const style = {
    ...tagStyle(primaryTag(section.category, section.region)),
    "--c": span.c,
    "--r": span.r,
    "--c2": span.c2,
    "--lift": t.lift,
  } as CSSProperties;

  function handleClick(e: MouseEvent) {
    if (!onSelect) return;
    e.preventDefault();
    onSelect(section.cluster_id);
  }

  return (
    <Link
      to={href}
      state={{ from: "today" }}
      onClick={handleClick}
      style={style}
      className={`bento-tile group flex flex-col gap-2 overflow-hidden rounded-lg border border-border bg-card outline-none focus-visible:ring-2 focus-visible:ring-ring ${span.size === "hero" ? "p-5" : "p-4"}`}
    >
      {/* Accent bar and (on the lead story) a wash in the topic's color. */}
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1" style={{ background: "var(--tag)" }} />
      {span.size === "hero" && (
        <span
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none"
          style={{ background: "radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--tag) 16%, transparent), transparent 60%)" }}
        />
      )}

      <div className="relative flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <TopicTags tags={tags} />
        {outlets != null && (
          <span className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
            {outlets} outlet{outlets !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <h3
        className="relative text-foreground"
        style={{ fontFamily: "var(--font-display)", fontWeight: span.size === "hero" ? 800 : 700, fontSize: t.headline, lineHeight: 1.18 }}
      >
        {section.headline}
      </h3>

      <ul className="relative space-y-1.5 text-base text-foreground/85 leading-snug">
        {section.bullets.slice(0, t.bullets).map((b, i) => (
          <li key={i} className="flex gap-2">
            <span aria-hidden="true" className="mt-[0.5em] h-1.5 w-1.5 rounded-full shrink-0" style={{ background: "var(--tag)" }} />
            <span className="line-clamp-2" dangerouslySetInnerHTML={{ __html: b }} />
          </li>
        ))}
      </ul>

      {span.size === "hero" && (
        <div className="relative mt-auto pt-1 flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span style={{ fontFamily: "var(--font-data)" }}>
            {section.article_count} article{section.article_count !== 1 ? "s" : ""}
          </span>
          <span className="tile-cta inline-flex items-center gap-1 font-semibold text-brand-accent">
            Open topic <ArrowRight size={15} />
          </span>
        </div>
      )}
    </Link>
  );
}

/**
 * The Daily Brief as a bento grid per region, most relevant topic largest.
 * Tiles open today's topic page by default; the Archive passes `topicHref`
 * and `onSelect` instead, since topic pages only exist for today's topics.
 */
export function DailyBrief({
  data,
  topicHref = id => `/cluster/${encodeURIComponent(id)}`,
  onSelect,
  showSources = true,
}: {
  data: DailySummary;
  topicHref?: (clusterId: string) => string;
  onSelect?: (clusterId: string) => void;
  showSources?: boolean;
}) {
  return (
    <div className="space-y-7">
      {REGIONS.map(({ region, heading }) => {
        const sections = data.sections.filter(s => (s.region ?? "us") === region);
        if (sections.length === 0) return null;
        const spans = bentoSpans(sections.length);
        return (
          <section key={region} aria-labelledby={`brief-${region}`} className="bento-wrap">
            <h2
              id={`brief-${region}`}
              className="flex items-center gap-2.5 pb-1.5 mb-3 border-b border-border"
              style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.35rem", lineHeight: 1.2 }}
            >
              <RegionIcon region={region} size={22} />
              {heading}
              <span className="ml-auto text-sm font-normal text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
                {sections.length} topic{sections.length !== 1 ? "s" : ""}
              </span>
            </h2>
            <div className="bento">
              {sections.map((s, i) => (
                <BriefTile
                  key={s.cluster_id}
                  section={s}
                  span={spans[i]}
                  href={topicHref(s.cluster_id)}
                  onSelect={onSelect}
                />
              ))}
            </div>
          </section>
        );
      })}

      {showSources && data.source_links?.length > 0 && (
        <div className="pt-5 border-t border-border space-y-2">
          <SectionLabel>Sources in today's brief</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {data.source_links.map((s, i) => (
              <SourceBadge key={i} source={s.source} url={s.url} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
