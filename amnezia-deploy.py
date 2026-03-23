#!/usr/bin/env python3
import sys
import os
import argparse
import paramiko
import bcrypt
import time

# --- Constants / Default Settings ---
IMAGE = "ghcr.io/w0rng/amnezia-wg-easy"
VPN_PORT = "993"
WEB_PORT = "4466"
STEALTH_PARAMS = {
    "JC": "10",
    "JMIN": "100",
    "JMAX": "1000",
    "S1": "15",
    "S2": "100",
    "H1": "1234567891",
    "H2": "1234567892",
    "H3": "1234567893",
    "H4": "1234567894"
}

def generate_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def deploy_server(ip, password, ext_ip):
    print(f"[*] Starting deployment to {ip}...")
    
    # 1. Generate Hash
    # Note: the $ character needs to be escaped in some contexts, but here it is a string.
    pw_hash = generate_hash(password)
    print(f"[*] Generated password hash.")

    # 2. Connect via SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, username='root', password=password)
        print(f"[+] Connected to {ip}")

        # 3. Cleanup old stuff
        print("[*] Cleaning up old amnezia containers...")
        stdin, stdout, stderr = ssh.exec_command("docker stop amnezia-wg-easy amnezia-awg2 || true; docker rm amnezia-wg-easy amnezia-awg2 || true")
        stdout.read() # Wait for completion

        # 4. Create config directory
        print("[*] Creating config directory...")
        ssh.exec_command("mkdir -p ~/.amnezia-wg-easy")

        # 5. Run new container
        print("[*] Launching new amnezia-wg-easy container...")
        docker_run_cmd = (
            f"docker run -d "
            f"--name=amnezia-wg-easy "
            f"-e WG_HOST={ext_ip} "
            f"-e PASSWORD_HASH='{pw_hash}' "
            f"-e PORT={WEB_PORT} "
            f"-e WG_PORT={VPN_PORT} "
            f"-e EXPERIMENTAL_AWG=true "
            f"-e JC={STEALTH_PARAMS['JC']} -e JMIN={STEALTH_PARAMS['JMIN']} -e JMAX={STEALTH_PARAMS['JMAX']} "
            f"-e S1={STEALTH_PARAMS['S1']} -e S2={STEALTH_PARAMS['S2']} "
            f"-e H1={STEALTH_PARAMS['H1']} -e H2={STEALTH_PARAMS['H2']} -e H3={STEALTH_PARAMS['H3']} -e H4={STEALTH_PARAMS['H4']} "
            f"-v ~/.amnezia-wg-easy:/etc/wireguard "
            f"-p {ip}:{WEB_PORT}:{WEB_PORT}/tcp "
            f"-p {VPN_PORT}:{VPN_PORT}/udp "
            f"--cap-add=NET_ADMIN "
            f"--cap-add=SYS_MODULE "
            f"--sysctl='net.ipv4.conf.all.src_valid_mark=1' "
            f"--sysctl='net.ipv4.ip_forward=1' "
            f"--device=/dev/net/tun:/dev/net/tun "
            f"--restart unless-stopped "
            f"{IMAGE}"
        )
        
        stdin, stdout, stderr = ssh.exec_command(docker_run_cmd)
        result = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            print(f"[-] Error during docker run: {error}")
            return
        
        print(f"[+] Container started: {result[:12]}")

        # 6. Configure UFW
        print("[*] Hardening server with UFW...")
        commands = [
            "ufw allow 22/tcp",
            "ufw allow 993/udp",
            "echo 'y' | ufw enable"
        ]
        for cmd in commands:
            ssh.exec_command(cmd)
        
        print("[+] Firewall configured.")
        print(f"\n[SUCCESS] Server {ip} is ready!")
        print(f"Web UI: http://{ip}:{WEB_PORT}")
        print(f"VPN Port: {VPN_PORT} (UDP) on {ext_ip}")

    except Exception as e:
        print(f"[-] Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amnezia VPN Deployer")
    parser.add_argument("--ip", required=True, help="Server local/private IP")
    parser.add_argument("--password", required=True, help="Root password")
    parser.add_argument("--ext-ip", required=True, help="Server public/external IP for clients")
    
    args = parser.parse_args()
    deploy_server(args.ip, args.password, args.ext_ip)
