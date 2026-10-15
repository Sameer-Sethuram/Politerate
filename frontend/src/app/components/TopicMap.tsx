import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import { ArrowRight, Maximize2, Minus, Plus } from "lucide-react";
import { AXIS_DIRECTION, AXIS_GENRES, AxisGenre, LayoutNode, MapLayout, genreDirection, layoutTopics } from "./topicLayout";
import { TopicCluster, outletCount, topicRelevance, topicTitle } from "./topicData";
import {
  TAG_ORDER, TOPIC_TAGS, TagKey, TagSwatch, TopicTags, genreWeights, tagWeights, topicTags,
} from "./topicTags";

// Circle radii in map units, by relevance (area grows with it).
const MIN_RADIUS = 14;
const MAX_RADIUS = 58;
// A tag needs this share of a topic to show in its circle's gradient.
const GRADIENT_MIN_SHARE = 0.08;
// Titles inside circles, in screen pixels.
const LABEL_FONT = "600 12px Alegreya, Georgia, serif";
const LABEL_LINE_HEIGHT = 14;
// Space between a line's ends and the circle's edge, and above/below the text.
const LABEL_PADDING_X = 8;
const LABEL_PADDING_Y = 4;
// Titles wrap into blocks at least this many times wider than tall, so
// they run across the circle rather than down it.
const LABEL_MIN_ASPECT = 2;
// The outlets note under a title.
const NOTE_FONT = "400 11px Alegreya, Georgia, serif";
const NOTE_LINE_HEIGHT = 13;
const NOTE_GAP = 3;
// Zoom limits, relative to the zoom that fits the whole map.
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 14;
// Pointer travel (px) that turns a press into a drag.
const DRAG_THRESHOLD = 5;
const VIEW_STORAGE_KEY = "politerate-topic-map-view";

const GENRE_TAG: Record<AxisGenre, TagKey> = { health: "health", tech: "tech", business: "business" };

interface View { k: number; x: number; y: number }

interface MapTopic {
  topic: TopicCluster;
  node: LayoutNode;
  index: number;
  title: string;
  tags: TagKey[];
  dominant: TagKey;
  // Gradient bands, in order from the center outward.
  stops: Array<{ offset: number; tag: TagKey }>;
  direction: { x: number; y: number } | null;
}

// ─── Title fitting ────────────────────────────────────────────────────────────

let measureContext: CanvasRenderingContext2D | null = null;
function textWidth(text: string, font = LABEL_FONT): number {
  measureContext ??= document.createElement("canvas").getContext("2d");
  if (!measureContext) return text.length * 6.5;
  measureContext.font = font;
  return measureContext.measureText(text).width;
}

interface TitleFit {
  // Smallest circle (screen px radius) that holds the whole title.
  minRadius: number;
  // Wraps from fewest lines (widest, needs the biggest circle) to most.
  options: Array<{ lines: string[]; widths: number[]; radius: number }>;
}

/** Ways to wrap `title` inside a circle, each with the circle radius (screen
 *  px) it needs. The title shows once its circle reaches minRadius, using
 *  the wrap with the fewest lines that fits: zooming in widens it into
 *  fewer, longer lines. Only wraps at least LABEL_MIN_ASPECT times wider
 *  than tall count, so titles run across the circle. */
function fitTitle(title: string): TitleFit {
  const words = title.split(/\s+/).filter(Boolean);
  const widths = words.map(word => textWidth(word));
  const space = textWidth(" ");
  const byLineCount = new Map<number, TitleFit["options"][number]>();
  for (let wrap = Math.max(...widths, 24); wrap <= 900; wrap += 4) {
    const lines: string[] = [];
    const lineWidths: number[] = [];
    let line = "", lineWidth = 0;
    words.forEach((word, i) => {
      if (line && lineWidth + space + widths[i] > wrap) {
        lines.push(line);
        lineWidths.push(lineWidth);
        line = "";
        lineWidth = 0;
      }
      line = line ? `${line} ${word}` : word;
      lineWidth = lineWidth ? lineWidth + space + widths[i] : widths[i];
    });
    lines.push(line);
    lineWidths.push(lineWidth);

    const height = lines.length * LABEL_LINE_HEIGHT;
    if (lines.length > 1 && Math.max(...lineWidths) < LABEL_MIN_ASPECT * height) continue;
    // Each line, centered, has to fit the circle's width at its own height:
    // its outer corners inside the circle. Middle lines can run wider than
    // the top and bottom ones.
    const radius = Math.max(
      ...lineWidths.map((w, i) => {
        const top = -height / 2 + i * LABEL_LINE_HEIGHT;
        const edge = Math.max(Math.abs(top), Math.abs(top + LABEL_LINE_HEIGHT)) + LABEL_PADDING_Y;
        return Math.hypot(w / 2 + LABEL_PADDING_X, edge);
      }),
    );
    const prev = byLineCount.get(lines.length);
    if (!prev || radius < prev.radius) byLineCount.set(lines.length, { lines, widths: lineWidths, radius });
    if (lines.length === 1) break;
  }
  // Keep a wrap only if it fits a smaller circle than every wrap with
  // fewer lines; otherwise the fewer-lines one is always the better pick.
  const options: TitleFit["options"] = [];
  for (const count of [...byLineCount.keys()].sort((a, b) => a - b)) {
    const option = byLineCount.get(count)!;
    if (!options.length || option.radius < options[options.length - 1].radius) options.push(option);
  }
  return { minRadius: options.length ? options[options.length - 1].radius : Infinity, options };
}

/** Room across a circle of radius `r` for a line of text whose top is at
 *  `top` (relative to the center), after padding. */
function lineRoom(r: number, top: number, height: number): number {
  const edge = Math.max(Math.abs(top), Math.abs(top + height)) + LABEL_PADDING_Y;
  return edge >= r ? 0 : 2 * (Math.sqrt(r * r - edge * edge) - LABEL_PADDING_X);
}

/** The outlets that reported a topic, as many as fit in `room` px:
 *  "CNN, Fox, BBC +9 more", else "12 outlets", else nothing. */
function outletNote(outlets: string[], room: number): string | null {
  const fits = (text: string) => textWidth(text, NOTE_FONT) <= room;
  if (fits(outlets.join(", "))) return outlets.join(", ");
  for (let shown = outlets.length - 1; shown >= 1; shown--) {
    const text = `${outlets.slice(0, shown).join(", ")} +${outlets.length - shown} more`;
    if (fits(text)) return text;
  }
  const count = `${outlets.length} outlet${outlets.length !== 1 ? "s" : ""}`;
  return fits(count) ? count : null;
}

/** A title (and, when there's room under it, its outlets note) laid out in
 *  a circle of screen radius `r`: each line's y relative to the center. */
function layoutLabel(fit: TitleFit, outlets: string[], r: number) {
  const title = fit.options.find(o => o.radius <= r)!;
  const titleHeight = title.lines.length * LABEL_LINE_HEIGHT;
  // With the note, the title moves up so title and note center together.
  const blockHeight = titleHeight + NOTE_GAP + NOTE_LINE_HEIGHT;
  const titleTop = -blockHeight / 2;
  const titleFits = title.widths.every(
    (w, i) => w <= lineRoom(r, titleTop + i * LABEL_LINE_HEIGHT, LABEL_LINE_HEIGHT),
  );
  const noteTop = titleTop + titleHeight + NOTE_GAP;
  const note = titleFits ? outletNote(outlets, lineRoom(r, noteTop, NOTE_LINE_HEIGHT)) : null;
  const top = note ? titleTop : -titleHeight / 2;
  return {
    lines: title.lines.map((line, i) => ({ text: line, y: top + (i + 0.5) * LABEL_LINE_HEIGHT })),
    note: note && { text: note, y: noteTop + NOTE_LINE_HEIGHT / 2 },
  };
}

// ─── Data → map ───────────────────────────────────────────────────────────────

// Where each tag's color sits on the map: politics at the center, genres at
// their axis points.
const TAG_DIRECTION: Record<TagKey, { x: number; y: number }> = {
  us: { x: 0, y: 0 },
  world: { x: 0, y: 0 },
  ...AXIS_DIRECTION,
};

/** Color bands for a circle's gradient, which runs along `direction`. Each
 *  tag's band is as wide as its share and on the side facing its place on
 *  the map: politics toward the center, health toward the health axis. */
function gradientStops(weights: Record<TagKey, number>, direction: { x: number; y: number } | null): MapTopic["stops"] {
  const d = direction ?? { x: 0, y: -1 };
  const along = (t: TagKey) => TAG_DIRECTION[t].x * d.x + TAG_DIRECTION[t].y * d.y;
  const kept = TAG_ORDER.filter(t => weights[t] >= GRADIENT_MIN_SHARE).sort((a, b) => along(a) - along(b));
  const total = kept.reduce((sum, t) => sum + weights[t], 0) || 1;
  let start = 0;
  return kept.map(tag => {
    const share = weights[tag] / total;
    const offset = start + share / 2;
    start += share;
    return { offset, tag };
  });
}

function buildMap(topics: TopicCluster[]): { layout: MapLayout; items: MapTopic[] } {
  const maxRelevance = Math.max(1, ...topics.map(topicRelevance));
  const inputs = topics.map(t => ({
    id: t.cluster_id,
    r: MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * Math.sqrt(topicRelevance(t) / maxRelevance),
    weights: genreWeights(t.category, t.map?.genre_weights),
    neighbors: t.map?.neighbors ?? [],
  }));
  const layout = layoutTopics(inputs);
  const items = layout.nodes.map((node, index) => {
    const topic = topics[index];
    const byTag = tagWeights(node.weights, topic.region);
    const dominant = TAG_ORDER.reduce((a, b) => (byTag[b] > byTag[a] ? b : a));
    const direction = genreDirection(node.weights);
    return {
      topic,
      node,
      index,
      title: topicTitle(topic),
      tags: topicTags(topic.category, topic.region, topic.map?.genre_weights),
      dominant,
      stops: gradientStops(byTag, direction),
      direction,
    };
  });
  // Biggest first, so small circles draw on top.
  items.sort((a, b) => b.node.r - a.node.r);
  return { layout, items };
}

// Screen space the fitted map keeps clear: room for the axis labels (fixed
// size text centered on their points), the zoom controls on the right, and
// the legend (its measured height) along the bottom.
const FIT_INSETS = { top: 26, right: 72, left: 104 };

function fitView(layout: MapLayout, width: number, height: number, legendHeight: number): View {
  const { minX, minY, maxX, maxY } = layout.bounds;
  // Below the political ring: its label, then the legend.
  const inset = { ...FIT_INSETS, bottom: legendHeight + 46 };
  const w = Math.max(width - inset.left - inset.right, 100);
  const h = Math.max(height - inset.top - inset.bottom, 100);
  const k = Math.min(w / (maxX - minX), h / (maxY - minY));
  return {
    k,
    x: inset.left + w / 2 - ((minX + maxX) / 2) * k,
    y: inset.top + h / 2 - ((minY + maxY) / 2) * k,
  };
}

function readSavedView(key: string): View | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(VIEW_STORAGE_KEY) ?? "null");
    return saved?.key === key ? saved.view : null;
  } catch {
    return null;
  }
}

function saveView(key: string, view: View) {
  try {
    sessionStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify({ key, view }));
  } catch {
    // Storage blocked: the map just opens fitted next time.
  }
}

// ─── Circles (memoized: panning only moves their group) ─────────────────────

const Circles = memo(function Circles({ items }: { items: MapTopic[] }) {
  return (
    <>
      <defs>
        {items.map(item => {
          if (item.stops.length < 2) return null;
          const d = item.direction ?? { x: 0, y: -1 };
          return (
            <linearGradient
              key={item.index}
              id={`topic-fill-${item.index}`}
              x1={0.5 - d.x / 2} y1={0.5 - d.y / 2} x2={0.5 + d.x / 2} y2={0.5 + d.y / 2}
            >
              {item.stops.map(s => (
                <stop key={s.tag} offset={s.offset} style={{ stopColor: TOPIC_TAGS[s.tag].color }} />
              ))}
            </linearGradient>
          );
        })}
        {/* Soft highlight so circles read as solid at any zoom. */}
        <radialGradient id="topic-sheen" cx="0.35" cy="0.3" r="0.75">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.22" />
          <stop offset="0.6" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>
      {items.map(item => (
        <g key={item.index} data-topic={item.topic.cluster_id}>
          <circle
            cx={item.node.x}
            cy={item.node.y}
            r={item.node.r}
            style={{
              fill: item.stops.length > 1 ? `url(#topic-fill-${item.index})` : TOPIC_TAGS[item.dominant].color,
              stroke: "var(--map-circle-edge)",
              strokeWidth: 1,
              cursor: "pointer",
            }}
            vectorEffect="non-scaling-stroke"
          />
          <circle cx={item.node.x} cy={item.node.y} r={item.node.r} fill="url(#topic-sheen)" pointerEvents="none" />
        </g>
      ))}
    </>
  );
});

// ─── Map ──────────────────────────────────────────────────────────────────────

export function TopicMap({
  topics,
  dataKey,
  onOpen,
}: {
  topics: TopicCluster[];
  // Identifies this set of topics; the saved view is reused only for it.
  dataKey: string;
  onOpen: (clusterId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  const [legendHeight, setLegendHeight] = useState(0);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [view, setView] = useState<View | null>(null);
  const viewRef = useRef<View | null>(null);
  viewRef.current = view;
  const [hovered, setHovered] = useState<string | null>(null);
  // Touch: the first tap on a circle previews it, with a button to open.
  const [pinned, setPinned] = useState(false);
  const [fontsReady, setFontsReady] = useState(false);

  const { layout, items } = useMemo(() => buildMap(topics), [topics]);
  const byId = useMemo(() => new Map(items.map(i => [i.topic.cluster_id, i])), [items]);
  const fit = useMemo(
    () => (size ? fitView(layout, size.w, size.h, legendHeight) : null),
    [layout, size, legendHeight],
  );

  // Titles are measured in the label font, once it has loaded.
  useEffect(() => {
    let live = true;
    document.fonts?.load(LABEL_FONT).finally(() => live && setFontsReady(true));
    return () => {
      live = false;
    };
  }, []);
  const titleFits = useMemo(
    () => new Map(fontsReady ? items.map(i => [i.topic.cluster_id, fitTitle(i.title)] as const) : []),
    [items, fontsReady],
  );

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize(prev => (prev && prev.w === width && prev.h === height ? prev : { w: width, h: height }));
      setLegendHeight(legendRef.current?.offsetHeight ?? 0);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // First view: the saved one for these topics, else the whole map.
  useEffect(() => {
    if (!fit || viewRef.current) return;
    setView(readSavedView(dataKey) ?? fit);
  }, [fit, dataKey]);

  useEffect(() => {
    if (!view) return;
    const id = window.setTimeout(() => saveView(dataKey, view), 250);
    return () => window.clearTimeout(id);
  }, [view, dataKey]);

  const clampK = useCallback(
    (k: number) => (fit ? Math.min(Math.max(k, fit.k * MIN_ZOOM), fit.k * MAX_ZOOM) : k),
    [fit],
  );

  const zoomAt = useCallback(
    (px: number, py: number, factor: number) => {
      setView(v => {
        if (!v) return v;
        const k = clampK(v.k * factor);
        return { k, x: px - ((px - v.x) * k) / v.k, y: py - ((py - v.y) * k) / v.k };
      });
    },
    [clampK],
  );

  const zoomCenter = (factor: number) => size && zoomAt(size.w / 2, size.h / 2, factor);

  // Wheel zoom around the cursor. Not passive, so the page doesn't scroll.
  // On the container: the SVG only mounts once the map has a size.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? rect.height : 1;
      // Trackpad pinches arrive as ctrl+wheel with small deltas.
      const speed = e.ctrlKey ? 0.01 : 0.0016;
      zoomAt(e.clientX - rect.left, e.clientY - rect.top, Math.exp(-e.deltaY * unit * speed));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  // ── Pointer gestures: drag to pan (right button, or left), pinch to zoom,
  //    click or tap a circle to open it.
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ x: number; y: number; view: View; moved: boolean; topic: string | null } | null>(null);
  const pinch = useRef<{ dist: number; mid: { x: number; y: number }; view: View } | null>(null);

  function local(e: ReactPointerEvent) {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function pinchState() {
    const [a, b] = [...pointers.current.values()];
    return { dist: Math.hypot(b.x - a.x, b.y - a.y) || 1, mid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } };
  }

  function onPointerDown(e: ReactPointerEvent<SVGSVGElement>) {
    const v = viewRef.current;
    if (!v || e.button > 2) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, local(e));
    if (pointers.current.size === 2) {
      pinch.current = { ...pinchState(), view: v };
      drag.current = null;
      return;
    }
    const target = e.target instanceof Element ? e.target.closest("[data-topic]") : null;
    drag.current = {
      x: e.clientX,
      y: e.clientY,
      view: v,
      moved: false,
      topic: e.button === 0 ? target?.getAttribute("data-topic") ?? null : null,
    };
  }

  function onPointerMove(e: ReactPointerEvent<SVGSVGElement>) {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, local(e));
    const p = pinch.current;
    if (p && pointers.current.size >= 2) {
      const now = pinchState();
      const k = clampK(p.view.k * (now.dist / p.dist));
      // Keep the map point under the fingers' midpoint under it.
      const wx = (p.mid.x - p.view.x) / p.view.k;
      const wy = (p.mid.y - p.view.y) / p.view.k;
      setView({ k, x: now.mid.x - wx * k, y: now.mid.y - wy * k });
      return;
    }
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) {
      d.moved = true;
      setHovered(null);
      setPinned(false);
    }
    if (d.moved) setView({ ...d.view, x: d.view.x + dx, y: d.view.y + dy });
  }

  function onPointerUp(e: ReactPointerEvent<SVGSVGElement>) {
    pointers.current.delete(e.pointerId);
    if (pinch.current) {
      if (pointers.current.size < 2) pinch.current = null;
      return;
    }
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved || e.type === "pointercancel") return;
    if (!d.topic) {
      setPinned(false);
      setHovered(null);
    } else if (e.pointerType === "mouse" || (pinned && hovered === d.topic)) {
      onOpen(d.topic);
    } else {
      setHovered(d.topic);
      setPinned(true);
    }
  }

  function onKeyDown(e: KeyboardEvent) {
    if (!size) return;
    const step = 80;
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step],
    };
    if (e.key === "+" || e.key === "=") zoomCenter(1.25);
    else if (e.key === "-" || e.key === "_") zoomCenter(0.8);
    else if (e.key === "0" && fit) setView(fit);
    else if (moves[e.key]) setView(v => (v ? { ...v, x: v.x + moves[e.key][0], y: v.y + moves[e.key][1] } : v));
    else if (e.key === "Escape") { setHovered(null); setPinned(false); }
    else return;
    e.preventDefault();
  }

  const toScreen = (x: number, y: number) => (view ? { x: x * view.k + view.x, y: y * view.k + view.y } : { x, y });
  const hoveredItem = hovered ? byId.get(hovered) : undefined;

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden rounded-lg border border-border select-none"
      style={{
        background: "var(--map-bg)",
        backgroundImage: "radial-gradient(var(--map-ring) 1px, transparent 1px)",
        backgroundSize: "22px 22px",
      }}
      onKeyDown={onKeyDown}
    >
      {size && view && (
        <svg
          ref={svgRef}
          width={size.w}
          height={size.h}
          className="block touch-none outline-none"
          style={{ cursor: drag.current?.moved ? "grabbing" : "grab" }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onContextMenu={e => e.preventDefault()}
          role="group"
          aria-label="Map of today's topics. Politics at the center; health, tech and business around it. Use the list view for a text version."
        >
          {/* Axes and the political center, behind the circles. */}
          <MapGuides layout={layout} toScreen={toScreen} k={view.k} />

          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            <Circles items={items} />
          </g>

          {/* Focus targets and the hover ring, in screen space. */}
          {items.map(item => {
            const c = toScreen(item.node.x, item.node.y);
            const r = item.node.r * view.k;
            const active = hovered === item.topic.cluster_id;
            return (
              <circle
                key={item.index}
                cx={c.x}
                cy={c.y}
                r={r + (active ? 3 : 0)}
                data-topic={item.topic.cluster_id}
                tabIndex={0}
                role="link"
                aria-label={`${item.title}. ${outletCount(item.topic)} outlets. Opens the topic.`}
                className="outline-none"
                style={{
                  fill: "transparent",
                  stroke: active ? "var(--foreground)" : "transparent",
                  strokeWidth: 2.5,
                  cursor: "pointer",
                }}
                onPointerEnter={e => e.pointerType === "mouse" && !drag.current?.moved && setHovered(item.topic.cluster_id)}
                onPointerLeave={e => e.pointerType === "mouse" && !pinned && setHovered(h => (h === item.topic.cluster_id ? null : h))}
                onFocus={() => setHovered(item.topic.cluster_id)}
                onBlur={() => setHovered(h => (h === item.topic.cluster_id ? null : h))}
                onKeyDown={e => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpen(item.topic.cluster_id);
                  }
                }}
              />
            );
          })}

          {/* Titles, once the circle can hold the whole title, in the
              fewest lines its current size allows, with the outlets that
              reported it underneath when there's room. */}
          <g pointerEvents="none">
            {items.map(item => {
              const fitInfo = titleFits.get(item.topic.cluster_id);
              const r = item.node.r * view.k;
              if (!fitInfo || r < fitInfo.minRadius) return null;
              const c = toScreen(item.node.x, item.node.y);
              if (c.x + r < 0 || c.y + r < 0 || c.x - r > size.w || c.y - r > size.h) return null;
              const tag = TOPIC_TAGS[item.dominant];
              const label = layoutLabel(fitInfo, [...new Set(item.topic.sources ?? [])], r);
              const halo = { stroke: tag.color, strokeWidth: 3, paintOrder: "stroke" as const, strokeLinejoin: "round" as const };
              return (
                <g key={item.index}>
                  <text x={c.x} textAnchor="middle" dominantBaseline="central" style={{ font: LABEL_FONT, fill: tag.ink, ...halo }}>
                    {label.lines.map((line, i) => (
                      <tspan key={i} x={c.x} y={c.y + line.y}>{line.text}</tspan>
                    ))}
                  </text>
                  {label.note && (
                    <text
                      x={c.x}
                      y={c.y + label.note.y}
                      textAnchor="middle"
                      dominantBaseline="central"
                      style={{ font: NOTE_FONT, fill: tag.ink, fillOpacity: 0.85, ...halo }}
                    >
                      {label.note.text}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      )}

      {hoveredItem && view && size && (
        <MapTooltip
          item={hoveredItem}
          anchor={toScreen(hoveredItem.node.x, hoveredItem.node.y)}
          radius={hoveredItem.node.r * view.k}
          size={size}
          pinned={pinned}
          onOpen={() => onOpen(hoveredItem.topic.cluster_id)}
        />
      )}

      {/* Zoom controls */}
      <div className="absolute top-3 right-3 flex flex-col overflow-hidden rounded-md border border-border bg-card shadow-sm">
        {[
          { label: "Zoom in", icon: <Plus size={18} />, action: () => zoomCenter(1.4) },
          { label: "Zoom out", icon: <Minus size={18} />, action: () => zoomCenter(1 / 1.4) },
          { label: "Fit the whole map", icon: <Maximize2 size={16} />, action: () => fit && setView(fit) },
        ].map(b => (
          <button
            key={b.label}
            type="button"
            onClick={b.action}
            title={b.label}
            aria-label={b.label}
            className="flex h-10 w-10 items-center justify-center text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors border-b border-border last:border-b-0"
          >
            {b.icon}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div
        ref={legendRef}
        className="pointer-events-none absolute bottom-3 left-3 right-16 sm:right-auto sm:max-w-xl rounded-md border border-border bg-card/90 px-3.5 py-2 text-sm text-muted-foreground shadow-sm backdrop-blur-sm"
      >
        <div className="flex flex-wrap gap-x-3.5 gap-y-1">
          {TAG_ORDER.map(t => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <TagSwatch tag={t} size={10} /> {TOPIC_TAGS[t].label}
            </span>
          ))}
        </div>
        <p className="mt-1 leading-snug">
          Bigger: more widely reported. Blended colors: topics spanning genres, like policy
          stories.{" "}
          <span className="pointer-coarse:hidden">Scroll to zoom, drag (or right-drag) to pan.</span>
          <span className="hidden pointer-coarse:inline">Pinch to zoom, drag to pan, tap twice to open.</span>
        </p>
      </div>
    </div>
  );
}

// ─── Guides: political ring, genre axes and labels ──────────────────────────

function MapGuides({
  layout,
  toScreen,
  k,
}: {
  layout: MapLayout;
  toScreen: (x: number, y: number) => { x: number; y: number };
  k: number;
}) {
  const center = toScreen(0, 0);
  const ring = layout.politicsRadius * k;
  // Tag colors pulled toward the text color, so yellow reads on sepia.
  const labelStyle = (tag: TagKey) => ({
    font: "700 13px Alegreya, Georgia, serif",
    letterSpacing: "0.14em",
    fill: `color-mix(in srgb, ${TOPIC_TAGS[tag].color} 70%, var(--foreground))`,
    stroke: "var(--map-bg)",
    strokeWidth: 4,
    paintOrder: "stroke" as const,
  });
  return (
    <g pointerEvents="none">
      <circle cx={center.x} cy={center.y} r={ring} style={{ fill: "var(--map-ring)", stroke: "var(--map-axis)", strokeWidth: 1, strokeDasharray: "2 5" }} />
      {AXIS_GENRES.map(g => {
        const dir = AXIS_DIRECTION[g];
        const end = toScreen(layout.axisLabels[g].x, layout.axisLabels[g].y);
        const start = toScreen(dir.x * layout.politicsRadius, dir.y * layout.politicsRadius);
        // A fixed distance past the genre's farthest circle, extending away
        // from the circles at any zoom.
        const point = toScreen(layout.axisLabels[g].x, layout.axisLabels[g].y);
        const label = { x: point.x + dir.x * 16, y: point.y + dir.y * 16 };
        const anchor = dir.x > 0.3 ? "start" : dir.x < -0.3 ? "end" : "middle";
        return (
          <g key={g}>
            <line x1={start.x} y1={start.y} x2={end.x} y2={end.y} style={{ stroke: "var(--map-axis)", strokeWidth: 1.25, strokeDasharray: "6 6" }} />
            <text x={label.x} y={label.y} textAnchor={anchor} dominantBaseline="central" style={labelStyle(GENRE_TAG[g])}>
              {TOPIC_TAGS[GENRE_TAG[g]].label.toUpperCase()}
            </text>
          </g>
        );
      })}
      <text
        x={center.x}
        y={center.y + ring + 18}
        textAnchor="middle"
        dominantBaseline="central"
        style={{ ...labelStyle("us"), fill: "var(--brand-accent)" }}
      >
        POLITICS
      </text>
    </g>
  );
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────

const TOOLTIP_WIDTH = 320;
const MAX_OUTLETS_LISTED = 14;

function MapTooltip({
  item,
  anchor,
  radius,
  size,
  pinned,
  onOpen,
}: {
  item: MapTopic;
  anchor: { x: number; y: number };
  radius: number;
  size: { w: number; h: number };
  pinned: boolean;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  useLayoutEffect(() => {
    setHeight(ref.current?.offsetHeight ?? 0);
  }, [item]);

  const width = Math.min(TOOLTIP_WIDTH, size.w - 24);
  const left = Math.min(Math.max(anchor.x - width / 2, 12), size.w - width - 12);
  const above = anchor.y - radius - 12 - height;
  const top = above >= 8 ? above : Math.min(anchor.y + radius + 12, size.h - height - 8);
  const outlets = [...new Set(item.topic.sources ?? [])];
  const listed = outlets.slice(0, MAX_OUTLETS_LISTED);

  return (
    <div
      ref={ref}
      role="tooltip"
      className={`absolute z-10 rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-lg ${pinned ? "" : "pointer-events-none"}`}
      style={{ left, top, width, visibility: height ? "visible" : "hidden" }}
    >
      <TopicTags tags={item.tags} />
      <p
        className="mt-2 text-foreground"
        style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.1rem", lineHeight: 1.25 }}
      >
        {item.title}
      </p>
      <p className="mt-2 text-sm text-muted-foreground" style={{ fontFamily: "var(--font-data)" }}>
        {outlets.length} outlet{outlets.length !== 1 ? "s" : ""} · {item.topic.article_count} article
        {item.topic.article_count !== 1 ? "s" : ""}
        {item.topic.in_brief && " · in today's brief"}
      </p>
      <p className="mt-1.5 text-sm leading-snug">
        <span className="font-semibold">Reported by </span>
        {listed.join(", ")}
        {outlets.length > listed.length && ` and ${outlets.length - listed.length} more`}
      </p>
      {pinned ? (
        <button
          type="button"
          onClick={onOpen}
          className="mt-3 inline-flex items-center gap-1.5 rounded bg-primary px-3.5 py-2 text-sm font-semibold text-primary-foreground"
        >
          Open topic <ArrowRight size={15} />
        </button>
      ) : (
        <p className="mt-2 text-xs uppercase tracking-wider text-muted-foreground">Click to open</p>
      )}
    </div>
  );
}

