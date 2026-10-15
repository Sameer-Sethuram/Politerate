import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Earth, Landmark } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Chunk {
  text: string;
  emotion: string;
  bias: string;
  subjective: boolean;
  techniques: Array<{ label: string; confidence: number }>;
}

export interface CredibilityData {
  score: number | null;
  label: string;
}

// ─── Brand ───────────────────────────────────────────────────────────────────

export function BrandIcon({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} fill="none" aria-hidden="true" className={`text-brand-accent shrink-0 ${className}`}>
      <g stroke="currentColor" strokeWidth="1.2">
        <line x1="26" y1="24" x2="10" y2="8" strokeDasharray="2.5 2" />
        <line x1="26" y1="24" x2="4" y2="24" strokeDasharray="2.5 2" />
        <line x1="26" y1="24" x2="10" y2="40" strokeDasharray="2.5 2" />
        <circle cx="10" cy="8" r="3.2" />
        <circle cx="4" cy="24" r="3.2" />
        <circle cx="10" cy="40" r="3.2" />
        <circle cx="26" cy="24" r="7" strokeDasharray="2.5 2" opacity="0.7" />
        <circle cx="26" cy="24" r="4" />
      </g>
      <g fill="currentColor">
        <circle cx="10" cy="8" r="1.15" />
        <circle cx="4" cy="24" r="1.15" />
        <circle cx="10" cy="40" r="1.15" />
        <circle cx="26" cy="24" r="1.5" />
      </g>
    </svg>
  );
}

// ─── Loading / States ─────────────────────────────────────────────────────────

export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div
      className="rounded-full border-2 border-border border-t-foreground animate-spin"
      style={{ width: size, height: size }}
    />
  );
}

export function StateBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      {children}
    </div>
  );
}

export function AiBanner() {
  return (
    <div className="bg-secondary border-b border-border text-center py-2.5 px-4 text-sm text-muted-foreground">
      ⚠ Summaries on this page are AI-generated — verify against linked sources before sharing.
    </div>
  );
}

// ─── Region ───────────────────────────────────────────────────────────────────

/** "us" / "world". A topic's articles share its region. Data saved before
 *  regions existed may have none; it counts as U.S. news. */
export type Region = "us" | "world";

export const REGIONS: Array<{ region: Region; label: string; heading: string }> = [
  { region: "us", label: "U.S.", heading: "U.S. News" },
  { region: "world", label: "World", heading: "World News" },
];

export function RegionIcon({ region, size = 14 }: { region: Region; size?: number }) {
  const Icon = region === "world" ? Earth : Landmark;
  return <Icon size={size} aria-hidden="true" className="shrink-0" />;
}

/** Neutral colors on purpose: blue/green/red already mean political lean. */
export function RegionTag({ region, className = "" }: { region: Region; className?: string }) {
  const label = REGIONS.find(r => r.region === region)?.label ?? region;
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-px rounded-sm border border-border bg-secondary text-secondary-foreground text-xs font-semibold uppercase tracking-wide whitespace-nowrap ${className}`}
      title={region === "world" ? "World news" : "U.S. news"}
    >
      <RegionIcon region={region} size={12} />
      {label}
    </span>
  );
}

// ─── Badges ───────────────────────────────────────────────────────────────────

// Hues for tinted chips (.chip-tint mixes them with the surface per theme).
const LEAN_HUES = { left: "#2563eb", center: "#16a34a", right: "#dc2626" };

const LEAN_MAP: Record<string, { label: string; hue: string }> = {
  left:         { label: "Left",   hue: LEAN_HUES.left },
  "lean-left":  { label: "Left",   hue: LEAN_HUES.left },
  label_0:      { label: "Left",   hue: LEAN_HUES.left },
  center:       { label: "Center", hue: LEAN_HUES.center },
  "lean-center":{ label: "Center", hue: LEAN_HUES.center },
  label_1:      { label: "Center", hue: LEAN_HUES.center },
  right:        { label: "Right",  hue: LEAN_HUES.right },
  "lean-right": { label: "Right",  hue: LEAN_HUES.right },
  label_2:      { label: "Right",  hue: LEAN_HUES.right },
};

const hueStyle = (hue: string) => ({ "--hue": hue }) as React.CSSProperties;
/** A hue readable as text on either theme's surfaces. */
const textHue = (hue: string) => `color-mix(in srgb, ${hue} var(--tint-ink-mix), var(--foreground))`;

export function LeanBadge({ lean }: { lean: string }) {
  const c = LEAN_MAP[lean?.toLowerCase()];
  if (!c) return null;
  return (
    <span
      className="chip-tint inline-flex items-center px-2 py-0.5 rounded-sm text-sm font-semibold"
      style={hueStyle(c.hue)}
    >
      {c.label}
    </span>
  );
}

export function CredBadge({ score }: { score: number }) {
  const hue = score >= 0.8 ? "#16a34a" : score >= 0.5 ? "#ca8a04" : "#dc2626";
  return (
    <span
      className="chip-tint inline-flex items-center px-2 py-0.5 rounded-sm text-sm tabular-nums"
      style={{ ...hueStyle(hue), fontFamily: "var(--font-data)" }}
      title="Credibility score (0–1): higher means less loaded, subjective language"
    >
      {score.toFixed(2)}
    </span>
  );
}

const EMOTION_HUES: Record<string, string> = {
  neutral:     "#6b7280",
  anger:       "#dc2626",
  fear:        "#d97706",
  sadness:     "#2563eb",
  joy:         "#059669",
  approval:    "#16a34a",
  disapproval: "#db2777",
  disgust:     "#9333ea",
  annoyance:   "#ea580c",
  optimism:    "#0284c7",
  confusion:   "#64748b",
};

export function EmotionBadge({ emotion }: { emotion: string }) {
  return (
    <span
      className="chip-tint inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-semibold capitalize"
      style={hueStyle(EMOTION_HUES[emotion] ?? EMOTION_HUES.neutral)}
    >
      {emotion}
    </span>
  );
}

export function BiasBar({ bias }: { bias: string }) {
  const segs = ["left", "center", "right"] as const;
  const colors: Record<string, string> = { left: "#2563eb", center: "#16a34a", right: "#dc2626" };
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-flex gap-0.5 items-center">
        {segs.map(s => (
          <span
            key={s}
            className="inline-block w-3.5 h-3.5 rounded-sm"
            style={{
              background: s === bias ? colors[s] : "var(--border)",
              opacity: s === bias ? 1 : 0.4,
            }}
          />
        ))}
      </span>
      <span
        className="text-sm font-medium capitalize"
        style={{ color: colors[bias] ? textHue(colors[bias]) : "var(--muted-foreground)" }}
      >
        {bias ? bias[0].toUpperCase() + bias.slice(1) : "—"}
      </span>
    </span>
  );
}

export function SubjectivityBar({ pct }: { pct: number }) {
  const v = Math.max(0, Math.min(100, Math.round(pct)));
  const high = v >= 85, med = v >= 70;
  const color = high ? "#16a34a" : med ? "#d97706" : "#dc2626";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="w-24 h-2 rounded-full bg-border-strong overflow-hidden">
        <span className="block h-full rounded-full" style={{ width: `${v}%`, background: color }} />
      </span>
      <span className="text-sm tabular-nums" style={{ color: textHue(color), fontFamily: "var(--font-data)" }}>
        {v}%
      </span>
    </span>
  );
}

// ─── Source badge ─────────────────────────────────────────────────────────────

export function SourceBadge({
  source, url, credibility, lean,
}: {
  source: string;
  url?: string;
  credibility?: CredibilityData;
  lean?: string;
}) {
  const isLink = !!url && url !== "#";
  const inner = (
    <>
      {lean && lean !== "unknown" && <LeanBadge lean={lean} />}
      {/* Only the outlet name is underlined: the lean/credibility chips
          inside a linked badge aren't text links themselves. */}
      <span
        className={
          isLink
            ? "text-sm link group-hover:text-brand-accent group-hover:decoration-[var(--accent)]"
            : "text-sm"
        }
      >
        {source}
      </span>
      {credibility?.score != null && <CredBadge score={credibility.score} />}
    </>
  );
  const cls =
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-card transition-colors text-foreground shrink-0";
  if (isLink) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={`${cls} group hover:border-[var(--accent)]`}
      >
        {inner}
      </a>
    );
  }
  return <span className={cls}>{inner}</span>;
}

// ─── Annotation ───────────────────────────────────────────────────────────────

const TECHNIQUE_CAT: Record<string, string> = {
  Loaded_Language: "persuasion",
  Name_Calling_Labeling: "persuasion",
  Appeal_to_fear_prejudice: "appeal",
  Appeal_to_Authority: "appeal",
  Flag_Waving: "appeal",
  Exaggeration_Minimization: "exaggeration",
  Bandwagon: "exaggeration",
  Black_and_White_Fallacy: "exaggeration",
  Doubt: "loaded",
  Thought_terminating_Cliches: "loaded",
  Reductio_ad_hitlerum: "loaded",
  Causal_Oversimplification: "loaded",
  Whataboutism_Straw_Men_Red_Herring: "loaded",
  Straw_Man: "loaded",
  Red_Herring: "loaded",
  Repetition: "loaded",
  Slogans: "loaded",
  Obfuscation_Intentional_Vagueness_Confusion: "loaded",
};

/** Hues behind analyzer-flagged text, by category (.annot / .chip-tint). */
export const ANNOT_HUES: Record<string, string> = {
  persuasion: "#ef4444",
  appeal: "#a855f7",
  exaggeration: "#ec4899",
  loaded: "#f97316",
  emotion: "#eab308",
};

export function chunkCategory(chunk: Chunk): string | null {
  if (chunk.techniques?.length) {
    const top = [...chunk.techniques].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))[0];
    return TECHNIQUE_CAT[top.label] ?? "loaded";
  }
  if (chunk.emotion && chunk.emotion !== "neutral") return "emotion";
  return null;
}

export function AnnotationLegend() {
  const items = [
    { hue: ANNOT_HUES.persuasion, label: "Persuasion" },
    { hue: ANNOT_HUES.appeal, label: "Appeal" },
    { hue: ANNOT_HUES.exaggeration, label: "Exaggeration" },
    { hue: ANNOT_HUES.loaded, label: "Loaded" },
    { hue: ANNOT_HUES.emotion, label: "Emotional" },
  ];
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {items.map(item => (
        <span key={item.label} className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <span className="annot inline-block w-3.5 h-3.5 rounded-sm" style={hueStyle(item.hue)} />
          {item.label}
        </span>
      ))}
      <span className="text-sm text-muted-foreground">Hover for label</span>
    </div>
  );
}

export function AnnotatedText({ chunks }: { chunks: Chunk[] }) {
  if (!chunks?.length) return null;
  return (
    <p className="leading-relaxed text-lg text-foreground">
      {chunks.map((chunk, i) => {
        const cat = chunkCategory(chunk);
        if (!cat) return <span key={i}>{chunk.text} </span>;
        const techList = chunk.techniques.map(t => t.label.replace(/_/g, " ")).join(", ");
        const emo = chunk.emotion !== "neutral" ? chunk.emotion : "";
        const tip = [techList, emo].filter(Boolean).join(" · ");
        return (
          <span
            key={i}
            title={tip}
            className="annot cursor-help rounded-sm px-0.5"
            style={hueStyle(ANNOT_HUES[cat] ?? ANNOT_HUES.loaded)}
          >
            {chunk.text}{" "}
          </span>
        );
      })}
    </p>
  );
}

// ─── Glossary term tooltip ────────────────────────────────────────────────────

/**
 * Definitions for the glossary terms the backend highlights
 * (`.politerate-term`, definition in `title`). One floating tooltip for the
 * whole page, so it isn't clipped by containers that hide overflow (Daily
 * Brief tiles clamp their text). Mounted once, in Layout.
 */
export function TermTooltip() {
  const [tip, setTip] = useState<{ text: string; anchor: DOMRect } | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const termOf = (target: EventTarget | null) =>
      target instanceof Element ? target.closest<HTMLElement>(".politerate-term") : null;

    function show(e: Event) {
      const el = termOf(e.target);
      if (!el) return;
      // Move the definition off `title` so the browser's own tooltip doesn't
      // show as well.
      if (el.hasAttribute("title")) {
        el.dataset.definition = el.getAttribute("title") ?? "";
        el.removeAttribute("title");
      }
      const text = el.dataset.definition;
      if (text) setTip({ text, anchor: el.getBoundingClientRect() });
    }
    function leave(e: MouseEvent) {
      const el = termOf(e.target);
      if (el && !el.contains(e.relatedTarget as Node | null)) setTip(null);
    }
    const hide = () => setTip(null);

    document.addEventListener("mouseover", show);
    document.addEventListener("mouseout", leave);
    document.addEventListener("focusin", show);
    document.addEventListener("focusout", hide);
    window.addEventListener("scroll", hide, true);
    return () => {
      document.removeEventListener("mouseover", show);
      document.removeEventListener("mouseout", leave);
      document.removeEventListener("focusin", show);
      document.removeEventListener("focusout", hide);
      window.removeEventListener("scroll", hide, true);
    };
  }, []);

  // Above the term, or below it near the top of the window; kept on screen.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !tip) return;
    const { width, height } = el.getBoundingClientRect();
    const { anchor } = tip;
    const left = Math.min(
      Math.max(anchor.left + anchor.width / 2 - width / 2, 12),
      window.innerWidth - width - 12,
    );
    const above = anchor.top - height - 8;
    el.style.left = `${left}px`;
    el.style.top = `${above >= 8 ? above : anchor.bottom + 8}px`;
    el.style.visibility = "visible";
  }, [tip]);

  if (!tip) return null;
  return createPortal(
    <div ref={ref} role="tooltip" className="term-tooltip" style={{ left: 0, top: 0, visibility: "hidden" }}>
      {tip.text}
    </div>,
    document.body,
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const TOPIC_ICONS: Record<string, string> = {
  climate: "🌍", econom: "📈", stock: "📈", market: "📈",
  health: "🏥", foreign: "🌍", war: "⚔️",
  election: "🗳️", vote: "🗳️", trump: "🏛️", biden: "🏛️",
  congress: "🏛️", senate: "🏛️", court: "⚖️", crime: "🚔",
  tech: "💻", science: "🔬", default: "📰",
};

export function getTopicIcon(text: string): string {
  const lower = (text ?? "").toLowerCase();
  for (const [kw, icon] of Object.entries(TOPIC_ICONS)) {
    if (lower.includes(kw)) return icon;
  }
  return TOPIC_ICONS.default;
}

/** The site's clock (backend config.TIMEZONE): days change at midnight Eastern. */
export const SITE_TIME_ZONE = "America/New_York";

/** Today's date on the site's clock, as YYYY-MM-DD. */
export function siteToday(): string {
  // en-CA formats dates as YYYY-MM-DD.
  return new Date().toLocaleDateString("en-CA", { timeZone: SITE_TIME_ZONE });
}

export function formatRelativeDate(iso?: string): string {
  if (!iso) return "Just now";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24) return `${hrs}h ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatTechnique(label: string): string {
  return label.replace(/_/g, " ");
}

// ─── Shared card wrapper ──────────────────────────────────────────────────────

export function Card({
  children, className = "",
}: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-card border border-border rounded ${className}`}>
      {children}
    </div>
  );
}

// ─── Page shell ───────────────────────────────────────────────────────────────

// Page widths. Layout's header/footer use the same values so their edges
// line up with the page content.
export const DEFAULT_WIDTH = "max-w-6xl";
// Near full-bleed, for dense grids like All Articles.
export const WIDE_WIDTH = "max-w-[120rem]";

export function PageContainer({ children, narrow = false, wide = false }: {
  children: React.ReactNode;
  narrow?: boolean;
  wide?: boolean;
}) {
  const maxWidth = narrow ? "max-w-4xl" : wide ? WIDE_WIDTH : DEFAULT_WIDTH;
  return (
    <div className={`mx-auto px-4 sm:px-6 py-8 ${maxWidth}`}>
      {children}
    </div>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2"
    >
      {children}
    </div>
  );
}
