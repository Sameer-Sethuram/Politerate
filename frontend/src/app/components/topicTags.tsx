import type { CSSProperties } from "react";
import type { Region } from "./shared";

// ─── Tags ─────────────────────────────────────────────────────────────────────

/** The colored tags on topics and articles. Political news splits into U.S.
 *  and World by region; health, tech and business are genres. */
export type TagKey = "us" | "world" | "health" | "tech" | "business";

export const TAG_ORDER: TagKey[] = ["us", "world", "health", "tech", "business"];

export const TOPIC_TAGS: Record<TagKey, { label: string; color: string; ink: string }> = {
  us:       { label: "U.S. Politics", color: "var(--tag-us)",       ink: "var(--tag-us-ink)" },
  world:    { label: "World News",    color: "var(--tag-world)",    ink: "var(--tag-world-ink)" },
  health:   { label: "Health",        color: "var(--tag-health)",   ink: "var(--tag-health-ink)" },
  tech:     { label: "Tech",          color: "var(--tag-tech)",     ink: "var(--tag-tech-ink)" },
  business: { label: "Business",      color: "var(--tag-business)", ink: "var(--tag-business-ink)" },
};

export function tagStyle(tag: TagKey): CSSProperties {
  return { "--tag": TOPIC_TAGS[tag].color, "--tag-ink": TOPIC_TAGS[tag].ink } as CSSProperties;
}

// ─── Genres (backend pipeline/topic_map.py) ──────────────────────────────────

export type Genre = "politics" | "health" | "tech" | "business";
export const GENRES: Genre[] = ["politics", "health", "tech", "business"];
export type GenreWeights = Record<Genre, number>;

/** How much a topic belongs to each genre, summing to 1. From the pipeline's
 *  map data; topics saved before it existed count fully as their category. */
export function genreWeights(category?: string | null, weights?: Partial<GenreWeights> | null): GenreWeights {
  const out: GenreWeights = { politics: 0, health: 0, tech: 0, business: 0 };
  const total = weights ? GENRES.reduce((sum, g) => sum + (weights[g] ?? 0), 0) : 0;
  if (weights && total > 0) {
    for (const g of GENRES) out[g] = (weights[g] ?? 0) / total;
  } else {
    out[GENRES.includes(category as Genre) ? (category as Genre) : "politics"] = 1;
  }
  return out;
}

/** Weights over tags: a topic's political share goes to U.S. or World by
 *  its region. Drives the map circles' gradients. */
export function tagWeights(weights: GenreWeights, region?: Region | null): Record<TagKey, number> {
  return {
    us: region === "world" ? 0 : weights.politics,
    world: region === "world" ? weights.politics : 0,
    health: weights.health,
    tech: weights.tech,
    business: weights.business,
  };
}

/** The tag a topic is filed under: its category, with political (and
 *  policy) topics split by region. Missing values count as U.S. politics. */
export function primaryTag(category?: string | null, region?: Region | null): TagKey {
  if (category === "health" || category === "tech" || category === "business") return category;
  return region === "world" ? "world" : "us";
}

// A genre this share of a topic also gets its own tag: a policy topic about
// drug prices is tagged U.S. Politics and Health.
const SECONDARY_TAG_SHARE = 0.25;

/** A topic's tags, its primary tag first. */
export function topicTags(
  category?: string | null,
  region?: Region | null,
  weights?: Partial<GenreWeights> | null,
): TagKey[] {
  const primary = primaryTag(category, region);
  const byTag = tagWeights(genreWeights(category, weights), region);
  const secondary = TAG_ORDER
    .filter(t => t !== primary && byTag[t] >= SECONDARY_TAG_SHARE)
    .sort((a, b) => byTag[b] - byTag[a]);
  return [primary, ...secondary];
}

// ─── Components ───────────────────────────────────────────────────────────────

export function TopicTag({ tag, className = "" }: { tag: TagKey; className?: string }) {
  return (
    <span
      className={`topic-tag inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap ${className}`}
      style={tagStyle(tag)}
    >
      {TOPIC_TAGS[tag].label}
    </span>
  );
}

export function TopicTags({ tags, className = "" }: { tags: TagKey[]; className?: string }) {
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}>
      {tags.map(t => <TopicTag key={t} tag={t} />)}
    </span>
  );
}

export function TagSwatch({ tag, size = 12 }: { tag: TagKey; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="topic-tag inline-block rounded-full shrink-0"
      style={{ ...tagStyle(tag), width: size, height: size }}
    />
  );
}
