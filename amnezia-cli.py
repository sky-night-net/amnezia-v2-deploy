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
DEFAULT_VPN_PORT = "993"
DEFAULT_WEB_PORT = "4466"
LOCAL_WEB_IP = "127.0.0.1"

DEFAULT_STEALTH = {
    "JC": "10", "JMIN": "100", "JMAX": "1000",
    "S1": "15", "S2": "100",
    "H1": "1234567891", "H2": "1234567892", "H3": "1234567893", "H4": "1234567894"
}

def install_dependencies():
    try:
        import paramiko
        import bcrypt
    except ImportError:
        print(f"{YELLOW}[!] Установка необходимых библиотек (paramiko, bcrypt)...{RESET}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "bcrypt"])
        print(f"{GREEN}[+] Библиотеки установлены. Проверка завершена.{RESET}")

# --- Локализация (RU/EN) ---
LOCALES = {
    "ru": {
        "welcome": "Добро пожаловать в Amnezia VPN Deployer!",
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
        "starting": "Начинаю процесс для {}...",
        "conn_error": "Ошибка подключения: {}",
        "success": "УСПЕХ!",
        "bye": "До встречи!",
        "missing_deps": "[!] Отсутствуют библиотеки. Установка...",
        "deps_ok": "[+] Библиотеки установлены.",
        "gen_hash": "Генерация защищенного хэша пароля...",
        "ssh_conn": "Подключение к {} как root...",
        "ssh_ok": "[+] SSH соединение установлено.",
        "cleanup_msg": "[*] Удаление существующих контейнеров и данных...",
        "cleanup_ok": "[+] Очистка завершена.",
        "deploy_start": "[*] Запуск развертывания {}...",
        "firewall_pass": "[*] Настройка брандмауэра (UFW)...",
        "client_list": "Список доступных клиентов:",
        "conf_for": "Конфигурация для {}:",
        "hub_title": "--- УСТАНОВКА MASTER HUB & DASHBOARD ---",
        "hub_desc": "Это превратит этот компьютер в центральный пульт управления.",
        "hub_found": "[+] Компоненты найдены.",
        "node_name_prompt": "Имя первой ноды (напр. ГЕРМАНИЯ)",
        "node_ip_prompt": "IP адрес для {}",
        "hub_instructions": "1. Запустите хаб: python3 stats_hub/hub_server.py\n2. Откройте панель: Amnezia_Premium_Dashboard/frontend/index.html"
    },
    "en": {
        "welcome": "Welcome to Amnezia VPN Deployer!",
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
        "starting": "Starting process for {}...",
        "conn_error": "Connection error: {}",
        "success": "SUCCESS!",
        "bye": "Goodbye!",
        "missing_deps": "[!] Missing dependencies. Installing...",
        "deps_ok": "[+] Dependencies installed.",
        "gen_hash": "Generating secure password hash...",
        "ssh_conn": "Connecting to {} as root...",
        "ssh_ok": "[+] SSH Connection established.",
        "cleanup_msg": "[*] Removing existing containers and data...",
        "cleanup_ok": "[+] Cleanup complete.",
        "deploy_start": "[*] Starting deployment of {}...",
        "firewall_pass": "[*] Hardening firewall (UFW)...",
        "client_list": "List of available clients:",
        "conf_for": "Configuration for {}:",
        "hub_title": "--- MASTER HUB & DASHBOARD SETUP ---",
        "hub_desc": "This computer will become your central management hub.",
        "hub_found": "[+] Components found.",
        "node_name_prompt": "Node name (e.g. GERMANY)",
        "node_ip_prompt": "IP address for {}",
        "hub_instructions": "1. Run hub: python3 stats_hub/hub_server.py\n2. Open panel: Amnezia_Premium_Dashboard/frontend/index.html"
    }
}

# Текущая локаль (по умолчанию английский до выбора)
L = LOCALES["en"]

def set_language():
    global L
    print(f"\n{BOLD}{CYAN}➤ {LOCALES['en']['select_lang']}{RESET}")
    choice = input(" [1/2]: ").strip()
    if choice == "1":
        L = LOCALES["ru"]
    else:
        L = LOCALES["en"]

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
            print_error(f"{L['conn_error'].format(e)}")
            return False

    def exec(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    def cleanup(self):
        print_step(L["cleanup_msg"])
        self.exec("docker stop amnezia-wg-easy amnezia-awg2 || true")
        self.exec("docker rm amnezia-wg-easy amnezia-awg2 || true")
        self.exec("rm -rf ~/.amnezia-wg-easy")
        print(f"{GREEN}{L['cleanup_ok']}{RESET}")

    def deploy(self):
        pw_hash = generate_hash(self.password)
        
        print_step(L["deploy_start"].format(IMAGE))
        docker_cmd = (
            f"docker run -d --name=amnezia-wg-easy "
            f"-e WG_HOST={self.ext_ip} "
            f"-e PASSWORD_HASH='{pw_hash}' "
            f"-e PORT={self.web_port} -e WG_PORT={self.vpn_port} "
            f"-e EXPERIMENTAL_AWG=true "
            f"-e JC={self.stealth['JC']} -e JMIN={self.stealth['JMIN']} -e JMAX={self.stealth['JMAX']} "
            f"-e S1={self.stealth['S1']} -e S2={self.stealth['S2']} "
            f"-e H1={self.stealth['H1']} -e H2={self.stealth['H2']} -e H3={self.stealth['H3']} -e H4={self.stealth['H4']} "
            f"-v ~/.amnezia-wg-easy:/etc/wireguard "
            f"-p {LOCAL_WEB_IP}:{self.web_port}:{self.web_port}/tcp "
            f"-p {self.vpn_port}:{self.vpn_port}/udp "
            f"--cap-add=NET_ADMIN --cap-add=SYS_MODULE "
            f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' --sysctl='net.ipv4.ip_forward=1' "
            f"--device=/dev/net/tun:/dev/net/tun --restart unless-stopped {IMAGE}"
        )
        out, err = self.exec(docker_cmd)
        if err and "is already in use" not in err:
            print_error(f"DEPLOY ERROR: {err}")
            return False
        
        print_step(L["firewall_pass"])
        self.exec("ufw allow 22/tcp")
        self.exec(f"ufw allow {self.vpn_port}/udp")
        self.exec("echo 'y' | ufw enable")
        
        print(f"\n{GREEN}{BOLD}=== {L['success']} ==={RESET}")
        print(f"IP: {self.ip} | Port: {self.vpn_port}\n")
        return True

    def check_status(self):
        print_step(f"{L['ip_prompt']}: {self.ip}")
        out, _ = self.exec("docker ps --filter name=amnezia-wg-easy --format '{{.Status}}'")
        if out:
            print(f"{GREEN}{BOLD}[ACTIVE]{RESET} {out}")
        else:
            print(f"{RED}{BOLD}[OFFLINE]{RESET}")

    def get_logs(self):
        print_step(f"LOGS ({self.ip})")
        out, _ = self.exec("docker logs --tail 20 amnezia-wg-easy")
        print("-" * 50)
        print(out if out else "...")
        print("-" * 50)

    def get_configs(self):
        print_step(L["client_list"])
        out, _ = self.exec("docker exec amnezia-wg-easy cat /etc/wireguard/wg0.json")
        try:
            import json
            data = json.loads(out)
            clients = data.get("clients", [])
            if not clients:
                print(L["no_clients"])
                return
            
            for idx, c in enumerate(clients):
                print(f"  {CYAN}{idx+1}.{RESET} {c['name']} ({c['address']})")
            
            c_idx = get_input(L["client_choice"], "1")
            try:
                target = clients[int(c_idx)-1]
                print(f"\n{BOLD}{L['conf_for'].format(target['name'])}{RESET}")
                conf_out, _ = self.exec(f"docker exec amnezia-wg-easy cat /etc/wireguard/clients/{target['id']}.conf")
                print(f"{YELLOW}{conf_out}{RESET}")
            except:
                print_error(L["invalid"])
        except Exception as e:
            print_error(f"Error: {e}")
            data = json.loads(out)
            clients = data.get("clients", [])
            if not clients:
                print("Клиентов не найдено.")
                return
            
            for idx, c in enumerate(clients):
                print(f"  {CYAN}{idx+1}.{RESET} {c['name']} ({c['address']})")
            
            c_idx = get_input("Введите номер клиента для получения конфига", "1")
            try:
                target = clients[int(c_idx)-1]
                print(f"\n{BOLD}Конфигурация для {target['name']}:{RESET}")
                # For a full terminal "premium" feel, we can't show a real QR image, 
                # but we can show the text config.
                conf_out, _ = self.exec(f"docker exec amnezia-wg-easy cat /etc/wireguard/clients/{target['id']}.conf")
                print(f"{YELLOW}{conf_out}{RESET}")
    def setup_hub(self):
        print(f"\n{BOLD}{CYAN}--- УСТАНОВКА MASTER HUB & DASHBOARD ---{RESET}")
        print("Это превратит этот компьютер в центральный пульт управления всеми вашими VPN-узлами.")
        
        try:
            print_step("Установка зависимостей (Flask, Flask-CORS)...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors", "requests"])
            
            # Создаем начальный конфиг если его нет
            hub_path = "stats_hub/hub_server.py"
            if os.path.exists(hub_path):
                print(f"{GREEN}[+] Компоненты найдены.{RESET}")
                node_name = get_input("Имя вашей первой ноды (напр. ГЕРМАНИЯ)", "Германия")
                node_ip = get_input(f"IP адрес для {node_name}", self.ip)
                
                print_step(f"Добавление {node_name} в конфиг мониторинга...")
                # Простейшая замена в файле для демонстрации (лучше через JSON в будущем)
                with open(hub_path, "r") as f:
                    content = f.read()
                
                new_node = f'{{"name": "{node_name}", "ip": "{node_ip}", "port": 9191}}'
                if "NODES = [" in content:
                    content = content.replace("NODES = [", f"NODES = [\n    {new_node},")
                
                with open(hub_path, "w") as f:
                    f.write(content)
                
                print(f"\n{GREEN}{BOLD}УСПЕХ!{RESET}")
                print(f"1. Запустите хаб: {BOLD}python3 {hub_path}{RESET}")
                print(f"2. Откройте панель: {BOLD}Amnezia_Premium_Dashboard/frontend/index.html{RESET}")
            else:
                print_error("Файлы хаба не найдены в репозитории.")
        except Exception as e:
            print_error(f"Ошибка при настройке хаба: {e}")

def print_banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"""{RED}{BOLD}
    ╔══════════════════════════════════════════════════╗
    ║        AMNEZIA v2 — PREMIUM TERMINAL APP         ║
    ║        Powered by SkyKnight Network              ║
    ╚══════════════════════════════════════════════════╝{RESET}""")

def run_cli():
    print_banner()
    install_dependencies()
    
    parser = argparse.ArgumentParser(description="Amnezia VPN Deployment Suite")
    parser.add_argument("--auto", action="store_true", help="Non-interactive mode")
    parser.add_argument("--ip", help="Remote Server IP")
    parser.add_argument("--password", help="Root Password")
    parser.add_argument("--ext-ip", help="Public IP for clients")
    parser.add_argument("--cleanup", action="store_true", help="Only cleanup server")
    
    args = parser.parse_args()

    # If no flags provided, enter interactive wizard
    if not (args.auto or args.cleanup):
        print(f"\n{BOLD}ВЫБЕРИТЕ ДЕЙСТВИЕ:{RESET}")
        print(f"  {GREEN}1.{RESET} Развернуть новый узел (Deploy)")
        print(f"  {CYAN}2.{RESET} Статус и здоровье узла (Status)")
        print(f"  {YELLOW}3.{RESET} Логи контейнера (Logs)")
        print(f"  {BOLD}4.{RESET} Получить конфиги клиентов (Configs)")
        print(f"  {MAGENTA}5.{RESET} Установить Master Hub & Dashboard {BOLD}(NEW){RESET}")
        print(f"  {RED}6.{RESET} Очистить сервер (Cleanup)")
        print(f"  {RED}0.{RESET} Выход (Exit)")
        
        choice = get_input("Введите номер действия", "1")
        if choice == "0": 
            print(f"\n{GREEN}До встречи!{RESET}")
            return
        
        print(f"\n{BOLD}--- ПАРАМЕТРЫ СЕРВЕРА ---{RESET}")
        ip = get_input("IP адрес сервера")
        password = get_input("Пароль SSH (root)")
        
        deployer = AmneziaDeployer(ip, password, "", "", "", {})
        
        if choice == "2":
            if deployer.connect(): deployer.check_status()
        elif choice == "3":
            if deployer.connect(): deployer.get_logs()
        elif choice == "4":
            if deployer.connect(): deployer.get_configs()
        elif choice == "5":
            deployer.setup_hub()
        elif choice == "6":
            if deployer.connect(): deployer.cleanup()
        elif choice == "1":
            ext_ip = get_input("Публичный (внешний) IP", ip)
            web_port = get_input("Порт панели управления", DEFAULT_WEB_PORT)
            vpn_port = get_input("Порт для VPN (UDP)", DEFAULT_VPN_PORT)
            
            print(f"\n{YELLOW}[*] Начинаю процесс для {ip}...{RESET}")
            # Re-init with full params for deploy
            deployer = AmneziaDeployer(ip, password, ext_ip, web_port, vpn_port, DEFAULT_STEALTH)
            if deployer.connect():
                deployer.cleanup()
                deployer.deploy()

    elif args.cleanup:
        if not (args.ip and args.password):
            print("Cleanup requires --ip and --password")
            return
        deployer = AmneziaDeployer(args.ip, args.password, "", "", "", {})
        if deployer.connect():
            deployer.cleanup()
            
    elif args.auto:
        if not (args.ip and args.password and args.ext_ip):
            print("Auto mode requires --ip, --password, and --ext-ip")
            return
        deployer = AmneziaDeployer(args.ip, args.password, args.ext_ip, DEFAULT_WEB_PORT, DEFAULT_VPN_PORT, DEFAULT_STEALTH)
        if deployer.connect():
            deployer.cleanup()
            deployer.deploy()

if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
        sys.exit(0)
