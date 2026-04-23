import { useState } from "react";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { analyzeArticle } from "../../api/client.js";
import {
  ScanText,
  Zap,
  AlertCircle,
  Loader2,
  Megaphone,
  TrendingUp,
} from "lucide-react";


// === Types matching your actual backend ===

interface TechniqueDetection {
  label: string;
  confidence: number;
}

interface ChunkAnalysis {
  text: string;
  techniques: TechniqueDetection[];
  emotion: string;
  subjective: boolean;
  bias: string;
}

interface ArticleLevelAnalysis {
  dominant_bias: string | null;
  dominant_emotion: string | null;
  subjectivity_ratio: number;
  technique_counts: Record<string, number>;
}

interface AnalysisResponse {
  chunks: ChunkAnalysis[];
  article: ArticleLevelAnalysis;
  cached: boolean;
  model_version: string;
}


// === Color/label helpers ===

const EMOTION_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  anger:       { bg: "bg-red-100",    border: "border-red-500",    text: "text-red-900" },
  fear:        { bg: "bg-amber-100",  border: "border-amber-500",  text: "text-amber-900" },
  sadness:     { bg: "bg-blue-100",   border: "border-blue-500",   text: "text-blue-900" },
  disapproval: { bg: "bg-pink-100",   border: "border-pink-500",   text: "text-pink-900" },
  disgust:     { bg: "bg-purple-100", border: "border-purple-500", text: "text-purple-900" },
  annoyance:   { bg: "bg-orange-100", border: "border-orange-500", text: "text-orange-900" },
  joy:         { bg: "bg-green-100",  border: "border-green-500",  text: "text-green-900" },
  approval:    { bg: "bg-emerald-100",border: "border-emerald-500",text: "text-emerald-900" },
  neutral:     { bg: "bg-gray-50",    border: "border-gray-300",   text: "text-gray-700" },
};

function getEmotionColor(emotion: string) {
  return EMOTION_COLORS[emotion] || EMOTION_COLORS.neutral;
}

function formatTechniqueName(label: string): string {
  return label.replace(/_/g, " ");
}

function getBiasDisplay(bias: string): string {
  const map: Record<string, string> = {
    LABEL_0: "left-leaning",
    LABEL_1: "center",
    LABEL_2: "right-leaning",
    left: "left-leaning",
    center: "center",
    right: "right-leaning",
  };
  return map[bias] || bias;
}


// === Main component ===

export function TextAnalyzerPage() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(null);

  const analyzeText = async () => {
    if (text.length < 50) {
      setError("Text must be at least 50 characters");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedChunkIndex(null);

    try {
      const analysis: AnalysisResponse = await analyzeArticle({
        text,
        url: url || null,
      });
      setResult(analysis);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setText("");
    setUrl("");
    setResult(null);
    setError(null);
    setSelectedChunkIndex(null);
  };

  const sampleText = `The devastating new policy is clearly an outrageous attack on freedom. Everyone knows this is a radical scheme that experts say will have catastrophic consequences. Studies show that this terrible decision was made without proper consideration. The fact is, they don't want you to know the truth about this shocking development.`;

  // Chunks with at least one technique detected (for the right-side cards)
  const flaggedChunks = result?.chunks
    .map((chunk, originalIndex) => ({ chunk, originalIndex }))
    .filter(({ chunk }) => chunk.techniques.length > 0 || chunk.subjective) ?? [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 bg-blue-100 rounded-lg">
            <ScanText className="size-8 text-blue-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Text Analyzer</h1>
            <p className="text-gray-600">
              AI-powered detection of emotional language and persuasion techniques
            </p>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-900">
            <strong>Powered by Politerate v1:</strong> Multi-head DeBERTa model analyzes
            text for persuasion techniques, evoked emotions, subjectivity, and political bias.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* === LEFT COLUMN: Input + legend === */}
        <div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Input</h2>

            <label className="block text-sm font-medium text-gray-700 mb-1">
              Article URL <span className="text-gray-400">(optional, enables caching)</span>
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="w-full mb-4 px-3 py-2 border border-gray-300 rounded-md text-sm"
            />

            <label className="block text-sm font-medium text-gray-700 mb-1">
              Article text
            </label>
            <Textarea
              placeholder="Paste article text here to analyze..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="min-h-[300px] mb-2"
            />
            <p className="text-xs text-gray-500 mb-4">
              {text.length} / 50,000 characters {text.length < 50 && "(minimum 50)"}
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                onClick={analyzeText}
                disabled={text.length < 50 || loading}
                className="flex-1"
              >
                {loading ? (
                  <>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  "Analyze Text"
                )}
              </Button>
              <Button onClick={() => setText(sampleText)} variant="outline">
                Load Sample
              </Button>
              <Button onClick={handleClear} variant="outline">
                Clear
              </Button>
            </div>
          </div>

          {/* Legend */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
            <h3 className="font-semibold text-gray-900 mb-4">How to read the results</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-start gap-3">
                <Zap className="size-4 text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-gray-900">Emotion color</strong>
                  <p className="text-gray-600">
                    Each sentence is colored by the emotion it evokes (anger, fear, joy, etc.)
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <AlertCircle className="size-4 text-orange-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-gray-900">Technique badges</strong>
                  <p className="text-gray-600">
                    Badges on sentences show detected persuasion techniques (loaded
                    language, appeal to fear, etc.)
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Megaphone className="size-4 text-purple-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-gray-900">Subjectivity</strong>
                  <p className="text-gray-600">
                    Subjective sentences have a dashed underline
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <TrendingUp className="size-4 text-blue-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="text-gray-900">Click any sentence</strong>
                  <p className="text-gray-600">to see detailed predictions in the panel</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* === RIGHT COLUMN: Results === */}
        <div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Analysis Results
              {result && (
                <span className="ml-2 text-sm font-normal text-gray-600">
                  ({result.chunks.length} chunks,{" "}
                  {flaggedChunks.length} flagged)
                </span>
              )}
              {result?.cached && (
                <span className="ml-2 text-xs font-normal text-green-700 bg-green-50 px-2 py-0.5 rounded">
                  cached
                </span>
              )}
            </h2>

            {!result ? (
              <div className="text-center py-12 text-gray-500">
                <ScanText className="size-12 mx-auto mb-3 text-gray-300" />
                <p>No analysis yet. Enter text and click "Analyze Text" to begin.</p>
              </div>
            ) : (
              <>
                {/* Article-level summary */}
                <div className="bg-gray-50 rounded-lg p-4 mb-6">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Overview</h3>
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <dt className="text-gray-500">Dominant bias</dt>
                      <dd className="font-medium text-gray-900">
                        {result.article.dominant_bias
                          ? getBiasDisplay(result.article.dominant_bias)
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Dominant emotion</dt>
                      <dd className="font-medium text-gray-900">
                        {result.article.dominant_emotion ?? "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Subjectivity</dt>
                      <dd className="font-medium text-gray-900">
                        {(result.article.subjectivity_ratio * 100).toFixed(0)}%
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Techniques found</dt>
                      <dd className="font-medium text-gray-900">
                        {Object.keys(result.article.technique_counts).length}
                      </dd>
                    </div>
                  </dl>
                </div>

                {/* Highlighted text */}
                <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 max-h-[400px] overflow-y-auto">
                  <div className="text-sm leading-relaxed space-y-2">
                    {result.chunks.map((chunk, i) => {
                      const colors = getEmotionColor(chunk.emotion);
                      const isSelected = selectedChunkIndex === i;
                      return (
                        <span
                          key={i}
                          onClick={() =>
                            setSelectedChunkIndex(isSelected ? null : i)
                          }
                          className={`
                            inline-block cursor-pointer px-1.5 py-0.5 rounded
                            ${colors.bg} ${colors.text}
                            ${chunk.subjective ? "border-b border-dashed border-gray-500" : ""}
                            ${isSelected ? `ring-2 ${colors.border}` : ""}
                            hover:ring-2 hover:${colors.border} transition
                            mr-1
                          `}
                          title={`emotion: ${chunk.emotion} | bias: ${getBiasDisplay(chunk.bias)}`}
                        >
                          {chunk.text}
                          {chunk.techniques.length > 0 && (
                            <span className="ml-1 text-xs text-orange-700">⚠</span>
                          )}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* Selected chunk detail */}
                {selectedChunkIndex !== null && result.chunks[selectedChunkIndex] && (
                  <ChunkDetail chunk={result.chunks[selectedChunkIndex]} />
                )}

                {/* Flagged chunks list */}
                {selectedChunkIndex === null && flaggedChunks.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">
                      Flagged sentences
                    </h3>
                    <div className="space-y-3 max-h-[400px] overflow-y-auto">
                      {flaggedChunks.map(({ chunk, originalIndex }) => (
                        <FlaggedChunkCard
                          key={originalIndex}
                          chunk={chunk}
                          onClick={() => setSelectedChunkIndex(originalIndex)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* How it works footer */}
      <div className="mt-12 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">How This Works</h2>
        <div className="text-sm text-gray-700 space-y-2">
          <p>
            Politerate uses a multi-head DeBERTa classifier trained on labeled political news
            to identify four dimensions per sentence:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>
              <strong>Persuasion techniques</strong> — 18 categories including loaded
              language, appeal to fear, and doubt
            </li>
            <li>
              <strong>Evoked emotion</strong> — what feeling the writer is trying to
              create in the reader
            </li>
            <li>
              <strong>Subjectivity</strong> — whether the sentence presents opinion or fact
            </li>
            <li>
              <strong>Political bias</strong> — left/center/right leaning framing
            </li>
          </ul>
          <p className="text-xs text-gray-500 italic mt-4">
            Predictions are probabilistic guidance, not definitive judgments.
          </p>
        </div>
      </div>
    </div>
  );
}


// === Subcomponents ===

function ChunkDetail({ chunk }: { chunk: ChunkAnalysis }) {
  const colors = getEmotionColor(chunk.emotion);
  return (
    <div className={`border-l-4 ${colors.border} ${colors.bg} p-4 rounded-r-lg`}>
      <p className={`text-sm italic mb-4 ${colors.text}`}>
        "{chunk.text}"
      </p>

      <div className="grid grid-cols-2 gap-3 text-sm mb-4">
        <div>
          <span className="text-gray-600">Emotion: </span>
          <span className="font-medium">{chunk.emotion}</span>
        </div>
        <div>
          <span className="text-gray-600">Bias: </span>
          <span className="font-medium">{getBiasDisplay(chunk.bias)}</span>
        </div>
        <div>
          <span className="text-gray-600">Tone: </span>
          <span className="font-medium">
            {chunk.subjective ? "subjective" : "neutral"}
          </span>
        </div>
      </div>

      {chunk.techniques.length > 0 ? (
        <div>
          <p className="text-sm font-semibold text-gray-900 mb-2">
            Detected techniques:
          </p>
          <ul className="space-y-1">
            {chunk.techniques.map((t) => (
              <li
                key={t.label}
                className="flex justify-between items-center text-sm bg-white rounded px-3 py-2"
              >
                <span>{formatTechniqueName(t.label)}</span>
                <span className="text-xs text-gray-500">
                  {(t.confidence * 100).toFixed(0)}% confident
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-gray-600 italic">
          No specific persuasion techniques detected.
        </p>
      )}
    </div>
  );
}


function FlaggedChunkCard({
  chunk,
  onClick,
}: {
  chunk: ChunkAnalysis;
  onClick: () => void;
}) {
  const colors = getEmotionColor(chunk.emotion);
  return (
    <div
      onClick={onClick}
      className={`border-l-4 ${colors.border} ${colors.bg} p-4 rounded-r-lg cursor-pointer hover:shadow-sm transition`}
    >
      <p className="text-sm text-gray-700 mb-2 line-clamp-2">"{chunk.text}"</p>
      <div className="flex flex-wrap gap-1.5">
        <span className={`text-xs px-2 py-0.5 rounded ${colors.bg} ${colors.text} border ${colors.border}`}>
          {chunk.emotion}
        </span>
        {chunk.subjective && (
          <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-700">
            subjective
          </span>
        )}
        {chunk.techniques.slice(0, 3).map((t) => (
          <span
            key={t.label}
            className="text-xs px-2 py-0.5 rounded bg-orange-50 text-orange-900 border border-orange-200"
          >
            {formatTechniqueName(t.label)}
          </span>
        ))}
        {chunk.techniques.length > 3 && (
          <span className="text-xs text-gray-500">
            +{chunk.techniques.length - 3} more
          </span>
        )}
      </div>
    </div>
  );
}