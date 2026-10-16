import { useState, useEffect } from "react";
import { Link } from "react-router";
import { RefreshCw, AlertCircle, Map as MapIcon } from "lucide-react";
import { Spinner, StateBox, AiBanner, PageContainer, formatRelativeDate, SITE_TIME_ZONE } from "./shared";
import { DailyBrief, DailySummary, StatPill } from "./DailyBrief";
import { errorMessage, fetchJson } from "../api";
import { TAG_ORDER, TOPIC_TAGS, TagSwatch } from "./topicTags";

function todayHeading(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", timeZone: SITE_TIME_ZONE,
  });
}

export function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [daily, setDaily] = useState<DailySummary | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setDaily(await fetchJson<DailySummary>("/api/daily-summary"));
    } catch (e) {
      setError(errorMessage(e, "Failed to load news"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const isEmpty = !loading && !error && !daily?.sections?.length;

  return (
    <div>
      <AiBanner />
      <PageContainer>
        {/* Header */}
        <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 pb-5 mb-5 border-b border-border">
          <div>
            <p
              className="text-sm tracking-[0.2em] uppercase text-muted-foreground"
              style={{ fontFamily: "var(--font-data)" }}
            >
              {todayHeading()}
            </p>
            <h1
              className="mt-1 tracking-tight"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 800,
                fontSize: "clamp(2.2rem, 5vw, 3.2rem)",
                lineHeight: 1.05,
                letterSpacing: "-0.01em",
              }}
            >
              Today's Brief
            </h1>
            <p className="mt-2 max-w-2xl text-lg text-muted-foreground leading-relaxed">
              The day's most-covered stories, summarized across outlets. Hover a highlighted term
              for its definition; open a story for every outlet's account.
            </p>
          </div>
          {daily && !isEmpty && (
            <div className="flex flex-col items-start sm:items-end gap-2">
              <div className="flex flex-wrap gap-2">
                <StatPill value={daily.cluster_count} label="topics" />
                <StatPill value={daily.total_articles} label="articles" />
                <StatPill value={daily.source_count} label="sources" />
              </div>
              {daily.last_updated && (
                <span className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
                  Updated {formatRelativeDate(daily.last_updated)}
                </span>
              )}
            </div>
          )}
        </header>

        {loading && (
          <StateBox>
            <Spinner />
            <p>Loading today's brief…</p>
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

        {isEmpty && (
          <StateBox>
            <p>No topic has enough coverage for a brief yet. Check back soon.</p>
            <div className="flex flex-wrap justify-center gap-3">
              <button
                onClick={load}
                className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded text-base font-medium hover:opacity-90"
              >
                <RefreshCw size={16} /> Refresh
              </button>
              <Link
                to="/topics"
                className="flex items-center gap-2 px-5 py-2.5 border border-border rounded text-base font-medium hover:bg-secondary transition-colors"
              >
                <MapIcon size={16} /> See all topics
              </Link>
            </div>
          </StateBox>
        )}

        {!loading && !error && daily && !isEmpty && (
          <>
            {/* Tag key */}
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-5 text-sm text-muted-foreground">
              {TAG_ORDER.map(t => (
                <span key={t} className="inline-flex items-center gap-2">
                  <TagSwatch tag={t} />
                  {TOPIC_TAGS[t].label}
                </span>
              ))}
            </div>

            <DailyBrief data={daily} />

            <Link
              to="/topics"
              className="group mt-10 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card px-6 py-5 hover:border-border-strong transition-colors"
            >
              {/* Phones get the topic list (TopicsPage), not the map. */}
              <span>
                <span className="block text-lg font-semibold" style={{ fontFamily: "var(--font-display)" }}>
                  <span className="md:hidden">Every topic today</span>
                  <span className="hidden md:inline">Every topic today, mapped</span>
                </span>
                <span className="block text-base text-muted-foreground">
                  <span className="md:hidden">All of today's topics, grouped by tag.</span>
                  <span className="hidden md:inline">
                    See how today's stories relate: politics at the center, health, tech and business around it.
                  </span>
                </span>
              </span>
              <span className="inline-flex items-center gap-2 font-semibold text-brand-accent">
                <span className="md:hidden">See every topic</span>
                <span className="hidden md:inline-flex items-center gap-2"><MapIcon size={18} /> Open the map</span>
              </span>
            </Link>
          </>
        )}
      </PageContainer>
    </div>
  );
}
