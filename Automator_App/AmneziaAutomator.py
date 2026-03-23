import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import paramiko
import threading
import json
import bcrypt
import os
import time
import sys
import base64

class AmneziaAutomator:
    def __init__(self, root):
        self.root = root
        self.root.title("Amnezia Automator v2.0 - GitHub Special")
        self.root.geometry("650x850")
        self.root.configure(bg="#0f1218")
        
        # Ресурсный путь (для PyInstaller)
        self.base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", foreground="#a0a0a0", background="#0f1218", font=("Outfit", 10))
        self.setup_ui()
        
    def setup_ui(self):
        # Header with logo
        header = tk.Frame(self.root, bg="#0f1218", pady=20)
        header.pack(fill="x")
        
        try:
            logo_path = os.path.join(self.base_path, "logo_sk.png")
            if os.path.exists(logo_path):
                self.logo_img = tk.PhotoImage(file=logo_path).subsample(4, 4)
                tk.Label(header, image=self.logo_img, bg="#0f1218").pack()
        except:
            pass
            
        tk.Label(header, text="SKYKNIGHT VPN", font=("Outfit", 18, "bold"), bg="#0f1218", fg="#e63946").pack()
        tk.Label(header, text="AUTOMATION ENGINE v2.0", font=("Outfit", 8), bg="#0f1218", fg="#6a7080").pack()

        # Canvas for scroll if needed
        container = tk.Frame(self.root, bg="#0f1218", padx=30)
        container.pack(fill="both", expand=True)

        # Fields
        self.inputs = {}
        fields = [
            ("IP сервера", "95.85.116.86"),
            ("SSH Логин", "root"),
            ("SSH Пароль", "1q2w3e!@571"),
            ("Порт VPN (UDP)", "993"),
            ("Порт Панели (TCP)", "4455"),
            ("Мастер-пароль", "1q2w3e!@571"),
        ]

        for label, default in fields:
            f_group = tk.Frame(container, bg="#0f1218", pady=5)
            f_group.pack(fill="x")
            tk.Label(f_group, text=label, width=20, anchor="w", fg="#a0a0a0").pack(side="left")
            entry = tk.Entry(f_group, bg="#1a1d23", fg="white", borderwidth=0, highlightthickness=1, highlightbackground="#333", insertbackground="white")
            entry.insert(0, default)
            entry.pack(side="right", fill="x", expand=True)
            self.inputs[label] = entry

        # Tokens Section
        tk.Label(container, text="Токены обфускации (I1/I2)", font=("Outfit", 10, "bold"), fg="#e63946", bg="#0f1218").pack(pady=(20, 10), anchor="w")
        
        self.i1_entry = tk.Entry(container, bg="#1a1d23", fg="#39d98a", highlightthickness=1, highlightbackground="#333")
        self.i1_entry.insert(0, "0x474554202f706c617965722f322f3237303534363f736561736f6e49643d34383833353226657069736f646549643d353032383933266261636b55726c3d687474707325334125324625324662656c65742e746d25324620485454502f312e310d0a486f73743a2062656c65742e746d0d0a0d0a")
        self.i1_entry.pack(fill="x", pady=2)
        
        self.i2_entry = tk.Entry(container, bg="#1a1d23", fg="#39d98a", highlightthickness=1, highlightbackground="#333")
        self.i2_entry.insert(0, "0x1234010000010000000000000573706565640562656c6574026d650000010001")
        self.i2_entry.pack(fill="x", pady=2)

        # Build Button
        self.btn = tk.Button(container, text="DEPLOY NETWORK", bg="#e63946", fg="white", font=("Outfit", 12, "bold"), 
                           borderwidth=0, cursor="hand2", command=self.start_deploy)
        self.btn.pack(fill="x", pady=25)

        # Logs
        self.log_area = scrolledtext.ScrolledText(container, height=12, bg="#000", fg="#00ff00", font=("Courier", 9), borderwidth=0)
        self.log_area.pack(fill="both", expand=True, pady=(0, 20))

    def log(self, text):
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def start_deploy(self):
        self.btn.config(state="disabled", text="DEPLOYING...")
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        ssh = None
        try:
            ip = self.inputs["IP сервера"].get()
            user = self.inputs["SSH Логин"].get()
            pwd = self.inputs["SSH Пароль"].get()
            wg_p = self.inputs["Порт VPN (UDP)"].get()
            web_p = self.inputs["Порт Панели (TCP)"].get()
            master = self.inputs["Мастер-пароль"].get()
            i1_val = self.i1_entry.get()
            i2_val = self.i2_entry.get()

            self.log(f"[*] Инициализация SSH соединения с {ip}...")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=user, password=pwd)

            # 1. Проверка Docker
            self.log("[*] Проверка Docker на сервере...")
            stdin, stdout, stderr = ssh.exec_command("docker --version")
            if stdout.channel.recv_exit_status() != 0:
                self.log("[!] Docker не найден. Начинаю автоматическую установку...")
                ssh.exec_command("curl -fsSL https://get.docker.com | sh")
                time.sleep(2)
            else:
                self.log("[+] Docker уже установлен.")

            # 2. Подготовка Dashboard
            self.log("[*] Подготовка Premium Dashboard...")
            # Создаем папку на сервере
            ssh.exec_command("mkdir -p /root/dashboard/frontend /root/dashboard/backend")
            
            sftp = ssh.open_sftp()
            
            # Пути к компонентам
            if hasattr(sys, '_MEIPASS'):
                dash_base = os.path.join(self.base_path, "Amnezia_Premium_Dashboard")
            else:
                dash_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Amnezia_Premium_Dashboard")
            
            frontend_files = ["index.html", "style.css", "app.js", "logo_sk.png"]
            
            for f in frontend_files:
                local_f = os.path.join(dash_base, "frontend", f)
                if os.path.exists(local_f):
                    if f == "app.js":
                        with open(local_f, 'r') as file:
                            content = file.read()
                        # Инъекция токенов
                        content = content.replace("const i1 = '0x...';", f"const i1 = '{i1_val}';")
                        content = content.replace("const i2 = '0x...';", f"const i2 = '{i2_val}';")
                        temp_path = "/tmp/app_patched.js"
                        with open(temp_path, 'w') as temp_f:
                            temp_f.write(content)
                        sftp.put(temp_path, f"/root/dashboard/frontend/{f}")
                    else:
                        sftp.put(local_f, f"/root/dashboard/frontend/{f}")
            
            # Backend (statsCollector)
            collector_path = os.path.join(dash_base, "backend", "statsCollector.py")
            if os.path.exists(collector_path):
                sftp.put(collector_path, "/root/dashboard/backend/statsCollector.py")

            sftp.close()

            # 3. Запуск VPN
            self.log("[*] Развертывание VPN контейнера...")
            pw_hash = bcrypt.hashpw(master.encode(), bcrypt.gensalt()).decode()
            
            # Остановка старого
            ssh.exec_command("docker stop amnezia-wg-easy || true && docker rm amnezia-wg-easy || true")
            
            docker_cmd = (
                f"docker run -d --name=amnezia-wg-easy "
                f"-e WG_HOST={ip} -e PASSWORD_HASH='{pw_hash}' "
                f"-e PORT={web_p} -e WG_PORT={wg_p} -e EXPERIMENTAL_AWG=true "
                f"-v /root/.amnezia-wg-easy:/etc/wireguard "
                f"-v /root/dashboard/frontend:/app/www "
                f"-p {wg_p}:{wg_p}/udp -p {web_p}:{web_p}/tcp "
                f"--cap-add=NET_ADMIN --cap-add=SYS_MODULE "
                f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' --sysctl='net.ipv4.ip_forward=1' "
                f"--restart unless-stopped ghcr.io/w0rng/amnezia-wg-easy"
            )
            ssh.exec_command(docker_cmd)

            # 4. Запуск бэкенда статистики
            self.log("[*] Запуск системы аналитики...")
            ssh.exec_command("apt-get install -y python3-pip && pip3 install flask flask-cors apscheduler --break-system-packages || true")
            ssh.exec_command("nohup python3 /root/dashboard/backend/statsCollector.py > /dev/null 2>&1 &")

            # 5. UFW
            self.log("[*] Настройка Firewall...")
            ssh.exec_command("ufw allow 22/tcp && ufw allow 9191/tcp")
            ssh.exec_command(f"ufw allow {wg_p}/udp && ufw allow {web_p}/tcp")
            ssh.exec_command("echo 'y' | ufw enable")

            self.log("[+] ПРОЦЕСС ЗАВЕРШЕН УСПЕШНО!")
            messagebox.showinfo("SkyKnight Deployer", f"Сеть успешно развернута!\nПанель: http://{ip}:{web_p}")

        except Exception as e:
            self.log(f"[!] ОШИБКА: {str(e)}")
            messagebox.showerror("Deployment Error", str(e))
        finally:
            if ssh: ssh.close()
            self.btn.config(state="normal", text="DEPLOY NETWORK")

if __name__ == "__main__":
    root = tk.Tk()
    app = AmneziaAutomator(root)
    root.mainloop()
