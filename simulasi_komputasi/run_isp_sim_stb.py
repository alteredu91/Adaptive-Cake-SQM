#!/usr/bin/env python3
"""
QoS CAKE Adaptive - Local ISP Simulation Topology Setup
Skrip ini dijalankan langsung di dalam STB sebagai root.
Fungsi: membuat topologi network namespace virtual (ns_client, ns_isp, router)
dan merutekan lalu lintas untuk simulasi uji komputasi.
"""

import os
import sys
import subprocess
import time

def is_root():
    return os.geteuid() == 0

def run_cmd(cmd):
    print(f"--> Menjalankan: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        if res.stderr:
            print(f"    [!] Error/Peringatan: {res.stderr.strip()}")
        return False
    return True

def main():
    if not is_root():
        print("[-] Error: Skrip ini harus dijalankan sebagai ROOT (sudo python3 run_isp_sim_stb.py)!")
        sys.exit(1)

    print("=================================================================")
    print("   MEMBUAT TOPOLOGI SIMULASI ISP SECARA LOKAL DI STB             ")
    print("=================================================================")

    # 1. Bersihkan namespace lama jika ada
    print("\n[*] Langkah 1: Membersihkan konfigurasi lama...")
    run_cmd(["ip", "netns", "delete", "ns_client"])
    run_cmd(["ip", "netns", "delete", "ns_isp"])
    run_cmd(["ip", "link", "delete", "veth_rtr_lan"])
    run_cmd(["ip", "link", "delete", "veth_rtr_wan"])
    time.sleep(1)

    # 2. Buat namespace baru
    print("\n[*] Langkah 2: Membuat network namespace ns_client dan ns_isp...")
    run_cmd(["ip", "netns", "add", "ns_client"])
    run_cmd(["ip", "netns", "add", "ns_isp"])

    # 3. Buat veth pair
    print("\n[*] Langkah 3: Membuat veth pair (kabel virtual)...")
    run_cmd(["ip", "link", "add", "veth_rtr_lan", "type", "veth", "peer", "name", "veth_cli"])
    run_cmd(["ip", "link", "add", "veth_rtr_wan", "type", "veth", "peer", "name", "veth_isp"])

    # 4. Pindahkan ujung veth ke dalam namespace
    print("\n[*] Langkah 4: Memindahkan interface ke namespace masing-masing...")
    run_cmd(["ip", "link", "set", "veth_cli", "netns", "ns_client"])
    run_cmd(["ip", "link", "set", "veth_isp", "netns", "ns_isp"])

    # 5. Konfigurasi interface STB Router (main namespace)
    print("\n[*] Langkah 5: Mengonfigurasi IP router pada STB...")
    run_cmd(["ip", "addr", "add", "10.0.1.1/24", "dev", "veth_rtr_lan"])
    run_cmd(["ip", "link", "set", "veth_rtr_lan", "up"])
    run_cmd(["ip", "addr", "add", "10.0.2.1/24", "dev", "veth_rtr_wan"])
    run_cmd(["ip", "link", "set", "veth_rtr_wan", "up"])

    # 6. Konfigurasi Namespace Klien (ns_client)
    print("\n[*] Langkah 6: Mengonfigurasi network di ns_client...")
    run_cmd(["ip", "netns", "exec", "ns_client", "ip", "addr", "add", "10.0.1.2/24", "dev", "veth_cli"])
    run_cmd(["ip", "netns", "exec", "ns_client", "ip", "link", "set", "veth_cli", "up"])
    run_cmd(["ip", "netns", "exec", "ns_client", "ip", "link", "set", "lo", "up"])
    run_cmd(["ip", "netns", "exec", "ns_client", "ip", "route", "add", "default", "via", "10.0.1.1"])

    # 7. Konfigurasi Namespace ISP (ns_isp)
    print("\n[*] Langkah 7: Mengonfigurasi network di ns_isp...")
    run_cmd(["ip", "netns", "exec", "ns_isp", "ip", "addr", "add", "10.0.2.2/24", "dev", "veth_isp"])
    run_cmd(["ip", "netns", "exec", "ns_isp", "ip", "link", "set", "veth_isp", "up"])
    run_cmd(["ip", "netns", "exec", "ns_isp", "ip", "link", "set", "lo", "up"])
    run_cmd(["ip", "netns", "exec", "ns_isp", "ip", "route", "add", "default", "via", "10.0.2.1"])

    # 8. Aktifkan IP Forwarding & Routing
    print("\n[*] Langkah 8: Mengaktifkan IP forwarding dan iptables...")
    run_cmd(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    run_cmd(["iptables", "-t", "filter", "-F", "FORWARD"])
    run_cmd(["iptables", "-t", "filter", "-A", "FORWARD", "-j", "ACCEPT"])

    # 9. Atur Bottleneck ISP pada veth_isp (Simulasi Kecepatan Sumber Internet 100 Mbps)
    print("\n[*] Langkah 9: Memasang bottleneck ISP 100 Mbps pada veth_isp...")
    run_cmd(["ip", "netns", "exec", "ns_isp", "tc", "qdisc", "replace", "dev", "veth_isp", "root", "handle", "1:", "htb", "default", "11"])
    run_cmd(["ip", "netns", "exec", "ns_isp", "tc", "class", "add", "dev", "veth_isp", "parent", "1:", "classid", "1:11", "htb", "rate", "100mbit"])
    run_cmd(["ip", "netns", "exec", "ns_isp", "tc", "qdisc", "add", "dev", "veth_isp", "parent", "1:11", "handle", "11:", "pfifo", "limit", "1000"])

    print("\n=================================================================")
    print("   TOPOLOGI SIMULASI BERHASIL AKTIF LOKAL DI STB!")
    print("   Client IP : 10.0.1.2  |  Router LAN IP : 10.0.1.1")
    print("   ISP IP    : 10.0.2.2  |  Router WAN IP : 10.0.2.1")
    print("=================================================================\n")

if __name__ == "__main__":
    main()
