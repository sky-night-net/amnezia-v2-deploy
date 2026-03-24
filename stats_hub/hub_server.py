import requests
import json
import time
import threading
import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PORT = 5000
HUB_CONFIG = "hub_config.json"

# Load or init nodes
if os.path.exists(HUB_CONFIG):
    with open(HUB_CONFIG, "r") as f:
        NODES = json.load(f)
else:
    NODES = []

node_stats = {}

def poll_nodes():
    """Background thread to poll node status via HTTP or SNMP."""
    while True:
        for node in NODES:
            node_name = node['name']
            node_ip = node['ip']
            try:
                # 1. Try Native HTTP Polling (9191)
                try:
                    r = requests.get(f"http://{node_ip}:9191/stats/live", timeout=3)
                    if r.status_code == 200:
                        node_stats[node_name] = {"status": "Online", "mode": "Native", "data": r.json()}
                        continue
                except: pass

                # 2. SNMP Polling (if Native failed and node has SNMP)
                # (Placeholder: In a real implementation we'd use pysnmp here)
                node_stats[node_name] = {"status": "Partial", "mode": "SNMP", "data": {"msg": "SNMP data active"}}
                
            except Exception as e:
                node_stats[node_name] = {"status": "Offline", "error": str(e)}
        
        time.sleep(15)

@app.route('/hub/stats')
def get_hub_stats():
    return jsonify(node_stats)

@app.route('/hub/nodes', methods=['GET'])
def get_nodes():
    return jsonify(NODES)

@app.route('/hub/add_node', methods=['POST'])
def add_node():
    # TODO: Implement dynamic node addition from UI
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    threading.Thread(target=poll_nodes, daemon=True).start()
    print(f"Amnezia Master Hub v2 (Docker Edition) started on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)
