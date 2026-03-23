import webview
import paramiko
import json
import bcrypt
import time
import os
import threading

class Api:
    def __init__(self, window):
        self._window = window

    def run_install(self, params):
        def _task():
            try:
                host = params['host']
                user = params['user']
                password = params['pass']
                wg_port = params['wg_port']
                web_port = params['web_port']
                web_pass = params['web_pass']
                i1 = params['i1']
                i2 = params['i2']

                self._window.evaluate_js(f"setStatus('[*] Подключение к {host}...')")
                
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, username=user, password=password)

                self._window.evaluate_js("setStatus('[*] Генерация хеша пароля...')")
                pw_hash = bcrypt.hashpw(web_pass.encode(), bcrypt.gensalt()).decode()

                self._window.evaluate_js("setStatus('[*] Установка модуля ядра Amnezia (может занять время)...')")
                kernel_cmds = [
                    "apt-get update",
                    "apt-get install -y software-properties-common",
                    "add-apt-repository -y ppa:amnezia/ppa",
                    "apt-get update",
                    "apt-get install -y amneziawg",
                    "modprobe amneziawg"
                ]
                for k_cmd in kernel_cmds:
                    ssh.exec_command(k_cmd)
                
                self._window.evaluate_js("setStatus('[*] Очистка старых контейнеров...')")
                ssh.exec_command("docker stop amnezia-wg-easy || true")
                ssh.exec_command("docker rm amnezia-wg-easy || true")

                self._window.evaluate_js("setStatus('[*] Запуск нового контейнера 1.5...')")
                awg_envs = (
                    f"-e WG_PERSISTENT_KEEPALIVE=25 -e JC=6 -e JMIN=50 -e JMAX=1000 "
                    f"-e S1=78 -e S2=87 -e H1=918939037 -e H2=1319269495 -e H3=1051781005 -e H4=744876729 "
                    f"-e WG_ALLOWED_IPS=0.0.0.0/0"
                )
                docker_cmd = (f"docker run -d --name=amnezia-wg-easy -e LANG=en -e WG_HOST={host} "
                              f"-e PASSWORD_HASH='{pw_hash}' -e PORT={web_port} -e WG_PORT={wg_port} "
                              f"-e WG_CONFIG_PORT={wg_port} -e EXPERIMENTAL_AWG=true {awg_envs} "
                              f"-v /root/.amnezia-wg-easy:/etc/wireguard -p {wg_port}:{wg_port}/udp "
                              f"-p {web_port}:{web_port}/tcp --cap-add=NET_ADMIN --cap-add=SYS_MODULE "
                              f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' --sysctl='net.ipv4.ip_forward=1' "
                              f"--device=/dev/net/tun:/dev/net/tun --restart unless-stopped "
                              f"ghcr.io/w0rng/amnezia-wg-easy")
                
                ssh.exec_command(docker_cmd)
                time.sleep(5)

                self._window.evaluate_js("setStatus('[*] Патчинг экспорта конфигураций...')")
                patch_js = (
                    "docker exec amnezia-wg-easy sed -i "
                    "'/H4 = ${config.server.h4}/a I1 = ${config.server.i1 || \"\"}\\nI2 = ${config.server.i2 || \"\"}' "
                    "/app/lib/WireGuard.js"
                )
                ssh.exec_command(patch_js)

                self._window.evaluate_js("setStatus('[*] Применение токенов обфускации...')")
                update_json = (
                    f"docker exec amnezia-wg-easy node -e '"
                    f"const fs = require(\"fs\"); "
                    f"const conf = JSON.parse(fs.readFileSync(\"/etc/wireguard/wg0.json\")); "
                    f"conf.server.i1 = \"{i1}\"; "
                    f"conf.server.i2 = \"{i2}\"; "
                    f"fs.writeFileSync(\"/etc/wireguard/wg0.json\", JSON.stringify(conf, null, 2));'"
                )
                ssh.exec_command(update_json)
                ssh.exec_command("docker restart amnezia-wg-easy")
                self._window.evaluate_js("setStatus('[*] Настройка Firewall (UFW)...')")
                ssh.exec_command("ufw allow 22/tcp")
                ssh.exec_command(f"ufw allow {wg_port}/udp")
                ssh.exec_command(f"ufw allow {web_port}/tcp")
                ssh.exec_command("echo 'y' | ufw enable")

                self._window.evaluate_js("setStatus('УСТАНОВКА ЗАВЕРШЕНА!', true)")
                ssh.close()

            except Exception as e:
                self._window.evaluate_js(f"setStatus('ОШИБКА: {str(e)}')")
        
        threading.Thread(target=_task).start()

def main():
    # Path to index.html
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, 'ui', 'index.html')
    
    window = webview.create_window('Amnezia Automator', html_path, width=600, height=800, resizable=False)
    api = Api(window)
    window.expose(api)
    webview.start()

if __name__ == '__main__':
    main()
