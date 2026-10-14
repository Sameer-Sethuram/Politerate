import { useState, useEffect } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, AlertCircle } from "lucide-react";
import {
  Spinner, StateBox, AiBanner, SourceBadge, SectionLabel, PageContainer, Region, RegionTag,
} from "./shared";
import { ArticleBlock, ArticleEntry, AnalysisStatus, ClusterArticle } from "./ArticleBreakdown";
import { DefinedTerm, DetailedSummary, KeyTermChips, TopicSummary } from "./TopicSummary";

interface ClusterData {
  cluster_id: string;
  titles?: string[];
  summary: string;
  highlighted_summary?: string;
  detailed_summary?: DetailedSummary | null;
  region?: Region | null;
  article_count: number;
  articles: ClusterArticle[];
  sources: string[];
  defined_terms?: DefinedTerm[];
}

export function ClusterPage() {
  // react-router already URL-decodes route params.
  const { clusterId = "" } = useParams<{ clusterId: string }>();

  const [cluster, setCluster] = useState<ClusterData | null>(null);
  const [analysisEntries, setAnalysisEntries] = useState<Record<string, ArticleEntry>>({});
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>("loading");
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clusterId) return;
    const id = encodeURIComponent(clusterId);

    // /api/summaries/<id> (unlike the /api/summaries list) includes `articles`.
    (async () => {
      try {
        const res = await fetch(`/api/summaries/${id}`);
        if (res.status === 404) throw new Error("Cluster not found in current snapshot.");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setCluster(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load cluster");
      } finally {
        setLoading(false);
      }
    })();

    // Analysis is slow and optional - load in parallel without blocking the page.
    (async () => {
      try {
        const res = await fetch(`/api/cluster/${id}/analysis`);
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error ?? `HTTP ${res.status}`);
        }
        const data = await res.json();
        const byUrl: Record<string, ArticleEntry> = {};
        for (const entry of data.articles ?? []) byUrl[entry.url] = entry;
        setAnalysisEntries(byUrl);
        setAnalysisStatus("done");
      } catch (e) {
        setAnalysisError(e instanceof Error ? e.message : "Unknown error");
        setAnalysisStatus("error");
      }
    })();
  }, [clusterId]);

  return (
    <div>
      <AiBanner />
      {/* Same width as the Daily Brief on the home page. */}
      <PageContainer>
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-base text-muted-foreground mb-6 link"
        >
          <ArrowLeft size={17} />
          Back to Today
        </Link>

        {loading && (
          <StateBox>
            <Spinner />
            <p>Loading topic…</p>
          </StateBox>
        )}

        {!loading && error && (
          <StateBox>
            <AlertCircle className="text-destructive" size={32} />
            <p className="text-destructive font-medium">{error}</p>
            <Link
              to="/"
              className="px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90"
            >
              Back to Today
            </Link>
          </StateBox>
        )}

        {!loading && !error && cluster && (
          <div className="space-y-6">
            {/* Cluster header */}
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                {cluster.region && <RegionTag region={cluster.region} className="text-sm py-1.5 px-2.5" />}
                <span
                  className="px-3 py-1.5 rounded bg-secondary text-secondary-foreground text-sm"
                  style={{ fontFamily: "var(--font-data)" }}
                >
                  {cluster.article_count} article{cluster.article_count !== 1 ? "s" : ""}
                </span>
                <span
                  className="px-3 py-1.5 rounded bg-secondary text-secondary-foreground text-sm"
                  style={{ fontFamily: "var(--font-data)" }}
                >
                  {cluster.sources?.length ?? 0} source{cluster.sources?.length !== 1 ? "s" : ""}
                </span>
                {!!cluster.defined_terms?.length && (
                  <span
                    className="px-3 py-1.5 rounded bg-secondary text-secondary-foreground text-sm"
                    style={{ fontFamily: "var(--font-data)" }}
                  >
                    {cluster.defined_terms.length} key term{cluster.defined_terms.length !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <h1
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 800,
                  fontSize: "clamp(1.75rem, 4vw, 2.4rem)",
                  lineHeight: 1.15,
                  letterSpacing: "-0.01em",
                }}
              >
                {cluster.titles?.[0] ?? "Topic Summary"}
              </h1>
            </div>

            {/* Summary card */}
            <div className="bg-card border border-border rounded p-6 sm:p-8 shadow-sm space-y-5">
              <TopicSummary
                detailed={cluster.detailed_summary}
                fallbackHtml={cluster.highlighted_summary || cluster.summary}
              />

              {cluster.defined_terms && cluster.defined_terms.length > 0 && (
                <div className="pt-4 border-t border-border space-y-2">
                  <SectionLabel>Key Terms</SectionLabel>
                  <KeyTermChips terms={cluster.defined_terms} />
                </div>
              )}

              <div className="pt-4 border-t border-border space-y-2">
                <SectionLabel>Sources</SectionLabel>
                <div className="flex flex-wrap gap-1.5">
                  {cluster.articles.map((a, i) => (
                    <SourceBadge key={i} source={a.source} url={a.url} lean={a.lean ?? undefined} />
                  ))}
                </div>
              </div>
            </div>

            {/* Per-article breakdown */}
            <div>
              <h2
                className="mb-4"
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: "1.55rem",
                  lineHeight: 1.2,
                }}
              >
                Per-Article Breakdown
              </h2>
              <div className="space-y-4">
                {cluster.articles.map(article => (
                  <ArticleBlock
                    key={article.url}
                    article={article}
                    entry={analysisEntries[article.url]}
                    status={analysisStatus}
                    statusError={analysisError}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </PageContainer>
    </div>
  );
}
