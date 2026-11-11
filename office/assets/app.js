import { createScene } from "./scene.js";

const stage = document.getElementById("stage");
const svg = document.getElementById("scene");
const side = document.getElementById("side");
const bubbles = document.getElementById("bubbles");
const connection = document.getElementById("connection");
const missionChip = document.getElementById("mission-chip");
const topKpis = document.getElementById("top-kpis");
const stageNote = document.getElementById("stage-note");
const deptLegend = document.getElementById("dept-legend");
const nav = document.getElementById("nav");
const toast = document.getElementById("toast");

let state = null;
let scene = null;
let stream = null;
let currentMissionId = new URLSearchParams(window.location.search).get("mission_id");
let selectedAgent = null;
let panelView = "overview";
let detailReturn = "overview";
let missions = [];
let lastEventId = 0;
let handoffQueue = Promise.resolve();
let handoffPending = 0;
let sideScrollKey = "";
let missionWatcher = null;
const activeBubbles = [];

/* ------------------------------------------------------------------ */
/* Utilitaires                                                         */
/* ------------------------------------------------------------------ */
function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function short(value, limit = 110) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1).trimEnd()}…`;
}

function initials(name) {
  return String(name ?? "?").slice(0, 2).toUpperCase();
}

function fmtTime(value) {
  if (!value) return "--:--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function agentById(agentId) {
  return state?.agents?.find((agent) => agent.id === agentId) || null;
}

function missionStatusTone(status) {
  if (status === "completed") return "done";
  if (status === "failed") return "blocked";
  if (status === "cancelled") return "idle";
  if (status === "created" || status === "waiting_approval") return "waiting";
  return "working";
}

function setConnection(kind, label) {
  connection.dataset.state = kind;
  connection.querySelector("span").textContent = label;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

async function copyPath(path) {
  try {
    await navigator.clipboard.writeText(path);
    showToast("Chemin copié.");
  } catch {
    const area = document.createElement("textarea");
    area.value = path;
    document.body.append(area);
    area.select();
    try {
      document.execCommand("copy");
      showToast("Chemin copié.");
    } catch {
      showToast("Copie impossible.");
    }
    area.remove();
  }
}

/* ------------------------------------------------------------------ */
/* Chargement et flux SSE                                              */
/* ------------------------------------------------------------------ */
function stateUrl(missionId) {
  const url = new URL("/api/state", window.location.origin);
  if (missionId) url.searchParams.set("mission_id", missionId);
  return url;
}

async function fetchState(missionId) {
  const response = await fetch(stateUrl(missionId), { cache: "no-store" });
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function fetchMissions() {
  try {
    const response = await fetch("/api/missions", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    missions = payload.missions || [];
    if (panelView === "missions") renderSide();
  } catch {
    // Le panneau Missions affiche l'état déjà connu en cas d'échec.
  }
}

function applyState(data, { reset = false } = {}) {
  const changed = reset || !state || state.mission?.id !== data.mission?.id;
  state = data;
  if (!scene || changed) {
    scene = createScene(svg, data.agents || []);
    scene.select(selectedAgent);
  } else {
    scene.setAgents(data.agents || []);
  }
  if (changed) {
    lastEventId = maxEventId(data.events);
    if (data.mission?.id) currentMissionId = data.mission.id;
    const url = new URL(window.location.href);
    if (currentMissionId) url.searchParams.set("mission_id", currentMissionId);
    else url.searchParams.delete("mission_id");
    window.history.replaceState(null, "", url);
  }
  renderAll();
  if (changed) fetchMissions();
}

function maxEventId(events) {
  return (events || []).reduce((max, event) => Math.max(max, event.id || 0), 0);
}

function openStream(missionId) {
  if (stream) {
    stream.close();
    stream = null;
  }
  stopMissionWatch();
  setConnection("retry", "Connexion…");
  const source = new EventSource(
    `/events?mission_id=${encodeURIComponent(missionId)}`,
  );
  stream = source;

  source.addEventListener("open", () => {
    setConnection("live", "SSE connecté");
  });

  source.addEventListener("snapshot", (message) => {
    try {
      const data = JSON.parse(message.data);
      applyState(data, {
        reset: !state || state.mission?.id !== data.mission?.id,
      });
      setConnection("live", "SSE connecté");
    } catch {
      setConnection("offline", "Flux illisible");
    }
  });

  source.addEventListener("office", (message) => {
    try {
      const payload = JSON.parse(message.data);
      handleOfficeEvent(payload.event, payload.state);
    } catch {
      // Un événement illisible ne doit pas interrompre le flux.
    }
  });

  source.addEventListener("error", () => {
    setConnection("retry", "Reconnexion…");
  });
}

function handleOfficeEvent(event, nextState) {
  if (!event) return;
  if (!nextState) return;
  if ((event.id || 0) <= lastEventId) {
    state = nextState;
    scene?.setAgents(nextState.agents || []);
    renderAll();
    return;
  }
  state = nextState;
  lastEventId = event.id || lastEventId;
  scene?.setAgents(nextState.agents || []);
  renderAll();
  animateEvent(event);
  if (["mission_completed", "mission_failed", "mission_cancelled"].includes(event.type)) {
    fetchMissions();
  }
}

/* ------------------------------------------------------------------ */
/* Animations pilotées par les événements réels                        */
/* ------------------------------------------------------------------ */
const EVENT_KINDS = {
  mission_created: "info",
  mission_started: "start",
  mission_planned: "info",
  mission_approved: "done",
  mission_reviewed: "info",
  mission_cancel_requested: "fail",
  task_started: "start",
  task_completed: "done",
  task_failed: "fail",
  task_blocked: "fail",
  report_ready: "report",
  mission_completed: "done",
  mission_failed: "fail",
  mission_cancelled: "fail",
  approval_required: "start",
};

const EVENT_TITLES = {
  mission_created: "Mission créée",
  mission_started: "Mission démarrée",
  mission_planned: "Plan établi",
  mission_approved: "Mission approuvée",
  mission_reviewed: "Revue terminée",
  mission_cancel_requested: "Annulation demandée",
  task_started: "Tâche démarrée",
  task_completed: "Tâche terminée",
  task_failed: "Tâche en échec",
  task_blocked: "Tâche bloquée",
  report_ready: "Rapport prêt",
  mission_completed: "Mission terminée",
  mission_failed: "Mission en échec",
  mission_cancelled: "Mission annulée",
  approval_required: "Approbation requise",
};

function eventDescription(event) {
  const payload = event.payload || {};
  const agent = event.agent ? agentById(event.agent) : null;
  const who = agent ? agent.name : "Système";
  switch (event.type) {
    case "mission_created":
      return {
        title: "Mission créée",
        detail: short(payload.instruction || "", 140),
      };
    case "mission_started":
      return { title: "Mission démarrée", detail: short(payload.instruction || "", 120) };
    case "mission_planned":
      return {
        title: "Plan établi",
        detail: `${payload.task_count ?? "?"} tâches · ${(payload.agents || []).length} agents`,
      };
    case "mission_approved":
      return { title: "Mission approuvée", detail: short(payload.reason || "", 90) };
    case "approval_required":
      return { title: "Approbation requise", detail: short(payload.reason || "", 110) };
    case "mission_reviewed":
      return {
        title: "Revue terminée",
        detail: `${payload.completed ?? 0} tâche(s) OK · ${payload.failed ?? 0} en échec`,
      };
    case "task_started":
      return { title: `${who} démarre`, detail: short(payload.title || "", 120) };
    case "task_completed":
      return { title: `${who} termine`, detail: short(payload.summary || payload.title || "", 130) };
    case "task_failed":
      return { title: `${who} — échec`, detail: short(payload.error || payload.title || "", 130) };
    case "task_blocked":
      return { title: `${who} — bloqué`, detail: short(payload.reason || payload.title || "", 120) };
    case "report_ready":
      return { title: "Rapport prêt", detail: short(payload.path || "", 130) };
    case "mission_completed":
      return { title: "Mission terminée", detail: short(payload.report || "0 anomalie déclarée", 130) };
    case "mission_failed":
      return { title: "Mission en échec", detail: short(payload.error || "", 130) };
    case "mission_cancelled":
      return { title: "Mission annulée", detail: short(payload.reason || "", 110) };
    case "mission_cancel_requested":
      return { title: "Annulation demandée", detail: short(payload.reason || "", 110) };
    default:
      return { title: EVENT_TITLES[event.type] || event.type, detail: "" };
  }
}

function findTask(event) {
  const payload = event.payload || {};
  if (payload.key) {
    const byKey = state?.tasks?.find((task) => task.key === payload.key);
    if (byKey) return byKey;
  }
  return state?.tasks?.find(
    (task) => task.agent === event.agent && task.title === payload.title,
  ) || null;
}

function animateEvent(event) {
  const agentId = event.agent || "manager";
  const payload = event.payload || {};
  if (event.type === "task_started") {
    showBubble(agentId, `▶ ${short(payload.title || "Tâche démarrée", 90)}`, "info");
    animateHandoff(event);
    return;
  }
  if (event.type === "task_completed") {
    showBubble(agentId, `✓ ${short(payload.summary || "Tâche terminée", 95)}`, "ok");
    return;
  }
  if (event.type === "task_failed") {
    showBubble(agentId, `⚠ Échec : ${short(payload.error || "tâche en échec", 80)}`, "danger", 6000);
    return;
  }
  if (event.type === "task_blocked") {
    showBubble(agentId, `⏸ ${short(payload.reason || "dépendance non satisfaite", 90)}`, "warn");
    return;
  }
  if (event.type === "report_ready") {
    showBubble(agentId, "📄 Rapport prêt", "ok");
    return;
  }
  if (event.type === "mission_planned") {
    showBubble(agentId, `Plan : ${payload.task_count ?? "?"} tâches`, "info");
    return;
  }
  if (event.type === "mission_completed") {
    showBubble(agentId, "🎉 Mission terminée", "ok", 6000);
    return;
  }
  if (event.type === "mission_failed") {
    showBubble(agentId, "⚠ Mission en échec", "danger", 6000);
    return;
  }
  if (event.type === "approval_required") {
    showBubble(agentId, "⏳ Approbation requise", "warn", 6000);
    return;
  }
  if (event.type === "mission_cancelled") {
    showBubble(agentId, "Mission annulée", "warn");
  }
}

function animateHandoff(event) {
  const task = findTask(event);
  if (!task || !task.depends_on?.length) return;
  const dependency = state?.tasks?.find((item) => item.key === task.depends_on[0]);
  if (!dependency || dependency.agent === task.agent) return;
  if (dependency.status !== "completed") return;
  if (handoffPending >= 2) return;
  const from = dependency.agent;
  const to = task.agent;
  handoffPending += 1;
  handoffQueue = handoffQueue
    .then(async () => {
      const fromAgent = agentById(from);
      const toAgent = agentById(to);
      if (!fromAgent || !toAgent) return;
      showBubble(from, `↪ Passation vers ${toAgent.name}`, "info", 4200);
      await scene?.handoff(from, to);
      showBubble(to, `Reçu de ${fromAgent.name}`, "ok", 3000);
    })
    .catch(() => {})
    .finally(() => {
      handoffPending -= 1;
    });
}

function clearBubble(entry) {
  window.clearTimeout(entry.timer);
  entry.element.remove();
  const index = activeBubbles.indexOf(entry);
  if (index >= 0) activeBubbles.splice(index, 1);
}

function showBubble(agentId, text, tone = "info", ttl = 4800) {
  if (!scene) return;
  const position = scene.getPosition(agentId);
  const matrix = svg.getScreenCTM();
  if (!matrix) return;
  const point = svg.createSVGPoint();
  point.x = position.x;
  point.y = position.y - 98;
  const screen = point.matrixTransform(matrix);
  const bounds = svg.getBoundingClientRect();
  const left = Math.max(118, Math.min(bounds.width - 118, screen.x - bounds.left));
  const top = Math.max(122, screen.y - bounds.top);

  // Un seul message par agent : le plus récent remplace le précédent.
  for (const entry of activeBubbles.filter((item) => item.agentId === agentId)) {
    clearBubble(entry);
  }

  const element = document.createElement("div");
  element.className = "bubble";
  element.dataset.tone = tone;
  element.textContent = text;
  element.style.left = `${left}px`;
  element.style.top = `${top}px`;
  bubbles.append(element);

  const entry = { agentId, element, timer: 0 };
  entry.timer = window.setTimeout(() => clearBubble(entry), ttl);
  activeBubbles.push(entry);

  // Plafond global : on ne laisse jamais la scène saturée de messages.
  while (activeBubbles.length > 4) clearBubble(activeBubbles[0]);
}

/* ------------------------------------------------------------------ */
/* Rendu                                                               */
/* ------------------------------------------------------------------ */
function renderAll() {
  renderHeader();
  renderStageNote();
  renderDepartments();
  renderSide();
  renderNav();
}

function renderDepartments() {
  const departments = state?.departments || [];
  const agents = state?.agents || [];
  if (!departments.length) {
    deptLegend.hidden = true;
    deptLegend.innerHTML = "";
    return;
  }
  const rows = departments
    .map((department) => {
      const count = agents.filter((agent) => agent.department === department.id).length;
      if (!count) return "";
      return `
        <span class="dept-row">
          <i style="background:${esc(department.color)}"></i>
          ${esc(department.label)}
          <b>${count}</b>
        </span>`;
    })
    .join("");
  deptLegend.innerHTML = `<span class="dept-title">Départements</span>${rows}`;
  deptLegend.hidden = false;
}

function renderHeader() {
  const mission = state?.mission;
  if (!mission) {
    missionChip.textContent = "Aucune mission";
    missionChip.title = "Aucune mission enregistrée";
    topKpis.innerHTML = "";
    return;
  }
  missionChip.textContent = `#${mission.id} · ${mission.status_label}`;
  missionChip.title = mission.instruction || mission.id;
  const stats = state.stats;
  const allure = state.allure;
  topKpis.innerHTML = `
    <span>Tâches <b>${stats.tasks_done}/${stats.tasks_total}</b></span>
    <span>Preuves <b>${stats.evidence_total}</b></span>
    ${allure ? `<span>Allure <b>${allure.total}</b></span>` : `<span>Agents <b>${stats.agents_working}</b> actifs</span>`}
  `;
}

function renderStageNote() {
  const mission = state?.mission;
  let text = "";
  if (!mission) {
    text = "Aucune mission — le bureau attend une demande explicite.";
  } else if (mission.status === "waiting_approval") {
    text = "Approbation requise — aucune tâche ne sera lancée sans validation.";
  } else if (mission.status === "completed") {
    text = "Mission terminée — rapport disponible dans l'onglet Rapports.";
  } else if (mission.status === "failed") {
    text = "Mission en échec — consultez les événements et le rapport.";
  } else if (mission.status === "cancelled") {
    text = "Mission annulée — aucune tâche ne sera relancée.";
  }
  stageNote.textContent = text;
  stageNote.hidden = !text;
}

function renderNav() {
  const active = panelView === "detail" ? "agents" : panelView;
  for (const button of nav.querySelectorAll(".nav-item")) {
    button.classList.toggle("is-active", button.dataset.view === active);
  }
}

function renderSide() {
  const key = `${panelView}:${selectedAgent || ""}`;
  const previousScroll = side.scrollTop;
  let html = "";

  if (panelView === "detail" && selectedAgent) html = detailMarkup(selectedAgent);
  else if (panelView === "missions") html = missionsMarkup();
  else if (panelView === "agents") html = agentsMarkup();
  else if (panelView === "reports") html = reportsMarkup();
  else html = overviewMarkup();

  side.innerHTML = html;
  side.scrollTop = key === sideScrollKey ? previousScroll : 0;
  sideScrollKey = key;
}

function overviewMarkup() {
  if (!state?.mission) {
    return `
      <section class="card">
        <div class="card-head"><span class="eyebrow">Équipe</span><span class="badge">8 agents</span></div>
        <div class="empty-line">
          Le bureau est prêt. Créez une demande via Telegram ou la CLI :
          aucune mission ne se lance automatiquement.
        </div>
      </section>
      <section class="card">
        <div class="card-head"><span class="eyebrow">Mission</span></div>
        <div class="empty-line">Aucune mission enregistrée dans <code>workspace/missions.db</code>.</div>
      </section>`;
  }

  const mission = state.mission;
  const stats = state.stats;
  const team = `
    <section class="card">
      <div class="card-head"><span class="eyebrow">État de l'équipe</span><span class="badge">8 agents</span></div>
      <div class="team-counts">
        <div class="count-tile" data-tone="working"><b>${stats.agents_working}</b><span>en travail</span></div>
        <div class="count-tile" data-tone="done"><b>${stats.agents_done}</b><span>terminés</span></div>
        <div class="count-tile" data-tone="waiting"><b>${stats.agents_waiting}</b><span>en attente</span></div>
        <div class="count-tile" data-tone="blocked"><b>${stats.agents_blocked}</b><span>bloqués</span></div>
      </div>
    </section>`;

  const missionCard = `
    <section class="card">
      <div class="card-head">
        <span class="eyebrow">Mission courante</span>
        <span class="badge" data-status="${missionStatusTone(mission.status)}">${esc(mission.status_label)}</span>
      </div>
      <div class="mission-id">#${esc(mission.id)}</div>
      <p class="mission-instruction">${esc(mission.instruction)}</p>
      <div class="progress"><i style="width:${mission.progress}%"></i></div>
      <div class="progress-meta">
        <span>${mission.tasks_done}/${mission.tasks_total} tâches</span>
        <span>${mission.progress}%</span>
      </div>
      ${mission.requires_approval ? `<div class="next-step" style="margin-top:10px"><b>Approbation requise</b>${esc(mission.approval_reason || "Validation explicite nécessaire.")}</div>` : ""}
    </section>`;

  const feed = state.events.slice(-12).reverse();
  const activity = `
    <section class="card">
      <div class="card-head"><span class="eyebrow">Activité récente</span><span class="badge">${state.stats.events_total} événements</span></div>
      <div class="feed">
        ${feed.length ? feed.map(feedRowMarkup).join("") : '<div class="empty-line">Aucun événement réel enregistré.</div>'}
      </div>
    </section>`;

  const kpi = kpiMarkup();

  return team + missionCard + kpi + activity + nextStepMarkup();
}

function kpiMarkup() {
  const stats = state.stats;
  if (state.allure) {
    const total = state.allure.total || 0;
    const passed = state.allure.passed || 0;
    const percent = total ? Math.round((passed * 100) / total) : 0;
    return `
      <section class="card">
        <div class="card-head"><span class="eyebrow">Résultats</span><span class="badge" data-status="done">Allure 2</span></div>
        <div class="donut-row">
          <div class="donut" style="--p:${percent}"><b>${percent}%</b></div>
          <div class="donut-legend">
            <b>${total} résultats</b>
            <span>${passed} réussis · ${state.allure.failed} échec(s)</span>
            <span>${state.allure.anomalies} anomalie(s) · ${state.allure.skipped} ignoré(s)</span>
          </div>
        </div>
      </section>`;
  }
  const percent = stats.progress;
  return `
    <section class="card">
      <div class="card-head"><span class="eyebrow">Progression</span><span class="badge">${stats.tasks_done}/${stats.tasks_total}</span></div>
      <div class="donut-row">
        <div class="donut" style="--p:${percent}"><b>${percent}%</b></div>
        <div class="donut-legend">
          <b>${stats.tasks_done} tâches terminées</b>
          <span>${stats.tasks_running} en cours · ${stats.tasks_pending} en attente</span>
          <span>${stats.tasks_blocked + stats.tasks_failed} bloquée(s) ou en échec</span>
        </div>
      </div>
      <div class="kpis" style="margin-top:10px">
        <div class="kpi" data-tone="green"><b>${stats.evidence_total}</b><span>preuves</span></div>
        <div class="kpi" data-tone="blue"><b>${stats.events_total}</b><span>événements</span></div>
      </div>
    </section>`;
}

function nextStepMarkup() {
  if (!state?.mission) return "";
  const status = state.mission.status;
  let title = "Mission en cours";
  let text = "Les agents travaillent sur les tâches planifiées.";
  if (status === "waiting_approval") {
    title = "Approbation requise";
    text = "La mission attend une validation explicite avant toute exécution.";
  } else if (status === "completed") {
    title = "Rapport disponible";
    text = "La mission est terminée. Consultez les rapports et les résultats Allure.";
  } else if (status === "failed") {
    title = "Mission en échec";
    text = "Consultez les événements et le rapport pour identifier la cause réelle.";
  } else if (status === "cancelled") {
    title = "Mission annulée";
    text = "Aucune tâche ne sera relancée ; une nouvelle demande est nécessaire.";
  } else if (status === "created") {
    title = "Mission créée";
    text = "La mission n'a pas encore été exécutée.";
  }
  return `
    <section class="card">
      <span class="eyebrow">Prochaine étape</span>
      <div class="next-step" style="margin-top:7px"><b>${esc(title)}</b>${esc(text)}</div>
    </section>`;
}

function feedRowMarkup(event) {
  const description = eventDescription(event);
  return `
    <div class="event-row" data-kind="${EVENT_KINDS[event.type] || "info"}">
      <time>${fmtTime(event.created_at)}</time>
      <span class="event-dot"></span>
      <div class="event-body">
        <b>${esc(description.title)}</b>
        ${description.detail ? `<span>${esc(description.detail)}</span>` : ""}
      </div>
    </div>`;
}

function missionsMarkup() {
  const rows = missions.length
    ? missions.map((mission) => `
        <button type="button" class="mission-row${mission.id === state?.mission?.id ? " is-selected" : ""}"
                data-action="load-mission" data-mission="${esc(mission.id)}">
          <span class="id">#${esc(mission.id)}</span>
          <p>${esc(mission.instruction || "")}</p>
          <span class="meta">
            <span>${esc(mission.status_label)}</span>
            <span>${mission.tasks_done}/${mission.tasks_total} · ${mission.progress}%</span>
          </span>
        </button>`).join("")
    : '<div class="empty-line">Aucune mission enregistrée. Créez une demande via Telegram ou la CLI.</div>';

  return `
    <section class="card">
      <div class="card-head">
        <span class="eyebrow">Missions récentes</span>
        <button type="button" class="copy-btn" data-action="refresh-missions">Rafraîchir</button>
      </div>
      <div class="mission-list">${rows}</div>
    </section>
    <section class="card">
      <span class="eyebrow">Rappel</span>
      <div class="empty-line">Sélectionner une mission recharge le bureau et son flux SSE. Aucune mission n'est lancée.</div>
    </section>`;
}

function agentsMarkup() {
  const rows = (state?.agents || []).map((agent) => `
    <button type="button" class="agent-row" data-action="open-agent" data-agent="${esc(agent.id)}">
      <span class="agent-avatar" style="background:${esc(agent.color)}">${esc(initials(agent.name))}</span>
      <span class="agent-meta">
        <b>${esc(agent.name)}</b>
        <span>${esc(agent.role)} · ${esc(agent.status_label)}</span>
      </span>
      <span class="badge" data-status="${esc(agent.status)}">${esc(agent.status_label)}</span>
    </button>`).join("");

  const departments = (state?.departments || []).map((department) => `
    <span class="badge" style="border-color:${esc(department.color)}66;color:${esc(department.color)}">${esc(department.label)}</span>`).join(" ");

  return `
    <section class="card">
      <div class="card-head"><span class="eyebrow">Équipe</span><span class="badge">8 agents</span></div>
      <div class="agent-list">${rows}</div>
    </section>
    <section class="card">
      <span class="eyebrow">Départements</span>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px">${departments}</div>
    </section>`;
}

function reportsMarkup() {
  if (!state?.mission) {
    return `
      <section class="card">
        <div class="card-head"><span class="eyebrow">Rapports</span></div>
        <div class="empty-line">Aucune mission sélectionnée. Les rapports restent locaux et sont ignorés par Git.</div>
      </section>`;
  }
  const mission = state.mission;
  return `
    <section class="card">
      <div class="card-head">
        <span class="eyebrow">Rapports</span>
        <span class="badge" data-status="${missionStatusTone(mission.status)}">${esc(mission.status_label)}</span>
      </div>
      <div class="mission-id">#${esc(mission.id)}</div>
      <div class="detail-section">
        <h3>Rapport Markdown</h3>
        ${mission.report_path ? pathMarkup(mission.report_path) : '<p class="empty-line">Aucun rapport Markdown enregistré.</p>'}
      </div>
      <div class="detail-section">
        <h3>Résultats Allure 2</h3>
        ${state.allure
          ? `${pathMarkup(state.allure.dir)}<p class="empty-line" style="padding-top:6px">${state.allure.total} résultats · ${state.allure.passed} réussis · ${state.allure.failed} échec(s) · ${state.allure.anomalies} anomalie(s).</p>`
          : '<p class="empty-line">Aucun résultat Allure pour cette mission.</p>'}
      </div>
      <div class="detail-section">
        <h3>Synthèse JSON</h3>
        <p class="empty-line">Le reporter écrit aussi <code>reports/missions/&lt;mission&gt;.json</code> et les preuves dans le workspace local.</p>
      </div>
    </section>
    <section class="card">
      <span class="eyebrow">Rendu HTML</span>
      <div class="empty-line">La CLI Allure est optionnelle et gratuite : <code>allure serve reports\\allure-results\\&lt;mission&gt;</code>. Les fichiers JSON restent autonomes.</div>
    </section>`;
}

function pathMarkup(path) {
  return `
    <div class="path-box">
      <code title="${esc(path)}">${esc(path)}</code>
      <button type="button" class="copy-btn" data-action="copy" data-copy="${esc(path)}">Copier</button>
    </div>`;
}

function detailMarkup(agentId) {
  const agent = agentById(agentId);
  if (!agent) return '<section class="card"><div class="empty-line">Agent introuvable.</div></section>';
  const tasks = (state?.tasks || []).filter((task) => task.agent === agentId);
  const events = (state?.events || [])
    .filter((event) => (agentId === "manager" ? !event.agent : event.agent === agentId))
    .slice(-6)
    .reverse();

  return `
    <button type="button" class="back-btn" data-action="back">← Retour</button>
    <section class="card">
      <div class="detail-head">
        <span class="agent-avatar" style="background:${esc(agent.color)}">${esc(initials(agent.name))}</span>
        <div>
          <b>${esc(agent.name)}</b>
          <span>${esc(agent.role)} · ${esc(agent.department_label)}</span>
        </div>
      </div>
      <div class="status-row" style="margin-top:11px">
        <span class="badge" data-status="${esc(agent.status)}">${esc(agent.status_label)}</span>
        <span class="eyebrow">${agent.tasks_done}/${agent.tasks_total} tâches</span>
      </div>
      <div class="detail-section">
        <h3>Rôle</h3>
        <p>${esc(agent.summary)}</p>
      </div>
      <div class="detail-section">
        <h3>Tâche actuelle</h3>
        <p>${esc(agent.current_task)}</p>
      </div>
      <div class="detail-section">
        <h3>Tâches</h3>
        ${tasks.length ? `<div class="task-list">${tasks.map(taskMarkup).join("")}</div>` : '<p class="empty-line">Aucune tâche planifiée pour cet agent.</p>'}
      </div>
      <div class="detail-section">
        <h3>Dernier résultat</h3>
        <p>${esc(agent.last_result || "Aucun résultat enregistré.")}</p>
      </div>
      <div class="detail-section">
        <h3>Activité</h3>
        <div class="feed">${events.length ? events.map(feedRowMarkup).join("") : '<div class="empty-line">Aucun événement pour cet agent.</div>'}</div>
      </div>
    </section>`;
}

function taskMarkup(task) {
  return `
    <div class="task-item" data-status="${esc(task.status)}">
      <b>${esc(task.title)}</b>
      <span>${esc(task.status_label)} · ${task.evidence_count} preuve(s)${task.result ? ` · ${esc(short(task.result, 80))}` : ""}</span>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Navigation et interactions                                          */
/* ------------------------------------------------------------------ */
function setView(view) {
  panelView = view;
  selectedAgent = null;
  detailReturn = view === "missions" || view === "agents" || view === "reports" ? view : "overview";
  scene?.select(null);
  if (view === "missions") fetchMissions();
  renderNav();
  renderSide();
}

function openAgent(agentId) {
  if (!agentById(agentId)) return;
  detailReturn = panelView === "detail" ? detailReturn : panelView;
  selectedAgent = agentId;
  panelView = "detail";
  scene?.select(agentId);
  renderNav();
  renderSide();
}

function closeDetail() {
  selectedAgent = null;
  scene?.select(null);
  panelView = detailReturn || "overview";
  renderNav();
  renderSide();
}

async function loadMission(missionId) {
  if (!missionId) return;
  if (stream) {
    stream.close();
    stream = null;
  }
  setConnection("retry", "Chargement…");
  try {
    const data = await fetchState(missionId);
    selectedAgent = null;
    detailReturn = "overview";
    panelView = "overview";
    state = null;
    lastEventId = 0;
    applyState(data, { reset: true });
    if (data.mission?.id) openStream(data.mission.id);
    else {
      setConnection("retry", "En attente");
      watchForMission();
    }
  } catch {
    setConnection("offline", "Mission introuvable");
    showToast("Mission introuvable.");
    watchForMission();
  }
}

nav.addEventListener("click", (event) => {
  const button = event.target.closest(".nav-item");
  if (!button) return;
  setView(button.dataset.view);
});

side.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "back") closeDetail();
  else if (action === "open-agent") openAgent(target.dataset.agent);
  else if (action === "load-mission") loadMission(target.dataset.mission);
  else if (action === "refresh-missions") fetchMissions();
  else if (action === "copy") copyPath(target.dataset.copy);
});

stage.addEventListener("agent-select", (event) => {
  openAgent(event.detail.agentId);
});

/* ------------------------------------------------------------------ */
/* Démarrage                                                           */
/* ------------------------------------------------------------------ */
function stopMissionWatch() {
  if (missionWatcher) {
    window.clearTimeout(missionWatcher);
    missionWatcher = null;
  }
}

function watchForMission() {
  if (missionWatcher || stream) return;
  missionWatcher = window.setTimeout(async () => {
    missionWatcher = null;
    try {
      const response = await fetch("/api/missions", { cache: "no-store" });
      if (response.ok) {
        const payload = await response.json();
        missions = payload.missions || [];
        if (missions.length) {
          await loadMission(missions[0].id);
          return;
        }
      }
    } catch {
      // Le serveur peut redevenir disponible : on retentera.
    }
    watchForMission();
  }, 5000);
}

async function init() {
  setConnection("connecting", "Connexion…");
  let data;
  try {
    data = await fetchState(currentMissionId);
  } catch (error) {
    if (currentMissionId) {
      currentMissionId = null;
      window.history.replaceState(null, "", window.location.pathname);
      showToast("Mission introuvable, affichage de la plus récente.");
      try {
        data = await fetchState(null);
      } catch {
        showFatal("Le serveur du bureau ne répond pas.");
        return;
      }
    } else {
      showFatal("Le serveur du bureau ne répond pas.");
      return;
    }
  }

  applyState(data, { reset: true });
  if (data.mission?.id) {
    setConnection("live", "SSE connecté");
    openStream(data.mission.id);
  } else {
    setConnection("retry", "En attente");
    watchForMission();
  }
}

function showFatal(message) {
  setConnection("offline", "Hors ligne");
  deptLegend.hidden = true;
  deptLegend.innerHTML = "";
  side.innerHTML = `
    <section class="card">
      <div class="card-head"><span class="eyebrow">Bureau indisponible</span></div>
      <div class="empty-line">${esc(message)} Lancez le serveur avec
      <code>scripts\\run_office.py</code>, puis rechargez cette page.</div>
    </section>`;
  topKpis.innerHTML = "";
  missionChip.textContent = "Hors ligne";
}

init();
