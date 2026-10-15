import type { Region } from "./shared";
import type { DetailedSummary, DefinedTerm } from "./TopicSummary";
import type { GenreWeights } from "./topicTags";

/** A topic from /api/summaries. */
export interface TopicCluster {
  cluster_id: string;
  summary: string;
  highlighted_summary?: string;
  detailed_summary?: DetailedSummary | null;
  titles: string[];
  sources: string[];
  urls: string[];
  article_count: number;
  outlet_count?: number | null;
  source_credibility?: Array<{ score: number | null; label: string }>;
  defined_terms?: DefinedTerm[];
  region?: Region | null;
  category?: string | null;
  // Daily Brief ranking (summarizer.brief_relevance) and selection.
  relevance?: number;
  in_brief?: boolean;
  // Where the map places it (pipeline/topic_map.py); missing on topics
  // saved before the map existed.
  map?: {
    genre_weights?: Partial<GenreWeights> | null;
    neighbors?: Array<[string, number]>;
  } | null;
}

export interface SummariesData {
  last_updated?: string;
  clusters: TopicCluster[];
}

export function topicTitle(t: TopicCluster): string {
  return t.titles?.[0] || "Untitled topic";
}

export function topicHref(id: string): string {
  return `/cluster/${encodeURIComponent(id)}`;
}

export function outletCount(t: TopicCluster): number {
  return t.outlet_count || new Set(t.sources ?? []).size;
}

// Mirrors summarizer.BRIEF_WEIGHTS, for topics served without `relevance`.
const RELEVANCE_WEIGHTS = { us: 1.5, world: 1.25, genre: 1.0 };

/** How widely reported a topic is, weighted the way the Daily Brief ranks. */
export function topicRelevance(t: TopicCluster): number {
  if (t.relevance != null) return t.relevance;
  const genre = t.category && t.category !== "politics";
  const weight = genre ? RELEVANCE_WEIGHTS.genre : t.region === "world" ? RELEVANCE_WEIGHTS.world : RELEVANCE_WEIGHTS.us;
  return outletCount(t) * weight;
}
