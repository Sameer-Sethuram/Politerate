import { useState, useEffect } from "react";
import { Link } from "react-router";
import { RefreshCw, AlertCircle } from "lucide-react";
import {
  BrandIcon, Spinner, StateBox, AiBanner, SourceBadge, SectionLabel,
  getTopicIcon, formatRelativeDate,
} from "./shared";

interface Cluster {
  cluster_id: string;
  summary: string;
  highlighted_summary?: string;
  titles: string[];
  sources: string[];
  urls: string[];
  article_count: number;
  source_credibility?: Array<{ score: number | null; label: string }>;
  defined_terms?: Array<{ term: string; definition: string }>;
}

interface BriefSection {
  cluster_id: string;
  headline: string;
  bullets: string[];
  article_count: number;
}

interface DailySummary {
  sections: BriefSection[];
  cluster_count: number;
  total_articles: number;
  source_count: number;
  source_links: Array<{ source: string; url: string }>;
}

interface SummariesData {
  last_updated?: string;
  clusters: Cluster[];
}

function StatPill({ value, label }: { value: number; label: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-secondary text-secondary-foreground text-xs"
      style={{ fontFamily: "var(--font-data)" }}
    >
      <strong>{value}</strong>&nbsp;{label}
    </span>
  );
}

function DailyBriefCard({ data }: { data: DailySummary }) {
  return (
    <article className="bg-card border border-border rounded p-6 sm:p-8 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-4 pb-5 mb-5 border-b border-border">
        <h2
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "1.5rem",
            lineHeight: 1.2,
          }}
        >
          Today's Political Brief
        </h2>
        <div className="flex flex-wrap gap-2">
          <StatPill value={data.cluster_count} label="topics" />
          <StatPill value={data.total_articles} label="articles" />
          <StatPill value={data.source_count} label="sources" />
        </div>
      </header>

      <div className="space-y-6 mb-6">
        {data.sections.map(s => (
          <section key={s.cluster_id}>
            <h3 className="flex items-start gap-2 mb-2">
              <span className="text-lg leading-none mt-0.5 shrink-0">{getTopicIcon(s.bullets.join(" "))}</span>
              <Link
                to={`/cluster/${encodeURIComponent(s.cluster_id)}`}
                className="hover:underline decoration-[var(--accent)] underline-offset-2"
                style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "1.05rem", lineHeight: 1.35 }}
              >
                {s.headline.length > 110 ? s.headline.slice(0, 110) + "…" : s.headline}
              </Link>
            </h3>
            <ul className="list-disc pl-11 space-y-1.5 text-base text-foreground leading-relaxed marker:text-muted-foreground">
              {s.bullets.map((b, i) => (
                <li key={i} dangerouslySetInnerHTML={{ __html: b }} />
              ))}
            </ul>
          </section>
        ))}
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

function ClusterCard({ cluster }: { cluster: Cluster }) {
  const icon = getTopicIcon(cluster.summary);
  const title = cluster.titles?.[0] ?? "News Summary";
  const detailUrl = `/cluster/${encodeURIComponent(cluster.cluster_id)}`;

  return (
    <article className="bg-card border border-border rounded flex flex-col gap-0 hover:shadow-md transition-shadow">
      {/* Head */}
      <div className="flex items-start gap-3 p-5 pb-4">
        <span className="text-2xl leading-none mt-0.5 shrink-0">{icon}</span>
        <div className="min-w-0 flex-1">
          <Link
            to={detailUrl}
            className="block hover:underline decoration-[var(--accent)] underline-offset-2 transition-colors"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: "1rem",
              lineHeight: 1.35,
              color: "var(--foreground)",
            }}
          >
            {title.length > 90 ? title.slice(0, 90) + "…" : title}
          </Link>
          <span
            className="mt-1 block text-xs text-muted-foreground"
            style={{ fontFamily: "var(--font-data)" }}
          >
            {cluster.article_count} article{cluster.article_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div
        className="px-5 pb-4 text-sm text-foreground leading-relaxed flex-1 [&_mark]:bg-yellow-100 [&_mark]:rounded-sm [&_mark]:px-0.5"
        dangerouslySetInnerHTML={{ __html: cluster.highlighted_summary || cluster.summary }}
      />

      {/* Sources */}
      <div className="px-5 pb-4 pt-3 border-t border-border space-y-2">
        <SectionLabel>Sources</SectionLabel>
        <div className="flex flex-wrap gap-1.5">
          {cluster.sources.map((src, i) => (
            <SourceBadge
              key={i}
              source={src}
              url={cluster.urls?.[i]}
              credibility={cluster.source_credibility?.[i] ?? undefined}
              lean={cluster.source_credibility?.[i]?.label}
            />
          ))}
        </div>
      </div>

      {/* Key terms */}
      {cluster.defined_terms && cluster.defined_terms.length > 0 && (
        <div className="px-5 pb-4 pt-3 border-t border-border space-y-2">
          <SectionLabel>Key Terms</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {cluster.defined_terms.map(t => (
              <span
                key={t.term}
                title={t.definition}
                className="cursor-help inline-flex px-2 py-0.5 rounded-sm text-xs font-medium bg-secondary text-secondary-foreground border border-border"
              >
                {t.term}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer link */}
      <div className="px-5 py-3 border-t border-border text-right">
        <Link
          to={detailUrl}
          className="text-sm font-medium hover:underline"
          style={{ color: "var(--accent)" }}
        >
          Full breakdown →
        </Link>
      </div>
    </article>
  );
}

export function HomePage() {
  const [view, setView] = useState<"daily" | "topics">("daily");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [daily, setDaily] = useState<DailySummary | null>(null);
  const [summaries, setSummaries] = useState<SummariesData | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [dailyRes, sumRes] = await Promise.all([
        fetch("/api/daily-summary"),
        fetch("/api/summaries"),
      ]);
      if (!sumRes.ok) throw new Error(`HTTP ${sumRes.status}`);
      const [dailyData, sumData] = await Promise.all([dailyRes.json(), sumRes.json()]);
      setDaily(dailyData);
      setSummaries(sumData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load news");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const noBrief = !daily?.sections?.length;
  const noClusters = !summaries?.clusters?.length;
  const isEmpty = !loading && !error && noBrief && noClusters;

  return (
    <div>
      <AiBanner />

      {/* Hero */}
      <div className="border-b border-border bg-card">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 text-center">
          <h1
            className="flex items-center justify-center gap-3 sm:gap-4 tracking-tight text-brand-dark"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "clamp(2.5rem, 6vw, 4rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.01em",
            }}
          >
            <BrandIcon className="w-[0.9em] h-[0.9em]" />
            <span>
              Po<span className="text-brand-accent">literate</span>
            </span>
          </h1>
          <p className="mt-3 text-xs tracking-[0.2em] uppercase text-muted-foreground">
            Multi-Source&nbsp;&nbsp;·&nbsp;&nbsp;Unbiased&nbsp;&nbsp;·&nbsp;&nbsp;Political News
          </p>
          <p className="mt-4 max-w-lg mx-auto text-muted-foreground text-sm leading-relaxed">
            Today's political news, summarized across trusted outlets with key terms highlighted
            and sources one click away.
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 pb-2 flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-0.5 p-1 bg-secondary rounded">
          {(["daily", "topics"] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={[
                "px-4 py-1.5 rounded text-sm font-medium transition-colors capitalize",
                view === v
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {v === "daily" ? "Daily Brief" : "Topics"}
            </button>
          ))}
        </div>

        {summaries?.last_updated && (
          <span
            className="text-xs text-muted-foreground"
            style={{ fontFamily: "var(--font-data)" }}
          >
            Updated {formatRelativeDate(summaries.last_updated)}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 pb-12">
        {loading && (
          <StateBox>
            <Spinner />
            <p>Loading today's summaries…</p>
          </StateBox>
        )}

        {!loading && error && (
          <StateBox>
            <AlertCircle className="text-destructive" size={32} />
            <p className="text-destructive font-medium">Unable to load: {error}</p>
            <button
              onClick={load}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <RefreshCw size={14} /> Try Again
            </button>
          </StateBox>
        )}

        {!loading && !error && isEmpty && (
          <StateBox>
            <p>No summaries available yet. Check back soon.</p>
            <button
              onClick={load}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-medium hover:opacity-90"
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </StateBox>
        )}

        {!loading && !error && !isEmpty && (
          <>
            {view === "daily" && daily && !noBrief && <DailyBriefCard data={daily} />}
            {view === "topics" && summaries && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {summaries.clusters.map(c => (
                  <ClusterCard key={c.cluster_id} cluster={c} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
