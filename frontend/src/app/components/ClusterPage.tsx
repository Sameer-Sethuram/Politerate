import { useState, useEffect } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, AlertCircle, ExternalLink } from "lucide-react";
import {
  Spinner, StateBox, AiBanner, SourceBadge, AnnotationLegend, AnnotatedText,
  BiasBar, EmotionBadge, SubjectivityBar, SectionLabel,
  Chunk, chunkCategory, formatTechnique,
} from "./shared";

interface DefinedTerm {
  term: string;
  definition: string;
}

interface ClusterArticle {
  url: string;
  title?: string;
  source: string;
  credibility_score?: number | null;
  credibility_label?: string;
  lean?: string | null;
}

interface ClusterData {
  cluster_id: string;
  titles?: string[];
  summary: string;
  highlighted_summary?: string;
  article_count: number;
  articles: ClusterArticle[];
  sources: string[];
  defined_terms?: DefinedTerm[];
}

interface ArticleAnalysis {
  dominant_bias: string;
  dominant_emotion: string;
  subjectivity_ratio: number;
  technique_counts: Record<string, number>;
}

interface ArticleEntry {
  url: string;
  analysis_status?: string;
  analysis_error?: string;
  analysis?: { article: ArticleAnalysis; chunks: Chunk[] } | null;
}

type AnalysisStatus = "loading" | "done" | "error";

function ArticleBlock({
  article,
  entry,
  status,
  statusError,
}: {
  article: ClusterArticle;
  entry?: ArticleEntry;
  status: AnalysisStatus;
  statusError: string | null;
}) {
  const [showAnnotated, setShowAnnotated] = useState(true);
  const [showChunks, setShowChunks] = useState(false);

  const analysis = entry?.analysis;
  const chunks = analysis?.chunks ?? [];
  const hasAnalysis = !!analysis && !entry?.analysis_error;

  return (
    <section className="bg-card border border-border rounded overflow-hidden">
      {/* Article header */}
      <div className="p-5 border-b border-border">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3
              className="leading-snug mb-1"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: "1rem",
              }}
            >
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline decoration-[var(--accent)] underline-offset-2"
              >
                {article.title ?? "Untitled"}
              </a>
            </h3>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <strong>{article.source}</strong>
              {article.credibility_score != null && (
                <>
                  <span>·</span>
                  <span style={{ fontFamily: "var(--font-data)" }}>
                    credibility {article.credibility_score.toFixed(2)}
                  </span>
                </>
              )}
              {article.credibility_label && article.credibility_label !== "unknown" && (
                <>
                  <span>·</span>
                  <span>bias {article.credibility_label}</span>
                </>
              )}
            </div>
          </div>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
            title="Open original"
          >
            <ExternalLink size={14} />
          </a>
        </div>
      </div>

      {/* Analysis slot */}
      <div className="p-5">
        {status === "loading" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner size={14} />
            <span>Loading analysis…</span>
          </div>
        )}

        {status === "error" && (
          <p className="text-sm text-muted-foreground">
            Analyzer request failed: {statusError}
          </p>
        )}

        {status === "done" && !entry && (
          <p className="text-sm text-muted-foreground">No analysis available.</p>
        )}

        {/* Analysis is read from the pipeline's cache, never run live. */}
        {status === "done" && entry && !entry.analysis && !entry.analysis_error && (
          <p className="text-sm text-muted-foreground">
            {entry.analysis_status === "pending"
              ? "Analysis pending — this article hasn’t been processed yet. Refresh after the next pipeline run."
              : "No cached analysis available for this article."}
          </p>
        )}

        {entry?.analysis_error && (
          <p className="text-sm text-muted-foreground">
            Analyzer unavailable: {entry.analysis_error}
          </p>
        )}

        {hasAnalysis && (
          <div className="space-y-4">
            {/* Annotated text */}
            {chunks.length > 0 && (
              <div>
                <div className="flex items-center justify-between gap-4 mb-3">
                  <AnnotationLegend />
                  <button
                    onClick={() => setShowAnnotated(a => !a)}
                    className="shrink-0 text-xs border border-border rounded px-3 py-1 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showAnnotated ? "Hide analysis" : "Show analysis"}
                  </button>
                </div>
                {showAnnotated ? (
                  <AnnotatedText chunks={chunks} />
                ) : (
                  <p className="text-sm leading-7">{chunks.map(c => c.text).join(" ")}</p>
                )}
              </div>
            )}

            {/* Summary grid */}
            <div className="border-t border-border pt-4">
              <SectionLabel>Summary</SectionLabel>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-2">
                <div className="bg-secondary rounded p-3 space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider" style={{ fontSize: "0.65rem" }}>Bias</div>
                  <BiasBar bias={analysis!.article.dominant_bias ?? "center"} />
                </div>
                <div className="bg-secondary rounded p-3 space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider" style={{ fontSize: "0.65rem" }}>Emotion</div>
                  <EmotionBadge emotion={analysis!.article.dominant_emotion ?? "neutral"} />
                </div>
                <div className="bg-secondary rounded p-3 space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider" style={{ fontSize: "0.65rem" }}>Subjectivity</div>
                  <SubjectivityBar pct={Math.round(100 * (analysis!.article.subjectivity_ratio ?? 0))} />
                </div>
                <div className="bg-secondary rounded p-3 space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider" style={{ fontSize: "0.65rem" }}>Techniques</div>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(analysis!.article.technique_counts ?? {})
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 6)
                      .map(([label, count]) => (
                        <span
                          key={label}
                          className="text-xs px-1.5 py-0.5 rounded-sm bg-card border border-border"
                        >
                          {formatTechnique(label)} ×{count}
                        </span>
                      ))}
                    {Object.keys(analysis!.article.technique_counts ?? {}).length === 0 && (
                      <span className="text-xs text-muted-foreground">None flagged</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Chunk breakdown toggle */}
            {chunks.length > 0 && (
              <div className="border-t border-border pt-3">
                <button
                  onClick={() => setShowChunks(s => !s)}
                  className="text-sm font-medium hover:underline"
                  style={{ color: "var(--accent)" }}
                >
                  {showChunks
                    ? "Hide chunk-by-chunk breakdown"
                    : `Show chunk-by-chunk breakdown (${chunks.length})`}
                </button>
                {showChunks && (
                  <div className="mt-3 space-y-2">
                    {chunks.map((c, i) => (
                      <div
                        key={i}
                        className="rounded border-l-2 pl-3 py-2 text-sm bg-secondary"
                        style={{ borderLeftColor: "var(--border)" }}
                      >
                        <p className="text-foreground leading-snug mb-1.5">{c.text}</p>
                        <div className="flex flex-wrap gap-2 items-center text-xs text-muted-foreground">
                          <EmotionBadge emotion={c.emotion ?? "neutral"} />
                          <BiasBar bias={c.bias ?? "center"} />
                          <span>·</span>
                          <span>{c.subjective ? "subjective" : "objective"}</span>
                          {c.techniques?.map(t => (
                            <span
                              key={t.label}
                              className="px-1.5 py-0.5 rounded-sm bg-card border border-border"
                            >
                              {formatTechnique(t.label)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
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
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft size={14} />
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
              className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-medium hover:opacity-90"
            >
              Back to Today
            </Link>
          </StateBox>
        )}

        {!loading && !error && cluster && (
          <div className="space-y-6">
            {/* Cluster header */}
            <div>
              <div className="flex flex-wrap gap-2 mb-3">
                <span
                  className="px-2.5 py-1 rounded bg-secondary text-secondary-foreground text-xs"
                  style={{ fontFamily: "var(--font-data)" }}
                >
                  {cluster.article_count} article{cluster.article_count !== 1 ? "s" : ""}
                </span>
                <span
                  className="px-2.5 py-1 rounded bg-secondary text-secondary-foreground text-xs"
                  style={{ fontFamily: "var(--font-data)" }}
                >
                  {cluster.sources?.length ?? 0} source{cluster.sources?.length !== 1 ? "s" : ""}
                </span>
                {!!cluster.defined_terms?.length && (
                  <span
                    className="px-2.5 py-1 rounded bg-secondary text-secondary-foreground text-xs"
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
                  fontSize: "clamp(1.5rem, 4vw, 2rem)",
                  lineHeight: 1.15,
                  letterSpacing: "-0.01em",
                }}
              >
                {cluster.titles?.[0] ?? "Topic Summary"}
              </h1>
            </div>

            {/* Summary card */}
            <div className="bg-card border border-border rounded p-5 shadow-sm space-y-4">
              <div
                className="text-base text-foreground leading-relaxed [&_mark]:bg-yellow-100 [&_mark]:rounded-sm [&_mark]:px-0.5"
                dangerouslySetInnerHTML={{
                  __html: cluster.highlighted_summary || cluster.summary,
                }}
              />

              {cluster.defined_terms && cluster.defined_terms.length > 0 && (
                <div className="pt-3 border-t border-border space-y-2">
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

              <div className="pt-3 border-t border-border space-y-2">
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
                className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground"
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
      </div>
    </div>
  );
}
