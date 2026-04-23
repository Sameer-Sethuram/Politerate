import { useParams, Link } from "react-router";
import { useState, useEffect } from "react";
import { getArticleById, mockArticles } from "../data/mockArticles";
import { BiasIndicator } from "../components/BiasIndicator";
import { TrustScore } from "../components/TrustScore";
import { ArrowLeft, ExternalLink, Calendar, Tag, ScanText, Loader2, AlertCircle, Zap, Target, TrendingUp, MessageSquare } from "lucide-react";
import { ArticleCard } from "../components/ArticleCard";
import { Button } from "../components/ui/button";

// TODO: Replace with your backend endpoint
const BACKEND_URL = "http://localhost:8000";

interface LabeledChunk {
  text: string;
  label: "emotion" | "persuasion" | "loaded" | "appeal" | "exaggeration" | null;
  explanation: string;
  start: number;
  end: number;
}

interface AnalysisResponse {
  chunks: LabeledChunk[];
}

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const article = id ? getArticleById(id) : undefined;
  const [chunks, setChunks] = useState<LabeledChunk[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    if (article) {
      analyzeArticle();
    }
  }, [article?.id]);

  const analyzeArticle = async () => {
    if (!article) return;

    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const response = await fetch(`${BACKEND_URL}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: article.content }),
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const data: AnalysisResponse = await response.json();
      setChunks(data.chunks);
      setShowAnalysis(true);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Analysis failed");
      console.error("Analysis error:", err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const renderHighlightedContent = () => {
    if (!article || chunks.length === 0) return article?.content;

    const parts: JSX.Element[] = [];
    let lastIndex = 0;

    const sortedChunks = [...chunks].sort((a, b) => a.start - b.start);

    sortedChunks.forEach((chunk, index) => {
      if (chunk.start > lastIndex) {
        parts.push(
          <span key={`text-${index}`}>
            {article.content.slice(lastIndex, chunk.start)}
          </span>
        );
      }

      if (chunk.label) {
        const colorMap = {
          emotion: "bg-yellow-200 border-b-2 border-yellow-500",
          persuasion: "bg-red-200 border-b-2 border-red-500",
          loaded: "bg-orange-200 border-b-2 border-orange-500",
          appeal: "bg-purple-200 border-b-2 border-purple-500",
          exaggeration: "bg-pink-200 border-b-2 border-pink-500",
        };

        parts.push(
          <span
            key={`chunk-${index}`}
            className={`${colorMap[chunk.label]} px-1 rounded cursor-help`}
            title={chunk.explanation}
          >
            {chunk.text}
          </span>
        );
      } else {
        parts.push(<span key={`chunk-${index}`}>{chunk.text}</span>);
      }

      lastIndex = chunk.end;
    });

    if (lastIndex < article.content.length) {
      parts.push(<span key="text-end">{article.content.slice(lastIndex)}</span>);
    }

    return <>{parts}</>;
  };

  const getTypeIcon = (type: LabeledChunk["label"]) => {
    if (!type) return null;
    switch (type) {
      case "emotion":
        return <Zap className="size-4" />;
      case "persuasion":
        return <Target className="size-4" />;
      case "loaded":
        return <AlertCircle className="size-4" />;
      case "appeal":
        return <MessageSquare className="size-4" />;
      case "exaggeration":
        return <TrendingUp className="size-4" />;
    }
  };

  const getTypeColor = (type: LabeledChunk["label"]) => {
    if (!type) return "";
    switch (type) {
      case "emotion":
        return "border-yellow-500 bg-yellow-50";
      case "persuasion":
        return "border-red-500 bg-red-50";
      case "loaded":
        return "border-orange-500 bg-orange-50";
      case "appeal":
        return "border-purple-500 bg-purple-50";
      case "exaggeration":
        return "border-pink-500 bg-pink-50";
    }
  };

  const getTypeName = (type: LabeledChunk["label"]) => {
    if (!type) return "";
    switch (type) {
      case "emotion":
        return "Emotional Language";
      case "persuasion":
        return "Persuasion Technique";
      case "loaded":
        return "Loaded Language";
      case "appeal":
        return "Appeal to Authority";
      case "exaggeration":
        return "Exaggeration";
    }
  };

  if (!article) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Article Not Found</h2>
        <Link to="/" className="text-blue-600 hover:text-blue-700">
          Return to Home
        </Link>
      </div>
    );
  }

  const relatedArticles = mockArticles
    .filter((a) => a.id !== article.id && a.category === article.category)
    .slice(0, 3);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric"
    });
  };

  const labeledChunks = chunks.filter((c) => c.label !== null);

  return (
    <div className="bg-white">
      {/* Breadcrumb */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 transition-colors"
        >
          <ArrowLeft className="size-4" />
          Back to Articles
        </Link>
      </div>

      {/* Article Header */}
      <div className="bg-gradient-to-b from-gray-50 to-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center gap-2 mb-4">
            <Tag className="size-4 text-gray-500" />
            <span className="text-sm text-gray-600">{article.category}</span>
          </div>
          
          <h1 className="text-4xl font-bold text-gray-900 mb-6">
            {article.title}
          </h1>

          <div className="flex flex-wrap items-center gap-6 text-sm text-gray-600 mb-8">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900">{article.source}</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="size-4" />
              {formatDate(article.date)}
            </div>
          </div>

          {/* Metrics Cards */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-600 mb-2">Political Bias</p>
              <BiasIndicator bias={article.bias} showLabel={true} />
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-600 mb-2">Trust Score</p>
              <TrustScore score={article.trustScore} showLabel={true} />
            </div>
          </div>
        </div>
      </div>

      {/* Article Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Summary Section */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Summary</h2>
          <div className="bg-blue-50 border-l-4 border-blue-600 p-6 rounded-r-lg">
            <p className="text-gray-700 leading-relaxed">{article.summary}</p>
          </div>
        </div>

        {/* Full Content with AI Analysis */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900">Article Content</h2>
            <div className="flex items-center gap-3">
              {isAnalyzing && (
                <span className="flex items-center gap-2 text-sm text-gray-600">
                  <Loader2 className="size-4 animate-spin" />
                  Analyzing...
                </span>
              )}
              {!isAnalyzing && chunks.length > 0 && (
                <Button
                  onClick={() => setShowAnalysis(!showAnalysis)}
                  variant={showAnalysis ? "default" : "outline"}
                  size="sm"
                  className="flex items-center gap-2"
                >
                  <ScanText className="size-4" />
                  {showAnalysis ? "Hide Analysis" : "Show Analysis"}
                </Button>
              )}
            </div>
          </div>

          {analysisError && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                <strong>Note:</strong> AI analysis is currently unavailable. {analysisError}
              </p>
            </div>
          )}

          <div className="prose max-w-none bg-gray-50 rounded-lg p-6">
            <p className="text-gray-700 leading-relaxed">
              {showAnalysis && chunks.length > 0 ? renderHighlightedContent() : article.content}
            </p>
          </div>

          {showAnalysis && chunks.length > 0 && (
            <>
              {/* Analysis Legend */}
              <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <ScanText className="size-5" />
                  AI Analysis Legend
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-yellow-200 border-b-2 border-yellow-500 rounded"></div>
                    <span className="text-xs text-gray-700">Emotional</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-red-200 border-b-2 border-red-500 rounded"></div>
                    <span className="text-xs text-gray-700">Persuasion</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-orange-200 border-b-2 border-orange-500 rounded"></div>
                    <span className="text-xs text-gray-700">Loaded</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-purple-200 border-b-2 border-purple-500 rounded"></div>
                    <span className="text-xs text-gray-700">Authority</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-pink-200 border-b-2 border-pink-500 rounded"></div>
                    <span className="text-xs text-gray-700">Exaggeration</span>
                  </div>
                </div>
              </div>

              {/* Detailed Analysis Breakdown */}
              {labeledChunks.length > 0 && (
                <div className="mt-6 bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="font-semibold text-gray-900 mb-4">
                    Detailed Analysis ({labeledChunks.length} items detected)
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {labeledChunks.map((chunk, index) => (
                      <div
                        key={index}
                        className={`border-l-4 ${getTypeColor(chunk.label)} p-4 rounded-r-lg`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5">{getTypeIcon(chunk.label)}</div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-sm text-gray-900">
                                {getTypeName(chunk.label)}
                              </span>
                            </div>
                            <p className="text-sm text-gray-700 mb-1">
                              "<strong>{chunk.text}</strong>"
                            </p>
                            <p className="text-xs text-gray-600">{chunk.explanation}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Original Article Link */}
        <div className="bg-gray-50 rounded-lg p-6 mb-12">
          <h3 className="font-semibold text-gray-900 mb-3">Read the Full Article</h3>
          <p className="text-sm text-gray-600 mb-4">
            This is a summary and analysis. For the complete article, visit the original source.
          </p>
          <a
            href={article.originalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            View Original Article
            <ExternalLink className="size-4" />
          </a>
        </div>

        {/* Understanding the Metrics */}
        <div className="bg-gray-50 rounded-lg p-6 mb-12">
          <h3 className="font-semibold text-gray-900 mb-3">Understanding Our Analysis</h3>
          <div className="space-y-3 text-sm text-gray-700">
            <div>
              <strong>Political Bias:</strong> Indicates the editorial perspective of the news source
              based on language, topic selection, and framing. Ranges from Left to Right with Center
              representing balanced coverage.
            </div>
            <div>
              <strong>Trust Score:</strong> A measure of source credibility based on factual accuracy,
              transparency, editorial standards, and correction policies. Scores above 85 indicate
              highly reliable sources.
            </div>
            <div>
              <strong>AI Language Analysis:</strong> Our AI models automatically scan article content
              to identify emotionally charged language, persuasion techniques, loaded terms, appeals
              to authority, and exaggeration. Click "Show Analysis" to see highlighted text and
              detailed explanations for each detected pattern.
            </div>
          </div>
        </div>

        {/* Related Articles */}
        {relatedArticles.length > 0 && (
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              Different Perspectives on {article.category}
            </h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {relatedArticles.map((relatedArticle) => (
                <ArticleCard key={relatedArticle.id} article={relatedArticle} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
