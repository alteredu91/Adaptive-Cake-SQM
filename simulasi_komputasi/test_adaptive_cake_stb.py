#!/usr/bin/env python3
"""
QoS CAKE Adaptive - Local Benchmark Orchestrator
Skrip ini dijalankan langsung di dalam STB sebagai root.
Fungsi: menjalankan skenario pengujian (Default CAKE vs Tuned CAKE vs Adaptif CAKE),
mengirim traffic iperf3 di dalam namespace virtual, dan mengekspor tabel hasil benchmark.
"""

import os
import sys
import time
import subprocess
import re

def is_root():
    return os.geteuid() == 0

def run_cmd(cmd, shell=False):
    res = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return res.stdout, res.stderr

def run_cmd_bg(cmd, shell=False):
    # Menjalankan proses di background secara lokal
    if shell:
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    if not is_root():
        print("[-] Error: Skrip ini harus dijalankan sebagai ROOT (sudo python3 test_adaptive_cake_stb.py)!")
        sys.exit(1)

    # Pastikan file daemon ada
    daemon_path = "/usr/local/bin/cake_adaptive.py"
    if not os.path.exists(daemon_path):
        print(f"[-] Peringatan: Daemon {daemon_path} tidak ditemukan di sistem.")
        print("Mencoba mencari di ../src/cake_adaptive.py...")
        daemon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/cake_adaptive.py"))
        if not os.path.exists(daemon_path):
            print("[-] Error: File core daemon tidak ditemukan. Pasang terlebih dahulu!")
            sys.exit(1)

    print("=================================================================")
    print("   QoS CAKE Adaptive - LOCAL BENCHMARK & COMPUTATIONAL TESTS     ")
    print("=================================================================")
    print(f"Menggunakan Daemon : {daemon_path}")
    print("=================================================================\n")

    # Pastikan topologi simulasi telah dibuat
    if not os.path.exists("/sys/class/net/veth_rtr_lan"):
        print("[*] Topologi simulasi belum dibuat. Menjalankan skrip topologi...")
        run_cmd(["python3", "run_isp_sim_stb.py"])
        time.sleep(1)

    scenarios = [
        # GRUP A: Low Latency / Metro (0ms delay)
        {
            "group": "Grup A (0ms Delay - Metro/Lokal)",
            "qos_name": "CAKE Default (rtt 100ms)",
            "delay_cmd": "tc qdisc del dev veth_rtr_wan root 2>/dev/null || true",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us",
            "use_daemon": False
        },
        {
            "group": "Grup A (0ms Delay - Metro/Lokal)",
            "qos_name": "CAKE Tuned (rtt 10ms)",
            "delay_cmd": "tc qdisc del dev veth_rtr_wan root 2>/dev/null || true",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us rtt 10ms",
            "use_daemon": False
        },
        {
            "group": "Grup A (0ms Delay - Metro/Lokal)",
            "qos_name": "CAKE Adaptif (Daemon)",
            "delay_cmd": "tc qdisc del dev veth_rtr_wan root 2>/dev/null || true",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us",
            "use_daemon": True
        },
        # GRUP B: High Latency / WAN (80ms delay)
        {
            "group": "Grup B (80ms Delay - WAN/Global)",
            "qos_name": "CAKE Default (rtt 100ms)",
            "delay_cmd": "/usr/local/sbin/tc qdisc replace dev veth_rtr_wan root netem delay 80ms limit 1000",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us",
            "use_daemon": False
        },
        {
            "group": "Grup B (80ms Delay - WAN/Global)",
            "qos_name": "CAKE Tuned (rtt 10ms)",
            "delay_cmd": "/usr/local/sbin/tc qdisc replace dev veth_rtr_wan root netem delay 80ms limit 1000",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us rtt 10ms",
            "use_daemon": False
        },
        {
            "group": "Grup B (80ms Delay - WAN/Global)",
            "qos_name": "CAKE Adaptif (Daemon)",
            "delay_cmd": "/usr/local/sbin/tc qdisc replace dev veth_rtr_wan root netem delay 80ms limit 1000",
            "qos_setup": "/usr/local/sbin/tc qdisc replace dev veth_rtr_lan root cake bandwidth 90mbit diffserv4 sync 500us",
            "use_daemon": True
        }
    ]

    results = []

    print("\n--- Memulai Pengujian QoS CAKE Adaptif ---")

    for s in scenarios:
        print(f"\n==================================================")
        print(f"Menguji: {s['group']} | {s['qos_name']}")
        print(f"==================================================")
        
        # 1. Bersihkan sisa proses iperf & daemon lama
        run_cmd("ip netns exec ns_isp killall -9 iperf3 2>/dev/null", shell=True)
        run_cmd("pkill -f cake_adaptive.py", shell=True)
        run_cmd("rm -f /tmp/cake_adaptive.log", shell=True)
        time.sleep(0.5)
        
        # 2. Jalankan iperf3 server di ISP namespace (background)
        run_cmd_bg(["ip", "netns", "exec", "ns_isp", "iperf3", "-s", "-p", "5201", "-D"])
        run_cmd_bg(["ip", "netns", "exec", "ns_isp", "iperf3", "-s", "-p", "5202", "-D"])
        time.sleep(0.5)
        
        # 3. Terapkan delay WAN
        print(f"Menerapkan WAN Delay: {s['delay_cmd']}")
        run_cmd(s['delay_cmd'], shell=True)
        
        # 4. Terapkan QoS Router
        print(f"Menerapkan QoS Router: {s['qos_setup']}")
        run_cmd(s['qos_setup'], shell=True)
        
        # 5. Jika skenario adaptif, jalankan daemon kustom secara lokal
        daemon_proc = None
        if s['use_daemon']:
            print("Menjalankan CAKE Adaptive Daemon...")
            # Panggil daemon dengan logging ke file log sementara
            daemon_cmd = f"python3 {daemon_path} --interface veth_rtr_lan --ping-dest 10.0.2.2 --bandwidth 90mbit --interval 0.5 > /tmp/cake_adaptive.log 2>&1"
            daemon_proc = run_cmd_bg(daemon_cmd, shell=True)
            time.sleep(1.5) # Beri waktu pembacaan RTT pertama
            
        # 6. Jalankan simulasi traffic
        print("Menjalankan traffic iperf3 (TCP Download + UDP YouTube 40M) dan ping game...")
        run_cmd_bg("ip netns exec ns_client iperf3 -c 10.0.2.2 -p 5201 -t 10 -P 2 -R > /tmp/tcp.out 2>&1", shell=True)
        time.sleep(0.2)
        run_cmd_bg("ip netns exec ns_client iperf3 -c 10.0.2.2 -p 5202 -u -b 40M -t 10 -R > /tmp/udp.out 2>&1", shell=True)
        time.sleep(1.0)
        run_cmd_bg("ip netns exec ns_client ping -c 40 -i 0.2 -Q 184 10.0.2.2 > /tmp/ping.out 2>&1", shell=True)
        
        print("Simulasi berjalan (12 detik)...")
        time.sleep(12.0)
        
        # 7. Hentikan daemon adaptif jika berjalan
        daemon_behavior = "N/A"
        if s['use_daemon']:
            print("Menghentikan Daemon...")
            run_cmd("pkill -f cake_adaptive.py", shell=True)
            if daemon_proc:
                daemon_proc.terminate()
            time.sleep(0.5)
            
            # Analisis log adaptasi daemon
            try:
                with open("/tmp/cake_adaptive.log", "r") as log_f:
                    log_out = log_f.read()
                print("--- LOG DAEMON ADAPTIF ---")
                print(log_out.strip())
                print("--------------------------")
                changes = re.findall(r'Mengubah RTT CAKE ke (\d+)ms', log_out)
                if changes:
                    daemon_behavior = f"Set {changes[-1]}ms"
                else:
                    daemon_behavior = "No change (kept 100ms)"
            except Exception:
                daemon_behavior = "Log error"
                
        # 8. Baca dan parsing hasil output
        try:
            with open("/tmp/tcp.out", "r") as f:
                tcp_txt = f.read()
            with open("/tmp/udp.out", "r") as f:
                udp_txt = f.read()
            with open("/tmp/ping.out", "r") as f:
                ping_txt = f.read()
        except Exception as e:
            print(f"[-] Gagal membaca file log output: {e}")
            continue
        
        # Parsing Latensi Game
        latencies = []
        for line in ping_txt.split('\n'):
            if "time=" in line:
                try:
                    latencies.append(float(line.split("time=")[1].split()[0]))
                except:
                    pass
        avg_lat = sum(latencies)/len(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0
        
        # Parsing Throughput TCP
        tcp_speed = "0.0 Mbps"
        for line in tcp_txt.split('\n'):
            if "receiver" in line or (("sender" in line) and ("receiver" not in tcp_txt)):
                parts = line.split()
                try:
                    idx = parts.index("Mbits/sec")
                    tcp_speed = f"{parts[idx-1]} Mbps"
                except:
                    pass
                    
        # Parsing Throughput UDP
        udp_speed = "0.0 Mbps"
        for line in udp_txt.split('\n'):
            if "receiver" in line or (("sender" in line) and ("receiver" not in udp_txt)):
                parts = line.split()
                try:
                    idx = parts.index("Mbits/sec")
                    udp_speed = f"{parts[idx-1]} Mbps"
                except:
                    pass
                    
        print(f"Hasil -> TCP: {tcp_speed} | UDP: {udp_speed} | Latency Avg/Max: {avg_lat:.2f}/{max_lat:.2f} ms")
        
        results.append({
            "group": s['group'],
            "qos_name": s['qos_name'],
            "tcp_speed": tcp_speed,
            "udp_speed": udp_speed,
            "avg_lat": avg_lat,
            "max_lat": max_lat,
            "daemon_behavior": daemon_behavior
        })
        
        # Hapus file output sementara
        run_cmd("rm -f /tmp/tcp.out /tmp/udp.out /tmp/ping.out /tmp/cake_adaptive.log", shell=True)

    # 9. Bersihkan topologi simulasi
    print("\n--- Membersihkan Topologi Simulasi ISP ---")
    run_cmd("ip netns exec ns_isp killall -9 iperf3 2>/dev/null", shell=True)
    run_cmd("/usr/local/sbin/tc qdisc del dev veth_rtr_lan root 2>/dev/null || true", shell=True)
    run_cmd("/usr/local/sbin/tc qdisc del dev veth_rtr_wan root 2>/dev/null || true", shell=True)
    run_cmd("ip netns delete ns_client 2>/dev/null", shell=True)
    run_cmd("ip netns delete ns_isp 2>/dev/null", shell=True)
    run_cmd("ip link delete veth_rtr_lan 2>/dev/null", shell=True)
    run_cmd("ip link delete veth_rtr_wan 2>/dev/null", shell=True)

    # Cetak tabel hasil pengujian ke console
    print("\n" + "="*95)
    print(f"{'HASIL PENGUJIAN ADAPTIF RTT CAKE SQM PADA STB FISIK':^95}")
    print("="*95)
    print(f"{'Grup Pengujian':<30} | {'Skenario QoS':<24} | {'TCP Speed':<12} | {'UDP Speed':<10} | {'Game Lat Avg/Max':<18} | {'Daemon Res'}")
    print("-"*95)
    for r in results:
        lat_str = f"{r['avg_lat']:.2f}/{r['max_lat']:.2f} ms"
        print(f"{r['group']:<30} | {r['qos_name']:<24} | {r['tcp_speed']:<12} | {r['udp_speed']:<10} | {lat_str:<18} | {r['daemon_behavior']}")
    print("="*95)

    # Tulis hasil ke file teks lokal
    results_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adaptive_bench_results.txt")
    with open(results_file, "w") as f:
        f.write("HASIL PENGUJIAN ADAPTIF RTT CAKE SQM PADA STB FISIK\n")
        f.write("="*95 + "\n")
        f.write(f"{'Grup Pengujian':<30} | {'Skenario QoS':<24} | {'TCP Speed':<12} | {'UDP Speed':<10} | {'Game Lat Avg/Max':<18} | {'Daemon Res'}\n")
        f.write("-"*95 + "\n")
        for r in results:
            lat_str = f"{r['avg_lat']:.2f}/{r['max_lat']:.2f} ms"
            f.write(f"{r['group']:<30} | {r['qos_name']:<24} | {r['tcp_speed']:<12} | {r['udp_speed']:<10} | {lat_str:<18} | {r['daemon_behavior']}\n")
        f.write("="*95 + "\n")

    print(f"\nHasil pengujian berhasil diekspor ke: {results_file}")

if __name__ == "__main__":
    main()
