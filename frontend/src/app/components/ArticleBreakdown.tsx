import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import {
  Spinner, AnnotationLegend, AnnotatedText, BiasBar, CredBadge, EmotionBadge, LeanBadge, SubjectivityBar,
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
  open: controlledOpen,
  onToggle,
}: {
  article: ClusterArticle;
  entry?: ArticleEntry;
  status: AnalysisStatus;
  statusError: string | null;
  // Collapsed by default; pass both to control it from outside.
  open?: boolean;
  onToggle?: () => void;
}) {
  const [ownOpen, setOwnOpen] = useState(false);
  const open = controlledOpen ?? ownOpen;
  const toggle = onToggle ?? (() => setOwnOpen(o => !o));
  const [showAnnotated, setShowAnnotated] = useState(true);
  const [showChunks, setShowChunks] = useState(false);

  const analysis = entry?.analysis;
  const chunks = analysis?.chunks ?? [];
  const hasAnalysis = !!analysis && !entry?.analysis_error;
  const agg = hasAnalysis ? analysis!.article : null;
  const panelId = `breakdown-${article.url.replace(/[^a-zA-Z0-9]/g, "").slice(-40)}`;

  return (
    <section className={`bg-card border rounded-lg overflow-hidden transition-colors ${open ? "border-border-strong" : "border-border"}`}>
      {/* Header: which outlet, at a glance. Toggles the breakdown. */}
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="w-full flex items-start gap-4 p-4 sm:p-5 text-left hover:bg-secondary/50 transition-colors"
      >
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>{article.source}</span>
            {article.lean && article.lean !== "unknown" && <LeanBadge lean={article.lean} />}
            {article.credibility_score != null && <CredBadge score={article.credibility_score} />}
          </div>
          <p className="text-base text-foreground/85 leading-snug">{article.title ?? "Untitled"}</p>
          {agg && (
            <p className="text-sm text-muted-foreground capitalize" style={{ fontFamily: "var(--font-data)" }}>
              {[
                agg.dominant_bias && `${agg.dominant_bias} bias`,
                agg.dominant_emotion,
                agg.subjectivity_ratio != null && `${Math.round(100 * agg.subjectivity_ratio)}% subjective`,
              ].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        <ChevronDown
          size={22}
          className={`shrink-0 mt-1 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div id={panelId} className="border-t border-border">
          <div className="p-5 border-b border-border">
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-base font-medium link"
            >
              Read the original at {article.source} <ExternalLink size={15} />
            </a>
            {article.credibility_label && article.credibility_label !== "unknown" && (
              <span className="ml-3 text-sm text-muted-foreground">bias label: {article.credibility_label}</span>
            )}
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
        </div>
      )}
    </section>
  );
}
