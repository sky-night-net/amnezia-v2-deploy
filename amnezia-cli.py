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
        
        print("\n" + "="*40)
        print("   SUCCESSFULLY DEPLOYED AMNEZIA VPN")
        print("="*40)
        print(f"Server IP:  {self.ip}")
        print(f"External:   {self.ext_ip}")
        print(f"Web UI:     http://{LOCAL_WEB_IP}:{self.web_port}")
        print(f"VPN Port:   {self.vpn_port} (UDP)")
        print(f"Password:   [the one you provided]")
        print("="*40 + "\n")
        return True

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
        print(f"  {YELLOW}2.{RESET} Очистить сервер (Cleanup)")
        print(f"  {RED}3.{RESET} Выход (Exit)")
        
        choice = get_input("Введите номер действия", "1")
        if choice == "3": 
            print(f"\n{GREEN}До встречи!{RESET}")
            return
        
        print(f"\n{BOLD}--- ПАРАМЕТРЫ СЕРВЕРА ---{RESET}")
        ip = get_input("IP адрес сервера")
        password = get_input("Пароль SSH (root)")
        
        if choice == "2":
            deployer = AmneziaDeployer(ip, password, "", "", "", {})
            if deployer.connect():
                deployer.cleanup()
            return
        
        ext_ip = get_input("Публичный (внешний) IP", ip)
        web_port = get_input("Порт панели управления", DEFAULT_WEB_PORT)
        vpn_port = get_input("Порт для VPN (UDP)", DEFAULT_VPN_PORT)
        
        print(f"\n{YELLOW}[*] Начинаю процесс для {ip}...{RESET}")
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
