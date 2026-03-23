import requests
import json
import time
import threading
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Список нод (можно расширять динамически)
NODES = [
    # {"name": "Frankfurt", "ip": "95.85.114.66", "port": 9191},
]

# Глобальное хранилище данных
node_stats = {}

def poll_nodes():
    while True:
        for node in NODES:
            try:
                # Опрашиваем нативный statsCollector_native.py на каждой ноде
                r = requests.get(f"http://{node['ip']}:{node['port']}/stats/live", timeout=5)
                if r.status_code == 200:
                    node_stats[node['name']] = {
                        "status": "Online",
                        "data": r.json(),
                        "last_seen": time.time()
                    }
                else:
                    node_stats[node['name']] = {"status": "Error", "data": {}, "last_seen": time.time()}
            except:
                node_stats[node['name']] = {"status": "Offline", "data": {}, "last_seen": time.time()}
        
        time.sleep(30)

@app.route('/hub/stats')
def get_hub_stats():
    return jsonify(node_stats)

@app.route('/hub/nodes')
def get_nodes():
    return jsonify(NODES)

if __name__ == '__main__':
    # Запуск поллинга в фоне
    threading.Thread(target=poll_nodes, daemon=True).start()
    print("Amnezia Master Hub started on port 9292")
    app.run(host='0.0.0.0', port=9292)
