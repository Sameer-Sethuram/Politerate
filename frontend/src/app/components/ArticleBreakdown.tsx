import { useState } from "react";
import { ExternalLink } from "lucide-react";
import {
  Spinner, AnnotationLegend, AnnotatedText, BiasBar, EmotionBadge, SubjectivityBar,
  SectionLabel, Chunk, formatTechnique,
} from "./shared";

export interface ClusterArticle {
  url: string;
  title?: string;
  source: string;
  credibility_score?: number | null;
  credibility_label?: string;
  lean?: string | null;
  summary?: string | null;
}

export interface ArticleAnalysis {
  dominant_bias: string;
  dominant_emotion: string;
  subjectivity_ratio: number;
  technique_counts: Record<string, number>;
}

export interface ArticleEntry {
  url: string;
  analysis_status?: string;
  analysis_error?: string;
  analysis?: { article: ArticleAnalysis; chunks: Chunk[] } | null;
}

export type AnalysisStatus = "loading" | "done" | "error";

export function ArticleBlock({
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
              className="leading-snug mb-1.5"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: "1.25rem",
              }}
            >
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="link"
              >
                {article.title ?? "Untitled"}
              </a>
            </h3>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
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
            className="shrink-0 text-muted-foreground hover:text-brand-accent transition-colors mt-1"
            title="Open original"
          >
            <ExternalLink size={17} />
          </a>
        </div>
        {article.summary && (
          <div className="mt-4 pl-4 border-l-2" style={{ borderLeftColor: "var(--accent)" }}>
            <SectionLabel>This outlet's summary</SectionLabel>
            <p className="text-lg leading-relaxed text-foreground">{article.summary}</p>
          </div>
        )}
      </div>

      {/* Analysis slot */}
      <div className="p-5">
        {status === "loading" && (
          <div className="flex items-center gap-2 text-base text-muted-foreground">
            <Spinner size={16} />
            <span>Loading analysis…</span>
          </div>
        )}

        {status === "error" && (
          <p className="text-base text-muted-foreground">
            Analyzer request failed: {statusError}
          </p>
        )}

        {status === "done" && !entry && (
          <p className="text-base text-muted-foreground">No analysis available.</p>
        )}

        {/* Analysis is read from the pipeline's cache, never run live. */}
        {status === "done" && entry && !entry.analysis && !entry.analysis_error && (
          <p className="text-base text-muted-foreground">
            {entry.analysis_status === "pending"
              ? "Analysis pending — this article hasn’t been processed yet. Refresh after the next pipeline run."
              : "No cached analysis available for this article."}
          </p>
        )}

        {entry?.analysis_error && (
          <p className="text-base text-muted-foreground">
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
                    className="shrink-0 text-sm font-medium border border-border rounded px-4 py-1.5 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showAnnotated ? "Hide analysis" : "Show analysis"}
                  </button>
                </div>
                {showAnnotated ? (
                  <AnnotatedText chunks={chunks} />
                ) : (
                  <p className="text-lg leading-relaxed">{chunks.map(c => c.text).join(" ")}</p>
                )}
              </div>
            )}

            {/* Summary grid: scalar metrics in a row, techniques full-width below */}
            <div className="border-t border-border pt-4">
              <SectionLabel>Summary</SectionLabel>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2">
                <div className="bg-secondary rounded p-3.5 space-y-1.5">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Bias</div>
                  <BiasBar bias={analysis!.article.dominant_bias ?? "center"} />
                </div>
                <div className="bg-secondary rounded p-3.5 space-y-1.5">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Emotion</div>
                  <EmotionBadge emotion={analysis!.article.dominant_emotion ?? "neutral"} />
                </div>
                <div className="bg-secondary rounded p-3.5 space-y-1.5">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Subjectivity</div>
                  <SubjectivityBar pct={Math.round(100 * (analysis!.article.subjectivity_ratio ?? 0))} />
                </div>
                <div className="sm:col-span-3 bg-secondary rounded p-3.5 space-y-1.5">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Techniques</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(analysis!.article.technique_counts ?? {})
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 6)
                      .map(([label, count]) => (
                        <span
                          key={label}
                          className="text-sm px-2 py-0.5 rounded-sm bg-card border border-border"
                        >
                          {formatTechnique(label)} ×{count}
                        </span>
                      ))}
                    {Object.keys(analysis!.article.technique_counts ?? {}).length === 0 && (
                      <span className="text-sm text-muted-foreground">None flagged</span>
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
                  className="text-base font-medium link"
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
                        className="rounded border-l-2 pl-3.5 py-2.5 text-base bg-secondary"
                        style={{ borderLeftColor: "var(--border)" }}
                      >
                        <p className="text-foreground leading-snug mb-2">{c.text}</p>
                        <div className="flex flex-wrap gap-2 items-center text-sm text-muted-foreground">
                          <EmotionBadge emotion={c.emotion ?? "neutral"} />
                          <BiasBar bias={c.bias ?? "center"} />
                          <span>·</span>
                          <span>{c.subjective ? "subjective" : "objective"}</span>
                          {c.techniques?.map(t => (
                            <span
                              key={t.label}
                              className="px-2 py-0.5 rounded-sm bg-card border border-border"
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
