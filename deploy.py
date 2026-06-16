#!/usr/bin/env python3
"""
QoS CAKE Adaptive - Windows-to-STB Deployment Script
Skrip ini berjalan di Windows untuk menyalin seluruh folder proyek qos-cake-adaptive
ke home directory STB (192.168.1.21) via SFTP. Setelah disalin, Anda dapat
masuk ke STB via SSH dan menjalankan instalasi lokal.
"""

import os
import sys
import paramiko

STB_IP = "192.168.1.21"
STB_USER = "freischutz"
STB_PASS = "kiken"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def sftp_upload_dir(sftp, local_dir, remote_dir):
    try:
        sftp.mkdir(remote_dir)
        print(f"[+] Membuat direktori remote: {remote_dir}")
    except IOError:
        pass  # Direktori sudah ada

    for item in os.listdir(local_dir):
        # Abaikan folder/file temporer, git, cache, atau skrip deployment itu sendiri
        if item in [".git", "__pycache__", ".idea", "deploy.py", "test_ssh_stb.py", "test_ssh_local.py"]:
            continue

        local_path = os.path.join(local_dir, item)
        remote_path = os.path.join(remote_dir, item).replace("\\", "/")

        if os.path.isdir(local_path):
            sftp_upload_dir(sftp, local_path, remote_path)
        else:
            print(f"    --> Mengirim file: {item}")
            sftp.put(local_path, remote_path)

def main():
    print("=================================================================")
    print("   QoS CAKE Adaptive - DEPLOYMENT UTILITY (PC to STB)           ")
    print("=================================================================")
    print(f"Target STB       : {STB_IP}")
    print(f"User             : {STB_USER}")
    print(f"Folder Lokal     : {BASE_DIR}")
    print("=================================================================\n")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("[*] Menghubungkan ke STB via SSH...")
    try:
        client.connect(STB_IP, username=STB_USER, password=STB_PASS, timeout=10)
        print("[+] Berhasil terhubung!")
    except Exception as e:
        print(f"[-] Gagal terhubung ke STB: {e}")
        sys.exit(1)

    print("[*] Memulai transfer file proyek ke STB...")
    sftp = client.open_sftp()
    
    remote_dest_dir = f"/home/{STB_USER}/qos-cake-adaptive"
    
    try:
        sftp_upload_dir(sftp, BASE_DIR, remote_dest_dir)
        print("[+] Semua file proyek berhasil dikirim ke STB!")
    except Exception as e:
        print(f"[-] Terjadi kesalahan saat pengiriman file: {e}")
        sftp.close()
        client.close()
        sys.exit(1)

    sftp.close()
    client.close()

    print("\n=================================================================")
    print("   PENGIRIMAN FILE SELESAI!")
    print("=================================================================")
    print("Sekarang silakan masuk ke STB Anda (SSH atau Terminal) dan jalankan:")
    print("  1. Masuk ke folder proyek:")
    print(f"     cd ~/qos-cake-adaptive")
    print("  2. Jalankan instalasi lokal sebagai root:")
    print("     sudo python3 install.py")
    print("=================================================================\n")

if __name__ == "__main__":
    main()
