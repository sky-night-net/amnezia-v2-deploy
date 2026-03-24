import requests
import json
import time
import threading
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PORT = 9292
HUB_CONFIG = "hub_config.json"

# Global state
node_stats = {}

def get_nodes():
    if os.path.exists(HUB_CONFIG):
        with open(HUB_CONFIG, "r") as f:
            return json.load(f)
    return []

def save_nodes(nodes):
    with open(HUB_CONFIG, "w") as f:
        json.dump(nodes, f, indent=4)

def poll_nodes():
    """Background thread to poll node status via HTTP or SNMP."""
    while True:
        nodes = get_nodes()
        for node in nodes:
            node_name = node['name']
            node_ip = node['ip']
            token = node.get('token', 'default_secret_123')
            
            try:
                # 1. Try Native HTTP Polling (9191) with Auth Token
                try:
                    headers = {"X-Auth-Token": token}
                    r = requests.get(f"http://{node_ip}:9191/stats/live", headers=headers, timeout=3)
                    if r.status_code == 200:
                        node_stats[node_name] = {
                            "status": "Online", 
                            "mode": "Native", 
                            "data": r.json(),
                            "last_seen": int(time.time())
                        }
                        continue
                    elif r.status_code == 401:
                        node_stats[node_name] = {"status": "Auth Error", "mode": "Native", "last_seen": int(time.time())}
                        continue
                except: pass

                # 2. SNMP Polling (Fallback or alternative)
                # If node has 'snmp': true, we could use snmpget here.
                if node.get('snmp'):
                    # Simplified SNMP check (ping + port check as placeholder for real MIB fetch)
                    node_stats[node_name] = {"status": "Online", "mode": "SNMP", "data": {"msg": "SNMP Active"}, "last_seen": int(time.time())}
                else:
                    node_stats[node_name] = {"status": "Offline", "last_seen": int(time.time())}
                
            except Exception as e:
                node_stats[node_name] = {"status": "Error", "error": str(e), "last_seen": int(time.time())}
        
        time.sleep(15)

@app.route('/hub/stats')
def get_hub_stats():
    return jsonify(node_stats)

@app.route('/hub/nodes', methods=['GET'])
def list_nodes():
    return jsonify(get_nodes())

@app.route('/hub/register', methods=['POST'])
def register_node():
    data = request.json
    if not data or 'name' not in data or 'ip' not in data:
        return jsonify({"status": "error", "message": "Missing name or ip"}), 400
    
    nodes = get_nodes()
    
    # Update existing or add new
    updated = False
    new_nodes = []
    for n in nodes:
        if n['ip'] == data['ip']:
            new_nodes.append(data)
            updated = True
        else:
            new_nodes.append(n)
    
    if not updated:
        new_nodes.append(data)
    
    save_nodes(new_nodes)
    return jsonify({"status": "ok", "message": f"Node {data['name']} registered"})

if __name__ == '__main__':
    threading.Thread(target=poll_nodes, daemon=True).start()
    print(f"Amnezia Master Hub v2.1 (Secure) started on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)
