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
  c: number;   // columns on the six-column grid
  r: number;   // rows on the six-column grid
  c2: number;  // columns on the two-column grid
  size: TileSize;
}

/**
 * Spans for `n` tiles, most relevant first, that fill every row of the
 * six-column grid: the lead story takes a 4×2 block (beside one tall tile
 * or two short ones), then rows of two uneven tiles, then rows of three.
 */
export function bentoSpans(n: number): TileSpan[] {
  if (n <= 0) return [];
  let spans: Array<[number, number]>;
  if (n === 1) spans = [[6, 1]];
  else if (n === 2 || n === 4) spans = [[4, 2], [2, 2]];
  else spans = [[4, 2], [2, 1], [2, 1]];

  // The rest as rows of two (bigger tiles, first) and rows of three; every
  // count from 2 up splits into those.
  const rest = n - spans.length;
  let threes = Math.floor(rest / 3);
  while (threes > 0 && (rest - 3 * threes) % 2) threes -= 1;
  const twos = (rest - 3 * threes) / 2;
  for (let i = 0; i < twos; i++) spans.push(...(i % 2 ? [[2, 1], [4, 1]] : [[4, 1], [2, 1]]) as Array<[number, number]>);
  for (let i = 0; i < threes; i++) spans.push([2, 1], [2, 1], [2, 1]);

  // Two-column grid: the lead story spans both, the rest one each, and a
  // leftover last tile spans both.
  return spans.map(([c, r], i) => ({
    c,
    r,
    c2: i === 0 || (i === n - 1 && (n - 1) % 2 === 1) ? 2 : 1,
    size: i === 0 && n > 1 ? "hero" : r === 2 ? "tall" : c >= 4 ? "wide" : "small",
  }));
}

const TILE: Record<TileSize, { bullets: number; headline: string; headlineClamp: string; bulletClamp: string; lift: number }> = {
  hero:  { bullets: 4, headline: "clamp(1.5rem, 3.2cqi, 2.1rem)", headlineClamp: "", bulletClamp: "line-clamp-3", lift: 1.012 },
  tall:  { bullets: 3, headline: "1.35rem", headlineClamp: "line-clamp-4", bulletClamp: "line-clamp-3", lift: 1.025 },
  wide:  { bullets: 2, headline: "1.3rem",  headlineClamp: "line-clamp-3", bulletClamp: "line-clamp-2", lift: 1.018 },
  small: { bullets: 1, headline: "1.2rem",  headlineClamp: "line-clamp-4", bulletClamp: "line-clamp-3", lift: 1.035 },
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
      className="bento-tile group flex flex-col gap-3 overflow-hidden rounded-lg border border-border bg-card p-5 sm:p-6 outline-none focus-visible:ring-2 focus-visible:ring-ring"
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

      <div className="relative flex flex-wrap items-center justify-between gap-2">
        <TopicTags tags={tags} />
        {outlets != null && (
          <span className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
            {outlets} outlet{outlets !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <h3
        className={`relative ${t.headlineClamp} text-foreground`}
        style={{ fontFamily: "var(--font-display)", fontWeight: span.size === "hero" ? 800 : 700, fontSize: t.headline, lineHeight: 1.18 }}
      >
        {section.headline}
      </h3>

      <ul className={`relative space-y-2 text-foreground/90 leading-relaxed ${span.size === "hero" ? "text-lg" : "text-base"}`}>
        {section.bullets.slice(0, t.bullets).map((b, i) => (
          <li key={i} className="flex gap-2.5">
            <span aria-hidden="true" className="mt-[0.6em] h-1.5 w-1.5 rounded-full shrink-0" style={{ background: "var(--tag)" }} />
            <span className={t.bulletClamp} dangerouslySetInnerHTML={{ __html: b }} />
          </li>
        ))}
      </ul>

      <div className="relative mt-auto pt-1 flex items-center justify-between gap-3 text-sm text-muted-foreground">
        <span style={{ fontFamily: "var(--font-data)" }}>
          {section.article_count} article{section.article_count !== 1 ? "s" : ""}
          {section.bullets.length > t.bullets && ` · ${section.bullets.length - t.bullets} more point${section.bullets.length - t.bullets !== 1 ? "s" : ""}`}
        </span>
        <span className="tile-cta inline-flex items-center gap-1 font-semibold text-brand-accent">
          Open topic <ArrowRight size={15} />
        </span>
      </div>
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
    <div className="space-y-10">
      {REGIONS.map(({ region, heading }) => {
        const sections = data.sections.filter(s => (s.region ?? "us") === region);
        if (sections.length === 0) return null;
        const spans = bentoSpans(sections.length);
        return (
          <section key={region} aria-labelledby={`brief-${region}`} className="bento-wrap">
            <h2
              id={`brief-${region}`}
              className="flex items-center gap-2.5 pb-2 mb-5 border-b border-border"
              style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.45rem", lineHeight: 1.2 }}
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
