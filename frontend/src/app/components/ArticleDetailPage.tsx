import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import { ExternalLink, ArrowLeft, AlertCircle } from "lucide-react";
import {
  Spinner, StateBox, LeanBadge, CredBadge, AnnotationLegend, AnnotatedText,
  PageContainer, Chunk, Region, RegionTag,
} from "./shared";

interface ArticleData {
  title?: string;
  source?: string;
  region?: Region | null;
  bias_label?: string;
  credibility_label?: string;
  credibility_score?: number;
  text?: string;
  chunks?: Chunk[];
  analysis_status?: string;
}

export function ArticleDetailPage() {
  const [params] = useSearchParams();
  const url = params.get("url") ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ArticleData | null>(null);
  const [showAnnotated, setShowAnnotated] = useState(true);

  useEffect(() => {
    if (!url) {
      setError("No article URL specified.");
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch(`/api/article/analysis?url=${encodeURIComponent(url)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setData(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load article");
      } finally {
        setLoading(false);
      }
    })();
  }, [url]);

  const hasChunks = data?.chunks && data.chunks.length > 0 && data.analysis_status !== "pending";

  return (
    <PageContainer narrow>
      {/* Back link */}
      <Link
        to="/all-articles"
        className="inline-flex items-center gap-1.5 text-base text-muted-foreground mb-6 link"
      >
        <ArrowLeft size={17} />
        All Articles
      </Link>

      {loading && (
        <StateBox>
          <Spinner />
          <p>Loading article…</p>
        </StateBox>
      )}

      {!loading && error && (
        <StateBox>
          <AlertCircle className="text-destructive" size={32} />
          <p className="text-destructive font-medium mb-2">Article not found</p>
          <p className="text-base text-muted-foreground">{error}</p>
          <Link
            to="/all-articles"
            className="mt-3 px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90"
          >
            Back to Articles
          </Link>
        </StateBox>
      )}

      {!loading && !error && data && (
        <article className="bg-card border border-border rounded overflow-hidden shadow-sm">
          {/* Article header */}
          <header className="p-6 sm:p-8 border-b border-border">
            {data.region && <RegionTag region={data.region} className="mb-3" />}
            <h1
              className="mb-4"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: "1.85rem",
                lineHeight: 1.25,
              }}
            >
              {data.title ?? "Untitled"}
            </h1>

            <div className="flex flex-wrap items-center gap-2 text-base">
              {data.source && (
                <span className="font-semibold text-muted-foreground">{data.source}</span>
              )}
              {(data.bias_label ?? data.credibility_label) &&
                (data.bias_label ?? data.credibility_label) !== "unknown" && (
                  <LeanBadge lean={data.bias_label ?? data.credibility_label ?? ""} />
                )}
              {data.credibility_score != null && <CredBadge score={data.credibility_score} />}
              {url && (
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-brand-accent border border-border hover:border-[var(--accent)] rounded px-3 py-1.5 transition-colors ml-auto"
                >
                  <ExternalLink size={15} />
                  Original article
                </a>
              )}
            </div>
          </header>

          {/* Article body */}
          <div className="p-6 sm:p-8">
            {hasChunks ? (
              <>
                {/* Toggle */}
                <div className="flex items-center justify-between gap-4 mb-4">
                  <AnnotationLegend />
                  <button
                    onClick={() => setShowAnnotated(a => !a)}
                    className="shrink-0 text-sm font-medium border border-border rounded px-4 py-1.5 text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                  >
                    {showAnnotated ? "Hide analysis" : "Show analysis"}
                  </button>
                </div>

                {showAnnotated ? (
                  <AnnotatedText chunks={data.chunks!} />
                ) : (
                  <p className="text-lg leading-relaxed text-foreground whitespace-pre-wrap">
                    {data.chunks!.map(c => c.text).join(" ")}
                  </p>
                )}
              </>
            ) : data.text ? (
              <p className="text-lg leading-relaxed text-foreground whitespace-pre-wrap">{data.text}</p>
            ) : (
              <p className="text-base text-muted-foreground italic">
                No content available for this article.
              </p>
            )}
          </div>
        </article>
      )}
    </PageContainer>
  );
}
