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

def get_input(prompt, default=""):
    # Форматируем промпт красиво
    formatted_prompt = f"{BOLD}{CYAN}➤ {prompt}{RESET} {YELLOW}[{default}]{RESET}: "
    try:
        res = input(formatted_prompt).strip()
    except EOFError:
        # Если ввод перехвачен (curl | bash), тихо переключаемся на TTY
        try:
            sys.stdin = open('/dev/tty')
            # Не печатаем промпт второй раз, так как он уже виден в консоли
            res = input().strip()
        except:
            return default
    return res if res else default

def print_step(text):
    print(f"{GREEN}{BOLD}[*]{RESET} {text}")

def print_error(text):
    print(f"{RED}{BOLD}[!]{RESET} {RED}ОШИБКА: {text}{RESET}")

def generate_hash(password):
    import bcrypt
    print_step("Генерация защищенного хэша пароля...")
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
            print(f"[*] Connecting to {self.ip} as root...")
            self.ssh.connect(self.ip, username='root', password=self.password, timeout=15)
            print("[+] SSH Connection established.")
            return True
        except Exception as e:
            print(f"[-] ERROR: Could not connect to {self.ip}: {e}")
            return False

    def exec(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    def cleanup(self):
        print("[*] Removing existing Amnezia containers and cleaning data...")
        self.exec("docker stop amnezia-wg-easy amnezia-awg2 || true")
        self.exec("docker rm amnezia-wg-easy amnezia-awg2 || true")
        self.exec("rm -rf ~/.amnezia-wg-easy")
        print("[+] Cleanup complete.")

    def deploy(self):
        pw_hash = generate_hash(self.password)
        
        print(f"[*] Starting deployment of {IMAGE}...")
        # Note: We bind the web port to LOCAL_WEB_IP to restrict access
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
            print(f"[-] DEPLOYMENT ERROR: {err}")
            return False
        
        print(f"[+] Container initialized. ID: {out[:12]}")
            
        print("[*] Hardening firewall (UFW)...")
        # Ensure SSH is open
        self.exec("ufw allow 22/tcp")
        # Open VPN port
        self.exec(f"ufw allow {self.vpn_port}/udp")
        # Enable UFW
        self.exec("echo 'y' | ufw enable")
        print("[+] Firewall rules applied.")
        
    def check_status(self):
        print_step(f"Проверка состояния контейнера на {self.ip}...")
        out, _ = self.exec("docker ps --filter name=amnezia-wg-easy --format '{{.Status}} | {{.Image}}'")
        if out:
            print(f"{GREEN}{BOLD}[ACTIVE]{RESET} {out}")
            return True
        else:
            print(f"{RED}{BOLD}[NOT FOUND]{RESET} Контейнер не запущен или отсутствует.")
            return False

    def get_logs(self):
        print_step("Загрузка логов (сокращенно, последние 20 строк)...")
        out, _ = self.exec("docker logs --tail 20 amnezia-wg-easy")
        print("-" * 50)
        print(out if out else "Логов нет.")
        print("-" * 50)

    def get_configs(self):
        print_step("Список доступных клиентов:")
        # We try to read from the JSON db inside the container
        out, _ = self.exec("docker exec amnezia-wg-easy cat /etc/wireguard/wg0.json")
        try:
            import json
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
            except:
                print_error("Неверный номер.")
        except Exception as e:
            print_error(f"Не удалось получить список: {e}")

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
        print(f"  {RED}5.{RESET} Очистить сервер (Cleanup)")
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
