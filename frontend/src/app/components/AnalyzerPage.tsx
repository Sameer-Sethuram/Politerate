import { useState, useRef } from "react";
import { AlertCircle } from "lucide-react";
import {
  Spinner, StateBox, AnnotationLegend, AnnotatedText, BiasBar,
  EmotionBadge, SubjectivityBar, SectionLabel, PageContainer,
  Chunk, formatTechnique, chunkCategory,
} from "./shared";

interface ArticleAnalysis {
  dominant_bias: string;
  dominant_emotion: string;
  subjectivity_ratio: number;
  technique_counts: Record<string, number>;
}

interface AnalysisResult {
  article: ArticleAnalysis;
  chunks: Chunk[];
  model_version?: string;
  cached?: boolean;
}

const SAMPLE_TEXT =
  "The devastating new policy is clearly an outrageous attack on freedom. Everyone knows this is a radical scheme that experts say will have catastrophic consequences. Studies show that this terrible decision was made without proper consideration. The fact is, they don't want you to know the truth about this shocking development. Bipartisan support has been lacking, and according to recent research, moderate lawmakers remain skeptical of the proposed changes.";

const CAT_COLORS: Record<string, string> = {
  persuasion: "#fee2e2",
  appeal: "#f3e8ff",
  exaggeration: "#fce7f3",
  loaded: "#ffedd5",
  emotion: "#fef3c7",
};

function SummaryGrid({ article, chunks, modelVersion }: { article: ArticleAnalysis; chunks: Chunk[]; modelVersion?: string }) {
  const pct = Math.round(100 * (article.subjectivity_ratio ?? 0));
  const techEntries = Object.entries(article.technique_counts ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div className="bg-secondary rounded p-4 space-y-1">
        <SectionLabel>Dominant Bias</SectionLabel>
        <BiasBar bias={article.dominant_bias ?? "center"} />
      </div>
      <div className="bg-secondary rounded p-4 space-y-1">
        <SectionLabel>Dominant Emotion</SectionLabel>
        <EmotionBadge emotion={article.dominant_emotion ?? "neutral"} />
      </div>
      <div className="bg-secondary rounded p-4 space-y-1">
        <SectionLabel>Subjectivity</SectionLabel>
        <SubjectivityBar pct={pct} />
      </div>
      <div className="bg-secondary rounded p-4 space-y-1">
        <SectionLabel>Techniques Detected</SectionLabel>
        {techEntries.length === 0 ? (
          <span className="text-xs text-muted-foreground">None detected</span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {techEntries.slice(0, 6).map(([label, count]) => (
              <span
                key={label}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                style={{ background: CAT_COLORS[chunkCategory({ techniques: [{ label, confidence: 1 }], emotion: "", bias: "", subjective: false, text: "" }) ?? "loaded"] ?? "#ffedd5", color: "#0f0e0c" }}
              >
                {formatTechnique(label)}
                <span className="opacity-60">×{count}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="sm:col-span-2 bg-secondary rounded p-4 space-y-1">
        <SectionLabel>Chunks analyzed</SectionLabel>
        <span className="text-xs" style={{ fontFamily: "var(--font-data)" }}>
          {chunks.length} chunks{modelVersion ? ` · ${modelVersion}` : ""}
        </span>
      </div>
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: Chunk }) {
  const techniques = chunk.techniques ?? [];
  return (
    <div
      className="border border-border rounded p-4 bg-card space-y-2"
      style={{
        borderLeftWidth: "3px",
        borderLeftColor: getEmotionColor(chunk.emotion),
      }}
    >
      <p className="text-sm leading-relaxed text-foreground">{chunk.text}</p>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <EmotionBadge emotion={chunk.emotion ?? "neutral"} />
        <BiasBar bias={chunk.bias ?? "center"} />
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">{chunk.subjective ? "subjective" : "objective"}</span>
        {techniques.length > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <div className="flex flex-wrap gap-1">
              {techniques.map(t => (
                <span
                  key={t.label}
                  title={`Confidence: ${Math.round(t.confidence * 100)}%`}
                  className="px-1.5 py-0.5 rounded-sm text-xs font-medium bg-secondary text-secondary-foreground"
                >
                  {formatTechnique(t.label)}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function getEmotionColor(emotion: string): string {
  const map: Record<string, string> = {
    anger: "#dc2626", fear: "#d97706", sadness: "#2563eb", joy: "#16a34a",
    approval: "#16a34a", disapproval: "#db2777", disgust: "#9333ea",
    annoyance: "#ea580c", optimism: "#0284c7",
  };
  return map[emotion] ?? "var(--border)";
}

export function AnalyzerPage() {
  const [text, setText] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [showAnnotated, setShowAnnotated] = useState(true);
  const [showChunks, setShowChunks] = useState(false);

  const charCount = text.length;
  const tooShort = charCount > 0 && charCount < 50;

  async function analyze() {
    if (charCount < 50) {
      setError("Text must be at least 50 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), url: urlInput.trim() || null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
      setShowAnnotated(true);
      setShowChunks(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer narrow>
      {/* Header */}
      <div className="mb-8 pb-6 border-b border-border">
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "2rem",
            lineHeight: 1.15,
          }}
        >
          Text Analyzer
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Paste any article or excerpt. Politerate flags emotion, persuasion techniques,
          subjectivity, and political lean — chunk by chunk.
        </p>
        <div className="mt-3 px-4 py-3 bg-secondary rounded border border-border text-sm">
          <strong>Powered by multi-head DeBERTa:</strong> 18 persuasion-technique heads + 28-class
          emotion + subjectivity + 3-way bias (left / center / right).
        </div>
      </div>

      {/* Input card */}
      <div className="bg-card border border-border rounded p-6 mb-6 shadow-sm space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="analyzer-url" className="text-sm font-medium text-muted-foreground">
            Article URL{" "}
            <span className="text-muted-foreground font-normal">(optional — enables caching)</span>
          </label>
          <input
            id="analyzer-url"
            type="url"
            value={urlInput}
            onChange={e => setUrlInput(e.target.value)}
            placeholder="https://example.com/article"
            className="w-full px-3 py-2 rounded border border-border bg-input-background text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:border-accent focus:ring-2 focus:ring-[var(--accent)]/20 transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="analyzer-text" className="text-sm font-medium text-muted-foreground">
            Article text
          </label>
          <textarea
            id="analyzer-text"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Paste article text here…"
            rows={9}
            className="w-full px-3 py-2 rounded border border-border bg-input-background text-foreground text-sm placeholder:text-muted-foreground resize-y focus:outline-none focus:border-accent focus:ring-2 focus:ring-[var(--accent)]/20 transition-colors"
          />
          <div className="flex items-center gap-2 text-xs text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
            <span>{charCount.toLocaleString()} / 50,000 chars</span>
            {tooShort && <span className="text-destructive">· minimum 50</span>}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          <button
            onClick={analyze}
            disabled={loading || tooShort}
            className="px-5 py-2 bg-primary text-primary-foreground rounded text-sm font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? "Analyzing…" : "Analyze text"}
          </button>
          <button
            onClick={() => { setText(SAMPLE_TEXT); }}
            className="px-4 py-2 bg-secondary text-secondary-foreground rounded text-sm font-medium hover:bg-muted transition-colors"
          >
            Load sample
          </button>
          <button
            onClick={() => { setText(""); setUrlInput(""); setResult(null); setError(null); }}
            className="px-4 py-2 bg-secondary text-secondary-foreground rounded text-sm font-medium hover:bg-muted transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* How it works */}
      {!result && !loading && (
        <div className="bg-secondary border border-border rounded p-5 text-sm space-y-3">
          <h3
            className="font-semibold"
            style={{ fontFamily: "var(--font-display)", fontSize: "1rem" }}
          >
            How this works
          </h3>
          <ul className="space-y-1.5 text-muted-foreground">
            {[
              "Text is sent to your local model server for analysis",
              "AI models identify emotionally charged words and persuasion techniques",
              "Each text chunk is labeled with its classification and explanation",
              "Results are highlighted in the original text for easy review",
              "Detailed breakdown shows exactly why each section was flagged",
            ].map((item, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-muted-foreground shrink-0">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground border-t border-border pt-3">
            All analysis happens on your local model server. No data is sent to third-party services.
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <StateBox>
          <Spinner />
          <p>Analyzing text…</p>
        </StateBox>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded text-sm">
          <AlertCircle size={16} className="text-destructive shrink-0 mt-0.5" />
          <span className="text-destructive">{error}</span>
        </div>
      )}

      {/* Results */}
      {!loading && result && (
        <div className="space-y-5">
          {/* Annotated text card */}
          {result.chunks?.length > 0 && (
            <div className="bg-card border border-border rounded overflow-hidden shadow-sm">
              <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-border">
                <div>
                  <h2
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 700,
                      fontSize: "1.1rem",
                    }}
                  >
                    Annotated text
                    {result.cached && (
                      <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">
                        cached
                      </span>
                    )}
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Hover highlighted passages for details.
                  </p>
                </div>
                <button
                  onClick={() => setShowAnnotated(a => !a)}
                  className="text-xs font-medium border border-border rounded px-3 py-1.5 text-muted-foreground hover:text-foreground transition-colors shrink-0"
                >
                  {showAnnotated ? "Hide analysis" : "Show analysis"}
                </button>
              </div>
              <div className="px-6 py-5">
                <AnnotationLegend />
                {showAnnotated ? (
                  <AnnotatedText chunks={result.chunks} />
                ) : (
                  <p className="text-sm leading-7 text-foreground">{text}</p>
                )}
              </div>
            </div>
          )}

          {/* Summary card */}
          <div className="bg-card border border-border rounded overflow-hidden shadow-sm">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <h2
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                Analysis Summary
              </h2>
              <span
                className="text-xs text-muted-foreground"
                style={{ fontFamily: "var(--font-data)" }}
              >
                {result.chunks?.length ?? 0} chunks · {result.model_version ?? "—"}
              </span>
            </div>
            <div className="p-6">
              <SummaryGrid article={result.article} chunks={result.chunks ?? []} modelVersion={result.model_version} />
            </div>
          </div>

          {/* Chunk breakdown */}
          {result.chunks?.length > 0 && (
            <div className="bg-card border border-border rounded overflow-hidden shadow-sm">
              <button
                onClick={() => setShowChunks(s => !s)}
                className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-secondary transition-colors"
              >
                <h2
                  style={{
                    fontFamily: "var(--font-display)",
                    fontWeight: 700,
                    fontSize: "1.1rem",
                  }}
                >
                  Detailed Breakdown
                </h2>
                <span className="text-xs text-muted-foreground">
                  {showChunks ? "Hide" : `Show ${result.chunks.length} chunks`}
                </span>
              </button>
              {showChunks && (
                <div className="p-6 pt-0 space-y-3">
                  {result.chunks.map((c, i) => (
                    <ChunkCard key={i} chunk={c} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
