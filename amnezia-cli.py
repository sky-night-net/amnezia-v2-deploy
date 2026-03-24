#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║     AMNEZIA v2 — PREMIUM TERMINAL APP            ║
║     Powered by Sky Night Network                 ║
║     github.com/sky-night-net/amnezia-v2-deploy   ║
╚══════════════════════════════════════════════════╝

One-command installer:
  curl -sL https://raw.githubusercontent.com/sky-night-net/amnezia-v2-deploy/main/install.sh | bash
"""

import sys
import os
import importlib
import subprocess
import time
import json

if os.name == 'nt':
    os.system('color')

# Optional/External dependencies
try:
    import bcrypt
    import paramiko
    import requests as req
except ImportError:
    pass

# ─── Version ────────────────────────────────────────────────────────────────
APP_DIR      = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(APP_DIR, "VERSION")
REMOTE_VER_URL = "https://raw.githubusercontent.com/sky-night-net/amnezia-v2-deploy/main/VERSION"

def get_local_version() -> str:
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except Exception:
        return "unknown"

def get_remote_version() -> str:
    """Fetch remote VERSION file. Returns empty string on failure."""
    try:
        import urllib.request
        with urllib.request.urlopen(REMOTE_VER_URL, timeout=5) as r:
            return r.read().decode().strip()
    except Exception:
        return ""

# ─── ANSI Colors ────────────────────────────────────────────────────────────
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

# ─── Constants ──────────────────────────────────────────────────────────────
IMAGE           = "ghcr.io/w0rng/amnezia-wg-easy"
HUB_BASE_IMAGE  = "python:3.10-slim"
SNMP_IMAGE      = "prom/snmp-exporter:latest"
DEFAULT_VPN_PORT = "993"
DEFAULT_WEB_PORT = "4466"
HUB_PORT        = "9292"
LOCAL_ONLY_WEB  = "127.0.0.1"

DEFAULT_STEALTH = {
    "JC": "10", "JMIN": "100", "JMAX": "1000",
    "S1": "15",  "S2": "100",
    "H1": "1234567891", "H2": "1234567892",
    "H3": "1234567893", "H4": "1234567894"
}

# ─── Localisation ───────────────────────────────────────────────────────────
LOCALES = {
    "ru": {
        "select_lang":   "Выберите язык / Select Language (1: RU, 2: EN)",
        "menu_title":    "ГЛАВНОЕ МЕНЮ:",
        "opt_deploy":    "🚀  Развернуть новый VPN-узел",
        "opt_status":    "📡  Статус узла",
        "opt_logs":      "📋  Логи контейнера",
        "opt_configs":   "📂  Конфиги клиентов",
        "opt_hub":       "🖥️   Установить Master Hub",
        "opt_cleanup":   "🗑️   Очистить сервер",
        "opt_exit":      "🚪  Выход",
        "opt_update":    "🔄  Проверить обновления",
        "enter_choice":  "Введите номер действия",
        "upd_checking":  "Проверяю наличие обновлений...",
        "upd_latest":    "У вас уже последняя версия (v{})",
        "upd_avail":     "Доступна новая версия: v{} (у вас v{})",
        "upd_ask":       "Обновить? (y/n)",
        "upd_doing":     "Обновляю...",
        "upd_ok":        "Обновление установлено! Перезапускаю приложение...",
        "upd_fail":      "Ошибка обновления: {}",
        "upd_no_git":    "Git не найден. Скачайте свежую версию вручную.",
        "upd_offline":   "Нет соединения с интернетом. Работаю в оффлайн-режиме.",
        "params_title":  "─── ПАРАМЕТРЫ СЕРВЕРА ───",
        "ip_prompt":     "IP адрес сервера",
        "pass_prompt":   "Пароль SSH (root)",
        "extip_prompt":  "Публичный IP сервера",
        "webport_prompt": "Порт веб-панели",
        "vpnport_prompt": "Порт VPN (UDP)",
        "snmp_prompt":   "Включить SNMP-мониторинг? (y/n)",
        "hub_ip_prompt": "IP вашего Хаба для авторегистрации (Enter = пропустить)",
        "hub_loc_prompt": "Где установить Hub?\n  1 — Локально (на этом компьютере)\n  2 — На удалённом сервере",
        "hub_name_prompt": "Имя этого узла в панели Хаба",
        "conn_error":    "Ошибка подключения: {}",
        "conn_ok":       "SSH соединение установлено",
        "gen_hash":      "Генерирую защищённый хэш пароля...",
        "cleanup_msg":   "Удаляю старые контейнеры...",
        "cleanup_ok":    "Очистка завершена",
        "deploy_start":  "Разворачиваю VPN...",
        "snmp_start":    "Запускаю SNMP-агент...",
        "firewall_msg":  "Настраиваю файрвол (UFW)...",
        "success":       "✅  ГОТОВО!",
        "bye":           "До встречи! 👋",
        "missing_deps":  "Устанавливаю зависимости...",
        "deps_ok":       "Зависимости установлены",
        "client_list":   "Список клиентов:",
        "no_clients":    "Клиентов не найдено",
        "client_choice": "Номер клиента",
        "conf_for":      "Конфигурация для {}:",
        "logs_title":    "Последние 30 строк логов:",
        "hub_deploy":    "Разворачиваю Master Hub в Docker...",
        "hub_ok":        "Хаб запущен! Панель доступна на http://{}:{}",
        "hub_fail":      "Ошибка Хаба: {}",
        "hub_upload":    "Загружаю файлы на сервер...",
        "docker_check":  "Проверяю/устанавливаю Docker на сервере...",
        "token_gen":     "Генерирую токен безопасности...",
        "reg_hub":       "Регистрирую узел в Хабе...",
        "reg_ok":        "Узел зарегистрирован в Хабе ✓",
        "reg_fail":      "Хаб недоступен, пропускаю регистрацию",
        "invalid":       "Неверный выбор, попробуйте снова.",
        "no_ip":         "IP адрес не может быть пустым!",
        "web_public_prompt": "Сделать веб-панель доступной из интернета (0.0.0.0)? (y/n)",
        "hub_install_prompt": "Установить Master Hub на этот сервер? (y/n)",
        "subnet_prompt": "Подсеть VPN (например, 10.8.0.0/24)",
        "adv_stealth_prompt": "Настроить параметры обфускации (Advanced Stealth)? (y/n)",
        "h_subnet":      "Внутренний IP-диапазон VPN (обычно 10.8.0.0/24).",
        "h_jc":          "Количество Junk-пакетов для обфускации.",
        "h_jmin":        "Мин. размер Junk-пакета.",
        "h_jmax":        "Макс. размер Junk-пакета.",
        "h_s1":          "S1: размер первого фрагмента пакета.",
        "h_s2":          "S2: размер второго фрагмента пакета.",
        "h_h":           "Уникальный 4-байтовый заголовок.",
    },
    "en": {
        "select_lang":   "Select Language (1: RU, 2: EN)",
        "menu_title":    "MAIN MENU:",
        "opt_deploy":    "🚀  Deploy new VPN node",
        "opt_status":    "📡  Node status",
        "opt_logs":      "📋  Container logs",
        "opt_configs":   "📂  Client configs",
        "opt_hub":       "🖥️   Install Master Hub",
        "opt_cleanup":   "🗑️   Cleanup server",
        "opt_exit":      "🚪  Exit",
        "opt_update":    "🔄  Check for updates",
        "enter_choice":  "Enter action number",
        "upd_checking":  "Checking for updates...",
        "upd_latest":    "You are on the latest version (v{})",
        "upd_avail":     "New version available: v{} (you have v{})",
        "upd_ask":       "Update now? (y/n)",
        "upd_doing":     "Updating...",
        "upd_ok":        "Update installed! Restarting...",
        "upd_fail":      "Update failed: {}",
        "upd_no_git":    "Git not found. Download the fresh version manually.",
        "upd_offline":   "No internet connection. Running in offline mode.",
        "params_title":  "─── SERVER PARAMETERS ───",
        "ip_prompt":     "Server IP address",
        "pass_prompt":   "SSH Password (root)",
        "extip_prompt":  "Public server IP",
        "webport_prompt": "Web panel port",
        "vpnport_prompt": "VPN port (UDP)",
        "snmp_prompt":   "Enable SNMP monitoring? (y/n)",
        "hub_ip_prompt": "Your Hub IP for auto-registration (Enter = skip)",
        "hub_loc_prompt": "Where to install Hub?\n  1 — Locally (this machine)\n  2 — Remote server",
        "hub_name_prompt": "Node name in Hub dashboard",
        "conn_error":    "Connection error: {}",
        "conn_ok":       "SSH connection established",
        "gen_hash":      "Generating secure password hash...",
        "cleanup_msg":   "Removing old containers...",
        "cleanup_ok":    "Cleanup complete",
        "deploy_start":  "Deploying VPN...",
        "snmp_start":    "Starting SNMP agent...",
        "firewall_msg":  "Configuring firewall (UFW)...",
        "success":       "✅  DONE!",
        "bye":           "Goodbye! 👋",
        "missing_deps":  "Installing dependencies...",
        "deps_ok":       "Dependencies installed",
        "client_list":   "Client list:",
        "no_clients":    "No clients found",
        "client_choice": "Client number",
        "conf_for":      "Config for {}:",
        "logs_title":    "Last 30 log lines:",
        "hub_deploy":    "Deploying Master Hub in Docker...",
        "hub_ok":        "Hub running! Dashboard at http://{}:{}",
        "hub_fail":      "Hub error: {}",
        "hub_upload":    "Uploading files to server...",
        "docker_check":  "Checking/installing Docker on server...",
        "token_gen":     "Generating security token...",
        "reg_hub":       "Registering node with Hub...",
        "reg_ok":        "Node registered with Hub ✓",
        "reg_fail":      "Hub unreachable, skipping registration",
        "invalid":       "Invalid choice, please try again.",
        "no_ip":         "IP address cannot be empty!",
        "web_public_prompt": "Make web panel accessible from internet (0.0.0.0)? (y/n)",
        "hub_install_prompt": "Install Master Hub on this server? (y/n)",
        "subnet_prompt": "VPN Subnet (e.g., 10.8.0.0/24)",
        "adv_stealth_prompt": "Configure Advanced Stealth parameters? (y/n)",
        "h_subnet":      "Internal VPN IP range (usually 10.8.0.0/24).",
        "h_jc":          "Number of Junk packets for obfuscation.",
        "h_jmin":        "Min size of Junk packet.",
        "h_jmax":        "Max size of Junk packet.",
        "h_s1":          "S1: size of the first packet fragment.",
        "h_s2":          "S2: size of the second packet fragment.",
        "h_h":           "Unique 4-byte header.",
    }
}

L = LOCALES["en"]

# ─── Helpers ────────────────────────────────────────────────────────────────

def print_banner():
    os.system("clear" if os.name == "posix" else "cls")
    print(f"""{MAGENTA}{BOLD}
    ╔══════════════════════════════════════════════════╗
    ║        AMNEZIA v2 — PREMIUM TERMINAL APP         ║
    ║        Powered by Sky Night Network              ║
    ╚══════════════════════════════════════════════════╝{RESET}
""")

def ok(text):
    print(f"  {GREEN}{BOLD}✓{RESET} {text}")

def step(text):
    print(f"  {CYAN}→{RESET} {text}")

def err(text):
    print(f"  {RED}{BOLD}✗{RESET} {RED}{text}{RESET}")

def separator():
    print(f"  {DIM}{'─' * 48}{RESET}")

def get_input(prompt, default="", help_text="", required=False):
    """Safe input that works both interactively and via curl|bash."""
    if help_text:
        print(f"  {DIM}ℹ {help_text}{RESET}")
    hint = f" [{default}]" if default else ""
    full_prompt = f"  {CYAN}➤{RESET} {BOLD}{prompt}{hint}{RESET}: "
    while True:
        try:
            val = input(full_prompt).strip()
        except EOFError:
            # Reached when stdin is piped — reconnect to terminal
            try:
                tty_path = "CON" if os.name == "nt" else "/dev/tty"
                sys.stdin = open(tty_path)
                val = input(full_prompt).strip()
            except Exception:
                return default
        result = val if val else default
        if required and not result:
            err(L["no_ip"])
            continue
        return result

def set_language():
    global L
    print(f"\n  {BOLD}{CYAN}➤ {LOCALES['en']['select_lang']}{RESET}")
    choice = get_input("", "1")
    L = LOCALES["ru"] if choice == "1" else LOCALES["en"]
    print()

def install_dependencies():
    """Install Python dependencies, gracefully handle all environments."""
    packages = ["paramiko", "bcrypt", "requests"]
    missing = []
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return

    step(L["missing_deps"])
    # Try in order: venv pip → break-system-packages → user install
    pip_flags_options = [
        [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
        [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + missing,
        [sys.executable, "-m", "pip", "install", "--quiet", "--user"] + missing,
    ]
    for flags in pip_flags_options:
        try:
            subprocess.check_call(flags, stderr=subprocess.DEVNULL)
            ok(L["deps_ok"])
            return
        except subprocess.CalledProcessError:
            continue
    err("Could not install dependencies. Please run: pip install paramiko bcrypt requests")
    sys.exit(1)

def generate_hash(password: str) -> str:
    import bcrypt
    step(L["gen_hash"])
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

# ─── Deployer ───────────────────────────────────────────────────────────────

class AmneziaDeployer:
    def __init__(self, ip: str, password: str,
                 ext_ip: str = "", web_port: str = "",
                 vpn_port: str = "", stealth: dict | None = None):
        import paramiko
        self.ip       = ip
        self.password = password
        self.ext_ip   = ext_ip or ip
        self.web_port = web_port or DEFAULT_WEB_PORT
        self.vpn_port = vpn_port or DEFAULT_VPN_PORT
        self.stealth  = stealth or DEFAULT_STEALTH
        self.client   = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # ── SSH ─────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        step(L["conn_ok"] + f" ({self.ip})")
        try:
            self.client.connect(
                self.ip, username="root",
                password=self.password, timeout=20
            )
            ok(L["conn_ok"])
            return True
        except Exception as e:
            err(L["conn_error"].format(e))
            return False

    def run(self, cmd: str, timeout: int = 120) -> tuple:
        """Execute command on remote host, return (stdout, stderr)."""
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="replace").strip()
        er  = stderr.read().decode(errors="replace").strip()
        return out, er

    def run_quiet(self, cmd: str):
        """Run and ignore errors."""
        try:
            self.run(cmd)
        except Exception:
            pass

    # ── Docker helpers ──────────────────────────────────────────────────────
    def ensure_docker(self):
        step(L["docker_check"])
        out, _ = self.run("docker --version 2>/dev/null || echo MISSING")
        if "MISSING" in out or not out:
            self.run(
                "curl -fsSL https://get.docker.com | sh && "
                "systemctl enable docker && systemctl start docker"
            )
        ok("Docker ready")

    # ── Cleanup ─────────────────────────────────────────────────────────────
    def cleanup(self):
        step(L["cleanup_msg"])
        containers = ["amnezia-wg-easy", "amnezia-snmp", "amnezia-hub"]
        for c in containers:
            self.run_quiet(f"docker stop {c} 2>/dev/null; docker rm {c} 2>/dev/null")
        self.run_quiet("rm -rf ~/.amnezia-wg-easy /opt/amnezia-hub")
        ok(L["cleanup_ok"])

    # ── Deploy VPN node ─────────────────────────────────────────────────────
    def deploy(self, snmp_enabled: bool = False, hub_ip: str = "", 
               public_web: bool = False, subnet: str = "10.8.0.0/24",
               stealth: dict | None = None):
        import secrets
        auth_token = secrets.token_hex(16)
        
        bind_ip = "0.0.0.0" if public_web else LOCAL_ONLY_WEB
        stealth_params = stealth or self.stealth

        # 1. Hash password
        pw_hash = generate_hash(self.password)

        # 2. Ensure Docker
        self.ensure_docker()

        # 3. Start VPN container
        step(L["deploy_start"])
        docker_cmd = (
            f"docker run -d --name=amnezia-wg-easy --restart=unless-stopped "
            f"-e WG_HOST={self.ext_ip} "
            f"-e PASSWORD_HASH='{pw_hash}' "
            f"-e STATS_TOKEN='{auth_token}' "
            f"-e PORT={self.web_port} "
            f"-e WG_PORT={self.vpn_port} "
            f"-e EXPERIMENTAL_AWG=true "
            f"-e JC={stealth_params['JC']} -e JMIN={stealth_params['JMIN']} -e JMAX={stealth_params['JMAX']} "
            f"-e S1={stealth_params['S1']} -e S2={stealth_params['S2']} "
            f"-e H1={stealth_params['H1']} -e H2={stealth_params['H2']} "
            f"-e H3={stealth_params['H3']} -e H4={stealth_params['H4']} "
            f"-e WG_DEFAULT_ADDRESS={subnet} "
            f"-v ~/.amnezia-wg-easy:/etc/wireguard "
            f"-p {bind_ip}:{self.web_port}:{self.web_port}/tcp "
            f"-p {self.vpn_port}:{self.vpn_port}/udp "
            f"--cap-add=NET_ADMIN --cap-add=SYS_MODULE "
            f"--sysctl net.ipv4.conf.all.src_valid_mark=1 "
            f"--sysctl net.ipv4.ip_forward=1 "
            f"--device=/dev/net/tun:/dev/net/tun "
            f"{IMAGE}"
        )
        out, er = self.run(docker_cmd)
        if er and "Error" in er:
            err(f"Docker error: {er[:200]}")
            return False

        # 4. Check if container is actually running
        time.sleep(2)
        ps_res, _ = self.run("docker ps --filter name=amnezia-wg-easy --format '{{.Status}}'")
        if not ps_res:
            err("Container failed to start. Check logs (option 3).")
            # Maybe port is already in use?
            if "Already in use" in out or "already in use" in out or "Already in use" in er or "already in use" in er:
                 err(f"Port {self.web_port} or {self.vpn_port} is already in use!")
            return False
            
        ok("VPN container is running")

        # 4. Optional SNMP agent
        if snmp_enabled:
            step(L["snmp_start"])
            self.run(
                f"docker run -d --name=amnezia-snmp --restart=unless-stopped "
                f"-p 161:161/udp {SNMP_IMAGE}"
            )
            ok("SNMP agent started")

        # 5. Firewall
        step(L["firewall_msg"])
        self.run_quiet("ufw allow 22/tcp")
        self.run_quiet(f"ufw allow {self.vpn_port}/udp")
        if snmp_enabled:
            self.run_quiet("ufw allow 161/udp")
        if public_web:
            self.run_quiet(f"ufw allow {self.web_port}/tcp")
        self.run_quiet("echo y | ufw enable")
        ok("Firewall configured")

        # 6. Also deploy statsCollector on the node
        step("Deploying stats collector on node...")
        # Upload statsCollector_native.py if it exists locally
        local_sc = os.path.join(os.path.dirname(__file__), "statsCollector_native.py")
        if os.path.isfile(local_sc):
            try:
                sftp = self.client.open_sftp()
                sftp.put(local_sc, "/root/statsCollector_native.py")
                sftp.close()
                # Run it in background with the generated token
                self.run(
                    f"STATS_TOKEN={auth_token} nohup python3 "
                    f"/root/statsCollector_native.py > /root/stats.log 2>&1 &"
                )
                ok("Stats collector running")
            except Exception as ex:
                # Non-critical: node works without it
                pass

        # 7. Register with Hub
        if hub_ip and hub_ip.strip():
            step(L["reg_hub"])
            node_name = get_input(L["hub_name_prompt"], self.ip)
            try:
                import requests as req
                payload = {
                    "name":  node_name,
                    "ip":    self.ip,
                    "token": auth_token,
                    "snmp":  snmp_enabled
                }
                r = req.post(
                    f"http://{hub_ip}:{HUB_PORT}/hub/register",
                    json=payload, timeout=5
                )
                if r.status_code == 200:
                    ok(L["reg_ok"])
                else:
                    err(L["reg_fail"])
            except Exception:
                err(L["reg_fail"])

        separator()
        print(f"\n  {GREEN}{BOLD}{L['success']}{RESET}")
        if public_web:
            print(f"  {DIM}Web panel: http://{self.ip}:{self.web_port}")
        else:
            print(f"  {DIM}Web panel: ssh -L {self.web_port}:{LOCAL_ONLY_WEB}:{self.web_port} root@{self.ip}")
            print(f"  Then open: http://localhost:{self.web_port}")
        print(f"{RESET}\n")
        return True

    # ── Status ──────────────────────────────────────────────────────────────
    def check_status(self):
        separator()
        out, _ = self.run(
            "docker ps --filter name=amnezia-wg-easy "
            "--format '{{.Names}} | {{.Status}} | {{.Ports}}'"
        )
        if out:
            ok(f"Container: {out}")
        else:
            err("Container amnezia-wg-easy is NOT running")

        # Check stats collector
        out2, _ = self.run("pgrep -f statsCollector_native.py && echo RUNNING || echo STOPPED")
        if "RUNNING" in out2:
            ok("Stats collector: running")
        else:
            step("Stats collector: stopped (optional)")

        # Disk / memory
        disk, _ = self.run("df -h / | tail -1 | awk '{print $3\"/\"$2\" used\"}'")
        mem,  _ = self.run("free -h | grep Mem | awk '{print $3\"/\"$2\" used\"}'")
        ok(f"Disk: {disk}")
        ok(f"RAM:  {mem}")
        separator()

    # ── Logs ────────────────────────────────────────────────────────────────
    def get_logs(self):
        separator()
        step(L["logs_title"])
        out, _ = self.run("docker logs --tail 30 amnezia-wg-easy 2>&1")
        print(f"\n{DIM}{out or '(empty)'}{RESET}\n")
        separator()

    # ── Client Configs ──────────────────────────────────────────────────────
    def get_configs(self):
        step(L["client_list"])
        out, _ = self.run(
            "docker exec amnezia-wg-easy cat /etc/wireguard/wg0.json 2>/dev/null || echo '{}'"
        )
        try:
            data    = json.loads(out)
            clients = data.get("clients", [])
        except (json.JSONDecodeError, Exception):
            clients = []

        if not clients:
            err(L["no_clients"])
            return

        separator()
        for i, c in enumerate(clients):
            status = f"{GREEN}●{RESET}" if c.get("enabled", True) else f"{RED}○{RESET}"
            print(f"  {CYAN}{i+1}.{RESET} {status} {c.get('name','?')}  {DIM}{c.get('address','')}{RESET}")
        separator()

        idx_str = get_input(L["client_choice"], "1")
        try:
            if not idx_str:
                raise ValueError
            idx    = int(idx_str) - 1
            target = clients[idx]
        except (ValueError, IndexError):
            err(L["invalid"])
            return

        cid = target.get("id", "")
        cname = target.get("name", "client")
        if not cid:
            err("Client has no ID")
            return

        conf, _ = self.run(
            f"docker exec amnezia-wg-easy cat /etc/wireguard/clients/{cid}.conf 2>/dev/null"
        )
        if conf:
            print(f"\n  {BOLD}{L['conf_for'].format(cname)}{RESET}\n")
            print(f"{YELLOW}{conf}{RESET}\n")
        else:
            err("Config file not found on server")

    # ── Master Hub ──────────────────────────────────────────────────────────
    def setup_hub(self, remote: bool = False, hub_ip: str = ""):
        print(f"\n  {BOLD}{MAGENTA}{L['hub_deploy']}{RESET}")
        hub_src = os.path.join(os.path.dirname(__file__), "stats_hub")
        if not os.path.isdir(hub_src):
            err("stats_hub/ directory not found next to this script.")
            return

        # Write Dockerfile
        dockerfile = (
            f"FROM {HUB_BASE_IMAGE}\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install --quiet flask flask-cors requests\n"
            'CMD ["python", "hub_server.py"]\n'
        )
        with open(os.path.join(hub_src, "Dockerfile"), "w") as f:
            f.write(dockerfile)

        try:
            if not remote:
                # ── LOCAL Docker build ───────────────────────────────────
                # Verify Docker is available
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    err("Docker is not running. Please start Docker Desktop first.")
                    return

                step("Stopping old Hub container if any...")
                subprocess.run(
                    ["docker", "rm", "-f", "amnezia-hub"],
                    capture_output=True
                )

                step("Building Hub image (this may take 1-2 min)...")
                subprocess.check_call(
                    ["docker", "build", "-t", "amnezia-hub", hub_src],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                step("Starting Hub container...")
                subprocess.check_call([
                    "docker", "run", "-d",
                    "--name", "amnezia-hub",
                    "--restart", "always",
                    "-p", f"{HUB_PORT}:{HUB_PORT}",
                    "amnezia-hub"
                ])
                display_ip = "localhost"

            else:
                # ── REMOTE Docker deploy ─────────────────────────────────
                self.ensure_docker()

                step(L["hub_upload"])
                sftp = self.client.open_sftp()
                self.run("mkdir -p /opt/amnezia-hub")
                for fname in os.listdir(hub_src):
                    local_file = os.path.join(hub_src, fname)
                    if os.path.isfile(local_file):
                        sftp.put(local_file, f"/opt/amnezia-hub/{fname}")
                sftp.close()

                step("Building Hub on remote server...")
                self.run(
                    "docker rm -f amnezia-hub 2>/dev/null; "
                    "cd /opt/amnezia-hub && "
                    f"docker build -t amnezia-hub . && "
                    f"docker run -d --name amnezia-hub --restart always "
                    f"-p {HUB_PORT}:{HUB_PORT} amnezia-hub"
                )
                display_ip = self.ip

            separator()
            ok(L["hub_ok"].format(display_ip, HUB_PORT))
            print(f"  {DIM}Dashboard: http://{display_ip}:{HUB_PORT}/hub/stats{RESET}\n")

        except subprocess.CalledProcessError as e:
            err(L["hub_fail"].format(str(e)))
        except Exception as e:
            err(L["hub_fail"].format(str(e)))


# ─── Updater ─────────────────────────────────────────────────────────────────

def do_update():
    separator()
    step(L["upd_checking"])
    local_ver = get_local_version()
    remote_ver = get_remote_version()
    
    if not remote_ver:
        err(L["upd_offline"])
        return
        
    if local_ver == remote_ver:
        ok(L["upd_latest"].format(local_ver))
        return
        
    step(L["upd_avail"].format(remote_ver, local_ver))
    ans = get_input(L["upd_ask"], "n")
    if ans and ans.lower() not in ("y", "yes", "да", "д"):
        return
        
    step(L["upd_doing"])
    try:
        if os.path.exists(os.path.join(APP_DIR, ".git")):
            subprocess.check_output(
                ["git", "pull", "--ff-only", "--quiet"], 
                stderr=subprocess.STDOUT, 
                cwd=APP_DIR
            )
        else:
            # Python Native ZIP fallback for standalone/Windows users without Git
            import urllib.request
            import zipfile
            import io
            zip_url = "https://github.com/sky-night-net/amnezia-v2-deploy/archive/refs/heads/main.zip"
            req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                with zipfile.ZipFile(io.BytesIO(resp.read())) as z:
                    for file_info in z.infolist():
                        if file_info.is_dir(): continue
                        parts = file_info.filename.split('/', 1)
                        if len(parts) > 1 and parts[1]:
                            target_path = os.path.join(APP_DIR, parts[1])
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(z.read(file_info.filename))
        ok(L["upd_ok"])
        time.sleep(1)
        os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
        
    except subprocess.CalledProcessError as e:
        out = e.output.decode(errors="replace")
        if "not a git repository" in out.lower():
            err(L["upd_no_git"])
        else:
            err(L["upd_fail"].format(out.strip()[:100]))
    except Exception as e:
        err(L["upd_fail"].format(str(e)[:100]))


# ─── Menu ────────────────────────────────────────────────────────────────────

def run_cli():
    print_banner()
    set_language()
    install_dependencies()
    
    last_ip = ""
    last_pw = ""

    while True:
        print_banner()
        print(f"  {BOLD}{L['menu_title']}{RESET}\n")
        opts = [
            L["opt_deploy"],  # 1
            L["opt_status"],  # 2
            L["opt_logs"],    # 3
            L["opt_configs"], # 4
            L["opt_hub"],     # 5
            L["opt_cleanup"], # 6
            L["opt_update"],  # 7
        ]
        for i, opt in enumerate(opts, 1):
            print(f"  {CYAN}{i}{RESET}. {opt}")
        print(f"\n  {DIM}0{RESET}. {L['opt_exit']}")
        separator()

        choice = get_input(L["enter_choice"], "1")

        if choice == "0":
            print(f"\n  {GREEN}{L['bye']}{RESET}\n")
            sys.exit(0)

        if choice not in ("1", "2", "3", "4", "5", "6", "7"):
            err(L["invalid"])
            time.sleep(1)
            continue

        # ── Local actions (no SSH needed) ────────────────────────────────
        
        if choice == "7":
            do_update()
            input(f"\n  {DIM}Press Enter to continue...{RESET}")
            continue

        if choice == "5":
            print(f"\n  {BOLD}{L['params_title']}{RESET}\n")
            loc = get_input(L["hub_loc_prompt"], "1")
            if loc == "2":
                hub_ip  = get_input(L["ip_prompt"],   required=True)
                hub_pw  = get_input(L["pass_prompt"],  required=True)
                d = AmneziaDeployer(hub_ip, hub_pw)
                if d.connect():
                    d.setup_hub(remote=True, hub_ip=hub_ip)
            else:
                # Local hub — no SSH needed, create a dummy deployer just for hub logic
                d = AmneziaDeployer.__new__(AmneziaDeployer)
                d.ip = "localhost"
                d.setup_hub(remote=False)
            input(f"\n  {DIM}Press Enter to continue...{RESET}")
            continue

        # ── All other actions require SSH ────────────────────────────────
        print(f"\n  {BOLD}{L['params_title']}{RESET}\n")
        
        server_ip = get_input(L["ip_prompt"], last_ip, required=not bool(last_ip))
        server_pw = get_input(L["pass_prompt"], last_pw, required=not bool(last_pw))
        
        last_ip, last_pw = server_ip, server_pw

        if choice in ("1",):
            # Deploy needs more params
            ext_ip   = get_input(L["extip_prompt"],   server_ip)
            web_port = get_input(L["webport_prompt"],  DEFAULT_WEB_PORT)
            vpn_port = get_input(L["vpnport_prompt"],  DEFAULT_VPN_PORT)
            
            web_pub_ans = get_input(L["web_public_prompt"], "n")
            public_web = (web_pub_ans.lower() == "y")
            
            vpn_subnet = get_input(L["subnet_prompt"], "10.8.0.0/24", L["h_subnet"])
            
            stealth_dict = DEFAULT_STEALTH.copy()
            adv_ans = get_input(L["adv_stealth_prompt"], "n")
            if adv_ans.lower() == "y":
                stealth_dict["JC"]   = get_input("  JC",   stealth_dict["JC"],   L["h_jc"])
                stealth_dict["JMIN"] = get_input("  JMIN", stealth_dict["JMIN"], L["h_jmin"])
                stealth_dict["JMAX"] = get_input("  JMAX", stealth_dict["JMAX"], L["h_jmax"])
                stealth_dict["S1"]   = get_input("  S1",   stealth_dict["S1"],   L["h_s1"])
                stealth_dict["S2"]   = get_input("  S2",   stealth_dict["S2"],   L["h_s2"])
                stealth_dict["H1"]   = get_input("  H1",   stealth_dict["H1"],   L["h_h"])
                stealth_dict["H2"]   = get_input("  H2",   stealth_dict["H2"],   L["h_h"])
                stealth_dict["H3"]   = get_input("  H3",   stealth_dict["H3"],   L["h_h"])
                stealth_dict["H4"]   = get_input("  H4",   stealth_dict["H4"],   L["h_h"])

            snmp_ans = get_input(L["snmp_prompt"],     "n")
            
            hub_local_ans = get_input(L["hub_install_prompt"], "n")
            install_hub = (hub_local_ans.lower() == "y")
            
            hub_ip   = get_input(L["hub_ip_prompt"],   "")

            deployer = AmneziaDeployer(server_ip, server_pw, ext_ip, web_port, vpn_port)
            if deployer.connect():
                deployer.cleanup()
                snmp_val = (snmp_ans.lower() == "y")
                
                # Если Хаб ставится на этот же сервер, ставим его ДО деплоя VPN,
                # чтобы регистрация в Hub прошла успешно.
                if install_hub and (not hub_ip or hub_ip == server_ip):
                    deployer.setup_hub(remote=True)
                    hub_ip = server_ip

                if deployer.deploy(
                    snmp_enabled=snmp_val,
                    hub_ip=hub_ip,
                    public_web=public_web,
                    subnet=vpn_subnet,
                    stealth=stealth_dict
                ):
                    # Если Хаб ставится на другой сервер, ставим его после (хотя обычно наоборот)
                    # Но если он уже стоит (install_hub был True и мы его уже поставили выше), 
                    # то повторно не вызываем.
                    if install_hub and hub_ip != server_ip:
                         deployer.setup_hub(remote=True)
        else:
            deployer = AmneziaDeployer(server_ip, server_pw)
            if not deployer.connect():
                input(f"\n  {DIM}Press Enter to continue...{RESET}")
                continue

            if choice == "2":
                deployer.check_status()
            elif choice == "3":
                deployer.get_logs()
            elif choice == "4":
                deployer.get_configs()
            elif choice == "6":
                confirm = get_input("Are you sure? (yes/no)", "no")
                if confirm.lower() in ("y", "yes", "д", "да"):
                    deployer.cleanup()

        input(f"\n  {DIM}Press Enter to continue...{RESET}")


if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Interrupted.{RESET}\n")
        sys.exit(0)
