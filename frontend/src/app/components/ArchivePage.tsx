import { useState, useEffect } from "react";
import { AlertCircle } from "lucide-react";
import { Spinner, StateBox, SourceBadge, AiBanner, SectionLabel } from "./shared";

interface SnapshotMeta {
  date: string;
  cluster_count: number;
  article_count?: number;
  source_count?: number;
}

interface Cluster {
  titles?: string[];
  summary: string;
  highlighted_summary?: string;
  article_count?: number;
  sources?: string[];
  urls?: string[];
}

interface Snapshot {
  date: string;
  clusters: Cluster[];
  cluster_count: number;
  article_count: number;
  source_count: number;
}

function formatArchiveDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function StatPill({ value, label }: { value: number; label: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-secondary text-secondary-foreground text-xs"
      style={{ fontFamily: "var(--font-data)" }}
    >
      <strong>{value}</strong>&nbsp;{label}
    </span>
  );
}

export function ArchivePage() {
  const [dates, setDates] = useState<SnapshotMeta[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loadingDates, setLoadingDates] = useState(true);
  const [loadingSnap, setLoadingSnap] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datesError, setDatesError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/archive");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const snaps: SnapshotMeta[] = data.snapshots ?? [];
        setDates(snaps);
        if (snaps.length > 0) loadSnapshot(snaps[0].date);
      } catch (e) {
        setDatesError(e instanceof Error ? e.message : "Failed to load archive");
      } finally {
        setLoadingDates(false);
      }
    })();
  }, []);

  async function loadSnapshot(date: string) {
    setSelected(date);
    setLoadingSnap(true);
    setError(null);
    setSnapshot(null);
    try {
      const res = await fetch(`/api/archive/${date}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSnapshot(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load snapshot");
    } finally {
      setLoadingSnap(false);
    }
  }

  return (
    <div>
      <AiBanner />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Page header */}
        <div className="mb-8 pb-6 border-b border-border">
          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "2rem",
              lineHeight: 1.15,
            }}
          >
            Archive
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Browse past days' news summaries.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6">
          {/* Sidebar */}
          <aside className="bg-card border border-border rounded p-4 h-fit md:sticky md:top-24">
            <SectionLabel>Dates</SectionLabel>
            {loadingDates && (
              <div className="flex justify-center py-4">
                <Spinner size={20} />
              </div>
            )}
            {datesError && (
              <p className="text-xs text-destructive">{datesError}</p>
            )}
            {!loadingDates && dates.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No archive yet. Come back tomorrow.
              </p>
            )}
            <ul className="space-y-0.5">
              {dates.map(snap => (
                <li key={snap.date}>
                  <button
                    onClick={() => loadSnapshot(snap.date)}
                    className={[
                      "w-full flex justify-between items-center text-left px-3 py-2.5 rounded text-sm transition-colors",
                      selected === snap.date
                        ? "bg-primary text-primary-foreground font-medium"
                        : "text-foreground hover:bg-secondary",
                    ].join(" ")}
                  >
                    <span>{formatArchiveDate(snap.date)}</span>
                    <span
                      className="text-xs opacity-70 shrink-0"
                      style={{ fontFamily: "var(--font-data)" }}
                    >
                      {snap.cluster_count} topics
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {/* Main content */}
          <section>
            {!selected && !loadingDates && dates.length > 0 && (
              <StateBox>
                <p>Select a date to view that day's news.</p>
              </StateBox>
            )}

            {loadingSnap && (
              <StateBox>
                <Spinner />
                <p>Loading…</p>
              </StateBox>
            )}

            {error && !loadingSnap && (
              <StateBox>
                <AlertCircle className="text-destructive" size={28} />
                <p className="text-destructive text-sm">{error}</p>
              </StateBox>
            )}

            {!loadingSnap && !error && snapshot && (
              <div className="space-y-5">
                {/* Day header */}
                <div className="bg-card border border-border rounded p-5">
                  <h2
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 700,
                      fontSize: "1.4rem",
                      lineHeight: 1.2,
                      marginBottom: "0.75rem",
                    }}
                  >
                    {formatArchiveDate(snapshot.date)}
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    <StatPill value={snapshot.cluster_count} label="topics" />
                    <StatPill value={snapshot.article_count} label="articles" />
                    <StatPill value={snapshot.source_count} label="sources" />
                  </div>
                </div>

                {snapshot.clusters.length === 0 && (
                  <p className="text-sm text-muted-foreground">No summaries saved for this day.</p>
                )}

                {snapshot.clusters.map((cluster, i) => {
                  const title = cluster.titles?.[0] ?? "Topic summary";
                  return (
                    <article key={i} className="bg-card border border-border rounded p-5">
                      <h3
                        className="mb-1"
                        style={{
                          fontFamily: "var(--font-display)",
                          fontWeight: 600,
                          fontSize: "1.05rem",
                          lineHeight: 1.3,
                        }}
                      >
                        {title}
                      </h3>
                      <p
                        className="text-xs text-muted-foreground mb-3"
                        style={{ fontFamily: "var(--font-data)" }}
                      >
                        {cluster.article_count ?? 0} articles
                      </p>
                      <div
                        className="text-sm text-foreground leading-relaxed mb-4 [&_mark]:bg-yellow-100 [&_mark]:rounded-sm [&_mark]:px-0.5"
                        dangerouslySetInnerHTML={{
                          __html: cluster.highlighted_summary || cluster.summary || "",
                        }}
                      />
                      {cluster.sources && cluster.sources.length > 0 && (
                        <div className="pt-3 border-t border-border flex flex-wrap gap-1.5">
                          {cluster.sources.map((src, j) => (
                            <SourceBadge key={j} source={src} url={cluster.urls?.[j]} />
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
