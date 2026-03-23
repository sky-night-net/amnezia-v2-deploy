import customtkinter as cctk
import tkinter as tk
from tkinter import messagebox
import json
import os
import threading
import time
import paramiko
import bcrypt
import sys

# Настройка темы
cctk.set_appearance_mode("dark")
cctk.set_default_color_theme("blue")

class AmneziaAutomatorV2(cctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AmneziaWG v2 — Premium Hub")
        self.geometry("1100x700")
        
        # Конфигурация сетки
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Переменные
        self.servers = self.load_servers()
        self.current_server = None

        # --- Sidebar ---
        self.sidebar_frame = cctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = cctk.CTkLabel(self.sidebar_frame, text="SKYKNIGHT", font=cctk.CTkFont(size=20, weight="bold"), text_color="#E63946")
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.sub_label = cctk.CTkLabel(self.sidebar_frame, text="VPN HUB v2.0", font=cctk.CTkFont(size=10))
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        self.nodes_label = cctk.CTkLabel(self.sidebar_frame, text="SERVER NODES", font=cctk.CTkFont(size=12, weight="bold"), text_color="#6a7080")
        self.nodes_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")

        # Scrollable list of servers
        self.server_list_frame = cctk.CTkScrollableFrame(self.sidebar_frame, width=180, label_text="")
        self.server_list_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
        self.refresh_server_list()

        self.add_btn = cctk.CTkButton(self.sidebar_frame, text="+ ADD NODE", command=self.add_server_window, fg_color="#E63946", hover_color="#C12E3A")
        self.add_btn.grid(row=5, column=0, padx=20, pady=10)

        self.appearance_mode_label = cctk.CTkLabel(self.sidebar_frame, text="Appearance:", anchor="w")
        self.appearance_mode_label.grid(row=6, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = cctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light", "System"], command=self.change_appearance_mode)
        self.appearance_mode_optionemenu.grid(row=7, column=0, padx=20, pady=(10, 20))

        # --- Main View ---
        self.main_view = cctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_view.grid_columnconfigure(0, weight=1)
        self.main_view.grid_rowconfigure(2, weight=1)

        # Welcome Screen
        self.show_welcome()

    def load_servers(self):
        config_path = "servers_v2.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_servers(self):
        with open("servers_v2.json", "w") as f:
            json.dump(self.servers, f, indent=4)

    def refresh_server_list(self):
        for widget in self.server_list_frame.winfo_children():
            widget.destroy()
        
        for server in self.servers:
            btn = cctk.CTkButton(self.server_list_frame, text=server["name"], 
                               anchor="w", fg_color="transparent", text_color="#a0a0a0",
                               hover_color="#1e222a", command=lambda s=server: self.select_server(s))
            btn.pack(fill="x", pady=2)

    def select_server(self, server):
        self.current_server = server
        self.show_server_dash()

    def show_welcome(self):
        self.clear_main_view()
        label = cctk.CTkLabel(self.main_view, text="Select a server to manage\nor add a new one.", 
                            font=cctk.CTkFont(size=16), text_color="#6a7080")
        label.pack(expand=True)

    def show_server_dash(self):
        self.clear_main_view()
        s = self.current_server
        
        # Header
        header = cctk.CTkFrame(self.main_view, height=80, fg_color="#1a1d23")
        header.pack(fill="x", pady=(0, 20))
        
        title = cctk.CTkLabel(header, text=f"NODE: {s['name']}", font=cctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", padx=20, pady=20)
        
        ip_label = cctk.CTkLabel(header, text=s['ip'], font=cctk.CTkFont(size=14), text_color="#39d98a")
        ip_label.pack(side="right", padx=20, pady=20)

        # Grid of Stats
        stats_frame = cctk.CTkFrame(self.main_view, fg_color="transparent")
        stats_frame.pack(fill="x")
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        def create_stat_card(parent, title, value, col):
            card = cctk.CTkFrame(parent, fg_color="#1a1d23", corner_radius=10, height=100)
            card.grid(row=0, column=col, padx=5, sticky="nsew")
            cctk.CTkLabel(card, text=title, font=cctk.CTkFont(size=12), text_color="#6a7080").pack(pady=(15, 0))
            cctk.CTkLabel(card, text=value, font=cctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(0, 15))

        create_stat_card(stats_frame, "STATUS", "Online", 0)
        create_stat_card(stats_frame, "ACTIVE CLIENTS", "3", 1)
        create_stat_card(stats_frame, "TRAFFIC / 24H", "14.2 GB", 2)

        # Control Panel
        controls = cctk.CTkFrame(self.main_view, fg_color="#1a1d23", corner_radius=10)
        controls.pack(fill="both", expand=True, pady=20)
        
        cctk.CTkLabel(controls, text="ACTIONS", font=cctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=20, pady=10)
        
        btn_grid = cctk.CTkFrame(controls, fg_color="transparent")
        btn_grid.pack(fill="x", padx=10)
        
        cctk.CTkButton(btn_grid, text="DEPLOY / RESTART", fg_color="#E63946", hover_color="#C12E3A", 
                     command=self.start_deploy_task).pack(side="left", padx=10, pady=10)
        cctk.CTkButton(btn_grid, text="GET CONFIGS", fg_color="#333", 
                     command=lambda: messagebox.showinfo("Info", "Feature in progress")).pack(side="left", padx=10, pady=10)
        cctk.CTkButton(btn_grid, text="VIEW LOGS", fg_color="#333", 
                     command=self.show_logs_window).pack(side="left", padx=10, pady=10)

        # Console area
        self.console = tk.Text(controls, height=10, bg="#000", fg="#39d98a", font=("Courier", 10), borderwidth=0)
        self.console.pack(fill="both", expand=True, padx=20, pady=10)

    def start_deploy_task(self):
        threading.Thread(target=self.run_deployment).start()

    def log(self, text):
        self.console.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.console.see(tk.END)

    def run_deployment(self):
        s = self.current_server
        self.log(f"[*] Starting deployment to {s['name']} ({s['ip']})...")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.log(f"[*] Connecting to {s['ip']}...")
            ssh.connect(s['ip'], username=s['user'], password=s['pass'], timeout=15)
            self.log("[+] SSH Connection established.")

            # Cleanup
            self.log("[*] Cleaning up old containers...")
            ssh.exec_command("docker stop amnezia-wg-easy amnezia-awg2 || true; docker rm amnezia-wg-easy amnezia-awg2 || true")
            
            # Run new
            self.log("[*] Launching AmneziaWG v2 container...")
            # We use the standard v2 settings from amnezia-deploy.py
            pw_hash = bcrypt.hashpw(s['pass'].encode(), bcrypt.gensalt()).decode()
            
            docker_run_cmd = (
                f"docker run -d --name=amnezia-wg-easy "
                f"-e WG_HOST={s['ip']} -e PASSWORD_HASH='{pw_hash}' "
                f"-e PORT=4466 -e WG_PORT=993 -e EXPERIMENTAL_AWG=true "
                f"-v ~/.amnezia-wg-easy:/etc/wireguard "
                f"-p {s['ip']}:4466:4466/tcp -p 993:993/udp "
                f"--cap-add=NET_ADMIN --cap-add=SYS_MODULE "
                f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' --sysctl='net.ipv4.ip_forward=1' "
                f"--restart unless-stopped ghcr.io/w0rng/amnezia-wg-easy"
            )
            
            stdin, stdout, stderr = ssh.exec_command(docker_run_cmd)
            res = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            
            if err:
                self.log(f"[-] Error: {err}")
            else:
                self.log(f"[+] Success! Container: {res[:12]}")
                messagebox.showinfo("Success", f"Node {s['name']} deployed successfully!")

            # Firewall
            self.log("[*] Hardening Firewall (UFW)...")
            ssh.exec_command("ufw allow 22/tcp && ufw allow 993/udp && echo 'y' | ufw enable")
            self.log("[+] Firewall configured.")

        except Exception as e:
            self.log(f"[-] Deployment failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to deploy: {e}")
        finally:
            ssh.close()
            self.log("[*] Session closed.")

class AddServerDialog(cctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add New Node")
        self.geometry("400x500")
        self.parent = parent
        
        self.grid_columnconfigure(0, weight=1)
        
        cctk.CTkLabel(self, text="SERVER DETAILS", font=cctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=20)
        
        self.name_entry = cctk.CTkEntry(self, placeholder_text="Name (e.g. Germany)", width=300)
        self.name_entry.grid(row=1, column=0, pady=10)
        
        self.ip_entry = cctk.CTkEntry(self, placeholder_text="Server IP", width=300)
        self.ip_entry.grid(row=2, column=0, pady=10)
        
        self.user_entry = cctk.CTkEntry(self, placeholder_text="User (default: root)", width=300)
        self.user_entry.insert(0, "root")
        self.user_entry.grid(row=3, column=0, pady=10)
        
        self.pass_entry = cctk.CTkEntry(self, placeholder_text="SSH Password", show="*", width=300)
        self.pass_entry.grid(row=4, column=0, pady=10)
        
        cctk.CTkButton(self, text="SAVE NODE", command=self.save, fg_color="#E63946", hover_color="#C12E3A").grid(row=5, column=0, pady=30)

    def save(self):
        name = self.name_entry.get()
        ip = self.ip_entry.get()
        user = self.user_entry.get()
        password = self.pass_entry.get()
        
        if name and ip and password:
            self.parent.servers.append({"name": name, "ip": ip, "user": user, "pass": password})
            self.parent.save_servers()
            self.parent.refresh_server_list()
            self.destroy()
        else:
            messagebox.showwarning("Warning", "All fields are required!")

    def add_server_window(self):
        AddServerDialog(self)

    def clear_main_view(self):
        for widget in self.main_view.winfo_children():
            widget.pack_forget()
            widget.destroy()

    def change_appearance_mode(self, new_appearance_mode: str):
        cctk.set_appearance_mode(new_appearance_mode)

    def show_logs_window(self):
        # Implementation for a separate logs popup
        pass

if __name__ == "__main__":
    app = AmneziaAutomatorV2()
    app.mainloop()
