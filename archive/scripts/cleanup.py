#!/usr/bin/env python3
"""
QoS CAKE Adaptive Cleanup Script
Script ini dijalankan di STB untuk membersihkan qdisc, menonaktifkan systemd service, 
serta menghapus namespace simulasi jika ada, untuk merestorasi STB ke keadaan semula.
"""

import os
import sys
import subprocess
import time

def is_root():
    return os.geteuid() == 0

def run_cmd(cmd):
    print(f"Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if res.stdout:
                print(res.stdout.strip())
        else:
            if res.stderr:
                print(f"Error: {res.stderr.strip()}")
        return res.returncode == 0
    except Exception as e:
        print(f"Exception executing command: {e}")
        return False

def main():
    if not is_root():
        print("Error: Script ini harus dijalankan sebagai ROOT (sudo)!")
        sys.exit(1)

    print("\n=======================================================")
    print("MEMBERSIHKAN KONFIGURASI QOS CAKE ADAPTIVE & SIMULASI")
    print("=======================================================\n")

    # 1. Stop dan disable service systemd
    print("[1] Menghentikan & menonaktifkan systemd service...")
    run_cmd(["systemctl", "stop", "cake-adaptive", "web-monitor"])
    run_cmd(["systemctl", "disable", "cake-adaptive", "web-monitor"])
    run_cmd(["systemctl", "daemon-reload"])

    # 2. Hapus rules qdisc di interface default
    print("\n[2] Menghapus konfigurasi qdisc di interface...")
    interfaces = ["eth0", "wlan0", "veth_rtr_lan", "veth_rtr_wan", "lo"]
    for iface in interfaces:
        if os.path.exists(f"/sys/class/net/{iface}"):
            run_cmd(["tc", "qdisc", "del", "dev", iface, "root"])
            run_cmd(["/usr/local/sbin/tc", "qdisc", "del", "dev", iface, "root"])

    # 3. Hapus topologi namespace jika ada
    print("\n[3] Menghapus topologi namespace simulasi (jika ada)...")
    # Kill iperf3 yang mungkin berjalan di namespace
    run_cmd(["ip", "netns", "exec", "ns_isp", "killall", "-9", "iperf3"])
    run_cmd(["ip", "netns", "exec", "ns_client", "killall", "-9", "iperf3"])
    run_cmd(["killall", "-9", "iperf3"])
    
    # Hapus namespaces
    run_cmd(["ip", "netns", "delete", "ns_client"])
    run_cmd(["ip", "netns", "delete", "ns_isp"])
    
    # Hapus links veth
    run_cmd(["ip", "link", "delete", "veth_rtr_lan"])
    run_cmd(["ip", "link", "delete", "veth_rtr_wan"])

    # 4. Hapus file konfigurasi
    print("\n[4] Menghapus file konfigurasi...")
    config_file = "/etc/cake_adaptive.conf"
    if os.path.exists(config_file):
        try:
            os.remove(config_file)
            print(f"Dihapus: {config_file}")
        except Exception as e:
            print(f"Gagal menghapus {config_file}: {e}")

    print("\n=======================================================")
    print("Pembersihan selesai! STB kembali ke keadaan default.")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
