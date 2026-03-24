import sys
import os
import subprocess
import argparse
import time

# --- Цвета для "Премиального" терминала ---
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# --- App Logic ---
IMAGE = "ghcr.io/w0rng/amnezia-wg-easy"
HUB_DOCKER_IMAGE = "python:3.10-slim"
SNMP_IMAGE = "gponomarev/snmpd" # Lightweight SNMP agent
DEFAULT_VPN_PORT = "993"
DEFAULT_WEB_PORT = "4466"
LOCAL_WEB_IP = "127.0.0.1"

DEFAULT_STEALTH = {
    "JC": "10", "JMIN": "100", "JMAX": "1000",
    "S1": "15", "S2": "100",
    "H1": "1234567891", "H2": "1234567892", "H3": "1234567893", "H4": "1234567894"
}

# --- Локализация (RU/EN) ---
LOCALES = {
    "ru": {
        "welcome": "ДОБРО ПОЖАЛОВАТЬ В AMNEZIA VPN PREMIUM!",
        "select_lang": "Выберите язык / Select Language (1: RU, 2: EN)",
        "menu_title": "ВЫБЕРИТЕ ДЕЙСТВИЕ:",
        "opt_deploy": "Развернуть новый узел (Deploy)",
        "opt_status": "Статус и здоровье узла (Status)",
        "opt_logs": "Логи контейнера (Logs)",
        "opt_configs": "Получить конфиги клиентов (Configs)",
        "opt_hub": "Установить Master Hub & Dashboard",
        "opt_cleanup": "Очистить сервер (Cleanup)",
        "opt_exit": "Выход",
        "enter_choice": "Введите номер действия",
        "params_title": "--- ПАРАМЕТРЫ СЕРВЕРА ---",
        "ip_prompt": "IP адрес сервера",
        "pass_prompt": "Пароль SSH (root)",
        "extip_prompt": "Публичный (внешний) IP",
        "webport_prompt": "Порт панели управления",
        "vpnport_prompt": "Порт для VPN (UDP)",
        "snmp_prompt": "Включить SNMP мониторинг? (y/n)",
        "hub_loc_prompt": "Где установить Hub? (1: Локально (Docker), 2: Удаленный сервер)",
        "starting": "Начинаю процесс для {}...",
        "conn_error": "Ошибка подключения: {}",
        "success": "УСПЕХ!",
        "bye": "До встречи!",
        "missing_deps": "[!] Установка необходимых библиотек...",
        "deps_ok": "[+] Библиотеки установлены.",
        "gen_hash": "Генерация защищенного хэша пароля...",
        "ssh_conn": "Подключение к {} как root...",
        "ssh_ok": "[+] SSH соединение установлено.",
        "cleanup_msg": "[*] Удаление существующих контейнеров и данных...",
        "cleanup_ok": "[+] Очистка завершена.",
        "deploy_start": "[*] Запуск развертывания {}...",
        "snmp_start": "[*] Запуск SNMP агента...",
        "firewall_pass": "[*] Настройка брандмауэра (UFW)...",
        "client_list": "Список доступных клиентов:",
        "conf_for": "Конфигурация для {}:",
        "hub_title": "--- УСТАНОВКА MASTER HUB & DASHBOARD (DOCKER) ---",
        "hub_desc": "Центральный пульт управления всеми вашими нодами.",
        "hub_found": "[+] Компоненты найдены.",
        "docker_install": "[*] Проверка/Установка Docker на сервере...",
        "hub_instructions": "Хаб запущен в Docker! Панель будет доступна на порту 5000.",
        "invalid": "Неверный выбор.",
        "no_clients": "Клиентов не найдено.",
        "client_choice": "Введите номер клиента для получения конфига",
        "logs_title": "ЛОГИ ({})",
        "hub_fail": "Ошибка установки Хаба: {}"
    },
    "en": {
        "welcome": "WELCOME TO AMNEZIA VPN PREMIUM!",
        "select_lang": "Select Language (1: RU, 2: EN)",
        "menu_title": "SELECT ACTION:",
        "opt_deploy": "Deploy new node",
        "opt_status": "Node Health & Status",
        "opt_logs": "Container Logs",
        "opt_configs": "Get Client Configs",
        "opt_hub": "Install Master Hub & Dashboard",
        "opt_cleanup": "Cleanup Server",
        "opt_exit": "Exit",
        "enter_choice": "Enter action number",
        "params_title": "--- SERVER PARAMETERS ---",
        "ip_prompt": "Server IP",
        "pass_prompt": "SSH Password (root)",
        "extip_prompt": "Public (External) IP",
        "webport_prompt": "Web UI Port",
        "vpnport_prompt": "VPN Port (UDP)",
        "snmp_prompt": "Enable SNMP monitoring? (y/n)",
        "hub_loc_prompt": "Where to install Hub? (1: Locally (Docker), 2: Remote Server)",
        "starting": "Starting process for {}...",
        "conn_error": "Connection error: {}",
        "success": "SUCCESS!",
        "bye": "Goodbye!",
        "missing_deps": "[!] Installing dependencies...",
        "deps_ok": "[+] Dependencies installed.",
        "gen_hash": "Generating secure password hash...",
        "ssh_conn": "Connecting to {} as root...",
        "ssh_ok": "[+] SSH Connection established.",
        "cleanup_msg": "[*] Removing existing containers and data...",
        "cleanup_ok": "[+] Cleanup complete.",
        "deploy_start": "[*] Starting deployment of {}...",
        "snmp_start": "[*] Starting SNMP agent...",
        "firewall_pass": "[*] Hardening firewall (UFW)...",
        "client_list": "List of available clients:",
        "conf_for": "Configuration for {}:",
        "hub_title": "--- MASTER HUB & DASHBOARD (DOCKER) ---",
        "hub_desc": "Central management hub for all your nodes.",
        "hub_found": "[+] Components found.",
        "docker_install": "[*] Checking/Installing Docker on server...",
        "hub_instructions": "Hub is running in Docker! Panel available on port 5000.",
        "invalid": "Invalid choice.",
        "no_clients": "No clients found.",
        "client_choice": "Enter client number to show config",
        "logs_title": "LOGS ({})",
        "hub_fail": "Hub setup failed: {}"
    }
}

# --- Глобальные переменные ---
L = LOCALES["en"]

def set_language():
    global L
    print(f"\n{BOLD}{CYAN}➤ {LOCALES['en']['select_lang']}{RESET}")
    choice = input(" [1/2]: ").strip()
    if choice == "1":
        L = LOCALES["ru"]
    else:
        L = LOCALES["en"]

def install_dependencies():
    try:
        import paramiko
        import bcrypt
    except ImportError:
        print(f"{YELLOW}{L['missing_deps']}{RESET}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "paramiko", "bcrypt"])
        print(f"{GREEN}{L['deps_ok']}{RESET}")

def get_input(prompt, default=""):
    formatted_prompt = f"{BOLD}{CYAN}➤ {prompt}{RESET} {YELLOW}[{default}]{RESET}: "
    try:
        res = input(formatted_prompt).strip()
    except EOFError:
        try:
            sys.stdin = open('/dev/tty')
            res = input().strip()
        except:
            return default
    return res if res else default

def print_step(text):
    print(f"{GREEN}{BOLD}[*]{RESET} {text}")

def print_error(text):
    print(f"{RED}{BOLD}[!]{RESET} {RED}{text}{RESET}")

def generate_hash(password):
    import bcrypt
    print_step(L["gen_hash"])
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

class AmneziaDeployer:
    def __init__(self, ip, password, ext_ip, web_port, vpn_port, stealth_params):
        import paramiko
        self.ip = ip
        self.password = password
        self.ext_ip = ext_ip
        self.web_port = web_port
        self.vpn_port = vpn_port
        self.stealth = stealth_params
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            print(f"[*] {L['ssh_conn'].format(self.ip)}")
            self.ssh.connect(self.ip, username='root', password=self.password, timeout=15)
            print(f"{GREEN}{L['ssh_ok']}{RESET}")
            return True
        except Exception as e:
            print_error(L["conn_error"].format(e))
            return False

    def exec(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    def cleanup(self):
        print_step(L["cleanup_msg"])
        self.exec("docker stop amnezia-wg-easy amnezia-awg2 amnezia-snmp || true")
        self.exec("docker rm amnezia-wg-easy amnezia-awg2 amnezia-snmp || true")
        self.exec("rm -rf ~/.amnezia-wg-easy")
        print(f"{GREEN}{L['cleanup_ok']}{RESET}")

    def install_docker_remote(self):
        print_step(L["docker_install"])
        self.exec("curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh")

    def deploy(self, snmp_enabled=False):
        pw_hash = generate_hash(self.password)
        print_step(L["deploy_start"].format(IMAGE))
        docker_cmd = (
            f"docker run -d --name=amnezia-wg-easy "
            f"-e WG_HOST={self.ext_ip} "
            f"-e PASSWORD_HASH='{pw_hash}' "
            f"-e PORT={self.web_port} -e WG_PORT={self.vpn_port} "
            f"-e EXPERIMENTAL_AWG=true "
            f"-v ~/.amnezia-wg-easy:/etc/wireguard "
            f"-p {LOCAL_WEB_IP}:{self.web_port}:{self.web_port}/tcp "
            f"-p {self.vpn_port}:{self.vpn_port}/udp "
            f"--cap-add=NET_ADMIN --cap-add=SYS_MODULE "
            f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' --sysctl='net.ipv4.ip_forward=1' "
            f"--device=/dev/net/tun:/dev/net/tun --restart unless-stopped {IMAGE}"
        )
        self.exec(docker_cmd)
        
        if snmp_enabled:
            print_step(L["snmp_start"])
            self.exec(f"docker run -d --name=amnezia-snmp -p 161:161/udp --restart unless-stopped {SNMP_IMAGE}")

        print_step(L["firewall_pass"])
        self.exec("ufw allow 22/tcp")
        self.exec(f"ufw allow {self.vpn_port}/udp")
        if snmp_enabled: self.exec("ufw allow 161/udp")
        self.exec("echo 'y' | ufw enable")
        
        print(f"\n{GREEN}{BOLD}=== {L['success']} ==={RESET}")
        return True

    def check_status(self):
        print_step(f"{L['ip_prompt']}: {self.ip}")
        out, _ = self.exec("docker ps --filter name=amnezia-wg-easy --format '{{.Status}}'")
        if out: print(f"{GREEN}{BOLD}[ACTIVE]{RESET} {out}")
        else: print(f"{RED}{BOLD}[OFFLINE]{RESET}")

    def get_logs(self):
        print_step(L["logs_title"].format(self.ip))
        out, _ = self.exec("docker logs --tail 20 amnezia-wg-easy")
        print("-" * 50 + "\n" + (out if out else "...") + "\n" + "-" * 50)

    def get_configs(self):
        print_step(L["client_list"])
        out, _ = self.exec("docker exec amnezia-wg-easy cat /etc/wireguard/wg0.json")
        try:
            import json
            data = json.loads(out)
            clients = data.get("clients", [])
            for idx, c in enumerate(clients):
                print(f"  {CYAN}{idx+1}.{RESET} {c['name']} ({c['address']})")
            c_idx = get_input(L["client_choice"], "1")
            target = clients[int(c_idx)-1]
            print(f"\n{BOLD}{L['conf_for'].format(target['name'])}{RESET}")
            conf_out, _ = self.exec(f"docker exec amnezia-wg-easy cat /etc/wireguard/clients/{target['id']}.conf")
            print(f"{YELLOW}{conf_out}{RESET}")
        except: print_error(L["invalid"])

    def setup_hub(self, remote=False):
        print(f"\n{BOLD}{MAGENTA}{L['hub_title']}{RESET}")
        hub_path = "stats_hub"
        if not os.path.exists(hub_path): return
        try:
            # 1. Prepare Dockerfile
            dockerfile = f"FROM {HUB_DOCKER_IMAGE}\nWORKDIR /app\nCOPY . .\nRUN pip install flask flask-cors requests\nCMD [\"python\", \"hub_server.py\"]\n"
            with open(f"{hub_path}/Dockerfile", "w") as f: f.write(dockerfile)
            
            if not remote:
                print_step("Building Hub locally...")
                subprocess.check_call(["docker", "build", "-t", "amnezia-hub", hub_path])
                subprocess.check_call(["docker", "run", "-d", "--name", "amnezia-hub", "--restart", "always", "-p", "5000:5000", "amnezia-hub"])
            else:
                self.install_docker_remote()
                print_step("Uploading Hub to remote server (SFTP)...")
                sftp = self.ssh.open_sftp()
                remote_dir = "/opt/amnezia-hub"
                self.exec(f"mkdir -p {remote_dir}")
                
                for f_name in os.listdir(hub_path):
                    local_f = os.path.join(hub_path, f_name)
                    if os.path.isfile(local_f):
                        sftp.put(local_f, f"{remote_dir}/{f_name}")
                sftp.close()
                
                print_step("Building and running Hub in Docker on remote...")
                self.exec(f"cd {remote_dir} && docker build -t amnezia-hub .")
                self.exec("docker stop amnezia-hub || true && docker rm amnezia-hub || true")
                self.exec("docker run -d --name amnezia-hub --restart always -p 5000:5000 amnezia-hub")
                
            print(f"\n{GREEN}{BOLD}{L['success']}{RESET}\n{L['hub_instructions']}")
        except Exception as e: print_error(L["hub_fail"].format(e))

def print_banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"""{RED}{BOLD}
    ╔══════════════════════════════════════════════════╗
    ║        AMNEZIA v2 — PREMIUM TERMINAL APP         ║
    ║        Powered by SkyKnight Network              ║
    ╚══════════════════════════════════════════════════╝{RESET}""")

def run_cli():
    print_banner()
    set_language()
    install_dependencies()
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true")
    args, _ = parser.parse_known_args()
    if not args.auto:
        print(f"\n{BOLD}{L['menu_title']}{RESET}")
        opts = [L['opt_deploy'], L['opt_status'], L['opt_logs'], L['opt_configs'], L['opt_hub'], L['opt_cleanup']]
        for i, opt in enumerate(opts): print(f"  {CYAN}{i+1}.{RESET} {opt}")
        print(f"  {RED}0.{RESET} {L['opt_exit']}")
        choice = get_input(L["enter_choice"], "1")
        if choice == "0": return
        print(f"\n{BOLD}{L['params_title']}{RESET}")
        ip = get_input(L["ip_prompt"])
        password = get_input(L["pass_prompt"])
        deployer = AmneziaDeployer(ip, password, "", "", "", {})
        if choice == "2":
            if deployer.connect(): deployer.check_status()
        elif choice == "3":
            if deployer.connect(): deployer.get_logs()
        elif choice == "4":
            if deployer.connect(): deployer.get_configs()
        elif choice == "5":
            loc = get_input(L["hub_loc_prompt"], "1")
            if loc == "2":
                hub_ip = get_input(L["ip_prompt"]); hub_pw = get_input(L["pass_prompt"])
                hub_d = AmneziaDeployer(hub_ip, hub_pw, "", "", "", {})
                if hub_d.connect(): hub_d.setup_hub(remote=True)
            else: deployer.setup_hub(remote=False)
        elif choice == "6":
            if deployer.connect(): deployer.cleanup()
        elif choice == "1":
            ext_ip = get_input(L["extip_prompt"], ip)
            web_port = get_input(L["webport_prompt"], DEFAULT_WEB_PORT)
            vpn_port = get_input(L["vpnport_prompt"], DEFAULT_VPN_PORT)
            snmp = get_input(L["snmp_prompt"], "n")
            deployer = AmneziaDeployer(ip, password, ext_ip, web_port, vpn_port, DEFAULT_STEALTH)
            if deployer.connect():
                deployer.cleanup()
                deployer.deploy(snmp_enabled=(snmp.lower() == 'y'))

if __name__ == "__main__":
    try: run_cli()
    except KeyboardInterrupt: sys.exit(0)
