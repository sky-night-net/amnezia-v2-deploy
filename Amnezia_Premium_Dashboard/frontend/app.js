/**
 * AmneziaWG Premium Dashboard — app.js v3
 * Connects to the Master Hub API at port 9292.
 *
 * Architecture:
 *   Browser → GET /hub/nodes      → list of registered nodes
 *   Browser → GET /hub/stats      → live stats for all nodes (polled by Hub)
 *   Browser → POST /hub/register  → add/update a node
 *   Browser → GET /api/wireguard/client → clients list (direct to node's WG Easy panel)
 */

"use strict";

// ─── Config ──────────────────────────────────────────────────────────────────
const HUB_PORT   = 9292;
const HUB_API    = `${window.location.protocol}//${window.location.hostname}:${HUB_PORT}`;
let   PANEL_API  = "";   // Set when a node is selected (points to WG Easy panel via SSH tunnel)

// ─── State ───────────────────────────────────────────────────────────────────
let currentNode   = null;
let clientsData   = [];
let liveStats     = {};
let hubStatsCache = {};
let trafficChart  = null;
let clientsChart  = null;

// ─── DOM ─────────────────────────────────────────────────────────────────────
const loginScreen    = document.getElementById("login-screen");
const dashScreen     = document.getElementById("dashboard-screen");
const loginBtn       = document.getElementById("login-btn");
const logoutBtn      = document.getElementById("logout-btn");
const passwordInput  = document.getElementById("password");
const authError      = document.getElementById("auth-error");
const clientsGrid    = document.getElementById("clients-grid");
const nodesList      = document.getElementById("nodes-list");
const navItems       = document.querySelectorAll(".nav-item");
const tabs = {
  clients:   document.getElementById("tab-clients"),
  analytics: document.getElementById("tab-analytics"),
  settings:  document.getElementById("tab-settings"),
};

// ─── Init ────────────────────────────────────────────────────────────────────
if (localStorage.getItem("awg_session")) {
  showDashboard();
  loadNodes();
}

// ─── Auth ────────────────────────────────────────────────────────────────────
async function handleLogin() {
  const password = passwordInput.value.trim();
  if (!password) return;

  loginBtn.disabled   = true;
  loginBtn.textContent = "ПРОВЕРКА...";
  authError.classList.add("hidden");

  try {
    if (!currentNode) {
      // No node selected yet — just enter the dashboard
      localStorage.setItem("awg_session", "1");
      showDashboard();
      loadNodes();
      return;
    }
    // Try to authenticate against selected node's panel
    const res = await fetchTimeout(`${PANEL_API}/api/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      localStorage.setItem("awg_session", "1");
      showDashboard();
      loadNodes();
    } else {
      throw new Error("Unauthorized");
    }
  } catch {
    authError.classList.remove("hidden");
    loginBtn.disabled    = false;
    loginBtn.textContent = "ВОЙТИ";
  }
}

function showDashboard() {
  loginScreen.classList.remove("active");
  dashScreen.classList.add("active");
  initCharts();
}

loginBtn.addEventListener("click", handleLogin);
passwordInput.addEventListener("keydown", (e) => { if (e.key === "Enter") handleLogin(); });
logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("awg_session");
  location.reload();
});

// ─── Nodes ───────────────────────────────────────────────────────────────────
async function loadNodes() {
  try {
    const res   = await fetchTimeout(`${HUB_API}/hub/nodes`);
    const nodes = await res.json();
    renderNodes(nodes);
    // Auto-select first node
    if (nodes.length > 0 && !currentNode) {
      selectNode(nodes[0]);
    }
  } catch (e) {
    nodesList.innerHTML = `<p class="error-msg" style="padding:12px">Hub offline</p>`;
    console.warn("Hub unreachable:", e);
  }
}

function renderNodes(nodes) {
  nodesList.innerHTML = "";
  if (!nodes || nodes.length === 0) {
    nodesList.innerHTML = `<p style="padding:12px;color:#666;font-size:0.85rem">No nodes registered yet</p>`;
    return;
  }
  nodes.forEach((node) => {
    const stat   = hubStatsCache[node.name] || {};
    const status = stat.status || "—";
    const isOn   = status === "Online";
    const dot    = isOn ? "🟢" : (status === "Auth Error" ? "🟡" : "🔴");

    const item = document.createElement("div");
    item.className = `node-item${currentNode && currentNode.name === node.name ? " active" : ""}`;
    item.innerHTML = `
      <span class="node-status-dot">${dot}</span>
      <span class="node-name">${node.name}</span>
      <span style="font-size:0.7rem;color:#555;margin-left:auto">${status}</span>
    `;
    item.addEventListener("click", () => selectNode(node));
    nodesList.appendChild(item);
  });
}

function selectNode(node) {
  currentNode = node;
  PANEL_API   = `${window.location.protocol}//${node.ip}:4466`;

  // Update IP display
  const mono = document.querySelector(".mono");
  if (mono) mono.textContent = node.ip;

  // Refresh node list to update active class
  loadNodes();
  // Load clients for this node
  loadClients();
  // Update stats display
  applyHubStats();
}

// ─── Hub Stats Polling ───────────────────────────────────────────────────────
async function pollHubStats() {
  try {
    const res  = await fetchTimeout(`${HUB_API}/hub/stats`);
    hubStatsCache = await res.json();
    applyHubStats();
    // Refresh node dot colors
    if (nodesList.children.length > 0) {
      const nodes = await fetchTimeout(`${HUB_API}/hub/nodes`).then((r) => r.json()).catch(() => []);
      renderNodes(nodes);
    }
  } catch {
    // Hub offline — silently ignore, UI shows stale data
  }
}

function applyHubStats() {
  if (!currentNode) return;
  const stat = hubStatsCache[currentNode.name];
  if (!stat || !stat.data) return;
  liveStats = stat.data;
  // If clients tab is visible, re-render immediately
  if (tabs.clients.classList.contains("active")) {
    renderClientsGrid();
  }
}

setInterval(pollHubStats, 5000);

// ─── Clients ─────────────────────────────────────────────────────────────────
async function loadClients() {
  if (!currentNode) return;
  try {
    const res  = await fetchTimeout(`${PANEL_API}/api/wireguard/client`);
    clientsData = await res.json();
  } catch {
    clientsData = [];
  }
  // Merge live stats from Hub cache
  const stat = hubStatsCache[currentNode.name];
  liveStats  = (stat && stat.data) ? stat.data : {};
  renderClientsGrid();
}

function renderClientsGrid() {
  clientsGrid.innerHTML = "";
  const subtitle = document.getElementById("clients-subtitle");

  if (!clientsData || clientsData.length === 0) {
    clientsGrid.innerHTML = `<p class="error-msg">Нет клиентов. Добавьте первого.</p>`;
    if (subtitle) subtitle.textContent = "Нет клиентов";
    return;
  }

  let activeCount = 0;

  clientsData.forEach((client) => {
    // Match live stats by allowed IP
    let cStats = null;
    const cleanIp = (client.address || "").split("/")[0];
    for (const pk in liveStats) {
      if (liveStats[pk].allowed_ips && liveStats[pk].allowed_ips.some((ip) => ip.startsWith(cleanIp))) {
        cStats = liveStats[pk];
        break;
      }
    }

    const isOnline = cStats ? cStats.online : false;
    if (isOnline) activeCount++;

    const rx = cStats ? formatBytes(cStats.rx) : "—";
    const tx = cStats ? formatBytes(cStats.tx) : "—";
    const hs = cStats ? formatDate(cStats.latest_handshake) : "—";

    const card = document.createElement("div");
    card.className = "client-card glass-card";
    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="card-name">${escHtml(client.name || "?")}</div>
          <div class="card-ip">${escHtml(client.address || "")}</div>
        </div>
        <div class="status-badge ${isOnline ? "online" : "offline"}">
          <span class="status-dot"></span>${isOnline ? "Online" : "Offline"}
        </div>
      </div>
      <div class="card-traffic">
        <div class="card-traffic-item">
          <div class="card-traffic-label">↓ Получено</div>
          <div class="card-traffic-val">${rx}</div>
        </div>
        <div class="card-traffic-item">
          <div class="card-traffic-label">↑ Отправлено</div>
          <div class="card-traffic-val">${tx}</div>
        </div>
      </div>
      <div class="card-actions">
        <button class="card-btn" onclick="openDetail('${client.id}')">Детали</button>
        <button class="card-btn" onclick="showQRCode('${client.id}')">QR-код</button>
        <button class="card-btn" onclick="downloadConfig('${client.id}','${escHtml(client.name || 'client')}')">Скачать</button>
      </div>
    `;
    clientsGrid.appendChild(card);
  });

  if (subtitle) {
    subtitle.innerHTML = `Всего: <strong>${clientsData.length}</strong> | Активно: <strong style="color:var(--green)">${activeCount}</strong>`;
  }
}

// Auto-refresh clients tab every 15s
setInterval(() => {
  if (tabs.clients.classList.contains("active") && currentNode) {
    loadClients();
  }
}, 15000);

// ─── Navigation ──────────────────────────────────────────────────────────────
navItems.forEach((item) => {
  item.addEventListener("click", (e) => {
    e.preventDefault();
    const target = item.getAttribute("data-tab");
    navItems.forEach((i) => i.classList.remove("active"));
    item.classList.add("active");
    Object.values(tabs).forEach((t) => t.classList.remove("active"));
    tabs[target].classList.add("active");
    if (target === "analytics") loadAnalytics();
  });
});

// ─── Analytics ───────────────────────────────────────────────────────────────
function initCharts() {
  if (trafficChart) return; // already initialised

  const commonOpts = {
    chart: { type: "area", height: 260, toolbar: { show: false }, background: "transparent", animations: { enabled: true, speed: 400 } },
    theme: { mode: "dark" },
    stroke: { curve: "smooth", width: 2 },
    fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02 } },
    dataLabels: { enabled: false },
    grid: { borderColor: "rgba(255,255,255,0.05)", strokeDashArray: 4 },
    xaxis: { type: "datetime", labels: { style: { colors: "#6a7080" } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis: { labels: { formatter: (v) => formatBytes(v), style: { colors: "#6a7080" } } },
    tooltip: { theme: "dark", y: { formatter: (v) => formatBytes(v) } },
  };

  trafficChart = new ApexCharts(document.querySelector("#traffic-chart"), {
    ...commonOpts,
    colors: ["#39d98a", "#e63946"],
    series: [{ name: "Получено (RX)", data: [] }, { name: "Отправлено (TX)", data: [] }],
  });
  trafficChart.render();

  clientsChart = new ApexCharts(document.querySelector("#clients-chart"), {
    chart: { type: "bar", height: 260, toolbar: { show: false }, background: "transparent" },
    theme: { mode: "dark" },
    plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
    dataLabels: { enabled: false },
    colors: ["#e63946"],
    xaxis: { labels: { formatter: (v) => formatBytes(v), style: { colors: "#6a7080" } } },
    yaxis: { labels: { style: { colors: "#f0f0f5" } } },
    series: [{ name: "Трафик", data: [] }],
  });
  clientsChart.render();
}

async function loadAnalytics() {
  if (!currentNode) return;
  const summary = liveStats;

  let txTotal = 0, rxTotal = 0, activeCount = 0;
  const topClients = [];

  for (const pk in summary) {
    const d = summary[pk];
    rxTotal += d.rx_total || d.rx || 0;
    txTotal += d.tx_total || d.tx || 0;
    if (d.online) activeCount++;

    let cName = pk.substring(0, 8) + "…";
    clientsData.forEach((c) => {
      const cleanIp = (c.address || "").split("/")[0];
      if (d.allowed_ips && d.allowed_ips.some((ip) => ip.startsWith(cleanIp))) {
        cName = c.name;
      }
    });
    topClients.push({ x: cName, y: (d.rx_total || 0) + (d.tx_total || 0) });
  }

  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setEl("total-rx",    formatBytes(rxTotal));
  setEl("total-tx",    formatBytes(txTotal));
  setEl("active-count", activeCount);

  topClients.sort((a, b) => b.y - a.y);
  clientsChart.updateSeries([{ name: "Трафик", data: topClients.slice(0, 8) }]);

  // Fetch history from Hub (which proxies from the node)
  // For now we attempt direct fetch from node's stats collector
  // (Hub doesn't proxy history yet — that's a future enhancement)
  trafficChart.updateSeries([
    { name: "Получено (RX)", data: [] },
    { name: "Отправлено (TX)", data: [] },
  ]);
}

document.querySelectorAll(".period-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadAnalytics();
  });
});

// ─── Modals ───────────────────────────────────────────────────────────────────
const newClientModal = document.getElementById("modal");
const newClientInput = document.getElementById("new-client-name");

document.getElementById("add-client-btn").onclick = () => {
  newClientModal.classList.remove("hidden");
  newClientInput.focus();
};
document.getElementById("modal-close").onclick  = closeNewClientModal;
document.getElementById("cancel-modal").onclick = closeNewClientModal;
function closeNewClientModal() { newClientModal.classList.add("hidden"); newClientInput.value = ""; }

document.getElementById("confirm-create").onclick = async () => {
  const name = newClientInput.value.trim();
  if (!name) return;
  try {
    await fetch(`${PANEL_API}/api/wireguard/client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    closeNewClientModal();
    loadClients();
  } catch {
    alert("Ошибка создания клиента. Проверьте подключение к серверу.");
  }
};

// Detail modal
const detailModal = document.getElementById("detail-modal");
let currentDetailId = null;

window.openDetail = (clientId) => {
  const client = clientsData.find((c) => c.id === clientId);
  if (!client) return;
  currentDetailId = clientId;

  document.getElementById("detail-name").textContent = client.name || "—";
  document.getElementById("detail-ip").textContent   = client.address || "—";

  const cleanIp = (client.address || "").split("/")[0];
  let cStats = null;
  for (const pk in liveStats) {
    if (liveStats[pk].allowed_ips && liveStats[pk].allowed_ips.some((ip) => ip.startsWith(cleanIp))) {
      cStats = liveStats[pk];
      break;
    }
  }
  document.getElementById("detail-rx").textContent = cStats ? formatBytes(cStats.rx) : "—";
  document.getElementById("detail-tx").textContent = cStats ? formatBytes(cStats.tx) : "—";
  document.getElementById("detail-hs").textContent = cStats ? formatDate(cStats.latest_handshake) : "—";

  detailModal.classList.remove("hidden");
};

document.getElementById("detail-close").onclick  = () => detailModal.classList.add("hidden");
document.getElementById("detail-download").onclick = () => {
  const c = clientsData.find((c) => c.id === currentDetailId);
  if (c) downloadConfig(c.id, c.name);
};
document.getElementById("detail-qr").onclick     = () => showQRCode(currentDetailId);
document.getElementById("detail-delete").onclick = async () => {
  if (!confirm("Удалить клиента? Это действие необратимо.")) return;
  try {
    await fetch(`${PANEL_API}/api/wireguard/client/${currentDetailId}`, { method: "DELETE" });
    detailModal.classList.add("hidden");
    loadClients();
  } catch {
    alert("Ошибка удаления");
  }
};

// QR Code modal
const qrModal     = document.getElementById("qr-modal");
const qrContainer = document.getElementById("qr-container");

window.showQRCode = async (clientId) => {
  qrContainer.innerHTML = '<div class="loader"></div>';
  qrModal.classList.remove("hidden");
  try {
    const res = await fetch(`${PANEL_API}/api/wireguard/client/${clientId}/qrcode.svg`);
    if (!res.ok) throw new Error("Failed");
    const svg = await res.text();
    qrContainer.innerHTML = svg;
    const svgEl = qrContainer.querySelector("svg");
    if (svgEl) { svgEl.style.width = "100%"; svgEl.style.height = "auto"; }
  } catch {
    qrContainer.innerHTML = '<p style="color:var(--red)">Ошибка загрузки QR</p>';
  }
};
document.getElementById("qr-close").onclick = () => qrModal.classList.add("hidden");
qrModal.addEventListener("click", (e) => { if (e.target === qrModal) qrModal.classList.add("hidden"); });

// ─── Settings actions ─────────────────────────────────────────────────────────
window.resetAnalytics = async () => {
  if (!confirm("Сбросить всю статистику трафика? Это необратимо.")) return;
  if (!currentNode) { alert("Выберите узел"); return; }
  // Node's stats collector reset endpoint requires token — not available in browser
  // We just show a placeholder message
  alert("Для сброса статистики выполните на сервере:\n\nkill $(pgrep -f statsCollector) && rm /root/stats.db && python3 /root/statsCollector_native.py &");
};

window.downloadConfig = async (clientId, clientName) => {
  try {
    const res    = await fetch(`${PANEL_API}/api/wireguard/client/${clientId}/configuration`);
    const config = await res.text();
    const blob   = new Blob([config], { type: "text/plain" });
    const url    = URL.createObjectURL(blob);
    const a      = document.createElement("a");
    a.href       = url;
    a.download   = `${clientName || "client"}.conf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert("Ошибка скачивания конфига");
  }
};

// ─── Utilities ────────────────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDate(ts) {
  if (!ts || ts === 0) return "Никогда";
  return new Date(ts * 1000).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function fetchTimeout(url, opts = {}, ms = 6000) {
  const ctrl = new AbortController();
  const id   = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } finally {
    clearTimeout(id);
  }
}
