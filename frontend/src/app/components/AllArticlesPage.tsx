import { useState, useEffect } from "react";
import { Link } from "react-router";
import { ExternalLink, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { Spinner, StateBox, LeanBadge, CredBadge, PageContainer, SectionLabel } from "./shared";

interface Article {
  url: string;
  title: string;
  source: string;
  lean?: string;
  credibility_score?: number;
  in_summary: boolean;
  scraped_at: string;
}

function formatDayHeading(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

function ArticleCard({ article }: { article: Article }) {
  const detailUrl = `/article?url=${encodeURIComponent(article.url)}`;

  return (
    <article className="bg-card border border-border rounded p-4 hover:shadow-sm transition-shadow flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <Link
          to={detailUrl}
          className="text-sm font-medium text-foreground hover:underline decoration-[var(--accent)] underline-offset-2 leading-snug flex-1 min-w-0"
        >
          {article.title || "Untitled"}
        </Link>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
          onClick={e => e.stopPropagation()}
          title="Open original article"
        >
          <ExternalLink size={14} />
        </a>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground">{article.source}</span>
        {article.lean && article.lean !== "unknown" && <LeanBadge lean={article.lean} />}
        {article.credibility_score != null && <CredBadge score={article.credibility_score} />}
      </div>
    </article>
  );
}

function ArticleSection({
  title,
  subtitle,
  articles,
}: {
  title: string;
  subtitle?: string;
  articles: Article[];
}) {
  const [collapsed, setCollapsed] = useState(articles.length > 6);
  const visible = collapsed ? articles.slice(0, 6) : articles;

  return (
    <section>
      <div className="flex items-center justify-between gap-4 mb-4">
        <div>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "1.25rem",
              lineHeight: 1.2,
            }}
          >
            {title}
          </h2>
          {subtitle && <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {articles.length > 6 && (
          <button
            onClick={() => setCollapsed(c => !c)}
            className="flex items-center gap-1 text-xs text-muted-foreground border border-border rounded px-3 py-1.5 hover:text-foreground hover:border-foreground/20 transition-colors shrink-0"
          >
            {collapsed ? (
              <>Show all ({articles.length}) <ChevronDown size={12} /></>
            ) : (
              <>Show less <ChevronUp size={12} /></>
            )}
          </button>
        )}
      </div>

      {articles.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">No articles here yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {visible.map((a, i) => (
            <ArticleCard key={i} article={a} />
          ))}
        </div>
      )}
    </section>
  );
}

export function AllArticlesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inBrief, setInBrief] = useState<Article[]>([]);
  const [other, setOther] = useState<Article[]>([]);
  const [pastDays, setPastDays] = useState<[string, Article[]][]>([]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/all-articles");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const articles: Article[] = data.articles ?? [];
        const today: string = data.today;

        const todays = articles.filter(a => a.scraped_at.slice(0, 10) === today);
        setInBrief(todays.filter(a => a.in_summary));
        setOther(todays.filter(a => !a.in_summary));

        // Articles arrive newest first, so the day groups do too.
        const byDay = new Map<string, Article[]>();
        for (const a of articles) {
          const day = a.scraped_at.slice(0, 10);
          if (day === today) continue;
          if (!byDay.has(day)) byDay.set(day, []);
          byDay.get(day)!.push(a);
        }
        setPastDays([...byDay.entries()]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <PageContainer>
      {/* Page header */}
      <div className="mb-8 pb-6 border-b border-border">
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "2rem",
            lineHeight: 1.15,
          }}
        >
          All Articles
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Today's articles — split by whether they made the Daily Brief — plus articles from the past 7 days.
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

      {!loading && !error && (
        <div className="space-y-12">
          <ArticleSection
            title="In Today's Brief"
            articles={inBrief}
          />
          <ArticleSection
            title="Other Articles Today"
            subtitle="Passed credibility checks but not clustered or filtered out."
            articles={other}
          />

          {pastDays.length > 0 && (
            <div className="pt-8 border-t border-border">
              <SectionLabel>Past 7 Days</SectionLabel>
              <div className="mt-4 space-y-12">
                {pastDays.map(([day, articles]) => (
                  <ArticleSection key={day} title={formatDayHeading(day)} articles={articles} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
