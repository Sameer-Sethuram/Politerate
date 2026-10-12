import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router";
import { ExternalLink, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { Spinner, StateBox, LeanBadge, CredBadge, PageContainer, SectionLabel } from "./shared";

interface Article {
  url: string;
  title: string;
  source: string;
  lean?: string | null;
  credibility_score?: number | null;
  // Articles sharing a topic_id cover the same story (one topic cluster).
  topic_id: string | null;
  in_brief: boolean;
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
const LEADS_SHOWN = 9;

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
        <Link
          to={detailUrl}
          className="text-lg font-medium text-foreground hover:underline decoration-[var(--accent)] underline-offset-2 leading-snug flex-1 min-w-0"
        >
          {article.title || "Untitled"}
        </Link>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-1"
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
}: {
  group: DayGroup;
  heading: string;
  threshold: number;
}) {
  const [showAllLeads, setShowAllLeads] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const leads = showAllLeads ? group.leads : group.leads.slice(0, LEADS_SHOWN);
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {leads.map(a => (
              <ArticleCard
                key={a.url}
                article={a}
                otherOutlets={a.topic_id ? (group.storySize.get(a.topic_id) ?? 1) - 1 : 0}
              />
            ))}
          </div>
          {group.leads.length > LEADS_SHOWN && (
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
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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

export function AllArticlesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [today, setToday] = useState("");
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);

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

  const days = useMemo(() => {
    const byDay = new Map<string, Article[]>();
    for (const a of articles) {
      const day = a.scraped_at.slice(0, 10);
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day)!.push(a);
    }
    return [...byDay.keys()]
      .sort()
      .reverse()
      .map(day => groupDay(day, byDay.get(day)!, threshold));
  }, [articles, threshold]);

  return (
    <PageContainer>
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
          <p>No articles from the past 7 days yet.</p>
        </StateBox>
      )}

      {!loading && !error && days.length > 0 && (
        <div className="space-y-14">
          {days.map(group => (
            <DaySection
              key={group.day}
              group={group}
              threshold={threshold}
              heading={group.day === today ? `Today · ${formatDayHeading(group.day)}` : formatDayHeading(group.day)}
            />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
