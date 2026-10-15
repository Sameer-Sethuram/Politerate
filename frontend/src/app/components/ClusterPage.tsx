import { useState, useEffect } from "react";
import { Link, useLocation, useParams } from "react-router";
import { ArrowLeft, AlertCircle, ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import {
  Spinner, StateBox, AiBanner, SourceBadge, SectionLabel, PageContainer, Region,
} from "./shared";
import { ArticleBlock, ArticleEntry, AnalysisStatus, ClusterArticle } from "./ArticleBreakdown";
import { DefinedTerm, DetailedSummary, KeyTermChips, TopicSummary } from "./TopicSummary";
import { GenreWeights, TopicTags, topicTags } from "./topicTags";

// Where the back link goes, by the page that opened the topic.
const BACK_LINKS = {
  today: { to: "/", label: "Back to Today" },
  topics: { to: "/topics", label: "Back to Topics" },
} as const;

interface ClusterData {
  cluster_id: string;
  titles?: string[];
  summary: string;
  highlighted_summary?: string;
  detailed_summary?: DetailedSummary | null;
  region?: Region | null;
  category?: string | null;
  map?: { genre_weights?: Partial<GenreWeights> | null } | null;
  article_count: number;
  articles: ClusterArticle[];
  sources: string[];
  defined_terms?: DefinedTerm[];
}

export function ClusterPage() {
  // react-router already URL-decodes route params.
  const { clusterId = "" } = useParams<{ clusterId: string }>();
  const location = useLocation();
  const from = (location.state as { from?: keyof typeof BACK_LINKS } | null)?.from;
  const back = BACK_LINKS[from ?? "today"] ?? BACK_LINKS.today;
  // Breakdowns are collapsed; open the outlets you want to compare.
  const [openArticles, setOpenArticles] = useState<Set<string>>(new Set());

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
        {/* Back link: to the page that opened the topic (the Topics map
            keeps its zoom and position). */}
        <Link
          to={back.to}
          className="inline-flex items-center gap-1.5 text-base text-muted-foreground mb-6 link"
        >
          <ArrowLeft size={17} />
          {back.label}
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
              to={back.to}
              className="px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90"
            >
              {back.label}
            </Link>
          </StateBox>
        )}

        {!loading && !error && cluster && (
          <div className="space-y-6">
            {/* Cluster header */}
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <TopicTags tags={topicTags(cluster.category, cluster.region, cluster.map?.genre_weights)} />
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

            {/* Per-article breakdown, one dropdown per outlet */}
            <div>
              <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
                <div>
                  <h2
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 700,
                      fontSize: "1.55rem",
                      lineHeight: 1.2,
                    }}
                  >
                    Per-Article Breakdown
                  </h2>
                  <p className="mt-1 text-base text-muted-foreground">
                    Open an outlet to see its summary and how its language was analyzed.
                  </p>
                </div>
                {cluster.articles.length > 1 && (
                  <button
                    type="button"
                    onClick={() =>
                      setOpenArticles(
                        openArticles.size === cluster.articles.length
                          ? new Set()
                          : new Set(cluster.articles.map(a => a.url)),
                      )
                    }
                    className="inline-flex items-center gap-1.5 rounded border border-border px-3.5 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    {openArticles.size === cluster.articles.length ? (
                      <><ChevronsDownUp size={16} /> Collapse all</>
                    ) : (
                      <><ChevronsUpDown size={16} /> Expand all</>
                    )}
                  </button>
                )}
              </div>
              <div className="space-y-3">
                {cluster.articles.map(article => (
                  <ArticleBlock
                    key={article.url}
                    article={article}
                    entry={analysisEntries[article.url]}
                    status={analysisStatus}
                    statusError={analysisError}
                    open={openArticles.has(article.url)}
                    onToggle={() =>
                      setOpenArticles(prev => {
                        const next = new Set(prev);
                        if (next.has(article.url)) next.delete(article.url);
                        else next.add(article.url);
                        return next;
                      })
                    }
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
