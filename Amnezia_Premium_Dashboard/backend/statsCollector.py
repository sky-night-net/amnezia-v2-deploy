#!/usr/bin/env python3
"""
Amnezia WG Stats Collector + REST API
Collects traffic stats from WireGuard every 60s and serves them via HTTP.
"""
import subprocess, sqlite3, time, json, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

DB_PATH = '/root/stats.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS traffic (
        ts INTEGER,
        pubkey TEXT,
        rx INTEGER,
        tx INTEGER
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ts ON traffic(ts)')
    conn.commit()
    conn.close()

def collect():
    """Read wg show dump and save deltas to DB."""
    try:
        out = subprocess.check_output('docker exec amnezia-wg-easy wg show all dump 2>/dev/null', shell=True).decode()
    except:
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = int(time.time())
    
    for line in out.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 8:
            continue
        try:
            pubkey = parts[1]
            endpoint = parts[3]
            allowed_ips = parts[4]
            # Valid peers must have '/' in allowed_ips. The interface row does not.
            if '/' not in allowed_ips:
                continue
            
            rx = int(parts[6])
            tx = int(parts[7])
            c.execute('INSERT INTO traffic VALUES (?, ?, ?, ?)', (ts, pubkey, rx, tx))
        except (ValueError, IndexError):
            continue
    
    conn.commit()
    conn.close()

def get_history(pubkey, period_seconds):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    since = int(time.time()) - period_seconds
    
    rows = c.execute(
        'SELECT ts, rx, tx FROM traffic WHERE pubkey = ? AND ts > ? ORDER BY ts ASC',
        (pubkey, since)
    ).fetchall()
    conn.close()
    
    if len(rows) < 2:
        return []
    
    result = []
    for i in range(1, len(rows)):
        prev = rows[i-1]
        curr = rows[i]
        rx_delta = max(0, curr[1] - prev[1])
        tx_delta = max(0, curr[2] - prev[2])
        result.append({
            'ts': curr[0],
            'rx': rx_delta,
            'tx': tx_delta
        })
    return result

def get_all_clients_latest():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('''
        SELECT pubkey, rx, tx, MAX(ts) as last_ts
        FROM traffic
        GROUP BY pubkey
    ''').fetchall()
    conn.close()
    
    result = {}
    now = int(time.time())
    for row in rows:
        pubkey, rx, tx, last_ts = row
        result[pubkey] = {
            'rx_total': rx,
            'tx_total': tx,
            'last_seen': last_ts,
            'online': (now - last_ts) < 180
        }
    return result

def get_wg_peers():
    """Get live data from wg show."""
    try:
        out = subprocess.check_output('docker exec amnezia-wg-easy wg show all dump 2>/dev/null', shell=True).decode()
    except:
        return {}
    
    peers = {}
    for line in out.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 8:
            continue
        try:
            pubkey = parts[1]
            endpoint = parts[3]
            allowed_ips = parts[4]
            if '/' not in allowed_ips:
                continue
            
            latest_handshake = int(parts[5]) if parts[5] != '0' else 0
            rx = int(parts[6]) if len(parts) > 6 else 0
            tx = int(parts[7]) if len(parts) > 7 else 0
            now = int(time.time())
            online = (now - latest_handshake) < 180 if latest_handshake > 0 else False
            peers[pubkey] = {
                'endpoint': endpoint,
                'allowed_ips': allowed_ips,
                'latest_handshake': latest_handshake,
                'rx': rx,
                'tx': tx,
                'online': online
            }
        except (ValueError, IndexError):
            continue
    return peers


def cleanup_loop():
    """Delete records older than 30 days to save space."""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # 30 days retention
            limit = int(time.time()) - (30 * 24 * 3600)
            c.execute('DELETE FROM traffic WHERE ts < ?', (limit,))
            conn.commit()
            count = conn.total_changes
            if count > 0:
                print(f'[+] Cleanup: Removed {count} old records.')
            conn.close()
        except:
            pass
        time.sleep(3600 * 24) # Run once a day

class StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        
        # CORS headers
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if parsed.path == '/stats/live':
            data = get_wg_peers()
            self.wfile.write(json.dumps(data).encode())
        
        elif parsed.path == '/stats/history':
            pubkey = qs.get('pubkey', [None])[0]
            period = qs.get('period', ['day'])[0]
            period_map = {
                'hour': 3600,
                'day': 86400,
                'week': 604800,
                'month': 2592000
            }
            seconds = period_map.get(period, 86400)
            history = get_history(pubkey, seconds) if pubkey else []
            self.wfile.write(json.dumps(history).encode())
        
        elif parsed.path == '/stats/summary':
            summary = get_all_clients_latest()
            self.wfile.write(json.dumps(summary).encode())

        elif parsed.path == '/stats/reset':
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM traffic')
                conn.commit()
                conn.close()
                self.wfile.write(json.dumps({"status": "ok", "message": "Database cleared"}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        
        else:
            self.wfile.write(b'{}')

def collector_loop():
    while True:
        try:
            collect()
        except Exception as e:
            pass
        time.sleep(60)

if __name__ == '__main__':
    init_db()
    print('[+] Starting stats collector...')
    
    # Collector thread
    t1 = threading.Thread(target=collector_loop, daemon=True)
    t1.start()
    
    # Cleanup thread (retention policy)
    t2 = threading.Thread(target=cleanup_loop, daemon=True)
    t2.start()
    
    # Initial collection
    collect()
    print('[+] Initial data collected.')
    
    server = HTTPServer(('0.0.0.0', 9191), StatsHandler)
    print('[+] Stats API server running on :9191')
    server.serve_forever()
