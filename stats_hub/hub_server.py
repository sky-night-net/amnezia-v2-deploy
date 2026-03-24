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
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request, Response, redirect, render_template, render_template_string, session
from flask_cors import CORS
from collections import deque
import functools

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
HUB_PASSWORD = os.getenv("HUB_PASSWORD", "admin")

app.secret_key = os.getenv("HUB_SECRET", "super-secret-hub-key")

# In-memory state
node_stats: dict = {}
history_size = 60
traffic_history = {
    "down": deque([0]*history_size, maxlen=history_size),
    "up":   deque([0]*history_size, maxlen=history_size)
}
_lock = threading.Lock()

# ─── Database ───────────────────────────────────────────────────────────────
DB_FILE = os.getenv("HUB_DB", "amnezia_ui.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                ip TEXT UNIQUE,
                port INTEGER,
                token TEXT,
                status TEXT DEFAULT 'Offline',
                mode TEXT DEFAULT 'HTTP',
                last_seen INTEGER,
                settings TEXT
            );
            CREATE TABLE IF NOT EXISTS inbounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                protocol TEXT,
                port INTEGER,
                settings TEXT,
                FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inbound_id INTEGER,
                username TEXT,
                secret TEXT,
                traffic_limit INTEGER, -- in bytes
                traffic_used INTEGER DEFAULT 0,
                expiry_time INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(inbound_id) REFERENCES inbounds(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS traffic_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT, -- 'node' or 'client'
                target_id INTEGER,
                timestamp INTEGER,
                down INTEGER, -- in bytes
                up INTEGER
            );
        """)
    log.info(f"Database initialized: {DB_FILE}")

def migrate_from_json():
    """Import nodes from hub_config.json if it exists and DB is empty."""
    if not os.path.exists(CONFIG_FILE):
        return
    
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        if count > 0:
            return  # Already has data
        
        try:
            with open(CONFIG_FILE, "r") as f:
                nodes = json.load(f)
                for n in nodes:
                    conn.execute(
                        "INSERT OR IGNORE INTO nodes (name, ip, token) VALUES (?, ?, ?)",
                        (n.get("name"), n.get("ip"), n.get("token"))
                    )
            log.info(f"Migrated {len(nodes)} nodes from JSON to SQLite")
        except Exception as e:
            log.error(f"Migration failed: {e}")

# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_nodes() -> list:
    """Load nodes from DB."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM nodes").fetchall()
        return [dict(r) for r in rows]

def upsert_node(new_node: dict):
    """Add or update a node in DB."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO nodes (name, ip, token, last_seen) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                name = excluded.name,
                token = excluded.token,
                last_seen = excluded.last_seen
        """, (new_node.get("name"), new_node.get("ip"), new_node.get("token"), int(time.time())))

# ─── Polling thread ──────────────────────────────────────────────────────────

def poll_nodes():
    """Background thread: query each node's stats API every POLL_SEC seconds."""
    while True:
        nodes = load_nodes()
        for node in nodes:
            name  = node.get("name", node.get("ip", "unknown"))
            ip    = node.get("ip", "")
            token = node.get("token", "")
            node_id = node.get("id")

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

        # 3. Update aggregate history & DB
        total_down_val = 0.0
        total_up_val = 0.0
        with _lock:
            for n in node_stats.values():
                d = n.get("data", {})
                for k in ["net_in", "net_out"]:
                    val_str = str(d.get(k, "0"))
                    try:
                        num = float(val_str.split()[0])
                        if "MB" in val_str: num *= 1024
                        if k == "net_in":
                            total_down_val = total_down_val + float(num)
                        else:
                            total_up_val = total_up_val + float(num)
                    except (ValueError, IndexError, TypeError):
                        pass
            
            traffic_history["down"].append(round(float(total_down_val / 1024), 2))
            traffic_history["up"].append(round(float(total_up_val / 1024), 2))

        # 4. Save to DB history (every polling cycle for now)
        try:
            with get_db() as conn:
                now_ts = int(time.time())
                for name, info in node_stats.items():
                    d = info.get("data", {})
                    # Find node_id if not present
                    node_row = conn.execute("SELECT id FROM nodes WHERE ip = ?", (info['ip'],)).fetchone()
                    if node_row:
                        node_id = node_row['id']
                        # Update status
                        conn.execute("UPDATE nodes SET status=?, mode=?, last_seen=? WHERE id=?", 
                                   (info['status'], info['mode'], info['last_seen'], node_id))
                        # Save traffic point (simple diff or direct)
                        # For now, just save current speed as history point
                        conn.execute("INSERT INTO traffic_history (target_type, target_id, timestamp, down, up) VALUES (?, ?, ?, ?, ?)",
                                   ('node', node_id, now_ts, d.get("net_in_bytes", 0), d.get("net_out_bytes", 0)))
        except Exception as e:
            log.error(f"DB update failed: {e}")

        time.sleep(POLL_SEC)

# ─── Auth Decorator ──────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/hub/api/"):
                return jsonify({"status": "error", "message": "Unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == HUB_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        return render_template_string("<h2>Invalid Password</h2><a href='/login'>Try again</a>")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Login — Amnezia Hub</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>body { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; }</style>
    </head>
    <body class="flex items-center justify-center min-h-screen">
        <div class="bg-slate-800 p-8 rounded-2xl shadow-2xl w-96 border border-slate-700">
            <h1 class="text-2xl font-bold mb-6 text-center text-sky-400">Amnezia Hub Login</h1>
            <form method="POST">
                <input type="password" name="password" placeholder="Password" required 
                       class="w-full bg-slate-900 border-none rounded-lg px-4 py-3 mb-4 focus:ring-2 focus:ring-sky-500 outline-none">
                <button type="submit" class="w-full bg-sky-500 hover:bg-sky-600 py-3 rounded-lg font-bold transition-all">Login</button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/login")

def get_base_template(content, active_page='dashboard'):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amnezia Control Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; overflow-x: hidden; }}
        .glass {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }}
        .neon-border {{ box-shadow: 0 0 15px rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.2); }}
        .sidebar-item {{ transition: all 0.2s; border-radius: 0.75rem; }}
        .sidebar-item:hover {{ background: rgba(56, 189, 248, 0.1); color: #38bdf8; }}
        .sidebar-item.active {{ background: #38bdf8; color: white; box-shadow: 0 0 20px rgba(56, 189, 248, 0.3); }}
    </style>
</head>
<body class="flex min-h-screen">
    <!-- Sidebar -->
    <aside class="w-64 glass border-r border-slate-800 p-6 flex flex-col fixed h-full">
        <div class="flex items-center space-x-3 mb-10">
            <div class="w-10 h-10 bg-sky-500 rounded-lg flex items-center justify-center neon-border">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            </div>
            <h1 class="text-xl font-bold tracking-tight">Amnezia <span class="text-sky-400">UI</span></h1>
        </div>
        
        <nav class="flex-1 space-y-2">
            <a href="/" class="sidebar-item flex items-center space-x-3 px-4 py-3 {'active' if active_page=='dashboard' else 'text-slate-400'}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
                <span class="font-medium">Dashboard</span>
            </a>
            <a href="/inbounds" class="sidebar-item flex items-center space-x-3 px-4 py-3 {'active' if active_page=='inbounds' else 'text-slate-400'}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                <span class="font-medium">Inbounds</span>
            </a>
            <a href="/clients" class="sidebar-item flex items-center space-x-3 px-4 py-3 {'active' if active_page=='clients' else 'text-slate-400'}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                <span class="font-medium">Clients</span>
            </a>
        </nav>
        
        <div class="pt-6 border-t border-slate-800">
            <a href="/logout" class="flex items-center space-x-3 px-4 py-3 text-slate-500 hover:text-red-400 transition-colors">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                <span class="font-medium">Logout</span>
            </a>
        </div>
    </aside>

    <!-- Content -->
    <main class="flex-1 ml-64 p-8">
        {content}
    </main>
</body>
</html>
"""

@app.route("/")
@login_required
def index():
    """Premium Dashboard (v2.0)."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM nodes").fetchall()
        ui_stats = {}
        for n in rows:
            ui_stats[n['name']] = {
                "ip": n['ip'],
                "status": n['status'],
                "mode": n['mode'],
                "last_seen": n['last_seen'],
                "data": json.loads(n['settings'] or '{}')
            }

    content = render_template_string("""
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Nodes Total</p>
                <span class="text-4xl font-bold mt-2 block">{{ stats|length }}</span>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Aggregate Down</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold" id="total-down">0.0</span>
                    <span class="text-slate-400 text-sm mb-1">MB/s</span>
                </div>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Aggregate Up</p>
                <div class="flex items-end space-x-2 mt-2">
                    <span class="text-4xl font-bold" id="total-up">0.0</span>
                    <span class="text-slate-400 text-sm mb-1">MB/s</span>
                </div>
            </div>
            <div class="glass p-6 rounded-2xl">
                <p class="text-slate-400 text-xs font-bold uppercase tracking-wider">Status</p>
                <span class="text-xl font-bold mt-2 block text-green-400">System Healthy</span>
            </div>
        </div>

        <div class="glass p-6 rounded-2xl mb-8">
            <h2 class="text-lg font-semibold mb-6 flex items-center">
                <span class="w-2 h-2 bg-sky-500 rounded-full mr-2"></span> Network Throughput
            </h2>
            <div class="h-[260px] w-full"><canvas id="trafficChart"></canvas></div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {% for name, node in stats.items() %}
            <div class="glass p-6 rounded-2xl hover:neon-border transition-all">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="font-bold text-lg text-sky-400">{{ name }}</h3>
                        <p class="text-xs text-slate-400 font-mono">{{ node.ip }}</p>
                    </div>
                    <span class="px-3 py-1 bg-sky-500/10 text-sky-400 text-[10px] font-bold rounded-full border border-sky-500/20 uppercase">{{ node.status }}</span>
                </div>
                <div class="flex justify-between text-sm py-2">
                    <span class="text-slate-400">CPU/RAM:</span>
                    <span class="font-bold">{{ node.data.cpu or '0' }}% / {{ node.data.mem or '0' }}%</span>
                </div>
                <div class="flex justify-between text-sm py-2">
                    <span class="text-slate-400">Traffic:</span>
                    <span class="font-medium">↓{{ node.data.net_in or '0' }} | ↑{{ node.data.net_out or '0' }}</span>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <script>
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
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' } }, x: { display: false } }
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
            setInterval(updateStats, 5000); updateStats();
        </script>
    """, stats=ui_stats)
    return get_base_template(content, 'dashboard')

@app.route("/inbounds")
@login_required
def inbounds_page():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM nodes").fetchall()
        nodes = [dict(r) for r in rows]
    
    content = render_template_string("""
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold">Inbounds Management</h2>
            <button class="bg-sky-500 hover:bg-sky-600 px-4 py-2 rounded-lg text-sm font-bold transition-all">+ Add Node</button>
        </div>
        <div class="glass rounded-2xl overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-slate-800/50 text-slate-400 text-xs uppercase font-bold">
                    <tr>
                        <th class="px-6 py-4">Node Name</th>
                        <th class="px-6 py-4">IP Address</th>
                        <th class="px-6 py-4">Status</th>
                        <th class="px-6 py-4">Protocol</th>
                        <th class="px-6 py-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800">
                    {% for n in nodes %}
                    <tr class="hover:bg-slate-800/30 transition-colors">
                        <td class="px-6 py-4 font-semibold text-sky-400">{{ n.name }}</td>
                        <td class="px-6 py-4 font-mono text-xs">{{ n.ip }}</td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border border-sky-500/20 bg-sky-500/5 text-sky-400">{{ n.status }}</span>
                        </td>
                        <td class="px-6 py-4 text-sm">{{ n.mode }}</td>
                        <td class="px-6 py-4 text-right space-x-2">
                            <button class="text-xs text-slate-400 hover:text-white">Edit</button>
                            <button class="text-xs text-red-400 hover:text-red-300">Remove</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    """, nodes=nodes)
    return get_base_template(content, 'inbounds')

@app.route("/clients")
@login_required
def clients_page():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM clients").fetchall()
        clients = [dict(r) for r in rows]
    
    content = render_template_string("""
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold">Clients management</h2>
            <button class="bg-sky-500 hover:bg-sky-600 px-4 py-2 rounded-lg text-sm font-bold transition-all">+ Add Client</button>
        </div>
        <div class="glass rounded-2xl overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-slate-800/50 text-slate-400 text-xs uppercase font-bold">
                    <tr>
                        <th class="px-6 py-4">User</th>
                        <th class="px-6 py-4">Limit</th>
                        <th class="px-6 py-4">Used</th>
                        <th class="px-6 py-4">Expiry</th>
                        <th class="px-6 py-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800">
                    {% for c in clients %}
                    <tr class="hover:bg-slate-800/30 transition-colors">
                        <td class="px-6 py-4 font-semibold">{{ c.username }}</td>
                        <td class="px-6 py-4 text-sm">{{ c.traffic_limit or 'Unlimited' }}</td>
                        <td class="px-6 py-4 text-sm">{{ c.traffic_used }}</td>
                        <td class="px-6 py-4 text-sm text-slate-400">{{ c.expiry_time or 'Never' }}</td>
                        <td class="px-6 py-4 text-right space-x-2">
                            <button class="text-xs text-sky-400 hover:text-sky-300">QR Code</button>
                            <button class="text-xs text-red-400 hover:text-red-300">Delete</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    """, clients=clients)
    return get_base_template(content, 'clients')

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

    with get_db() as conn:
        conn.execute("DELETE FROM nodes WHERE ip = ?", (ip,))
    
    with _lock:
        to_del = [name for name, info in node_stats.items() if info.get("ip") == ip]
        for name in to_del:
            node_stats.pop(name, None)

    return jsonify({"status": "ok", "message": f"Node {ip} removed"})


# ─── Inbounds & Clients API ──────────────────────────────────────────────────

@app.route("/hub/api/inbounds", methods=["GET"])
@login_required
def api_list_inbounds():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM inbounds").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route("/hub/api/clients", methods=["GET"])
@login_required
def api_list_clients():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM clients").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route("/hub/api/clients/add", methods=["POST"])
@login_required
def api_add_client():
    data = request.get_json(force=True, silent=True) or {}
    inbound_id = data.get("inbound_id")
    username = data.get("username")
    if not inbound_id or not username:
        return jsonify({"status": "error", "message": "inbound_id and username required"}), 400
    
    with get_db() as conn:
        conn.execute("INSERT INTO clients (inbound_id, username, secret) VALUES (?, ?, ?)",
                   (inbound_id, username, data.get("secret", "")))
    return jsonify({"status": "ok", "message": "Client added"})

@app.errorhandler(404)
def not_found(_):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    log.error(f"Internal error: {e}")
    return jsonify({"status": "error", "message": "Internal server error"}), 500

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"Amnezia Master Hub v2.0 starting on port {PORT}")
    
    init_db()
    migrate_from_json()

    log.info(f"Poll interval: {POLL_SEC}s")

    # Start background poller
    t = threading.Thread(target=poll_nodes, daemon=True)
    t.start()

    # Start Flask (production mode via gunicorn is recommended, but Flask works fine for small setups)
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
