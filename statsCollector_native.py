#!/usr/bin/env python3
import subprocess, sqlite3, time, json, threading, os
from http.server import HTTPServer, BaseHTTPRequestHandler

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
    while True:
        try:
            out = subprocess.check_output('awg show all dump 2>/dev/null', shell=True).decode()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            ts = int(time.time())
            
            for line in out.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) < 8: continue
                if '/' not in parts[4]: continue
                pubkey = parts[1]
                
                rx = int(parts[6])
                tx = int(parts[7])
                c.execute('INSERT INTO traffic VALUES (?, ?, ?, ?)', (ts, pubkey, rx, tx))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Collect error: {e}")
        
        time.sleep(60)

class StatsHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if self.path == '/stats/live' or self.path == '/stats/summary':
            try:
                out = subprocess.check_output('awg show all dump 2>/dev/null', shell=True).decode()
                stats = {}
                for line in out.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) < 8: continue
                    if '/' not in parts[4]: continue
                    pubkey = parts[1]
                    stats[pubkey] = {
                        "online": (int(time.time()) - int(parts[5])) < 300 if int(parts[5]) > 0 else False,
                        "latest_handshake": int(parts[5]),
                        "rx": int(parts[6]),
                        "tx": int(parts[7]),
                        "rx_total": int(parts[6]),
                        "tx_total": int(parts[7]),
                        "allowed_ips": parts[4].split(',')
                    }
                self.wfile.write(json.dumps(stats).encode())
            except Exception as e:
                print("Error in /stats/live:", e)
                self.wfile.write(b'{}')
                
        elif self.path == '/stats/history':
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                # Aggregate total traffic for all clients over time (last 24 hours)
                limit_ts = int(time.time()) - 86400
                c.execute('''
                    SELECT ts * 1000, SUM(rx), SUM(tx)
                    FROM traffic 
                    WHERE ts > ?
                    GROUP BY ts 
                    ORDER BY ts ASC
                ''', (limit_ts,))
                rows = c.fetchall()
                conn.close()
                
                # Convert cumulative sizes to delta (bandwidth usage per minute)
                rx_series = []
                tx_series = []
                last_rx = 0
                last_tx = 0
                for row in rows:
                    if last_rx == 0 and last_tx == 0:
                        last_rx = row[1]
                        last_tx = row[2]
                        continue
                    
                    delta_rx = max(0, row[1] - last_rx)
                    delta_tx = max(0, row[2] - last_tx)
                    rx_series.append([row[0], delta_rx])
                    tx_series.append([row[0], delta_tx])
                    last_rx = row[1]
                    last_tx = row[2]

                res = {"rx": rx_series, "tx": tx_series}
                self.wfile.write(json.dumps(res).encode())
            except Exception as e:
                print(e)
                self.wfile.write(json.dumps({"rx": [], "tx": []}).encode())
                
        elif self.path == '/stats/reset':
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM traffic')
                conn.commit()
                conn.close()
                self.wfile.write(b'{"status":"ok"}')
            except:
                self.wfile.write(b'{"status":"error"}')
        else:
            self.wfile.write(b'{}')

if __name__ == '__main__':
    init_db()
    threading.Thread(target=collect, daemon=True).start()
    print("Stats API (AWG) running on port 9191")
    HTTPServer(('0.0.0.0', 9191), StatsHandler).serve_forever()
