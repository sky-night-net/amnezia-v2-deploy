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

from flask import Flask, jsonify, request, Response, redirect, render_template_string
from flask_cors import CORS

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

        time.sleep(POLL_SEC)

# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Redirect to stats or show simple UI."""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Amnezia V2 Master Hub</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, sans-serif; background: #1a1b1e; color: #eee; padding: 20px; }
            .node { background: #25262b; border-radius: 8px; padding: 15px; margin-bottom: 20px; border: 1px solid #373a40; }
            .online { color: #40c057; } .offline { color: #fa5252; } .snmp { color: #228be6; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
            h1 { color: #fff; border-bottom: 1px solid #333; padding-bottom: 10px; }
            .stat { font-size: 0.9em; margin-top: 5px; color: #a5a5a5; }
            b { color: #fff; }
        </style>
    </head>
    <body>
        <h1>🔭 Amnezia V2 Master Hub</h1>
        <div class="grid">
        {% for name, node in stats.items() %}
            <div class="node">
                <h3>{{ name }} <span class="{{ node.status.lower() }}">●</span></h3>
                <div class="stat">IP: <b>{{ node.ip }}</b></div>
                <div class="stat">Status: <b>{{ node.status }}</b> (via {{ node.mode }})</div>
                {% if node.data %}
                    <div class="stat">CPU: {{ node.data.cpu or '—' }}% | RAM: {{ node.data.mem or '—' }}%</div>
                    <div class="stat">Traffic: ↓{{ node.data.net_in or '—' }} | ↑{{ node.data.net_out or '—' }}</div>
                {% endif %}
                <div class="stat">Updated: {{ node.last_seen | int }}</div>
            </div>
        {% endfor %}
        </div>
        <p style="text-align:center; font-size:0.8em; color:#555">Auto-refresh every 15s</p>
        <script>setTimeout(() => location.reload(), 15000);</script>
    </body>
    </html>
    """, stats=node_stats)

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
