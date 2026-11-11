/**
 * Géométrie statique du bureau isométrique.
 * Les positions sont exprimées dans le repère du SVG (1040 × 760).
 */

export const SCENE = { width: 1040, height: 760 };

const ORIGIN = { x: 520, y: 210 };
const TILE = { w: 42, h: 21 };

export function iso(u, v) {
  return { x: ORIGIN.x + (u - v) * TILE.w, y: ORIGIN.y + (u + v) * TILE.h };
}

export function pointsAttr(points) {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

export const FLOOR = {
  top: iso(0, 0),
  right: iso(10, 0),
  bottom: iso(10, 10),
  left: iso(0, 10),
  points: [iso(0, 0), iso(10, 0), iso(10, 10), iso(0, 10)].map((p) => [p.x, p.y]),
};

export const WALLS = {
  left: [[100, 230], [520, 20], [520, 210], [100, 420]],
  right: [[520, 20], [940, 230], [940, 420], [520, 210]],
  floor: FLOOR.points,
};

export const WINDOW = {
  frame: [[130, 250], [495, 70], [495, 186], [130, 366]],
  sky: [[138, 258], [487, 78], [487, 132], [138, 312]],
  stands: [[138, 300], [487, 120], [487, 152], [138, 332]],
  field: [[138, 324], [487, 144], [487, 186], [138, 366]],
};

/**
 * Postes de travail. `x` / `y` correspondent au pied du bureau ; le
 * personnage se tient légèrement à droite, face au poste.
 */
export const DESKS = {
  manager: { x: 500, y: 315, color: "#8b5cf6" },
  qa_analyst: { x: 287, y: 335, color: "#3b82f6" },
  test_designer: { x: 427, y: 385, color: "#60a5fa" },
  api_tester: { x: 255, y: 465, color: "#22c55e" },
  api_automation: { x: 370, y: 505, color: "#4ade80" },
  ui_automation: { x: 512, y: 535, color: "#ec4899" },
  devops: { x: 690, y: 340, color: "#f59e0b" },
  qa_reporter: { x: 700, y: 460, color: "#06b6d4" },
};

export const HOME_OFFSET = { x: 28, y: 20 };

export function homeOf(agentId) {
  const desk = DESKS[agentId] || DESKS.manager;
  return { x: desk.x + HOME_OFFSET.x, y: desk.y + HOME_OFFSET.y };
}

/**
 * Zones de département : de simples tapis colorés au sol. Les libellés
 * sont affichés dans une légende HTML, jamais dans la scène, afin de ne
 * jamais être masqués par un meuble ou un personnage.
 */
export const ZONES = [
  {
    id: "direction",
    label: "Direction",
    color: "#8b5cf6",
    points: [[528, 272], [640, 330], [528, 388], [416, 330]],
  },
  {
    id: "analysis",
    label: "Analyse & Conception",
    color: "#3b82f6",
    points: [[480, 415], [310, 330], [250, 385], [420, 470]],
  },
  {
    id: "api",
    label: "Tests API",
    color: "#22c55e",
    points: [[270, 430], [420, 505], [350, 540], [200, 477]],
  },
  {
    id: "ui",
    label: "Automatisation UI",
    color: "#ec4899",
    points: [[505, 485], [605, 535], [505, 585], [405, 535]],
  },
  {
    id: "infra",
    label: "Infrastructure",
    color: "#f59e0b",
    points: [[700, 320], [810, 375], [740, 415], [630, 360]],
  },
  {
    id: "reporting",
    label: "Reporting",
    color: "#06b6d4",
    points: [[790, 480], [690, 430], [610, 470], [710, 520]],
  },
];

export const DECOR = [
  { type: "plant", x: 150, y: 350, scale: 0.95 },
  { type: "plant", x: 858, y: 330, scale: 0.9 },
  { type: "plant", x: 148, y: 434, scale: 0.78 },
  { type: "plant", x: 812, y: 448, scale: 0.82 },
  { type: "plant", x: 592, y: 606, scale: 0.8 },
  { type: "plant", x: 362, y: 300, scale: 0.72 },
  { type: "server", x: 842, y: 382, scale: 0.82 },
  { type: "sofa", x: 596, y: 442, scale: 0.74 },
  { type: "table", x: 622, y: 470, scale: 0.68 },
  { type: "ball", x: 640, y: 482, scale: 0.78 },
  { type: "cooler", x: 462, y: 398, scale: 0.74 },
];
