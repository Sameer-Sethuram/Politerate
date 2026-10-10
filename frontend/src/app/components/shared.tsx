import React from "react";

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
    <div className="bg-secondary border-b border-border text-center py-2 px-4 text-xs text-muted-foreground">
      ⚠ Summaries on this page are AI-generated — verify against linked sources before sharing.
    </div>
  );
}

// ─── Badges ───────────────────────────────────────────────────────────────────

const LEAN_MAP: Record<string, { label: string; bg: string; color: string }> = {
  left:         { label: "Left",   bg: "#dbeafe", color: "#1d4ed8" },
  "lean-left":  { label: "Left",   bg: "#dbeafe", color: "#1d4ed8" },
  label_0:      { label: "Left",   bg: "#dbeafe", color: "#1d4ed8" },
  center:       { label: "Center", bg: "#dcfce7", color: "#15803d" },
  "lean-center":{ label: "Center", bg: "#dcfce7", color: "#15803d" },
  label_1:      { label: "Center", bg: "#dcfce7", color: "#15803d" },
  right:        { label: "Right",  bg: "#fee2e2", color: "#b91c1c" },
  "lean-right": { label: "Right",  bg: "#fee2e2", color: "#b91c1c" },
  label_2:      { label: "Right",  bg: "#fee2e2", color: "#b91c1c" },
};

export function LeanBadge({ lean }: { lean: string }) {
  const c = LEAN_MAP[lean?.toLowerCase()];
  if (!c) return null;
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-xs font-semibold"
      style={{ background: c.bg, color: c.color }}
    >
      {c.label}
    </span>
  );
}

export function CredBadge({ score }: { score: number }) {
  const high = score >= 0.8, med = score >= 0.5;
  const bg    = high ? "#dcfce7" : med ? "#fef9c3" : "#fee2e2";
  const color = high ? "#15803d" : med ? "#854d0e" : "#991b1b";
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-xs tabular-nums"
      style={{ background: bg, color, fontFamily: "var(--font-data)" }}
    >
      {score.toFixed(2)}
    </span>
  );
}

const EMOTION_STYLES: Record<string, { bg: string; color: string }> = {
  neutral:     { bg: "#f3f4f6", color: "#4b5563" },
  anger:       { bg: "#fee2e2", color: "#991b1b" },
  fear:        { bg: "#fef3c7", color: "#92400e" },
  sadness:     { bg: "#dbeafe", color: "#1e40af" },
  joy:         { bg: "#d1fae5", color: "#065f46" },
  approval:    { bg: "#dcfce7", color: "#065f46" },
  disapproval: { bg: "#fce7f3", color: "#9d174d" },
  disgust:     { bg: "#f3e8ff", color: "#6b21a8" },
  annoyance:   { bg: "#ffedd5", color: "#9a3412" },
  optimism:    { bg: "#e0f2fe", color: "#075985" },
  confusion:   { bg: "#f1f5f9", color: "#475569" },
};

export function EmotionBadge({ emotion }: { emotion: string }) {
  const s = EMOTION_STYLES[emotion] ?? EMOTION_STYLES.neutral;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={{ background: s.bg, color: s.color }}
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
            className="inline-block w-3 h-3 rounded-sm"
            style={{
              background: s === bias ? colors[s] : "var(--border)",
              opacity: s === bias ? 1 : 0.4,
            }}
          />
        ))}
      </span>
      <span
        className="text-xs font-medium capitalize"
        style={{ color: colors[bias] ?? "var(--muted-foreground)" }}
      >
        {bias ? bias[0].toUpperCase() + bias.slice(1) : "—"}
      </span>
    </span>
  );
}

export function SubjectivityBar({ pct }: { pct: number }) {
  const v = Math.max(0, Math.min(100, Math.round(pct)));
  const high = v >= 85, med = v >= 70;
  const color = high ? "#15803d" : med ? "#d97706" : "#dc2626";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="w-20 h-1.5 rounded-full bg-secondary overflow-hidden">
        <span className="block h-full rounded-full" style={{ width: `${v}%`, background: color }} />
      </span>
      <span className="text-xs tabular-nums" style={{ color, fontFamily: "var(--font-data)" }}>
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
  const inner = (
    <>
      {lean && lean !== "unknown" && <LeanBadge lean={lean} />}
      <span className="text-xs">{source}</span>
      {credibility?.score != null && <CredBadge score={credibility.score} />}
    </>
  );
  const cls =
    "inline-flex items-center gap-1.5 px-2 py-1 rounded border border-border bg-card hover:bg-secondary transition-colors text-foreground shrink-0";
  if (url && url !== "#") {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className={cls}>
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

const ANNOT_BG: Record<string, string> = {
  persuasion: "#fee2e2",
  appeal: "#f3e8ff",
  exaggeration: "#fce7f3",
  loaded: "#ffedd5",
  emotion: "#fef3c7",
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
    { bg: "#fee2e2", label: "Persuasion" },
    { bg: "#f3e8ff", label: "Appeal" },
    { bg: "#fce7f3", label: "Exaggeration" },
    { bg: "#ffedd5", label: "Loaded" },
    { bg: "#fef3c7", label: "Emotional" },
  ];
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {items.map(item => (
        <span key={item.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: item.bg }} />
          {item.label}
        </span>
      ))}
      <span className="text-xs text-muted-foreground">Hover for label</span>
    </div>
  );
}

export function AnnotatedText({ chunks }: { chunks: Chunk[] }) {
  if (!chunks?.length) return null;
  return (
    <p className="leading-7 text-sm text-foreground">
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
            className="cursor-help rounded-sm px-0.5"
            style={{ background: ANNOT_BG[cat] ?? ANNOT_BG.loaded }}
          >
            {chunk.text}{" "}
          </span>
        );
      })}
    </p>
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

export function PageContainer({ children, narrow = false }: {
  children: React.ReactNode;
  narrow?: boolean;
}) {
  return (
    <div className={`mx-auto px-4 sm:px-6 py-8 ${narrow ? "max-w-3xl" : "max-w-6xl"}`}>
      {children}
    </div>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2"
    >
      {children}
    </div>
  );
}
