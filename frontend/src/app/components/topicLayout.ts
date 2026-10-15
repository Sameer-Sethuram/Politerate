import type { Genre, GenreWeights } from "./topicTags";

/**
 * Lays out the Topics map. Political news is the center; health, tech and
 * business are points around it, 120° apart. Each topic is pulled toward
 * its blend of those points (its genre weights: a topic 70% politics and
 * 30% health aims 30% of the way out the health axis), toward the topics
 * whose articles read most like its own (embedding neighbors), and off any
 * circle it overlaps. A fixed number of steps from seeded starting points,
 * so the same topics always get the same map.
 */

export type AxisGenre = Exclude<Genre, "politics">;
export const AXIS_GENRES: AxisGenre[] = ["health", "tech", "business"];

// Health up, tech lower right, business lower left (degrees, y down).
const AXIS_ANGLE: Record<AxisGenre, number> = { health: -90, tech: 30, business: 150 };
export const AXIS_DIRECTION = Object.fromEntries(
  AXIS_GENRES.map(g => [g, { x: Math.cos((AXIS_ANGLE[g] * Math.PI) / 180), y: Math.sin((AXIS_ANGLE[g] * Math.PI) / 180) }]),
) as Record<AxisGenre, { x: number; y: number }>;

export interface LayoutInput {
  id: string;
  r: number;
  weights: GenreWeights;
  // [other topic's id, similarity], most similar first.
  neighbors: Array<[string, number]>;
}

export interface LayoutNode extends LayoutInput {
  x: number;
  y: number;
}

export interface Point { x: number; y: number }

export interface MapLayout {
  nodes: LayoutNode[];
  // Distance from the center to each genre's point.
  axisLength: number;
  // Outer edge of the political cluster, for its ring.
  politicsRadius: number;
  // Where each genre's label goes, just beyond its topics.
  axisLabels: Record<AxisGenre, Point>;
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
}

const TICKS = 360;
const SETTLE_TICKS = 80;
const VELOCITY_DECAY = 0.4;
const ANCHOR_STRENGTH = 0.06;
// Gap kept between circles, in map units.
const COLLIDE_PADDING = 4;
// Neighbor similarity (centered cosine, see topic_map.py) mapped to 0..1:
// at or below the floor a pair is merely related; at the ceiling, near
// duplicates that should sit touching.
const SIM_FLOOR = 0.2;
const SIM_CEIL = 0.7;

// Deterministic per-id numbers in [0, 1).
function hash01(id: string, salt: number): number {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}

/** Point a topic aims for: the weighted blend of the genres' points. */
export function genreTarget(weights: GenreWeights, axisLength: number): Point {
  let x = 0, y = 0;
  for (const g of AXIS_GENRES) {
    x += weights[g] * AXIS_DIRECTION[g].x * axisLength;
    y += weights[g] * AXIS_DIRECTION[g].y * axisLength;
  }
  return { x, y };
}

/** Direction from the center toward a topic's genres, or null for a purely
 *  political one. Orients its circle's color gradient. */
export function genreDirection(weights: GenreWeights): Point | null {
  const t = genreTarget(weights, 1);
  const len = Math.hypot(t.x, t.y);
  return len < 0.02 ? null : { x: t.x / len, y: t.y / len };
}

export function layoutTopics(inputs: LayoutInput[]): MapLayout {
  // Room for each region's circles, packed at about 80% density.
  const packedRadius = (area: number) => Math.sqrt(area / 0.8);
  const politicsArea = inputs.reduce((sum, n) => sum + n.r * n.r * n.weights.politics, 0);
  const centerRadius = packedRadius(politicsArea);
  const genreRadius = Math.max(
    0,
    ...AXIS_GENRES.map(g => packedRadius(inputs.reduce((sum, n) => sum + n.r * n.r * n.weights[g], 0))),
  );
  // Far enough out that the policy zone (halfway) clears the political
  // cluster and each genre's cluster clears it too.
  const axisLength = Math.max(380, 2 * centerRadius + 140, centerRadius + genreRadius + 160);

  const index = new Map(inputs.map((n, i) => [n.id, i]));
  const targets = inputs.map(n => genreTarget(n.weights, axisLength));

  // Seeded start: around each target, spread over its region's size.
  const xs = new Float64Array(inputs.length);
  const ys = new Float64Array(inputs.length);
  const vx = new Float64Array(inputs.length);
  const vy = new Float64Array(inputs.length);
  inputs.forEach((n, i) => {
    const angle = hash01(n.id, 1) * Math.PI * 2;
    const dist = Math.sqrt(hash01(n.id, 2)) * Math.max(centerRadius, n.r * 2);
    xs[i] = targets[i].x + Math.cos(angle) * dist;
    ys[i] = targets[i].y + Math.sin(angle) * dist;
  });

  // One spring per neighbor pair, at the pair's higher similarity.
  const springs = new Map<string, { a: number; b: number; s: number }>();
  inputs.forEach((n, a) => {
    for (const [otherId, sim] of n.neighbors) {
      const b = index.get(otherId);
      if (b == null || b === a) continue;
      const key = a < b ? `${a}:${b}` : `${b}:${a}`;
      const s = Math.min(1, Math.max(0, (sim - SIM_FLOOR) / (SIM_CEIL - SIM_FLOOR)));
      const prev = springs.get(key);
      if (!prev || prev.s < s) springs.set(key, { a: Math.min(a, b), b: Math.max(a, b), s });
    }
  });

  const collide = (strength: number) => {
    for (let i = 0; i < inputs.length; i++) {
      for (let j = i + 1; j < inputs.length; j++) {
        const dx = xs[j] - xs[i];
        const dy = ys[j] - ys[i];
        const min = inputs[i].r + inputs[j].r + COLLIDE_PADDING;
        const d2 = dx * dx + dy * dy;
        if (d2 >= min * min) continue;
        const d = Math.sqrt(d2) || 0.01;
        const push = ((min - d) / d) * strength;
        // Smaller circles give way to bigger ones.
        const wi = inputs[j].r ** 2 / (inputs[i].r ** 2 + inputs[j].r ** 2);
        xs[i] -= dx * push * wi;
        ys[i] -= dy * push * wi;
        xs[j] += dx * push * (1 - wi);
        ys[j] += dy * push * (1 - wi);
      }
    }
  };

  let alpha = 1;
  const alphaDecay = 1 - Math.pow(0.001, 1 / TICKS);
  for (let tick = 0; tick < TICKS; tick++) {
    for (let i = 0; i < inputs.length; i++) {
      vx[i] += (targets[i].x - xs[i]) * ANCHOR_STRENGTH * alpha;
      vy[i] += (targets[i].y - ys[i]) * ANCHOR_STRENGTH * alpha;
    }
    for (const { a, b, s } of springs.values()) {
      const dx = xs[b] - xs[a];
      const dy = ys[b] - ys[a];
      const d = Math.hypot(dx, dy) || 0.01;
      // Near duplicates rest touching; loosely related pairs further apart.
      const rest = (inputs[a].r + inputs[b].r + COLLIDE_PADDING) * (1 + (1 - s) * 0.9);
      const k = ((d - rest) / d) * (0.015 + 0.07 * s) * alpha * 0.5;
      vx[a] += dx * k; vy[a] += dy * k;
      vx[b] -= dx * k; vy[b] -= dy * k;
    }
    for (let i = 0; i < inputs.length; i++) {
      vx[i] *= 1 - VELOCITY_DECAY;
      vy[i] *= 1 - VELOCITY_DECAY;
      xs[i] += vx[i];
      ys[i] += vy[i];
    }
    collide(0.7);
    alpha -= alpha * alphaDecay;
  }
  for (let tick = 0; tick < SETTLE_TICKS; tick++) collide(1);

  const nodes: LayoutNode[] = inputs.map((n, i) => ({ ...n, x: xs[i], y: ys[i] }));

  const politicsRadius = Math.max(
    centerRadius * 0.6,
    ...nodes.filter(n => n.weights.politics >= 0.6).map(n => Math.hypot(n.x, n.y) + n.r),
  ) + 14;

  const axisLabels = Object.fromEntries(
    AXIS_GENRES.map(g => {
      const dir = AXIS_DIRECTION[g];
      // Beyond the farthest of its topics along the axis.
      const reach = Math.max(
        axisLength,
        ...nodes.filter(n => n.weights[g] >= 0.4).map(n => n.x * dir.x + n.y * dir.y + n.r),
      ) + 12;
      return [g, { x: dir.x * reach, y: dir.y * reach }];
    }),
  ) as Record<AxisGenre, Point>;

  const pts = [
    ...nodes.map(n => [n.x - n.r, n.y - n.r, n.x + n.r, n.y + n.r]),
    ...Object.values(axisLabels).map(p => [p.x, p.y, p.x, p.y]),
    [-politicsRadius, -politicsRadius, politicsRadius, politicsRadius + 18],
  ];
  const bounds = {
    minX: Math.min(...pts.map(p => p[0])),
    minY: Math.min(...pts.map(p => p[1])),
    maxX: Math.max(...pts.map(p => p[2])),
    maxY: Math.max(...pts.map(p => p[3])),
  };

  return { nodes, axisLength, politicsRadius, axisLabels, bounds };
}
