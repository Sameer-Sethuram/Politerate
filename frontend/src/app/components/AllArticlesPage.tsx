import { useState, useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { ExternalLink, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import {
  Spinner, StateBox, LeanBadge, CredBadge, PageContainer, SectionLabel, Region, REGIONS,
  RegionIcon, RegionTag,
} from "./shared";

interface Article {
  url: string;
  title: string;
  source: string;
  lean?: string | null;
  credibility_score?: number | null;
  // Articles sharing a topic_id cover the same story (one topic cluster).
  topic_id: string | null;
  in_brief: boolean;
  // Null only for data saved before regions existed (counts as U.S.).
  region: Region | null;
  scraped_at: string;
}

interface DayGroup {
  day: string;
  // One article per story: its most credible one, if it passes the
  // credibility threshold. Sorted by credibility.
  leads: Article[];
  // Everything else: other outlets on those stories, and articles below the
  // threshold. Sorted by credibility.
  more: Article[];
  storySize: Map<string, number>;
}

// Default when the API doesn't send one; mirrors backend CREDIBILITY_THRESHOLD.
const DEFAULT_THRESHOLD = 0.6;
// Top stories shown before "Show all", in full grid rows.
const LEAD_ROWS_SHOWN = 2;
// At most 4 cards per row, from 1280px wide; wider screens get wider cards.
const GRID = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5";
// GRID's breakpoints as [min-width in rem, columns], widest first. Media
// queries resolve rem against the browser default, same as Tailwind's.
const GRID_COLUMNS: Array<[number, number]> = [[80, 4], [64, 3], [40, 2]];

const regionOf = (a: Article): Region => a.region ?? "us";

/** ?region=us|world, or null for every article. */
function parseRegion(value: string | null): Region | null {
  return REGIONS.some(r => r.region === value) ? (value as Region) : null;
}

function currentGridColumns(): number {
  return GRID_COLUMNS.find(([rem]) => window.matchMedia(`(min-width: ${rem}rem)`).matches)?.[1] ?? 1;
}

/** Columns GRID is currently laid out in, tracking window resizes. */
function useGridColumns(): number {
  const [columns, setColumns] = useState(currentGridColumns);
  useEffect(() => {
    const onResize = () => setColumns(currentGridColumns());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return columns;
}

const credibilityOf = (a: Article) => a.credibility_score ?? -1;

function groupDay(day: string, articles: Article[], threshold: number): DayGroup {
  const sorted = [...articles].sort((a, b) => credibilityOf(b) - credibilityOf(a));
  const storySize = new Map<string, number>();
  for (const a of sorted) {
    if (a.topic_id) storySize.set(a.topic_id, (storySize.get(a.topic_id) ?? 0) + 1);
  }

  const leads: Article[] = [];
  const more: Article[] = [];
  const storiesLed = new Set<string>();
  for (const a of sorted) {
    const story = a.topic_id ?? a.url;
    if (!storiesLed.has(story) && credibilityOf(a) >= threshold) {
      storiesLed.add(story);
      leads.push(a);
    } else {
      more.push(a);
    }
  }
  return { day, leads, more, storySize };
}

function formatDayHeading(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

function ArticleCard({
  article,
  otherOutlets = 0,
  belowThreshold = false,
}: {
  article: Article;
  otherOutlets?: number;
  belowThreshold?: boolean;
}) {
  const detailUrl = `/article?url=${encodeURIComponent(article.url)}`;

  return (
    <article className="bg-card border border-border rounded p-5 hover:shadow-sm transition-shadow flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-lg font-medium leading-snug flex-1 min-w-0">
          <RegionTag region={regionOf(article)} className="mr-2 align-middle" />
          <Link to={detailUrl} className="link">
            {article.title || "Untitled"}
          </Link>
        </h3>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-muted-foreground hover:text-brand-accent transition-colors mt-1"
          onClick={e => e.stopPropagation()}
          title="Open original article"
        >
          <ExternalLink size={17} />
        </a>
      </div>

      <div className="mt-auto flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-muted-foreground">{article.source}</span>
        {article.lean && article.lean !== "unknown" && <LeanBadge lean={article.lean} />}
        {article.credibility_score != null && <CredBadge score={article.credibility_score} />}
      </div>

      {(article.in_brief || otherOutlets > 0 || belowThreshold) && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {article.in_brief && (
            <span
              className="px-2 py-0.5 rounded-sm font-semibold"
              style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}
            >
              In Daily Brief
            </span>
          )}
          {otherOutlets > 0 && (
            <span className="text-muted-foreground">
              +{otherOutlets} other outlet{otherOutlets !== 1 ? "s" : ""} on this story
            </span>
          )}
          {belowThreshold && (
            <span className="text-muted-foreground italic">Below the credibility threshold</span>
          )}
        </div>
      )}
    </article>
  );
}

function DaySection({
  group,
  heading,
  threshold,
  leadsShown,
}: {
  group: DayGroup;
  heading: string;
  threshold: number;
  leadsShown: number;
}) {
  const [showAllLeads, setShowAllLeads] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const leads = showAllLeads ? group.leads : group.leads.slice(0, leadsShown);
  const total = group.leads.length + group.more.length;

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-5 pb-3 border-b border-border">
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "1.75rem",
            lineHeight: 1.2,
          }}
        >
          {heading}
        </h2>
        <span className="text-base text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
          {group.leads.length} stor{group.leads.length !== 1 ? "ies" : "y"} · {total} article{total !== 1 ? "s" : ""}
        </span>
      </div>

      {group.leads.length > 0 && (
        <>
          <SectionLabel>Top stories · most credible source per story</SectionLabel>
          <div className={GRID}>
            {leads.map(a => (
              <ArticleCard
                key={a.url}
                article={a}
                otherOutlets={a.topic_id ? (group.storySize.get(a.topic_id) ?? 1) - 1 : 0}
              />
            ))}
          </div>
          {group.leads.length > leadsShown && (
            <button
              onClick={() => setShowAllLeads(s => !s)}
              className="mt-4 flex items-center gap-1.5 text-sm font-medium text-muted-foreground border border-border rounded px-4 py-2 hover:text-foreground hover:border-foreground/20 transition-colors"
            >
              {showAllLeads ? (
                <>Show fewer <ChevronUp size={15} /></>
              ) : (
                <>Show all {group.leads.length} top stories <ChevronDown size={15} /></>
              )}
            </button>
          )}
        </>
      )}

      {group.more.length > 0 && (
        <div className="mt-6">
          <button
            onClick={() => setShowMore(s => !s)}
            aria-expanded={showMore}
            className="w-full flex items-center justify-between gap-3 px-5 py-3.5 rounded border border-border bg-card hover:bg-secondary transition-colors text-left"
          >
            <span>
              <span className="text-base font-semibold">More coverage ({group.more.length})</span>
              <span className="block text-sm text-muted-foreground">
                Other outlets on the stories above, plus articles below the credibility threshold —
                sorted by credibility
              </span>
            </span>
            {showMore ? <ChevronUp size={20} className="shrink-0" /> : <ChevronDown size={20} className="shrink-0" />}
          </button>
          {showMore && (
            <div className={`mt-4 ${GRID}`}>
              {group.more.map(a => (
                <ArticleCard
                  key={a.url}
                  article={a}
                  belowThreshold={credibilityOf(a) < threshold}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function RegionFilter({
  value,
  counts,
  onChange,
}: {
  value: Region | null;
  counts: Record<Region | "all", number>;
  onChange: (region: Region | null) => void;
}) {
  // Short labels on phones so the three options fit on one line.
  const options = [
    { region: null, label: "All", short: "All", count: counts.all },
    ...REGIONS.map(r => ({ region: r.region, label: r.heading, short: r.label, count: counts[r.region] })),
  ];
  return (
    <div role="group" aria-label="Filter by region" className="inline-flex flex-wrap gap-0.5 p-1 bg-secondary rounded">
      {options.map(o => {
        const active = o.region === value;
        return (
          <button
            key={o.label}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.region)}
            className={[
              "flex items-center gap-2 px-3 sm:px-4 py-2 rounded text-base font-medium transition-colors",
              active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {o.region && <RegionIcon region={o.region} size={16} />}
            <span className="sm:hidden">{o.short}</span>
            <span className="hidden sm:inline">{o.label}</span>
            <span className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
              {o.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function AllArticlesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [today, setToday] = useState("");
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const leadsShown = LEAD_ROWS_SHOWN * useGridColumns();
  // ?region= keeps the filter across reloads, back/forward and shared links.
  const [params, setParams] = useSearchParams();
  const region = parseRegion(params.get("region"));

  function selectRegion(next: Region | null) {
    setParams(prev => {
      const updated = new URLSearchParams(prev);
      if (next) updated.set("region", next);
      else updated.delete("region");
      return updated;
    }, { replace: true });
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/all-articles");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setArticles(data.articles ?? []);
        setToday(data.today ?? "");
        setThreshold(data.credibility_threshold ?? DEFAULT_THRESHOLD);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const counts = useMemo(() => {
    const c: Record<Region | "all", number> = { all: articles.length, us: 0, world: 0 };
    for (const a of articles) c[regionOf(a)] += 1;
    return c;
  }, [articles]);

  const days = useMemo(() => {
    const byDay = new Map<string, Article[]>();
    for (const a of articles) {
      if (region && regionOf(a) !== region) continue;
      const day = a.scraped_at.slice(0, 10);
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day)!.push(a);
    }
    return [...byDay.keys()]
      .sort()
      .reverse()
      .map(day => groupDay(day, byDay.get(day)!, threshold));
  }, [articles, threshold, region]);

  return (
    <PageContainer wide>
      {/* Page header */}
      <div className="mb-8 pb-6 border-b border-border">
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "2.25rem",
            lineHeight: 1.15,
          }}
        >
          All Articles
        </h1>
        <p className="mt-2 text-lg text-muted-foreground max-w-4xl">
          Every article from the past 7 days, by day. Each story's most credible article comes
          first, sorted by credibility score, so no credible story gets buried — whether or not it
          made the Daily Brief.
        </p>
        {!loading && !error && articles.length > 0 && (
          <div className="mt-5">
            <RegionFilter value={region} counts={counts} onChange={selectRegion} />
          </div>
        )}
      </div>

      {loading && (
        <StateBox>
          <Spinner />
          <p>Loading articles…</p>
        </StateBox>
      )}

      {!loading && error && (
        <StateBox>
          <AlertCircle className="text-destructive" size={32} />
          <p className="text-destructive">{error}</p>
        </StateBox>
      )}

      {!loading && !error && days.length === 0 && (
        <StateBox>
          <p>
            {articles.length > 0 && region
              ? `No ${REGIONS.find(r => r.region === region)?.heading} articles from the past 7 days.`
              : "No articles from the past 7 days yet."}
          </p>
        </StateBox>
      )}

      {!loading && !error && days.length > 0 && (
        <div className="space-y-14">
          {days.map(group => (
            <DaySection
              key={group.day}
              group={group}
              threshold={threshold}
              leadsShown={leadsShown}
              heading={group.day === today ? `Today · ${formatDayHeading(group.day)}` : formatDayHeading(group.day)}
            />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
