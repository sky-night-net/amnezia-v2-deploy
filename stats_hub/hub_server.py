#!/usr/bin/env python3
"""
Amnezia Master Hub v3 — Central monitoring server for all VPN nodes.

Runs inside Docker, listens on port 9292.
Nodes register themselves via POST /hub/register after deployment.
"""

import json
import os
import time
import threading
import logging

from flask import Flask, jsonify, request, Response, redirect, render_template, render_template_string
from flask_cors import CORS
from collections import deque

try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ─── Setup ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("hub")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PORT        = int(os.getenv("HUB_PORT", "9292"))
CONFIG_FILE = os.getenv("HUB_CONFIG", "hub_config.json")
POLL_SEC    = int(os.getenv("POLL_INTERVAL", "15"))

# In-memory state
node_stats: dict = {}
history_size = 60
traffic_history = {
    "down": deque([0]*history_size, maxlen=history_size),
    "up":   deque([0]*history_size, maxlen=history_size)
}
_lock = threading.Lock()

# ─── Config helpers ──────────────────────────────────────────────────────────

def load_nodes() -> list:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_nodes(nodes: list):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(nodes, f, indent=2)
    except IOError as e:
        log.error(f"Cannot save config: {e}")


def upsert_node(new_node: dict):
    """Add or update a node by IP address."""
    nodes = load_nodes()
    updated = False
    result = []
    for n in nodes:
        if n.get("ip") == new_node.get("ip"):
            result.append(new_node)
            updated = True
        else:
            result.append(n)
    if not updated:
        result.append(new_node)
    save_nodes(result)

# ─── Polling thread ──────────────────────────────────────────────────────────

def poll_nodes():
    """Background thread: query each node's stats API every POLL_SEC seconds."""
    while True:
        nodes = load_nodes()
        for node in nodes:
            name  = node.get("name", node.get("ip", "unknown"))
            ip    = node.get("ip", "")
            token = node.get("token", "")

            if not ip:
                continue

            result = {
                "name":      name,
                "ip":        ip,
                "last_seen": int(time.time()),
                "status":    "Offline",
                "mode":      "—",
                "data":      {}
            }

            # 1. Try native HTTP stats collector (port 9191)
            if REQUESTS_AVAILABLE and token:
                try:
                    r = req_lib.get(
                        f"http://{ip}:9191/stats/live",
                        headers={"X-Auth-Token": token},
                        timeout=4
                    )
                    if r.status_code == 200:
                        result["status"] = "Online"
                        result["mode"]   = "HTTP"
                        result["data"]   = r.json()
                    elif r.status_code == 401:
                        result["status"] = "Auth Error"
                        result["mode"]   = "HTTP"
                except Exception:
                    pass  # Will fall through to SNMP / Offline

            # 2. If still Offline but node has SNMP, mark as SNMP
            if result["status"] == "Offline" and node.get("snmp"):
                result["status"] = "SNMP"
                result["mode"]   = "SNMP"

            with _lock:
                node_stats[name] = result

        # 3. Update aggregate history
        total_down = 0.0
        total_up = 0.0
        with _lock:
            for n in node_stats.values():
                d = n.get("data", {})
                # Try to parse strings like "1.2 MB/s" or "400 KB/s"
                for k, v in [("net_in", "down"), ("net_out", "up")]:
                    val_str = str(d.get(k, "0"))
                    try:
                        num = float(val_str.split()[0])
                        if "MB" in val_str: num *= 1024
                        if k == "net_in": total_down += float(num)
                        else: total_up += float(num)
                    except (ValueError, IndexError, TypeError): pass
            
            traffic_history["down"].append(round(total_down / 1024, 2))
            traffic_history["up"].append(round(total_up / 1024, 2))

        time.sleep(POLL_SEC)

# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Premium Dashboard."""
    return render_template_string(r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amnezia V2 Master Hub</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; }
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .neon-border { box-shadow: 0 0 15px rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.2); }
        .status-online { color: #4ade80; }
        .status-offline { color: #f87171; }
        .status-snmp { color: #38bdf8; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1e293b; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    </style>
</head>
<body class="min-h-screen pb-12">
    <header class="glass sticky top-0 z-50 px-6 py-4 flex items-center justify-between border-b border-slate-800">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 bg-sky-500 rounded-lg flex items-center justify-center neon-border">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            </div>
            <div>
                <h1 class="text-xl font-bold tracking-tight">Amnezia <span class="text-sky-400">Master Hub</span></h1>
                <p class="text-xs text-slate-400">Network monitoring & control</p>
            </div>
        </div>
        <div class="flex items-center space-x-6">
            <div class="hidden md:block text-right">
                <p class="text-[10px] uppercase text-slate-500 font-bold">Server Time</p>
                <p class="text-sm font-mono tracking-tighter" id="clock">--:--:--</p>
            </div>
            <button onclick="location.reload()" class="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg text-sm transition-all border border-slate-700">
                Refresh
            </button>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-6 space-y-8">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Nodes Total</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold">{{ stats|length }}</span>
                </div>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Aggregate Download</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold" id="total-down">0.0</span>
                    <span class="text-slate-400 text-sm mb-1">MB/s</span>
                </div>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Aggregate Upload</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold" id="total-up">0.0</span>
                    <span class="text-slate-400 text-sm mb-1">MB/s</span>
                </div>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Avg Latency</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold">--</span>
                    <span class="text-sky-400 text-sm mb-1">ms</span>
                </div>
            </div>
        </div>

        <div class="glass p-6 rounded-2xl">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-lg font-semibold flex items-center">
                    <span class="w-2 h-2 bg-sky-500 rounded-full mr-2"></span>
                    Network Throughput (Total)
                </h2>
            </div>
            <div class="h-[260px] w-full">
                <canvas id="trafficChart"></canvas>
            </div>
        </div>

        <div>
            <h2 class="text-xl font-bold mb-4">Connected Nodes</h2>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {% for name, node in stats.items() %}
                <div class="glass p-6 rounded-2xl hover:neon-border transition-all group">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center space-x-3">
                            <div class="w-12 h-12 bg-slate-800 rounded-xl flex items-center justify-center text-xl">🌐</div>
                            <div>
                                <h3 class="font-bold text-lg group-hover:text-sky-400 transition-colors">{{ name }}</h3>
                                <p class="text-xs text-slate-400 font-mono">{{ node.ip }}</p>
                            </div>
                        </div>
                        <span class="px-3 py-1 bg-sky-500/10 text-sky-400 text-[10px] font-bold rounded-full border border-sky-500/20 uppercase">
                            {{ node.status }}
                        </span>
                    </div>
                    
                    <div class="grid grid-cols-3 gap-4 border-y border-slate-800/50 py-4 my-4">
                        <div class="text-center">
                            <p class="text-[10px] uppercase tracking-wider text-slate-500">CPU</p>
                            <p class="text-lg font-bold">{{ node.data.cpu or '—' }}<span class="text-xs text-slate-500 font-normal">%</span></p>
                        </div>
                        <div class="text-center border-x border-slate-800/50">
                            <p class="text-[10px] uppercase tracking-wider text-slate-500">RAM</p>
                            <p class="text-lg font-bold">{{ node.data.mem or '—' }}<span class="text-xs text-slate-500 font-normal">%</span></p>
                        </div>
                        <div class="text-center">
                            <p class="text-[10px] uppercase tracking-wider text-slate-500">Mode</p>
                            <p class="text-lg font-bold text-sky-400">{{ node.mode }}</p>
                        </div>
                    </div>

                    <div class="flex justify-between items-center">
                        <div class="flex items-center space-x-4">
                            <div class="flex items-center">
                                <svg class="w-4 h-4 text-sky-400 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 14l-7 7m0 0l-7-7m7 7V3"></path></svg>
                                <span class="text-sm font-semibold">{{ node.data.net_in or '0' }}</span>
                            </div>
                            <div class="flex items-center">
                                <svg class="w-4 h-4 text-purple-400 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 10l7-7m0 0l7 7m-7-7v18"></path></svg>
                                <span class="text-sm font-semibold">{{ node.data.net_out or '0' }}</span>
                            </div>
                        </div>
                        <p class="text-[10px] text-slate-500 italic">Seen: {{ node.last_seen | int }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </main>

    <script>
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toTimeString().split(' ')[0];
        }, 1000);

        const ctx = document.getElementById('trafficChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array.from({length: 60}, (_, i) => i),
                datasets: [
                    { label: 'Download', data: [], borderColor: '#38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.1)', fill: true, tension: 0.4, borderWidth: 2, pointRadius: 0 },
                    { label: 'Upload', data: [], borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.1)', fill: true, tension: 0.4, borderWidth: 2, pointRadius: 0 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' } },
                    x: { display: false }
                }
            }
        });

        async function updateStats() {
            try {
                const r = await fetch('/hub/history');
                const d = await r.json();
                chart.data.datasets[0].data = d.down;
                chart.data.datasets[1].data = d.up;
                chart.update('none');
                
                if (d.down.length > 0) {
                    document.getElementById('total-down').innerText = d.down[d.down.length-1];
                    document.getElementById('total-up').innerText = d.up[d.up.length-1];
                }
            } catch(e) {}
        }
        setInterval(updateStats, 5000);
        updateStats();
    </script>
</body>
</html>
""", stats=node_stats)

@app.route("/hub/history")
def get_history():
    """Return traffic history for charts."""
    with _lock:
        return jsonify({
            "down": list(traffic_history["down"]),
            "up":   list(traffic_history["up"])
        })

@app.route("/hub/health")
def health():
    """Liveness probe."""
    return jsonify({"status": "ok", "uptime": int(time.time())})


@app.route("/hub/nodes", methods=["GET"])
def list_nodes():
    """Return the list of registered nodes."""
    return jsonify(load_nodes())


@app.route("/hub/stats", methods=["GET"])
def get_stats():
    """Return current stats for all nodes."""
    with _lock:
        return jsonify(node_stats)


@app.route("/hub/register", methods=["POST"])
def register_node():
    """Register or update a node. Called automatically by amnezia-cli after deployment."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    if not data.get("name") or not data.get("ip"):
        return jsonify({"status": "error", "message": "Fields 'name' and 'ip' are required"}), 400

    upsert_node(data)
    log.info(f"Node registered: {data['name']} ({data['ip']})")
    return jsonify({"status": "ok", "message": f"Node '{data['name']}' registered successfully"})


@app.route("/hub/remove", methods=["POST"])
def remove_node():
    """Remove a node by IP."""
    data = request.get_json(force=True, silent=True) or {}
    ip   = data.get("ip", "")
    if not ip:
        return jsonify({"status": "error", "message": "ip is required"}), 400

    nodes = [n for n in load_nodes() if n.get("ip") != ip]
    save_nodes(nodes)

    name = data.get("name", ip)
    with _lock:
        node_stats.pop(name, None)

    return jsonify({"status": "ok", "message": f"Node {ip} removed"})


@app.errorhandler(404)
def not_found(_):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    log.error(f"Internal error: {e}")
    return jsonify({"status": "error", "message": "Internal server error"}), 500

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"Amnezia Master Hub v3 starting on port {PORT}")
    log.info(f"Config file: {CONFIG_FILE}")
    log.info(f"Poll interval: {POLL_SEC}s")

    # Start background poller
    t = threading.Thread(target=poll_nodes, daemon=True)
    t.start()

    # Start Flask (production mode via gunicorn is recommended, but Flask works fine for small setups)
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
