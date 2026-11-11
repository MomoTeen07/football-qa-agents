import {
  DECOR,
  DESKS,
  FLOOR,
  HOME_OFFSET,
  SCENE,
  WALLS,
  WINDOW,
  ZONES,
  homeOf,
  iso,
  pointsAttr,
} from "./layout.js";
import { spriteMarkup } from "./sprites.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function rect(x, y, width, height, fill, extra = "") {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="${fill}" ${extra}/>`;
}

function line(x1, y1, x2, y2, stroke, width = 1, extra = "") {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}" ${extra}/>`;
}

/* ------------------------------------------------------------------ */
/* Décor statique                                                      */
/* ------------------------------------------------------------------ */
function defsMarkup() {
  return `
    <defs>
      <radialGradient id="bgGlow" cx="50%" cy="28%" r="72%">
        <stop offset="0%" stop-color="#1a2a49"/>
        <stop offset="48%" stop-color="#0d1729"/>
        <stop offset="100%" stop-color="#050a13"/>
      </radialGradient>
      <linearGradient id="wallLeft" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#16243d"/>
        <stop offset="100%" stop-color="#0f1a2d"/>
      </linearGradient>
      <linearGradient id="wallRight" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#101c30"/>
        <stop offset="100%" stop-color="#0b1526"/>
      </linearGradient>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#071226"/>
        <stop offset="100%" stop-color="#10233f"/>
      </linearGradient>
      <linearGradient id="field" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#1d6b46"/>
        <stop offset="100%" stop-color="#278a58"/>
      </linearGradient>
      <linearGradient id="sign" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#14263f"/>
        <stop offset="100%" stop-color="#0c1a2e"/>
      </linearGradient>
      <linearGradient id="screenGlow" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#0c2233"/>
        <stop offset="100%" stop-color="#071522"/>
      </linearGradient>
    </defs>`;
}

function floorMarkup() {
  let tiles = "";
  for (let u = 0; u < 10; u += 1) {
    for (let v = 0; v < 10; v += 1) {
      const p = [iso(u, v), iso(u + 1, v), iso(u + 1, v + 1), iso(u, v + 1)];
      const fill = (u + v) % 2 === 0 ? "#19263f" : "#1b2944";
      tiles += `<polygon points="${pointsAttr(p.map((item) => [item.x, item.y]))}" fill="${fill}" opacity=".92"/>`;
    }
  }

  let grid = "";
  for (let i = 0; i <= 10; i += 1) {
    const a = iso(i, 0);
    const b = iso(i, 10);
    const c = iso(0, i);
    const d = iso(10, i);
    grid += line(a.x, a.y, b.x, b.y, "#263654", 1, 'class="floor-grid"');
    grid += line(c.x, c.y, d.x, d.y, "#263654", 1, 'class="floor-grid"');
  }

  return `
    <polygon points="${pointsAttr(WALLS.floor)}" fill="#0a1322" opacity=".95"/>
    ${tiles}
    ${grid}
    <polygon points="${pointsAttr(WALLS.floor)}" fill="none" stroke="#38527d" stroke-width="2.5"/>
    <polygon points="520,266 638,325 520,384 402,325" fill="#8b5cf6" opacity=".06"/>
    <polygon points="520,266 638,325 520,384 402,325" fill="none" stroke="#8b5cf6" stroke-width="1.2" opacity=".22"/>
  `;
}

function zoneMarkup(zone) {
  const [p0, p1, , p3] = zone.points;
  const height = zone.id === "direction" ? 46 : 26;
  const glass = `
    <polygon points="${p0[0]},${p0[1]} ${p1[0]},${p1[1]} ${p1[0]},${p1[1] - height} ${p0[0]},${p0[1] - height}"
      fill="rgba(104, 164, 255, .035)" stroke="rgba(126, 184, 255, .16)" stroke-width="1"/>
    <polygon points="${p0[0]},${p0[1]} ${p3[0]},${p3[1]} ${p3[0]},${p3[1] - height} ${p0[0]},${p0[1] - height}"
      fill="rgba(104, 164, 255, .025)" stroke="rgba(126, 184, 255, .12)" stroke-width="1"/>`;
  return `
    <g data-zone="${zone.id}">
      <polygon points="${pointsAttr(zone.points)}" fill="${zone.color}" opacity=".09"/>
      <polygon points="${pointsAttr(zone.points)}" fill="none" stroke="${zone.color}" stroke-width="1.3" opacity=".42"/>
      ${glass}
    </g>`;
}

function windowMarkup() {
  let stars = "";
  for (let i = 0; i < 26; i += 1) {
    const t = (i * 37) % 100;
    const x = 150 + t * 3.2;
    const y = 250 - t * 1.62 - (i % 4) * 4;
    stars += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${i % 5 === 0 ? 1.4 : 0.9}" fill="#cfe3ff" opacity=".55"/>`;
  }

  let crowd = "";
  const crowdColors = ["#f59e0b", "#ef4444", "#3b82f6", "#e2e8f0", "#22c55e"];
  for (let i = 0; i < 58; i += 1) {
    const t = i / 57;
    const x = 142 + t * 340;
    const y = 300 - t * 176 + (i % 3) * 4;
    crowd += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="3.2" height="3.2" fill="${crowdColors[i % crowdColors.length]}" opacity=".82"/>`;
    if (i % 2 === 0) {
      crowd += `<rect x="${(x + 5).toFixed(1)}" y="${(y + 4).toFixed(1)}" width="2.4" height="2.4" fill="${crowdColors[(i + 2) % crowdColors.length]}" opacity=".55"/>`;
    }
  }

  let fieldStripes = "";
  const steps = 6;
  for (let i = 0; i < steps; i += 1) {
    const t0 = i / steps;
    const t1 = (i + 1) / steps;
    const x1 = 138 + t0 * 349;
    const y1 = 324 - t0 * 180;
    const x2 = 138 + t1 * 349;
    const y2 = 324 - t1 * 180;
    if (i % 2 === 0) {
      fieldStripes += `<polygon points="${x1},${y1} ${x2},${y2} ${x2},${y2 + 42} ${x1},${y1 + 42}" fill="#2f9b63" opacity=".55"/>`;
    }
    fieldStripes += line(x1, y1, x1, y1 + 42, "#d7f7e5", 1, 'opacity=".35"');
  }

  return `
    <g aria-hidden="true">
      <polygon points="${pointsAttr(WINDOW.frame)}" fill="#0a1528" stroke="#3b4d70" stroke-width="3"/>
      <polygon points="${pointsAttr(WINDOW.sky)}" fill="url(#sky)"/>
      ${stars}
      <polygon points="${pointsAttr(WINDOW.stands)}" fill="#182741"/>
      ${crowd}
      <polygon points="${pointsAttr(WINDOW.field)}" fill="url(#field)"/>
      ${fieldStripes}
      <polygon points="138,346 487,166 487,186 138,366" fill="#071426" opacity=".45"/>
      <polygon points="150,300 300,223 330,239 180,316" fill="#bfe6ff" opacity=".035"/>
      <polygon points="${pointsAttr(WINDOW.frame)}" fill="none" stroke="#4a628c" stroke-width="2"/>
      <line x1="312" y1="192" x2="312" y2="366" stroke="#2a3d60" stroke-width="2"/>
      <line x1="138" y1="300" x2="487" y2="120" stroke="#2a3d60" stroke-width="2"/>
    </g>`;
}

function wallMarkup() {
  return `
    <g aria-hidden="true">
      <polygon points="${pointsAttr(WALLS.left)}" fill="url(#wallLeft)" stroke="#2a3d60" stroke-width="2"/>
      <polygon points="${pointsAttr(WALLS.right)}" fill="url(#wallRight)" stroke="#2a3d60" stroke-width="2"/>
      ${[0, 1, 2, 3].map((i) => {
        const y = 120 + i * 62;
        return line(100, y, 520, y - 210, "#1c2c48", 1, 'opacity=".5"');
      }).join("")}
      ${[0, 1, 2, 3].map((i) => {
        const y = 120 + i * 62;
        return line(520, y - 210, 940, y, "#182640", 1, 'opacity=".45"');
      }).join("")}
      ${line(520, 20, 520, 210, "#2a3d60", 2)}
      <rect x="486" y="24" width="68" height="7" rx="3" fill="#1d2c47" stroke="#2a3d60"/>
      <rect x="500" y="14" width="40" height="12" rx="3" fill="#24375a" stroke="#3b537d"/>
      ${windowMarkup()}
      ${signMarkup()}
      ${trophyMarkup()}
      ${whiteboardMarkup()}
    </g>`;
}

function signMarkup() {
  return `
    <g transform="translate(742,176) rotate(26.565)" aria-hidden="true">
      <rect x="-112" y="-38" width="224" height="76" rx="8" fill="url(#sign)" stroke="#31527f" stroke-width="2"/>
      <rect x="-104" y="-30" width="208" height="60" rx="5" fill="none" stroke="#1f3a5d" stroke-width="1"/>
      <circle cx="-78" cy="0" r="18" fill="#f8fafc" stroke="#0a1220" stroke-width="2"/>
      <path d="M-78 -11l7 5-2.5 8.5h-9L-85 -6z" fill="#122033"/>
      <path d="M-94 0h6M-68 0h6M-78 12v-6M-85 -6l-5-5M-71 -6l5-5" stroke="#122033" stroke-width="2"/>
      <text x="-50" y="-6" fill="#e8f1ff" font-size="21" font-weight="800" letter-spacing="1.2">FOOTBALL</text>
      <text x="-50" y="18" fill="#7ee2a8" font-size="16" font-weight="800" letter-spacing="3.4">QA AGENTS</text>
      <text x="-50" y="31" fill="#6f8cb5" font-size="6.4" letter-spacing="2.2">QUARTIER GÉNÉRAL · TEMPS RÉEL</text>
    </g>`;
}

function trophyMarkup() {
  const cups = [-42, -14, 14, 42];
  return `
    <g transform="translate(610,232) rotate(26.565)" aria-hidden="true">
      <rect x="-62" y="0" width="124" height="6" rx="2" fill="#2a3d60" stroke="#0a1220"/>
      ${cups.map((x, i) => `
        <g transform="translate(${x},-14)">
          <path d="M-7 -8h14v6c0 5-3 8-7 8s-7-3-7-8z" fill="${i === 0 ? "#fcd34d" : "#c8a250"}" stroke="#0a1220" stroke-width="1.2"/>
          <rect x="-2" y="6" width="4" height="5" fill="#c8a250"/>
          <rect x="-6" y="11" width="12" height="3" rx="1" fill="#8f6f2e"/>
        </g>`).join("")}
      <text x="0" y="-28" text-anchor="middle" fill="#6f8cb5" font-size="6.5" letter-spacing="1.8">TROPHÉES QA</text>
    </g>`;
}

function whiteboardMarkup() {
  return `
    <g transform="translate(812,290) rotate(26.565)" aria-hidden="true">
      <rect x="-74" y="-48" width="148" height="92" rx="5" fill="#0c1a2c" stroke="#3b537d" stroke-width="2"/>
      <rect x="-68" y="-42" width="136" height="80" rx="3" fill="#0a1728"/>
      <text x="-60" y="-26" fill="#7ee2a8" font-size="8" font-weight="800" letter-spacing="1.6">QA LIVE</text>
      <text x="-60" y="-7" fill="#e8f1ff" font-size="18" font-weight="800">59 / 59</text>
      <text x="-60" y="7" fill="#9fb4d8" font-size="6.5" letter-spacing="1.2">RÉSULTATS ALLURE 2</text>
      <rect x="-60" y="15" width="88" height="5" rx="2.5" fill="#16233c"/>
      <rect x="-60" y="15" width="88" height="5" rx="2.5" fill="#22c55e"/>
      <text x="-60" y="31" fill="#7ee2a8" font-size="6.5">0 anomalie · 0 échec</text>
      <circle cx="52" cy="-14" r="12" fill="none" stroke="#22c55e" stroke-width="5" stroke-dasharray="66 10" transform="rotate(-90 52 -14)"/>
      <text x="52" y="-11" text-anchor="middle" fill="#c9f7dd" font-size="7" font-weight="800">100%</text>
    </g>`;
}

function plantMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="4" rx="16" ry="6" fill="#03070f" opacity=".4"/>
      <path d="M-11 0h22l-3 20h-16z" fill="#9a5a2e" stroke="#0a1220" stroke-width="2"/>
      <rect x="-12" y="-3" width="24" height="6" rx="2" fill="#b96c36" stroke="#0a1220" stroke-width="2"/>
      <rect x="-2" y="-28" width="4" height="27" fill="#237a49"/>
      <path d="M0 -22c-12 -3 -17 -12 -15 -19 8 0 14 6 15 14z" fill="#2f9e5f" stroke="#0a1220" stroke-width="1.5"/>
      <path d="M2 -30c11 -4 16 -13 13 -20 -8 0 -13 7 -13 15z" fill="#3cb371" stroke="#0a1220" stroke-width="1.5"/>
      <path d="M0 -13c-9 0 -14 -6 -14 -11 7 -1 12 3 14 8z" fill="#268a51" stroke="#0a1220" stroke-width="1.5"/>
      <path d="M2 -18c9 1 13 -4 14 -9 -7 -2 -12 2 -14 7z" fill="#34a866" stroke="#0a1220" stroke-width="1.5"/>
    </g>`;
}

function serverMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="6" rx="30" ry="10" fill="#03070f" opacity=".4"/>
      <polygon points="-26,-6 12,-26 40,-12 -2,8" fill="#243451" stroke="#0a1220" stroke-width="2"/>
      <polygon points="-26,-6 -2,8 -2,54 -26,40" fill="#16243a" stroke="#0a1220" stroke-width="2"/>
      <polygon points="-2,8 40,-12 40,34 -2,54" fill="#1b2b45" stroke="#0a1220" stroke-width="2"/>
      ${[14, 24, 34, 44].map((yy, i) => `<rect x="0" y="${yy}" width="30" height="5" rx="1" fill="#0c1628" stroke="#0a1220"/>`).join("")}
      ${[17, 27, 37, 47].map((yy, i) => `<rect class="led" x="3" y="${yy}" width="3" height="3" fill="${i % 2 ? "#22c55e" : "#f59e0b"}"/>`).join("")}
      <text x="18" y="26" fill="#6f8cb5" font-size="4.5" letter-spacing=".8">QA-STACK</text>
    </g>`;
}

function sofaMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="10" rx="48" ry="15" fill="#03070f" opacity=".4"/>
      <polygon points="-48,-2 -10,-22 40,-2 2,18" fill="#bf6a1f" stroke="#0a1220" stroke-width="2"/>
      <polygon points="-48,-2 2,18 2,32 -48,12" fill="#a85817" stroke="#0a1220" stroke-width="2"/>
      <polygon points="2,18 40,-2 40,12 2,32" fill="#8f4a13" stroke="#0a1220" stroke-width="2"/>
      <polygon points="-42,-6 -12,-20 28,-6 0,8" fill="#f0a34a" opacity=".55"/>
      <rect x="-36" y="-24" width="20" height="12" rx="3" fill="#e19a45" stroke="#0a1220" stroke-width="1.5"/>
      <rect x="4" y="-18" width="20" height="12" rx="3" fill="#e19a45" stroke="#0a1220" stroke-width="1.5"/>
    </g>`;
}

function tableMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="4" rx="26" ry="9" fill="#03070f" opacity=".4"/>
      <polygon points="0,-12 26,0 0,12 -26,0" fill="#b98a55" stroke="#0a1220" stroke-width="2"/>
      <polygon points="-26,0 0,12 0,17 -26,5" fill="#8a6038" stroke="#0a1220" stroke-width="1.5"/>
      <polygon points="26,0 0,12 0,17 26,5" fill="#714b2b" stroke="#0a1220" stroke-width="1.5"/>
    </g>`;
}

function ballMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="4" rx="9" ry="3" fill="#03070f" opacity=".4"/>
      <circle cx="0" cy="-4" r="9" fill="#f8fafc" stroke="#0a1220" stroke-width="2"/>
      <path d="M0 -12l4 3-1.5 5h-5L-4 -9z" fill="#122033"/>
      <path d="M-9 -4h4M5 -4h4M0 5v-3" stroke="#122033" stroke-width="1.4"/>
    </g>`;
}

function coolerMarkup(x, y, scale) {
  return `
    <g transform="translate(${x},${y}) scale(${scale})" aria-hidden="true">
      <ellipse cx="0" cy="6" rx="14" ry="5" fill="#03070f" opacity=".4"/>
      <rect x="-9" y="-22" width="18" height="30" rx="4" fill="#dbeafe" stroke="#0a1220" stroke-width="2"/>
      <rect x="-4" y="-28" width="8" height="8" rx="2" fill="#60a5fa" stroke="#0a1220" stroke-width="1.5"/>
      <rect x="-6" y="-18" width="12" height="14" rx="2" fill="#93c5fd" opacity=".8"/>
      <rect x="2" y="-8" width="8" height="3" fill="#334155"/>
    </g>`;
}

function decorMarkup(item) {
  if (item.type === "plant") return plantMarkup(item.x, item.y, item.scale);
  if (item.type === "server") return serverMarkup(item.x, item.y, item.scale);
  if (item.type === "sofa") return sofaMarkup(item.x, item.y, item.scale);
  if (item.type === "table") return tableMarkup(item.x, item.y, item.scale);
  if (item.type === "ball") return ballMarkup(item.x, item.y, item.scale);
  if (item.type === "cooler") return coolerMarkup(item.x, item.y, item.scale);
  return "";
}

/* ------------------------------------------------------------------ */
/* Postes de travail                                                   */
/* ------------------------------------------------------------------ */
function deskMarkup(agentId, desk) {
  const { x, y, color } = desk;
  return `
    <g transform="translate(${x},${y}) scale(.88)" data-desk="${agentId}" aria-hidden="true">
      <ellipse class="desk-shadow" cx="0" cy="30" rx="68" ry="24"/>
      <polygon class="desk-top" points="0,-27 56,0 0,27 -56,0" fill="#2c3f63"/>
      <polygon points="-56,0 0,27 0,42 -56,15" fill="#1b2a44" stroke="#0a1220" stroke-width="1.5"/>
      <polygon points="56,0 0,27 0,42 56,15" fill="#16233a" stroke="#0a1220" stroke-width="1.5"/>
      <polygon points="0,-27 56,0 0,4 -56,-23" fill="#3a5079" opacity=".55"/>

      <g transform="translate(0,-2)">
        <rect class="monitor-frame" x="-27" y="-44" width="54" height="34" rx="4"/>
        <rect class="monitor-screen" x="-22" y="-39" width="44" height="24" rx="2"/>
        <rect class="monitor-line" x="-17" y="-33" width="20" height="2" fill="${color}"/>
        <rect class="monitor-line" x="-17" y="-28" width="30" height="2" fill="#4a7fb8"/>
        <rect class="monitor-line" x="-17" y="-23" width="14" height="2" fill="#22c55e"/>
        <rect class="monitor-stand" x="-4" y="-10" width="8" height="8"/>
        <rect class="monitor-stand" x="-12" y="-3" width="24" height="4" rx="1"/>
      </g>

      <polygon points="-20,12 0,22 18,12 0,4" fill="#0f1b2e" stroke="#0a1220" stroke-width="1.5"/>
      <g transform="translate(-38,0) scale(.5)">${plantMarkup(0, 0, .7)}</g>
    </g>`;
}

/* ------------------------------------------------------------------ */
/* Personnages                                                         */
/* ------------------------------------------------------------------ */
function characterMarkup(agent, home) {
  const labelWidth = Math.max(58, Math.max(agent.name.length, agent.role.length) * 5.2 + 12);
  return `
    <g class="agent" data-agent="${agent.id}" data-status="${agent.status || "idle"}"
       transform="translate(${home.x},${home.y})" tabindex="0" role="button"
       aria-label="${agent.name}, ${agent.role}, ${agent.status_label || "Disponible"}">
      <rect class="hit" x="-30" y="-86" width="60" height="112"/>
      <g class="selection-ring" transform="translate(0,2)">
        <ellipse cx="0" cy="0" rx="27" ry="10"/>
      </g>
      <g class="sprite" transform="scale(.92)">${spriteMarkup(agent.sprite || {})}</g>
      <g class="nameplate" transform="translate(0,13)">
        <rect x="${-labelWidth / 2}" y="0" width="${labelWidth}" height="23" rx="5" stroke="${agent.color || "#64748b"}"/>
        <text class="name" x="0" y="9.5" text-anchor="middle">${agent.name}</text>
        <text class="role" x="0" y="18.5" text-anchor="middle">${agent.role}</text>
      </g>
      <g class="status-light" transform="translate(0,-80)">
        <circle class="light-halo" r="12" fill="#64748b"/>
        <circle class="light-ring" r="8" stroke="#64748b"/>
        <circle class="light-core" r="4.5" fill="#64748b"/>
      </g>
    </g>`;
}

/* ------------------------------------------------------------------ */
/* API publique                                                        */
/* ------------------------------------------------------------------ */
export function createScene(svg, agents) {
  svg.innerHTML = `
    ${defsMarkup()}
    <rect x="0" y="0" width="${SCENE.width}" height="${SCENE.height}" fill="url(#bgGlow)"/>
    ${wallMarkup()}
    ${floorMarkup()}
    ${ZONES.map(zoneMarkup).join("")}
    ${DECOR.map(decorMarkup).join("")}
    ${Object.entries(DESKS)
      .sort((a, b) => a[1].y - b[1].y)
      .map(([id, desk]) => deskMarkup(id, desk))
      .join("")}
    <g class="character-layer"></g>
  `;

  const characterLayer = svg.querySelector(".character-layer");
  const nodes = new Map();
  const agentData = new Map();

  for (const agent of agents) {
    const wrapper = document.createElementNS(SVG_NS, "svg");
    wrapper.innerHTML = characterMarkup(agent, homeOf(agent.id)).trim();
    const node = wrapper.firstElementChild;
    node.__x = homeOf(agent.id).x;
    node.__y = homeOf(agent.id).y;
    node.__status = agent.status || "idle";
    node.__token = 0;
    node.addEventListener("click", () => {
      node.dispatchEvent(new CustomEvent("agent-select", {
        bubbles: true,
        detail: { agentId: agent.id },
      }));
    });
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        node.dispatchEvent(new CustomEvent("agent-select", {
          bubbles: true,
          detail: { agentId: agent.id },
        }));
      }
    });
    characterLayer.append(node);
    nodes.set(agent.id, node);
    agentData.set(agent.id, agent);
  }

  function sortAgents() {
    const ordered = [...characterLayer.children].sort(
      (a, b) => (a.__y || 0) - (b.__y || 0),
    );
    for (const node of ordered) characterLayer.append(node);
  }

  function applyStatus(agentId) {
    const node = nodes.get(agentId);
    if (!node) return;
    const status = node.__status || "idle";
    node.dataset.status = status;
    node.classList.toggle("is-working", status === "working");
  }

  function setAgents(nextAgents) {
    for (const agent of nextAgents) {
      const node = nodes.get(agent.id);
      if (!node) continue;
      agentData.set(agent.id, agent);
      node.__status = agent.status || "idle";
      if (!node.classList.contains("is-walking")) applyStatus(agent.id);
      node.setAttribute(
        "aria-label",
        `${agent.name}, ${agent.role}, ${agent.status_label || "Disponible"}`,
      );
      node.classList.toggle("is-selected", selectedAgent === agent.id);
      const badge = node.querySelector(".nameplate rect");
      if (badge) badge.setAttribute("stroke", agent.color || "#64748b");
    }
  }

  function moveTo(agentId, target, duration = 900) {
    const node = nodes.get(agentId);
    if (!node) return Promise.resolve();
    const token = (node.__token || 0) + 1;
    node.__token = token;
    const from = { x: node.__x || 0, y: node.__y || 0 };
    const to = { x: target.x, y: target.y };
    const start = performance.now();
    node.classList.add("is-walking");
    node.dataset.status = "moving";
    sortAgents();

    return new Promise((resolve) => {
      let lastSort = -1;
      function frame(now) {
        if (node.__token !== token) {
          resolve();
          return;
        }
        const elapsed = Math.min(1, (now - start) / Math.max(1, duration));
        const eased = elapsed < 0.5
          ? 2 * elapsed * elapsed
          : 1 - Math.pow(-2 * elapsed + 2, 2) / 2;
        node.__x = from.x + (to.x - from.x) * eased;
        node.__y = from.y + (to.y - from.y) * eased;
        node.setAttribute("transform", `translate(${node.__x},${node.__y})`);
        const step = Math.floor(elapsed * 8);
        if (step !== lastSort) {
          lastSort = step;
          sortAgents();
        }
        if (elapsed < 1) {
          requestAnimationFrame(frame);
        } else {
          node.classList.remove("is-walking");
          node.__x = to.x;
          node.__y = to.y;
          applyStatus(agentId);
          sortAgents();
          resolve();
        }
      }
      requestAnimationFrame(frame);
    });
  }

  function walkHome(agentId, duration = 800) {
    return moveTo(agentId, homeOf(agentId), duration);
  }

  async function handoff(fromId, toId) {
    if (!nodes.has(fromId) || !nodes.has(toId) || fromId === toId) return;
    const home = homeOf(toId);
    const fromHome = homeOf(fromId);
    const side = fromHome.x <= home.x ? -1 : 1;
    const meeting = { x: home.x + side * 34, y: home.y + 3 };
    await moveTo(fromId, meeting, 950);
    await new Promise((resolve) => setTimeout(resolve, 1250));
    await walkHome(fromId, 950);
  }

  function getPosition(agentId) {
    const node = nodes.get(agentId);
    if (!node) return { x: 0, y: 0 };
    return { x: node.__x || 0, y: node.__y || 0 };
  }

  let selectedAgent = null;
  function select(agentId) {
    selectedAgent = agentId;
    for (const [id, node] of nodes) {
      node.classList.toggle("is-selected", id === agentId);
    }
  }

  sortAgents();
  setAgents(agents);

  return {
    setAgents,
    moveTo,
    walkHome,
    handoff,
    getPosition,
    select,
    nodes,
  };
}
