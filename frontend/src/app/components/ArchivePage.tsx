import { useState, useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "react-router";
import { AlertCircle, ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { Calendar } from "./ui/calendar";
import {
  Spinner, StateBox, SourceBadge, AiBanner, SectionLabel, getTopicIcon, Region,
} from "./shared";
import { DailyBrief, DailySummary } from "./DailyBrief";
import { GenreWeights, TopicTags, topicTags } from "./topicTags";
import { DefinedTerm, DetailedSummary, KeyTermChips, TopicSummary } from "./TopicSummary";
import { ArticleBlock, ArticleEntry, ClusterArticle } from "./ArticleBreakdown";
import { errorMessage, fetchJson } from "../api";
import { sanitizeHtml } from "../sanitize";

interface SnapshotMeta {
  date: string;
  cluster_count: number;
  article_count?: number;
  source_count?: number;
}

interface ArchiveCluster {
  cluster_id: string;
  titles?: string[];
  summary: string;
  highlighted_summary?: string;
  detailed_summary?: DetailedSummary | null;
  article_count?: number;
  sources?: string[];
  urls?: string[];
  source_credibility?: Array<{ score: number | null; label: string }>;
  defined_terms?: DefinedTerm[];
  region?: Region | null;
  category?: string | null;
  map?: { genre_weights?: Partial<GenreWeights> | null } | null;
}

interface Snapshot {
  date: string;
  clusters: ArchiveCluster[];
  cluster_count: number;
  article_count: number;
  source_count: number;
  daily_brief?: DailySummary;
}

type ArchivedArticle = ClusterArticle & ArticleEntry;

// Snapshot dates are "YYYY-MM-DD" in server-local time. Parse them as local
// dates; `new Date("2026-10-06")` is UTC midnight, the previous day west of GMT.
function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function dayKey(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function formatLongDate(day: string): string {
  return parseDay(day).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
}

const CALENDAR_CLASSES = {
  caption_label: "text-lg font-semibold",
  nav_button:
    "size-9 inline-flex items-center justify-center rounded border border-border bg-card text-foreground hover:bg-secondary transition-colors disabled:opacity-30 disabled:pointer-events-none",
  // Day cells shrink on phones so seven columns fit a 360px screen.
  head_cell: "text-muted-foreground rounded w-9 sm:w-10 font-normal text-sm",
  row: "flex w-full mt-1.5",
  cell: "relative p-0 text-center text-base focus-within:relative focus-within:z-20",
  day: "size-9 sm:size-10 p-0 inline-flex items-center justify-center rounded text-base font-normal transition-colors hover:bg-secondary aria-selected:opacity-100",
  day_selected:
    "bg-primary text-primary-foreground font-semibold hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
  day_today: "font-bold underline decoration-2 underline-offset-4 decoration-[var(--accent)]",
  day_disabled: "text-muted-foreground opacity-35 hover:bg-transparent cursor-default",
};

// A dot under each day that has an archive, so browsable days stand out
// from the greyed-out gaps.
const ARCHIVED_DAY_CLASS =
  "relative font-medium after:absolute after:bottom-1 after:left-1/2 after:-translate-x-1/2 after:size-1 after:rounded-full after:bg-[var(--accent)] aria-selected:after:bg-[var(--primary-foreground)]";

function ArchiveTopic({
  date,
  cluster,
  open,
  onToggle,
}: {
  date: string;
  cluster: ArchiveCluster;
  open: boolean;
  onToggle: () => void;
}) {
  const [articles, setArticles] = useState<ArchivedArticle[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = cluster.titles?.[0] ?? "Topic summary";
  const sources = cluster.sources ?? [];
  const articleCount = cluster.article_count ?? cluster.urls?.length ?? 0;

  // Articles (with their analysis payloads) load the first time the topic opens.
  useEffect(() => {
    if (!open || articles || loading || error) return;
    setLoading(true);
    (async () => {
      try {
        const data = await fetchJson<{ articles?: ArchivedArticle[] }>(
          `/api/archive/${date}/clusters/${encodeURIComponent(cluster.cluster_id)}`,
        );
        setArticles(data.articles ?? []);
      } catch (e) {
        setError(errorMessage(e, "Failed to load articles"));
      } finally {
        setLoading(false);
      }
    })();
  }, [open, articles, loading, error, date, cluster.cluster_id]);

  return (
    <article
      id={`topic-${cluster.cluster_id}`}
      className="bg-card border border-border rounded overflow-hidden scroll-mt-24"
    >
      <div className="p-6 space-y-4">
        <header className="flex items-start gap-3">
          <span className="text-2xl leading-none mt-0.5 shrink-0">{getTopicIcon(cluster.summary)}</span>
          <div className="min-w-0 flex-1">
            <h3
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: "1.3rem",
                lineHeight: 1.3,
              }}
            >
              {title}
            </h3>
            <p className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
              <TopicTags tags={topicTags(cluster.category, cluster.region, cluster.map?.genre_weights)} />
              <span>
                {articleCount} article{articleCount !== 1 ? "s" : ""} · {new Set(sources).size} source
                {new Set(sources).size !== 1 ? "s" : ""}
              </span>
            </p>
          </div>
        </header>

        {open ? (
          <TopicSummary
            detailed={cluster.detailed_summary}
            fallbackHtml={cluster.highlighted_summary || cluster.summary || ""}
          />
        ) : (
          // Collapsed: the overview, so the card doesn't repeat the Daily
          // Brief bullets above it (older snapshots only have the brief).
          <div
            className="text-lg text-foreground leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(
                cluster.detailed_summary?.overview_html
                || cluster.highlighted_summary
                || cluster.summary
                || "",
              ),
            }}
          />
        )}

        {open && !!cluster.defined_terms?.length && (
          <div className="pt-4 border-t border-border space-y-2">
            <SectionLabel>Key Terms</SectionLabel>
            <KeyTermChips terms={cluster.defined_terms} />
          </div>
        )}

        {sources.length > 0 && (
          <div className="pt-4 border-t border-border flex flex-wrap gap-1.5">
            {sources.map((src, j) => (
              <SourceBadge
                key={j}
                source={src}
                url={cluster.urls?.[j]}
                lean={cluster.source_credibility?.[j]?.label}
              />
            ))}
          </div>
        )}
      </div>

      <button
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-6 py-3.5 border-t border-border bg-secondary/40 hover:bg-secondary transition-colors text-left"
      >
        <span className="text-base font-semibold" style={{ color: "var(--accent)" }}>
          {open
            ? "Hide full summary and articles"
            : `Show full summary and all ${articleCount} articles with analysis`}
        </span>
        {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>

      {open && (
        <div className="p-6 border-t border-border bg-background/50 space-y-4">
          <h4
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "1.3rem",
              lineHeight: 1.2,
            }}
          >
            Per-Article Breakdown
          </h4>
          {loading && (
            <div className="flex items-center gap-2 text-base text-muted-foreground">
              <Spinner size={16} />
              <span>Loading articles…</span>
            </div>
          )}
          {error && <p className="text-base text-destructive">Couldn't load articles: {error}</p>}
          {articles?.map(a => (
            <ArticleBlock key={a.url} article={a} entry={a} status="done" statusError={null} />
          ))}
        </div>
      )}
    </article>
  );
}

export function ArchivePage() {
  // ?date=YYYY-MM-DD&topic=<cluster id> keeps the selection in the URL, so
  // back/forward and shared links land on the same day (and open topic).
  const [params, setParams] = useSearchParams();
  const pendingScroll = useRef<string | null>(null);
  const [dates, setDates] = useState<SnapshotMeta[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [month, setMonth] = useState<Date | undefined>(undefined);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const latestDay = useRef<string | null>(null);
  const [openTopics, setOpenTopics] = useState<Set<string>>(new Set());
  const [loadingDates, setLoadingDates] = useState(true);
  const [loadingSnap, setLoadingSnap] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datesError, setDatesError] = useState<string | null>(null);

  const days = useMemo(() => dates.map(d => d.date).sort(), [dates]);
  const available = useMemo(() => new Set(days), [days]);
  const selectedIndex = selected ? days.indexOf(selected) : -1;
  const prevDay = selectedIndex > 0 ? days[selectedIndex - 1] : null;
  const nextDay = selectedIndex >= 0 && selectedIndex < days.length - 1 ? days[selectedIndex + 1] : null;

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchJson<{ snapshots?: SnapshotMeta[] }>("/api/archive");
        const snaps: SnapshotMeta[] = data.snapshots ?? [];
        setDates(snaps);
        // Open the linked day if it's archived, else the latest (the API
        // lists newest first).
        const linked = params.get("date");
        if (linked && snaps.some(s => s.date === linked)) {
          loadSnapshot(linked, params.get("topic"));
        } else if (snaps.length > 0) {
          loadSnapshot(snaps[0].date);
        }
      } catch (e) {
        setDatesError(errorMessage(e, "Failed to load archive"));
      } finally {
        setLoadingDates(false);
      }
    })();
  }, []);

  async function loadSnapshot(date: string, topic: string | null = null) {
    setSelected(date);
    setMonth(parseDay(date));
    setOpenTopics(topic ? new Set([topic]) : new Set());
    pendingScroll.current = topic;
    setParams(topic ? { date, topic } : { date }, { replace: true });
    setLoadingSnap(true);
    setError(null);
    setSnapshot(null);
    // Clicking through days quickly: only the last day picked may show,
    // whichever response arrives last.
    latestDay.current = date;
    try {
      const snap = await fetchJson<Snapshot>(`/api/archive/${date}`);
      if (latestDay.current === date) setSnapshot(snap);
    } catch (e) {
      if (latestDay.current === date) setError(errorMessage(e, "Failed to load snapshot"));
    } finally {
      if (latestDay.current === date) setLoadingSnap(false);
    }
  }

  function toggleTopic(id: string) {
    setOpenTopics(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Daily Brief headlines open their topic below and scroll to it.
  function jumpToTopic(id: string) {
    setOpenTopics(prev => new Set(prev).add(id));
    if (selected) setParams({ date: selected, topic: id }, { replace: true });
    requestAnimationFrame(() =>
      document.getElementById(`topic-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }

  // A topic linked in the URL scrolls into view once its day has rendered.
  useEffect(() => {
    const id = pendingScroll.current;
    if (!snapshot || !id) return;
    pendingScroll.current = null;
    requestAnimationFrame(() =>
      document.getElementById(`topic-${id}`)?.scrollIntoView({ block: "start" }),
    );
  }, [snapshot]);

  const brief = snapshot?.daily_brief;

  return (
    <div>
      <AiBanner />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
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
            Archive
          </h1>
          <p className="mt-2 text-lg text-muted-foreground">
            Pick a day to read its Daily Brief and every topic covered that day.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-8 items-start">
          {/* Calendar */}
          <aside className="min-w-0 bg-card border border-border rounded p-3 sm:p-4 lg:sticky lg:top-24 space-y-3">
            <SectionLabel>Choose a day</SectionLabel>
            {loadingDates && (
              <div className="flex justify-center py-8">
                <Spinner size={22} />
              </div>
            )}
            {datesError && <p className="text-sm text-destructive">{datesError}</p>}
            {!loadingDates && !datesError && days.length === 0 && (
              <p className="text-base text-muted-foreground max-w-xs">
                No archive yet. Come back tomorrow.
              </p>
            )}
            {days.length > 0 && (
              <>
                <div className="flex justify-center">
                  <Calendar
                    mode="single"
                    selected={selected ? parseDay(selected) : undefined}
                    onSelect={d => {
                      if (d && available.has(dayKey(d))) loadSnapshot(dayKey(d));
                    }}
                    month={month}
                    onMonthChange={setMonth}
                    fromDate={parseDay(days[0])}
                    toDate={parseDay(days[days.length - 1])}
                    disabled={d => !available.has(dayKey(d))}
                    modifiers={{ archived: d => available.has(dayKey(d)) }}
                    modifiersClassNames={{ archived: ARCHIVED_DAY_CLASS }}
                    showOutsideDays={false}
                    className="p-1 sm:p-3"
                    classNames={CALENDAR_CLASSES}
                  />
                </div>
                <div className="flex items-center justify-between gap-2 pt-3 border-t border-border">
                  <button
                    onClick={() => prevDay && loadSnapshot(prevDay)}
                    disabled={!prevDay}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded border border-border text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-35 disabled:pointer-events-none"
                  >
                    <ChevronLeft size={16} /> Earlier day
                  </button>
                  <button
                    onClick={() => nextDay && loadSnapshot(nextDay)}
                    disabled={!nextDay}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded border border-border text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-35 disabled:pointer-events-none"
                  >
                    Later day <ChevronRight size={16} />
                  </button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Archive starts {formatLongDate(days[0])}.
                </p>
              </>
            )}
          </aside>

          {/* Selected day */}
          <section className="min-w-0">
            {loadingSnap && (
              <StateBox>
                <Spinner />
                <p>Loading…</p>
              </StateBox>
            )}

            {error && !loadingSnap && (
              <StateBox>
                <AlertCircle className="text-destructive" size={28} />
                <p className="text-destructive text-base">{error}</p>
              </StateBox>
            )}

            {!loadingSnap && !error && snapshot && (
              <div className="space-y-8">
                <h2
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 700,
                    fontSize: "1.75rem",
                    lineHeight: 1.2,
                  }}
                >
                  {formatLongDate(snapshot.date)}
                </h2>

                {brief && brief.sections.length > 0 ? (
                  <div>
                    <h3
                      className="mb-4"
                      style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.55rem", lineHeight: 1.2 }}
                    >
                      Daily Brief
                    </h3>
                    <DailyBrief
                      data={brief}
                      topicHref={id => `/archive?date=${snapshot.date}&topic=${encodeURIComponent(id)}`}
                      onSelect={jumpToTopic}
                      showSources={false}
                    />
                  </div>
                ) : (
                  <div className="bg-card border border-border rounded p-6 text-base text-muted-foreground">
                    No topic had enough coverage for a Daily Brief this day.
                  </div>
                )}

                <div>
                  <div className="mb-4">
                    <h2
                      style={{
                        fontFamily: "var(--font-display)",
                        fontWeight: 700,
                        fontSize: "1.55rem",
                        lineHeight: 1.2,
                      }}
                    >
                      All topics ({snapshot.clusters.length})
                    </h2>
                    <p className="mt-1 text-base text-muted-foreground">
                      Expand a topic for its full summary and each article's analysis.
                    </p>
                  </div>

                  {snapshot.clusters.length === 0 ? (
                    <p className="text-base text-muted-foreground">No summaries saved for this day.</p>
                  ) : (
                    <div className="space-y-5">
                      {snapshot.clusters.map(cluster => (
                        <ArchiveTopic
                          key={`${snapshot.date}:${cluster.cluster_id}`}
                          date={snapshot.date}
                          cluster={cluster}
                          open={openTopics.has(cluster.cluster_id)}
                          onToggle={() => toggleTopic(cluster.cluster_id)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
