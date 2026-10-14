import { useState, useEffect } from "react";
import { Link } from "react-router";
import { RefreshCw, AlertCircle } from "lucide-react";
import {
  BrandIcon, Spinner, StateBox, AiBanner, SourceBadge, SectionLabel,
  getTopicIcon, formatRelativeDate, Region, RegionTag,
} from "./shared";
import { DailyBriefCard, DailySummary } from "./DailyBrief";

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
  region?: Region | null;
}

interface SummariesData {
  last_updated?: string;
  clusters: Cluster[];
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
            className="block link"
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              fontSize: "1.2rem",
              lineHeight: 1.3,
            }}
          >
            {title.length > 90 ? title.slice(0, 90) + "…" : title}
          </Link>
          <span
            className="mt-1.5 flex items-center gap-2 text-sm text-muted-foreground"
            style={{ fontFamily: "var(--font-data)" }}
          >
            {cluster.region && <RegionTag region={cluster.region} />}
            {cluster.article_count} article{cluster.article_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div
        className="px-5 pb-4 text-base text-foreground leading-relaxed flex-1 [&_mark]:bg-yellow-100 [&_mark]:rounded-sm [&_mark]:px-0.5"
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
                className="cursor-help inline-flex px-2 py-0.5 rounded-sm text-sm font-medium bg-secondary text-secondary-foreground border border-border"
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
          className="text-base font-medium link"
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
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 text-center">
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
          <p className="mt-3 text-sm tracking-[0.2em] uppercase text-muted-foreground">
            Multi-Source&nbsp;&nbsp;·&nbsp;&nbsp;Unbiased&nbsp;&nbsp;·&nbsp;&nbsp;Political News
          </p>
          <p className="mt-4 max-w-2xl mx-auto text-muted-foreground text-lg leading-relaxed">
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
                "px-5 py-2 rounded text-base font-medium transition-colors capitalize",
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
            className="text-sm text-muted-foreground"
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
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90 transition-opacity"
            >
              <RefreshCw size={16} /> Try Again
            </button>
          </StateBox>
        )}

        {!loading && !error && isEmpty && (
          <StateBox>
            <p>No summaries available yet. Check back soon.</p>
            <button
              onClick={load}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90"
            >
              <RefreshCw size={16} /> Refresh
            </button>
          </StateBox>
        )}

        {!loading && !error && !isEmpty && (
          <>
            {view === "daily" && daily && !noBrief && <DailyBriefCard data={daily} />}
            {view === "topics" && summaries && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
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
