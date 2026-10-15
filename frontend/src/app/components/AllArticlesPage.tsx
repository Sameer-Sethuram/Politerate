import { useState, useEffect, useMemo, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { AlertCircle, ChevronDown, ChevronUp, ExternalLink, Search, SlidersHorizontal, X } from "lucide-react";
import { Spinner, StateBox, LeanBadge, CredBadge, PageContainer, SectionLabel, Region, siteToday } from "./shared";
import { TAG_ORDER, TOPIC_TAGS, TagKey, TagSwatch, TopicTag, primaryTag } from "./topicTags";

interface Article {
  url: string;
  title: string;
  source: string;
  lean?: string | null;
  credibility_score?: number | null;
  // Articles sharing a topic_id cover the same story (one topic cluster).
  topic_id: string | null;
  in_brief: boolean;
  // Null only for data saved before regions / categories existed (U.S. politics).
  region: Region | null;
  category?: string | null;
  scraped_at: string;
}

/** One story on one day: its articles, most credible first. */
interface Story {
  key: string;
  articles: Article[];
  inBrief: boolean;
  latest: string;
}

type Sort = "coverage" | "credibility" | "newest";

const SORTS: Array<{ value: Sort; label: string }> = [
  { value: "coverage", label: "Most covered" },
  { value: "credibility", label: "Most credible" },
  { value: "newest", label: "Newest" },
];

// Default when the API doesn't send one; mirrors backend CREDIBILITY_THRESHOLD.
const DEFAULT_THRESHOLD = 0.6;
// Stories shown per day before "Show all", in full grid rows.
const ROWS_SHOWN = 2;
const GRID = "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4 items-start";
// GRID's breakpoints as [min-width in rem, columns], widest first.
const GRID_COLUMNS: Array<[number, number]> = [[96, 4], [80, 3], [40, 2]];

const tagOf = (a: Article): TagKey => primaryTag(a.category, a.region);
const dayOf = (a: Article) => a.scraped_at.slice(0, 10);
const credibilityOf = (a: Article) => a.credibility_score ?? -1;

function currentGridColumns(): number {
  return GRID_COLUMNS.find(([rem]) => window.matchMedia(`(min-width: ${rem}rem)`).matches)?.[1] ?? 1;
}

function useGridColumns(): number {
  const [columns, setColumns] = useState(currentGridColumns);
  useEffect(() => {
    const onResize = () => setColumns(currentGridColumns());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return columns;
}

function formatDay(day: string, today: string): string {
  const d = new Date(day + "T12:00:00");
  const long = d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  return day === today ? `Today · ${long}` : long;
}

function shortDay(day: string, today: string): string {
  if (day === today) return "Today";
  const d = new Date(day + "T12:00:00");
  const t = new Date(today + "T12:00:00");
  if (Math.round((t.getTime() - d.getTime()) / 86400000) === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

// ─── Filters ──────────────────────────────────────────────────────────────────

interface Filters {
  day: string | null;
  tags: Set<TagKey>;
  minCredibility: number;
  outlets: Set<string>;
}

function readFilters(params: URLSearchParams): Filters {
  const cred = Number(params.get("cred"));
  return {
    day: /^\d{4}-\d{2}-\d{2}$/.test(params.get("day") ?? "") ? params.get("day") : null,
    tags: new Set(params.getAll("tag").filter((t): t is TagKey => (TAG_ORDER as string[]).includes(t))),
    minCredibility: Number.isFinite(cred) ? Math.min(Math.max(cred, 0), 1) : 0,
    outlets: new Set(params.getAll("outlet")),
  };
}

type Facet = keyof Filters;

/** Whether `a` passes every filter except `skip` (for that facet's counts). */
function passes(a: Article, f: Filters, skip?: Facet): boolean {
  if (skip !== "day" && f.day && dayOf(a) !== f.day) return false;
  if (skip !== "tags" && f.tags.size && !f.tags.has(tagOf(a))) return false;
  if (skip !== "minCredibility" && f.minCredibility > 0 && credibilityOf(a) < f.minCredibility) return false;
  if (skip !== "outlets" && f.outlets.size && !f.outlets.has(a.source)) return false;
  return true;
}

function countBy<T>(articles: Article[], key: (a: Article) => T): Map<T, number> {
  const counts = new Map<T, number>();
  for (const a of articles) counts.set(key(a), (counts.get(key(a)) ?? 0) + 1);
  return counts;
}

function FilterGroup({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <fieldset className="space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">{title}</legend>
        {action}
      </div>
      {children}
    </fieldset>
  );
}

function OptionButton({
  active, onClick, children, count,
}: { active: boolean; onClick: () => void; children: ReactNode; count?: number }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={[
        "w-full flex items-center gap-2.5 rounded px-3 py-1.5 text-left text-base transition-colors",
        active ? "bg-brand-accent-soft text-foreground font-semibold" : "text-foreground/85 hover:bg-secondary",
      ].join(" ")}
    >
      {children}
      {count != null && (
        <span className="ml-auto text-sm text-muted-foreground tabular-nums" style={{ fontFamily: "var(--font-data)" }}>
          {count}
        </span>
      )}
    </button>
  );
}

function FilterPanel({
  articles, filters, days, today, threshold, update,
}: {
  articles: Article[];
  filters: Filters;
  days: string[];
  today: string;
  threshold: number;
  update: (change: (p: URLSearchParams) => void) => void;
}) {
  const [outletQuery, setOutletQuery] = useState("");
  const dayCounts = useMemo(() => countBy(articles.filter(a => passes(a, filters, "day")), dayOf), [articles, filters]);
  const tagCounts = useMemo(() => countBy(articles.filter(a => passes(a, filters, "tags")), tagOf), [articles, filters]);
  const outletCounts = useMemo(
    () => countBy(articles.filter(a => passes(a, filters, "outlets")), a => a.source),
    [articles, filters],
  );
  const outlets = useMemo(() => [...new Set(articles.map(a => a.source))].sort((a, b) => a.localeCompare(b)), [articles]);
  const shownOutlets = outlets.filter(o => o.toLowerCase().includes(outletQuery.trim().toLowerCase()));

  const toggleValue = (key: string, value: string) =>
    update(p => {
      const values = p.getAll(key);
      p.delete(key);
      const next = values.includes(value) ? values.filter(v => v !== value) : [...values, value];
      next.forEach(v => p.append(key, v));
    });

  const credPresets = [
    { value: 0, label: "Any" },
    { value: threshold, label: `${threshold.toFixed(2)}+` },
    { value: 0.8, label: "0.80+" },
  ];

  return (
    <div className="space-y-7">
      <FilterGroup title="Date">
        <div className="space-y-0.5">
          <OptionButton active={!filters.day} onClick={() => update(p => p.delete("day"))} count={[...dayCounts.values()].reduce((a, b) => a + b, 0)}>
            All days
          </OptionButton>
          {days.map(day => (
            <OptionButton key={day} active={filters.day === day} onClick={() => update(p => p.set("day", day))} count={dayCounts.get(day) ?? 0}>
              {shortDay(day, today)}
            </OptionButton>
          ))}
        </div>
      </FilterGroup>

      <FilterGroup
        title="Genre"
        action={filters.tags.size > 0 && (
          <button type="button" onClick={() => update(p => p.delete("tag"))} className="text-sm link text-muted-foreground">
            All
          </button>
        )}
      >
        <div className="space-y-0.5">
          {TAG_ORDER.map(tag => (
            <OptionButton key={tag} active={filters.tags.has(tag)} onClick={() => toggleValue("tag", tag)} count={tagCounts.get(tag) ?? 0}>
              <TagSwatch tag={tag} />
              {TOPIC_TAGS[tag].label}
            </OptionButton>
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Credibility score">
        <div className="space-y-3">
          <div className="flex items-center justify-between text-base">
            <span>Minimum</span>
            <strong className="tabular-nums" style={{ fontFamily: "var(--font-data)" }}>
              {filters.minCredibility > 0 ? filters.minCredibility.toFixed(2) : "Any"}
            </strong>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={filters.minCredibility}
            onChange={e => {
              const v = Number(e.target.value);
              update(p => (v > 0 ? p.set("cred", v.toFixed(2)) : p.delete("cred")));
            }}
            aria-label="Minimum credibility score"
            className="w-full"
            style={{ accentColor: "var(--brand-accent)" }}
          />
          <div className="flex gap-1.5">
            {credPresets.map(preset => (
              <button
                key={preset.label}
                type="button"
                aria-pressed={Math.abs(filters.minCredibility - preset.value) < 0.001}
                onClick={() => update(p => (preset.value > 0 ? p.set("cred", preset.value.toFixed(2)) : p.delete("cred")))}
                className={[
                  "flex-1 rounded border px-2 py-1 text-sm transition-colors",
                  Math.abs(filters.minCredibility - preset.value) < 0.001
                    ? "border-[var(--accent)] bg-brand-accent-soft font-semibold"
                    : "border-border hover:bg-secondary",
                ].join(" ")}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <p className="text-sm text-muted-foreground leading-snug">
            Higher means less loaded, subjective language. {threshold.toFixed(2)} is the bar for the Daily Brief.
          </p>
        </div>
      </FilterGroup>

      <FilterGroup
        title="Outlet"
        action={filters.outlets.size > 0 && (
          <button type="button" onClick={() => update(p => p.delete("outlet"))} className="text-sm link text-muted-foreground">
            All
          </button>
        )}
      >
        <label className="relative block">
          <Search size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            value={outletQuery}
            onChange={e => setOutletQuery(e.target.value)}
            placeholder="Find an outlet"
            aria-label="Find an outlet"
            className="w-full rounded border border-border bg-input-background py-1.5 pl-8 pr-3 text-base placeholder:text-muted-foreground"
          />
        </label>
        <div className="max-h-72 overflow-y-auto space-y-0.5 pr-1">
          {shownOutlets.map(outlet => (
            <label
              key={outlet}
              className="flex items-center gap-2.5 rounded px-3 py-1.5 text-base cursor-pointer hover:bg-secondary"
            >
              <input
                type="checkbox"
                checked={filters.outlets.has(outlet)}
                onChange={() => toggleValue("outlet", outlet)}
                style={{ accentColor: "var(--brand-accent)" }}
                className="size-4"
              />
              <span className="min-w-0 truncate">{outlet}</span>
              <span className="ml-auto text-sm text-muted-foreground tabular-nums" style={{ fontFamily: "var(--font-data)" }}>
                {outletCounts.get(outlet) ?? 0}
              </span>
            </label>
          ))}
          {shownOutlets.length === 0 && <p className="px-3 py-1.5 text-sm text-muted-foreground">No outlet matches.</p>}
        </div>
      </FilterGroup>
    </div>
  );
}

// ─── Results ──────────────────────────────────────────────────────────────────

function ArticleLine({ article }: { article: Article }) {
  return (
    <li className="space-y-1">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-semibold">{article.source}</span>
        {article.lean && article.lean !== "unknown" && <LeanBadge lean={article.lean} />}
        {article.credibility_score != null && <CredBadge score={article.credibility_score} />}
      </div>
      <Link to={`/article?url=${encodeURIComponent(article.url)}`} className="block text-base leading-snug link">
        {article.title || "Untitled"}
      </Link>
    </li>
  );
}

function StoryCard({ story, threshold }: { story: Story; threshold: number }) {
  const [open, setOpen] = useState(false);
  const [lead, ...others] = story.articles;
  const tag = tagOf(lead);
  const outlets = new Set(story.articles.map(a => a.source)).size;

  return (
    <article
      className="relative flex flex-col gap-3 overflow-hidden rounded-lg border border-border bg-card p-5 hover:border-border-strong transition-colors"
    >
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1" style={{ background: TOPIC_TAGS[tag].color }} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TopicTag tag={tag} />
        {story.inBrief && (
          <span className="text-xs font-semibold uppercase tracking-wider text-brand-accent">In Daily Brief</span>
        )}
      </div>

      <div className="flex items-start justify-between gap-3">
        <h3 className="text-lg font-medium leading-snug flex-1 min-w-0">
          <Link to={`/article?url=${encodeURIComponent(lead.url)}`} className="link">
            {lead.title || "Untitled"}
          </Link>
        </h3>
        <a
          href={lead.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-muted-foreground hover:text-brand-accent transition-colors mt-1"
          title={`Open the original at ${lead.source}`}
          aria-label={`Open the original at ${lead.source}`}
        >
          <ExternalLink size={17} />
        </a>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-muted-foreground">{lead.source}</span>
        {lead.lean && lead.lean !== "unknown" && <LeanBadge lean={lead.lean} />}
        {lead.credibility_score != null && <CredBadge score={lead.credibility_score} />}
        {credibilityOf(lead) < threshold && (
          <span className="text-sm text-muted-foreground italic">below the brief's bar</span>
        )}
      </div>

      {others.length > 0 && (
        <div className="border-t border-border pt-2.5">
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            className="flex w-full items-center justify-between gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <span>
              +{others.length} more article{others.length !== 1 ? "s" : ""}
              {outlets > 1 && ` · ${outlets} outlets on this story`}
            </span>
            {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {open && (
            <ul className="mt-3 space-y-3">
              {others.map(a => <ArticleLine key={a.url} article={a} />)}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}

function DaySection({
  heading, stories, articleCount, threshold, shown,
}: { heading: string; stories: Story[]; articleCount: number; threshold: number; shown: number }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? stories : stories.slice(0, shown);
  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mb-4 pb-2.5 border-b border-border">
        <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.6rem", lineHeight: 1.2 }}>
          {heading}
        </h2>
        <span className="text-base text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
          {stories.length} stor{stories.length !== 1 ? "ies" : "y"} · {articleCount} article{articleCount !== 1 ? "s" : ""}
        </span>
      </div>
      <div className={GRID}>
        {visible.map(s => <StoryCard key={s.key} story={s} threshold={threshold} />)}
      </div>
      {stories.length > shown && (
        <button
          type="button"
          onClick={() => setShowAll(s => !s)}
          className="mt-4 flex items-center gap-1.5 text-sm font-medium text-muted-foreground border border-border rounded px-4 py-2 hover:text-foreground hover:border-border-strong transition-colors"
        >
          {showAll ? <>Show fewer <ChevronUp size={15} /></> : <>Show all {stories.length} stories <ChevronDown size={15} /></>}
        </button>
      )}
    </section>
  );
}

function groupStories(articles: Article[], sort: Sort): Story[] {
  const byStory = new Map<string, Article[]>();
  for (const a of articles) {
    const key = a.topic_id ?? a.url;
    if (!byStory.has(key)) byStory.set(key, []);
    byStory.get(key)!.push(a);
  }
  const stories = [...byStory.entries()].map(([key, list]) => {
    list.sort((a, b) => credibilityOf(b) - credibilityOf(a));
    return {
      key,
      articles: list,
      inBrief: list.some(a => a.in_brief),
      latest: list.reduce((m, a) => (a.scraped_at > m ? a.scraped_at : m), ""),
    };
  });
  const outlets = (s: Story) => new Set(s.articles.map(a => a.source)).size;
  const compare: Record<Sort, (a: Story, b: Story) => number> = {
    coverage: (a, b) => outlets(b) - outlets(a) || Number(b.inBrief) - Number(a.inBrief)
      || credibilityOf(b.articles[0]) - credibilityOf(a.articles[0]),
    credibility: (a, b) => credibilityOf(b.articles[0]) - credibilityOf(a.articles[0]) || outlets(b) - outlets(a),
    newest: (a, b) => b.latest.localeCompare(a.latest),
  };
  return stories.sort(compare[sort]);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function AllArticlesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [today, setToday] = useState(siteToday());
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const shown = ROWS_SHOWN * useGridColumns();
  // Filters live in the URL, so reloads, back/forward and shared links keep them.
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);
  const sort: Sort = SORTS.some(s => s.value === params.get("sort")) ? (params.get("sort") as Sort) : "coverage";

  function update(change: (p: URLSearchParams) => void) {
    setParams(prev => {
      const next = new URLSearchParams(prev);
      change(next);
      return next;
    }, { replace: true });
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/all-articles");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setArticles(data.articles ?? []);
        if (data.today) setToday(data.today);
        setThreshold(data.credibility_threshold ?? DEFAULT_THRESHOLD);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const days = useMemo(() => [...new Set(articles.map(dayOf))].sort().reverse(), [articles]);
  const matching = useMemo(() => articles.filter(a => passes(a, filters)), [articles, filters]);
  const sections = useMemo(() => {
    const byDay = new Map<string, Article[]>();
    for (const a of matching) {
      if (!byDay.has(dayOf(a))) byDay.set(dayOf(a), []);
      byDay.get(dayOf(a))!.push(a);
    }
    return [...byDay.keys()].sort().reverse().map(day => ({
      day,
      articleCount: byDay.get(day)!.length,
      stories: groupStories(byDay.get(day)!, sort),
    }));
  }, [matching, sort]);

  const active: Array<{ label: string; clear: () => void }> = [
    ...(filters.day ? [{ label: shortDay(filters.day, today), clear: () => update(p => p.delete("day")) }] : []),
    ...[...filters.tags].map(t => ({
      label: TOPIC_TAGS[t].label,
      clear: () => update(p => { const rest = p.getAll("tag").filter(v => v !== t); p.delete("tag"); rest.forEach(v => p.append("tag", v)); }),
    })),
    ...(filters.minCredibility > 0
      ? [{ label: `Credibility ${filters.minCredibility.toFixed(2)}+`, clear: () => update(p => p.delete("cred")) }]
      : []),
    ...[...filters.outlets].map(o => ({
      label: o,
      clear: () => update(p => { const rest = p.getAll("outlet").filter(v => v !== o); p.delete("outlet"); rest.forEach(v => p.append("outlet", v)); }),
    })),
  ];
  const clearAll = () => update(p => ["day", "tag", "cred", "outlet"].forEach(k => p.delete(k)));
  const storyCount = sections.reduce((n, s) => n + s.stories.length, 0);

  return (
    <PageContainer wide>
      <div className="mb-8 pb-6 border-b border-border">
        <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "2.25rem", lineHeight: 1.15 }}>
          All Articles
        </h1>
        <p className="mt-2 text-lg text-muted-foreground max-w-4xl">
          Every article from the past 7 days. Each story shows its most credible article, with the other
          outlets that covered it one click away. Filter by day, genre, credibility or outlet.
        </p>
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

      {!loading && !error && articles.length === 0 && (
        <StateBox>
          <p>No articles from the past 7 days yet.</p>
        </StateBox>
      )}

      {!loading && !error && articles.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-[17rem_minmax(0,1fr)] gap-8 items-start">
          {/* Filters: a sidebar on wide screens, a panel behind a button on narrow ones. */}
          <aside className="lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto lg:pr-2">
            <button
              type="button"
              onClick={() => setFiltersOpen(o => !o)}
              aria-expanded={filtersOpen}
              className="lg:hidden w-full flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-4 py-3 text-base font-semibold"
            >
              <span className="inline-flex items-center gap-2">
                <SlidersHorizontal size={18} /> Filters
                {active.length > 0 && <span className="text-sm font-normal text-muted-foreground">({active.length} on)</span>}
              </span>
              {filtersOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            <div className={`${filtersOpen ? "block" : "hidden"} lg:block mt-4 lg:mt-0 rounded-lg border border-border bg-card p-5`}>
              <FilterPanel
                articles={articles}
                filters={filters}
                days={days}
                today={today}
                threshold={threshold}
                update={update}
              />
            </div>
          </aside>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
              <p className="text-base text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
                <strong className="text-foreground">{storyCount}</strong> stor{storyCount !== 1 ? "ies" : "y"} ·{" "}
                <strong className="text-foreground">{matching.length}</strong> article{matching.length !== 1 ? "s" : ""}
              </p>
              <label className="inline-flex items-center gap-2 text-base">
                <span className="text-muted-foreground">Sort</span>
                <select
                  value={sort}
                  onChange={e => update(p => (e.target.value === "coverage" ? p.delete("sort") : p.set("sort", e.target.value)))}
                  className="rounded border border-border bg-card px-3 py-1.5 text-base"
                >
                  {SORTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </label>
            </div>

            {active.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 mb-6">
                <SectionLabel>Filtered by</SectionLabel>
                {active.map(f => (
                  <button
                    key={f.label}
                    type="button"
                    onClick={f.clear}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-sm hover:border-border-strong transition-colors"
                    aria-label={`Remove filter: ${f.label}`}
                  >
                    {f.label} <X size={14} />
                  </button>
                ))}
                <button type="button" onClick={clearAll} className="text-sm link text-muted-foreground">
                  Clear all
                </button>
              </div>
            )}

            {sections.length === 0 ? (
              <StateBox>
                <p>No articles match these filters.</p>
                <button type="button" onClick={clearAll} className="text-base link">Clear all filters</button>
              </StateBox>
            ) : (
              <div className="space-y-12">
                {sections.map(s => (
                  <DaySection
                    key={`${s.day}:${sort}`}
                    heading={formatDay(s.day, today)}
                    stories={s.stories}
                    articleCount={s.articleCount}
                    threshold={threshold}
                    shown={shown}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </PageContainer>
  );
}
