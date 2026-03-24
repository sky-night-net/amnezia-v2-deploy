const HUB_API = `${window.location.protocol}//${window.location.hostname}:9292`;
let current_node = null;
let API_BASE = '';
let STATS_API = '';
let sessionToken = localStorage.getItem('awg_v3_session');
let trafficChart, clientsChart;

// --- DOM elements ---
const screens = {
    login: document.getElementById('login-screen'),
    dashboard: document.getElementById('dashboard-screen')
};
const tabs = {
    clients: document.getElementById('tab-clients'),
    analytics: document.getElementById('tab-analytics'),
    settings: document.getElementById('tab-settings')
};
const navItems = document.querySelectorAll('.nav-item');
const loginBtn = document.getElementById('login-btn');
const logoutBtn = document.getElementById('logout-btn');
const passwordInput = document.getElementById('password');
const authError = document.getElementById('auth-error');
const clientsGrid = document.getElementById('clients-grid');

// --- Initialization ---
if (sessionToken) {
    showDashboard();
    loadNodes();
}

async function loadNodes() {
    try {
        const res = await fetch(`${HUB_API}/hub/nodes`);
        const nodes = await res.json();
        renderNodesList(nodes);
        if (nodes.length > 0 && !current_node) {
            selectNode(nodes[0]);
        }
    } catch (e) {
        console.error("Failed to load nodes", e);
    }
}

function renderNodesList(nodes) {
    const list = document.getElementById('nodes-list');
    list.innerHTML = '';
    nodes.forEach(node => {
        const item = document.createElement('div');
        item.className = `node-item ${current_node && current_node.name === node.name ? 'active' : ''}`;
        item.innerHTML = `
            <span class="node-status-dot"></span>
            <span class="node-name">${node.name}</span>
        `;
        item.onclick = () => selectNode(node);
        list.appendChild(item);
    });
}

let hub_stats_cache = {};

async function pollHubStats() {
    try {
        const res = await fetch(`${HUB_API}/hub/stats`);
        hub_stats_cache = await res.json();
        if (current_node) renderNodeStats(current_node.name);
    } catch (e) {
        console.error("Hub polling error", e);
    }
}

// Start polling
setInterval(pollHubStats, 5000);

function selectNode(node) {
    current_node = node;
    API_BASE = `${window.location.protocol}//${node.ip}:4466`;
    
    document.querySelector('.mono').textContent = node.ip;
    loadClients();
    renderNodeStats(node.name);
}

function renderNodeStats(node_name) {
    const stats = hub_stats_cache[node_name];
    if (!stats) return;
    
    // Logic to update UI with stats.data (which contains the AWG dump)
    // This will replace the previous direct fetch logic.
    updateUIWithNodeData(stats.data);
}

async function handleLogin() {
    const password = passwordInput.value;
    if (!password) return;
    loginBtn.disabled = true;
    loginBtn.textContent = 'ПРОВЕРКА...';
    authError.classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE}/api/session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        if (response.ok) {
            localStorage.setItem('awg_v3_session', 'true');
            showDashboard();
        } else throw new Error('Unauthorized');
    } catch (err) {
        authError.classList.remove('hidden');
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'ВОЙТИ';
    }
}

loginBtn.addEventListener('click', handleLogin);
passwordInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleLogin(); });
logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('awg_v3_session');
    location.reload();
});

// --- Navigation ---
navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const target = item.getAttribute('data-tab');
        navItems.forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        Object.values(tabs).forEach(t => t.classList.remove('active'));
        tabs[target].classList.add('active');

        if (target === 'analytics') loadAnalytics('hour');
    });
});

// --- Formatting ---
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(timestamp) {
    if (!timestamp) return 'Никогда';
    const d = new Date(timestamp * 1000);
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// --- Data Loading ---
async function fetchWithTimeout(resource, options = {}) {
    const { timeout = 5000 } = options;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(resource, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
}

let clientsData = [];
let liveStats = {};

async function loadClients() {
    if (!current_node) return;
    try {
        // Fetch clients list from main DB (node management)
        const resClients = await fetch(`${API_BASE}/api/wireguard/client`);
        clientsData = await resClients.json();

        // Use cached stats from the Hub instead of direct node fetch
        liveStats = (hub_stats_cache[current_node.name] || {}).data || {};

        renderClientsGrid();
    } catch (err) {
        clientsGrid.innerHTML = '<p class="error-msg">Ошибка связи с сервером</p>';
    }
}

function renderClientsGrid() {
    clientsGrid.innerHTML = '';
    const subtitle = document.getElementById('clients-subtitle');

    let activeCount = 0;

    clientsData.forEach(client => {
        // Find matching live stats by IP or rely on ID mapping if possible (we match by IP here)
        let cStats = null;
        for (const pk in liveStats) {
            const cleanIp = client.address.split('/')[0];
            if (liveStats[pk].allowed_ips.some(ip => ip.startsWith(cleanIp))) {
                cStats = liveStats[pk];
                break;
            }
        }

        const isOnline = cStats ? cStats.online : false;
        if (isOnline) activeCount++;

        const rx = cStats ? formatBytes(cStats.rx) : '—';
        const tx = cStats ? formatBytes(cStats.tx) : '—';
        const hs = cStats ? formatDate(cStats.latest_handshake) : '—';

        const card = document.createElement('div');
        card.className = 'client-card glass-card';
        card.innerHTML = `
            <div class="card-top">
                <div>
                    <div class="card-name">${client.name}</div>
                    <div class="card-ip">${client.address}</div>
                </div>
                <div class="status-badge ${isOnline ? 'online' : 'offline'}">
                    <span class="status-dot"></span> ${isOnline ? 'Online' : 'Offline'}
                </div>
            </div>
            <div class="card-traffic">
                <div class="card-traffic-item"><div class="card-traffic-label">↓ Получено</div><div class="card-traffic-val">${rx}</div></div>
                <div class="card-traffic-item"><div class="card-traffic-label">↑ Отправлено</div><div class="card-traffic-val">${tx}</div></div>
            </div>
            <div class="card-actions">
                <button class="card-btn" onclick="openDetail('${client.id}')">Детали</button>
                <button class="card-btn" onclick="showQRCode('${client.id}')">QR-код</button>
                <button class="card-btn" onclick="downloadConfig('${client.id}', '${client.name}')">Скачать</button>
            </div>
        `;
        clientsGrid.appendChild(card);
    });

    subtitle.innerHTML = `Всего: <strong>${clientsData.length}</strong> | Активно: <strong style="color:var(--green)">${activeCount}</strong>`;
}

// Periodically update clients tab
setInterval(() => {
    if (tabs.clients.classList.contains('active')) loadClients();
}, 10000);

// --- Analytics ---
function initCharts() {
    const commonOptions = {
        chart: { type: 'area', height: 260, toolbar: { show: false }, background: 'transparent' },
        theme: { mode: 'dark' },
        stroke: { curve: 'smooth', width: 2 },
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05, stops: [0, 90, 100] } },
        dataLabels: { enabled: false },
        grid: { borderColor: 'rgba(255,255,255,0.05)', strokeDashArray: 4 },
        xaxis: { type: 'datetime', labels: { style: { colors: '#6a7080' } }, axisBorder: { show: false }, axisTicks: { show: false } },
        yaxis: { labels: { formatter: (val) => formatBytes(val), style: { colors: '#6a7080' } } },
        tooltip: { theme: 'dark', y: { formatter: (val) => formatBytes(val) } }
    };

    trafficChart = new ApexCharts(document.querySelector("#traffic-chart"), {
        ...commonOptions,
        colors: ['#39d98a', '#e63946'],
        series: [{ name: 'Получено (RX)', data: [] }, { name: 'Отправлено (TX)', data: [] }]
    });
    trafficChart.render();

    clientsChart = new ApexCharts(document.querySelector("#clients-chart"), {
        chart: { type: 'bar', height: 260, toolbar: { show: false }, background: 'transparent' },
        theme: { mode: 'dark' },
        plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
        dataLabels: { enabled: false },
        colors: ['#e63946'],
        xaxis: { labels: { formatter: (val) => formatBytes(val), style: { colors: '#6a7080' } } },
        yaxis: { labels: { style: { colors: '#f0f0f5' } } },
        series: [{ name: 'Общий трафик', data: [] }]
    });
    clientsChart.render();
}

async function loadAnalytics(period) {
    try {
        const res = await fetch(`${HUB_API}/hub/stats`);
        const allNodesStats = await res.json();
        
        // If we are looking at a specific node, filter data
        const summary = current_node && allNodesStats[current_node.name] ? allNodesStats[current_node.name].data : {};

        let txTotal = 0, rxTotal = 0, active = 0;
        const topClients = [];

        for (const pk in summary) {
            rxTotal += summary[pk].rx_total;
            txTotal += summary[pk].tx_total;
            if (summary[pk].online) active++;

            // Map pubkey to name if possible
            let cName = pk.substring(0, 8) + '...';
            clientsData.forEach(c => {
                const ls = summary[pk];
                const cleanIp = c.address.split('/')[0];
                if (ls && ls.allowed_ips.some(ip => ip.startsWith(cleanIp))) cName = c.name;
            });

            topClients.push({
                x: cName,
                y: summary[pk].rx_total + summary[pk].tx_total
            });
        }

        document.getElementById('total-rx').textContent = formatBytes(rxTotal);
        document.getElementById('total-tx').textContent = formatBytes(txTotal);
        document.getElementById('active-count').textContent = active;

        topClients.sort((a, b) => b.y - a.y);
        clientsChart.updateSeries([{ name: 'Трафик', data: topClients.slice(0, 5) }]);

        const historyRes = await fetch(`${STATS_API}/stats/history`);
        const historyData = await historyRes.json();
        trafficChart.updateSeries([
            { name: 'Получено', data: historyData.rx },
            { name: 'Отправлено', data: historyData.tx }
        ]);

    } catch (e) {
        console.warn('Analytics failed', e);
    }
}



document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        loadAnalytics(btn.getAttribute('data-period'));
    });
});

// --- Modals ---
const newClientModal = document.getElementById('modal');
const newClientInput = document.getElementById('new-client-name');
document.getElementById('add-client-btn').onclick = () => {
    newClientModal.classList.remove('hidden');
    newClientInput.focus();
};
document.getElementById('modal-close').onclick = () => newClientModal.classList.add('hidden');
document.getElementById('cancel-modal').onclick = () => newClientModal.classList.add('hidden');

document.getElementById('confirm-create').onclick = async () => {
    const name = newClientInput.value.trim();
    if (!name) return;
    try {
        await fetch(`${API_BASE}/api/wireguard/client`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        newClientModal.classList.add('hidden');
        newClientInput.value = '';
        loadClients();
    } catch (e) {
        alert('Ошибка создания');
    }
};

// Detail Modal
const detailModal = document.getElementById('detail-modal');
let currentDetailId = null;

window.openDetail = (clientId) => {
    const client = clientsData.find(c => c.id === clientId);
    if (!client) return;

    currentDetailId = clientId;
    document.getElementById('detail-name').textContent = client.name;
    document.getElementById('detail-ip').textContent = client.address;

    let cStats = null;
    const cleanIp = client.address.split('/')[0];
    for (const pk in liveStats) {
        if (liveStats[pk].allowed_ips.some(ip => ip.startsWith(cleanIp))) {
            cStats = liveStats[pk];
            break;
        }
    }

    document.getElementById('detail-rx').textContent = cStats ? formatBytes(cStats.rx) : '—';
    document.getElementById('detail-tx').textContent = cStats ? formatBytes(cStats.tx) : '—';
    document.getElementById('detail-hs').textContent = cStats ? formatDate(cStats.latest_handshake) : '—';

    detailModal.classList.remove('hidden');

    if (window.detailChartObj) {
        window.detailChartObj.destroy();
        window.detailChartObj = null;
    }
    document.querySelector("#detail-chart").innerHTML = '';
};

document.getElementById('detail-close').onclick = () => detailModal.classList.add('hidden');
document.getElementById('detail-download').onclick = () => {
    const c = clientsData.find(c => c.id === currentDetailId);
    if (c) downloadConfig(c.id, c.name);
};
document.getElementById('detail-qr').onclick = () => showQRCode(currentDetailId);
document.getElementById('detail-delete').onclick = async () => {
    if (!confirm('Точно удалить?')) return;
    await fetch(`${API_BASE}/api/wireguard/client/${currentDetailId}`, { method: 'DELETE' });
    detailModal.classList.add('hidden');
    loadClients();
};

// QR Modal
const qrModal = document.getElementById('qr-modal');
const qrContainer = document.getElementById('qr-container');

window.showQRCode = async (clientId) => {
    qrContainer.innerHTML = '<span style="color:#666">Загрузка...</span>';
    qrModal.classList.remove('hidden');
    try {
        const response = await fetch(`${API_BASE}/api/wireguard/client/${clientId}/qrcode.svg`);
        if (!response.ok) throw new Error('Failed to fetch QR');
        const svg = await response.text();
        qrContainer.innerHTML = svg;

        // Make SVG fit nicely
        const svgEl = qrContainer.querySelector('svg');
        if (svgEl) {
            svgEl.style.width = '100%';
            svgEl.style.height = 'auto';
            svgEl.style.display = 'block';
        }
    } catch (e) {
        qrContainer.innerHTML = '<span style="color:var(--red)">Ошибка загрузки QR</span>';
    }
};

document.getElementById('qr-close').onclick = () => qrModal.classList.add('hidden');
// Close modal when clicking outside
qrModal.addEventListener('click', (e) => {
    if (e.target === qrModal) qrModal.classList.add('hidden');
});

// --- Settings ---
window.resetAnalytics = async () => {
    if (!confirm('Вы уверены, что хотите полностью очистить историю трафика? Это действие необратимо.')) return;

    try {
        const res = await fetch(`${STATS_API}/stats/reset`);
        const result = await res.json();
        if (result.status === 'ok') {
            alert('Аналитика успешно сброшена');
            if (tabs.analytics.classList.contains('active')) loadAnalytics('hour');
        } else {
            throw new Error(result.message);
        }
    } catch (e) {
        alert('Ошибка при сбросе: ' + e.message);
    }
};

window.downloadConfig = async (clientId, clientName) => {
    try {
        const response = await fetch(`${API_BASE}/api/wireguard/client/${clientId}/configuration`);
        const config = await response.text();

        const blob = new Blob([config], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${clientName}.conf`;
        a.click();
    } catch (e) {
        alert('Ошибка при скачивании');
    }
};
