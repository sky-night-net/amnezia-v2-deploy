#!/usr/bin/env python3
"""
Amnezia Stats Collector — runs on each VPN node, collects AWG/WireGuard traffic stats.

Start: STATS_TOKEN=<your_token> nohup python3 statsCollector_native.py &
Or use: systemctl (see README for service file)
"""

import subprocess
import sqlite3
import time
import json
import threading
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Configuration ───────────────────────────────────────────────────────────
DB_PATH    = os.getenv("STATS_DB",    "/root/stats.db")
AUTH_TOKEN = os.getenv("STATS_TOKEN", "default_secret_change_me")
LISTEN_PORT = int(os.getenv("STATS_PORT", "9191"))
COLLECT_INTERVAL = 60  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("stats")

# ─── Database ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS traffic (
            ts     INTEGER NOT NULL,
            pubkey TEXT    NOT NULL,
            rx     INTEGER NOT NULL DEFAULT 0,
            tx     INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_ts     ON traffic(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pubkey ON traffic(pubkey)")
    conn.commit()
    conn.close()
    log.info(f"Database ready at {DB_PATH}")

# ─── AWG data collection ─────────────────────────────────────────────────────

def parse_awg_dump(raw: str) -> list:
    """Parse `awg show all dump` output into a list of peer dicts."""
    peers = []
    for line in raw.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        # Skip interface header lines (no allowed IPs with /)
        if "/" not in parts[4]:
            continue
        try:
            peers.append({
                "pubkey":           parts[1],
                "allowed_ips":      parts[4].split(","),
                "latest_handshake": int(parts[5]) if parts[5].isdigit() else 0,
                "rx":               int(parts[6]) if parts[6].isdigit() else 0,
                "tx":               int(parts[7]) if parts[7].isdigit() else 0,
            })
        except (ValueError, IndexError):
            continue
    return peers


def get_live_stats() -> dict:
    """Return current AWG stats dict keyed by pubkey."""
    try:
        raw = subprocess.check_output(
            "awg show all dump 2>/dev/null",
            shell=True, timeout=10
        ).decode(errors="replace")
    except subprocess.SubprocessError:
        return {}

    now    = int(time.time())
    result = {}
    for p in parse_awg_dump(raw):
        pk          = p["pubkey"]
        last_hs     = p["latest_handshake"]
        is_online   = (now - last_hs) < 300 if last_hs > 0 else False
        result[pk]  = {
            "online":           is_online,
            "latest_handshake": last_hs,
            "rx":               p["rx"],
            "tx":               p["tx"],
            "rx_total":         p["rx"],
            "tx_total":         p["tx"],
            "allowed_ips":      p["allowed_ips"],
        }
    return result


def collect_loop():
    """Background thread: persist traffic snapshots to SQLite every COLLECT_INTERVAL seconds."""
    while True:
        try:
            stats = get_live_stats()
            if stats:
                conn = sqlite3.connect(DB_PATH)
                c    = conn.cursor()
                ts   = int(time.time())
                for pk, d in stats.items():
                    c.execute(
                        "INSERT INTO traffic(ts, pubkey, rx, tx) VALUES (?, ?, ?, ?)",
                        (ts, pk, d["rx"], d["tx"])
                    )
                conn.commit()
                conn.close()
        except Exception as e:
            log.error(f"Collect error: {e}")
        time.sleep(COLLECT_INTERVAL)

# ─── HTTP Handler ────────────────────────────────────────────────────────────

class StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default HTTP logging noise
        pass

    def _send_json(self, code: int, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        token = self.headers.get("X-Auth-Token", "")
        if token == AUTH_TOKEN:
            return True
        log.warning(f"Unauthorized request from {self.client_address[0]}")
        self._send_json(401, {"error": "Unauthorized"})
        return False

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Auth-Token, Content-Type")
        self.end_headers()

    def do_GET(self):
        if not self._check_auth():
            return

        path = urlparse(self.path).path

        if path in ("/stats/live", "/stats/summary"):
            self._send_json(200, get_live_stats())

        elif path == "/stats/history":
            self._handle_history()

        elif path == "/stats/reset":
            self._handle_reset()

        elif path == "/stats/health":
            self._send_json(200, {"status": "ok", "ts": int(time.time())})

        else:
            self._send_json(404, {"error": "Unknown endpoint"})

    def _handle_history(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c    = conn.cursor()
            # Last 24 hours, grouped by minute bucket
            limit_ts = int(time.time()) - 86400
            c.execute("""
                SELECT (ts / 60) * 60000 AS bucket, SUM(rx), SUM(tx)
                FROM traffic
                WHERE ts > ?
                GROUP BY bucket
                ORDER BY bucket ASC
            """, (limit_ts,))
            rows  = c.fetchall()
            conn.close()

            rx_series, tx_series = [], []
            prev_rx, prev_tx = None, None
            for bucket, sum_rx, sum_tx in rows:
                if prev_rx is None:
                    prev_rx, prev_tx = sum_rx, sum_tx
                    continue
                delta_rx = max(0, sum_rx - prev_rx)
                delta_tx = max(0, sum_tx - prev_tx)
                rx_series.append([bucket, delta_rx])
                tx_series.append([bucket, delta_tx])
                prev_rx, prev_tx = sum_rx, sum_tx

            self._send_json(200, {"rx": rx_series, "tx": tx_series})
        except Exception as e:
            log.error(f"History error: {e}")
            self._send_json(500, {"rx": [], "tx": []})

    def _handle_reset(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c    = conn.cursor()
            c.execute("DELETE FROM traffic")
            conn.commit()
            conn.close()
            self._send_json(200, {"status": "ok"})
        except Exception as e:
            log.error(f"Reset error: {e}")
            self._send_json(500, {"status": "error"})

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    threading.Thread(target=collect_loop, daemon=True).start()
    log.info(f"Stats API running on port {LISTEN_PORT}")
    log.info(f"Auth token: {'(set)' if AUTH_TOKEN != 'default_secret_change_me' else '(DEFAULT — CHANGE IT!)'}")
    try:
        HTTPServer(("0.0.0.0", LISTEN_PORT), StatsHandler).serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
