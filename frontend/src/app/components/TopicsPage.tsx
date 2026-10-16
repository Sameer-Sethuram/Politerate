import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { AlertCircle, List, Map as MapIcon, RefreshCw } from "lucide-react";
import { AiBanner, SectionLabel, SourceBadge, Spinner, StateBox, formatRelativeDate } from "./shared";
import { KeyTermChips } from "./TopicSummary";
import { TopicMap } from "./TopicMap";
import { errorMessage, fetchJson } from "../api";
import { sanitizeHtml } from "../sanitize";
import { SummariesData, TopicCluster, listedOutlets, topicHref, topicRelevance, topicTitle } from "./topicData";
import { TAG_ORDER, TOPIC_TAGS, TagKey, TagSwatch, TopicTags, primaryTag, tagStyle, topicTags } from "./topicTags";

type View = "map" | "list";

// Phones get the list only: the map needs room, and a mouse or a tablet, to
// read. Below Tailwind's md breakpoint (media queries read rem as 16px).
const PHONE_QUERY = "(max-width: 47.99rem)";

function useIsPhone(): boolean {
  const [isPhone, setIsPhone] = useState(() => window.matchMedia(PHONE_QUERY).matches);
  useEffect(() => {
    const query = window.matchMedia(PHONE_QUERY);
    const onChange = () => setIsPhone(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return isPhone;
}

const VIEWS: Array<{ view: View; label: string; icon: typeof MapIcon }> = [
  { view: "map", label: "Map", icon: MapIcon },
  { view: "list", label: "List", icon: List },
];

function ViewToggle({ value, onChange }: { value: View; onChange: (v: View) => void }) {
  return (
    <div role="group" aria-label="View" className="inline-flex gap-0.5 p-1 bg-secondary rounded">
      {VIEWS.map(({ view, label, icon: Icon }) => (
        <button
          key={view}
          type="button"
          aria-pressed={value === view}
          onClick={() => onChange(view)}
          className={[
            "flex items-center gap-2 px-4 py-1.5 rounded text-base font-medium transition-colors",
            value === view ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
          ].join(" ")}
        >
          <Icon size={16} /> {label}
        </button>
      ))}
    </div>
  );
}

// ─── List view ────────────────────────────────────────────────────────────────

function TopicCard({ topic }: { topic: TopicCluster }) {
  const href = topicHref(topic.cluster_id);
  const outlets = listedOutlets(topic);
  return (
    <article
      className="relative flex flex-col overflow-hidden rounded-lg border border-border bg-card hover:border-border-strong transition-colors"
      style={tagStyle(primaryTag(topic.category, topic.region))}
    >
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1" style={{ background: "var(--tag)" }} />
      <div className="p-5 pb-4 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TopicTags tags={topicTags(topic.category, topic.region, topic.map?.genre_weights)} />
          {topic.in_brief && (
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-accent">In today's brief</span>
          )}
        </div>
        <Link
          to={href}
          state={{ from: "topics" }}
          className="block link"
          style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.2rem", lineHeight: 1.3 }}
        >
          {topicTitle(topic)}
        </Link>
        <p className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
          {outlets} outlet{outlets !== 1 ? "s" : ""} · {topic.article_count} article{topic.article_count !== 1 ? "s" : ""}
        </p>
      </div>

      <div
        className="px-5 pb-4 text-base text-foreground leading-relaxed flex-1"
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(topic.highlighted_summary || topic.summary) }}
      />

      <div className="px-5 pb-4 pt-3 border-t border-border space-y-2">
        <SectionLabel>Sources</SectionLabel>
        <div className="flex flex-wrap gap-1.5">
          {topic.sources.map((src, i) => (
            <SourceBadge
              key={i}
              source={src}
              url={topic.urls?.[i]}
              credibility={topic.source_credibility?.[i] ?? undefined}
              lean={topic.source_credibility?.[i]?.label}
            />
          ))}
        </div>
      </div>

      {!!topic.defined_terms?.length && (
        <div className="px-5 pb-4 pt-3 border-t border-border space-y-2">
          <SectionLabel>Key Terms</SectionLabel>
          <KeyTermChips terms={topic.defined_terms} />
        </div>
      )}

      <div className="px-5 py-3 border-t border-border text-right">
        <Link to={href} state={{ from: "topics" }} className="text-base font-medium link text-brand-accent">
          Full breakdown →
        </Link>
      </div>
    </article>
  );
}

function TopicList({ topics }: { topics: TopicCluster[] }) {
  const groups = useMemo(() => {
    const byTag = new Map<TagKey, TopicCluster[]>();
    for (const t of topics) {
      const tag = primaryTag(t.category, t.region);
      if (!byTag.has(tag)) byTag.set(tag, []);
      byTag.get(tag)!.push(t);
    }
    return TAG_ORDER
      .filter(tag => byTag.has(tag))
      .map(tag => ({ tag, topics: byTag.get(tag)!.sort((a, b) => topicRelevance(b) - topicRelevance(a)) }));
  }, [topics]);

  return (
    <div className="space-y-12">
      {/* Jump links */}
      <nav aria-label="Topic groups" className="flex flex-wrap gap-2">
        {groups.map(({ tag, topics }) => (
          <a
            key={tag}
            href={`#group-${tag}`}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3.5 py-1.5 text-sm font-medium hover:border-border-strong transition-colors"
          >
            <TagSwatch tag={tag} />
            {TOPIC_TAGS[tag].label}
            <span className="text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>{topics.length}</span>
          </a>
        ))}
      </nav>

      {groups.map(({ tag, topics }) => (
        <section key={tag} id={`group-${tag}`} aria-labelledby={`group-${tag}-heading`} className="scroll-mt-24">
          <h2
            id={`group-${tag}-heading`}
            className="flex items-center gap-3 pb-2 mb-5 border-b border-border"
            style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.5rem", lineHeight: 1.2 }}
          >
            <TagSwatch tag={tag} size={16} />
            {TOPIC_TAGS[tag].label}
            <span className="ml-auto text-sm font-normal text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
              {topics.length} topic{topics.length !== 1 ? "s" : ""}
            </span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 items-start">
            {topics.map(t => <TopicCard key={t.cluster_id} topic={t} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

/** Height that fills the window below the element's top, at least `min`. */
function useFillHeight(ref: RefObject<HTMLElement | null>, active: boolean, min = 480): number {
  const [height, setHeight] = useState(min);
  useLayoutEffect(() => {
    if (!active) return;
    const measure = () => {
      const top = ref.current ? ref.current.getBoundingClientRect().top + window.scrollY : 0;
      setHeight(Math.max(min, window.innerHeight - top - 16));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [ref, active, min]);
  return height;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function TopicsPage() {
  const navigate = useNavigate();
  // ?view=list keeps the choice across reloads, back/forward and shared links.
  const [params, setParams] = useSearchParams();
  const isPhone = useIsPhone();
  const view: View = isPhone || params.get("view") === "list" ? "list" : "map";
  const [data, setData] = useState<SummariesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function setView(next: View) {
    setParams(prev => {
      const updated = new URLSearchParams(prev);
      if (next === "list") updated.set("view", "list");
      else updated.delete("view");
      return updated;
    }, { replace: true });
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchJson<SummariesData>("/api/summaries"));
    } catch (e) {
      setError(errorMessage(e, "Failed to load topics"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const topics = data?.clusters ?? [];
  const mapRef = useRef<HTMLDivElement>(null);
  const showMap = !loading && !error && topics.length > 0 && view === "map";
  const mapHeight = useFillHeight(mapRef, showMap);
  const dataKey = useMemo(
    () => `${data?.last_updated ?? ""}:${topics.map(t => t.cluster_id).join(",")}`,
    [data, topics],
  );

  return (
    <div>
      <AiBanner />
      <div className="max-w-[120rem] mx-auto px-4 sm:px-6 pt-6 pb-10">
        <header className="flex flex-wrap items-end justify-between gap-4 mb-5">
          <div>
            <h1
              style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "2.25rem", lineHeight: 1.15 }}
            >
              Topics
            </h1>
            <p className="mt-1 text-lg text-muted-foreground max-w-3xl">
              {view === "map"
                ? "Every topic today, placed by what it's about: politics at the center, health, tech and business around it, policy in between. Similar stories sit close together."
                : "Every topic today, grouped by tag and ordered by how widely each was reported."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {data?.last_updated && (
              <span className="text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
                {topics.length} topics · updated {formatRelativeDate(data.last_updated)}
              </span>
            )}
            {!isPhone && <ViewToggle value={view} onChange={setView} />}
          </div>
        </header>

        {loading && (
          <StateBox>
            <Spinner />
            <p>Loading today's topics…</p>
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

        {!loading && !error && topics.length === 0 && (
          <StateBox>
            <p>No topics yet today. Check back soon.</p>
          </StateBox>
        )}

        {!loading && !error && topics.length > 0 && (
          view === "map" ? (
            <div ref={mapRef} style={{ height: mapHeight }}>
              <TopicMap
                topics={topics}
                dataKey={dataKey}
                onOpen={id => navigate(topicHref(id), { state: { from: "topics" } })}
              />
            </div>
          ) : (
            <TopicList topics={topics} />
          )
        )}
      </div>
    </div>
  );
}
