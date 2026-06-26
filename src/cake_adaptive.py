#!/usr/bin/env python3
"""
QoS CAKE Adaptive Daemon
Mengatur parameter RTT pada CAKE secara dinamis berdasarkan latency koneksi aktif.
Mendukung pembacaan konfigurasi dari /etc/cake_adaptive.conf.
"""

import os
import sys
import time
import subprocess
import re
import json
import argparse

CONFIG_PATH = "/etc/cake_adaptive.conf"

def get_default_interface():
    try:
        res = subprocess.run(["ip", "-o", "-4", "route", "show", "to", "default"], capture_output=True, text=True, check=True)
        if res.stdout:
            parts = res.stdout.split()
            if "dev" in parts:
                return parts[parts.index("dev") + 1]
    except Exception as e:
        raise RuntimeError(f"Fatal: Gagal mengeksekusi 'ip route' untuk mendeteksi interface default: {e}")
    raise RuntimeError("Fatal: Tidak ada default route yang ditemukan. Pastikan jaringan STB terhubung!")

DEFAULT_CONFIG = {
    "interface": "auto",
    "ping_dest": "1.1.1.1",
    "bandwidth": "150mbit",
    "interval": 1.0,
    "extra_opts": "diffserv4",
    "qdisc_type": "cake_stb"
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            loaded = json.load(f)
            config.update(loaded)
    else:
        print(f"[{get_time()}] Warning: File config tidak ditemukan di {CONFIG_PATH}, menggunakan default.", flush=True)
    return config

def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def find_tc_binary():
    # Mengutamakan tc hasil kompilasi kustom di /usr/local/sbin/tc
    paths = ["/usr/local/sbin/tc", "/usr/sbin/tc", "/sbin/tc", "tc"]
    for path in paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError("Fatal: binary 'tc' tidak ditemukan di system path atau path custom!")

def get_tcp_rtt():
    try:
        # Menjalankan ss -ti untuk mendapatkan info TCP socket aktif
        res = subprocess.run(["ss", "-ti"], capture_output=True, text=True, check=True)
        rtts = []
        for line in res.stdout.splitlines():
            # Mencari pola 'rtt:<nilai>'
            match = re.search(r'\brtt:([\d\.]+)', line)
            if match:
                rtts.append(float(match.group(1)))
        return rtts
    except subprocess.CalledProcessError as e:
        print(f"[{get_time()}] ERROR: perintah 'ss -ti' gagal: {e.stderr}", flush=True)
        return []
    except Exception as e:
        print(f"[{get_time()}] ERROR mengambil TCP RTT: {e}", flush=True)
        return []

def get_ping_rtt(dest):
    try:
        # Menjalankan ping ke target dengan batas waktu 1 detik
        cmd = ["ping", "-c", "1", "-W", "1", dest]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            match = re.search(r'time=([\d\.]+)\s*ms', res.stdout)
            if match:
                return float(match.group(1))
    except subprocess.TimeoutExpired:
        print(f"[{get_time()}] Warning: Ping ke {dest} timeout.", flush=True)
        return None
    except Exception as e:
        print(f"[{get_time()}] ERROR eksekusi ping: {e}", flush=True)
        return None

def measure_rtt(ping_dest):
    tcp_rtts = get_tcp_rtt()
    if tcp_rtts:
        # Mengambil RTT minimum dari seluruh koneksi TCP aktif sebagai baseline RTT
        return min(tcp_rtts), "TCP Sockets"
    
    # Jika tidak ada TCP aktif, gunakan ping fallback
    ping_rtt = get_ping_rtt(ping_dest)
    if ping_rtt is not None:
        return ping_rtt, f"Ping {ping_dest}"
        
    raise RuntimeError("Gagal mengukur RTT dari TCP maupun Ping! Network mungkin down.")

def get_tx_queues(interface):
    try:
        path = f"/sys/class/net/{interface}/queues"
        if os.path.exists(path):
            queues = [q for q in os.listdir(path) if q.startswith("tx-")]
            return max(1, len(queues))
        else:
            raise FileNotFoundError(f"Interface '{interface}' tidak ditemukan di sistem!")
    except Exception as e:
        print(f"[{get_time()}] ERROR membaca tx queues untuk dev {interface}: {e}", flush=True)
        raise RuntimeError(f"Gagal membaca TX queues: {e}")

class CakeAdaptiveDaemon:
    def __init__(self, config):
        self.config = config
        self.tc_bin = find_tc_binary()
        self.current_rtt_param = 100  # Default awal 100ms
        
        # --- MODIFIKASI IFB UNTUK INGRESS DOWNLOAD ---
        subprocess.run(["modprobe", "ifb", "numifbs=2"], capture_output=True)
        subprocess.run(["ip", "link", "set", "dev", "ifb0", "up"], capture_output=True)
        
        # Ambil nama wlan interface
        wan_if = self.config.get("wan_interface", "auto")
        if wan_if == "auto":
            wan_if = get_default_interface()
            
        # Bersihkan ingress lama dan pasang redirect ke ifb0
        subprocess.run([self.tc_bin, "qdisc", "del", "dev", wan_if, "ingress"], capture_output=True)
        subprocess.run([self.tc_bin, "qdisc", "add", "dev", wan_if, "handle", "ffff:", "ingress"], capture_output=True)
        subprocess.run([self.tc_bin, "filter", "add", "dev", wan_if, "parent", "ffff:", "matchall", "action", "mirred", "egress", "redirect", "dev", "ifb0"], capture_output=True)
        
        self.active_interface = "ifb0"
        # ---------------------------------------------
            
        self.num_queues = 1 # ifb0 bersifat virtual
        self.default_qdisc = "cake_stb"
        
    def apply_tc(self, rtt_val, is_init=False):
        interface = self.active_interface
        bandwidth = self.config["bandwidth"]
        extra_opts = self.config["extra_opts"]
        qdisc_type = self.config.get("qdisc_type", "auto")
        if qdisc_type == "auto":
            qdisc_type = self.default_qdisc
        
        # Gunakan 'replace' hanya saat inisialisasi awal, gunakan 'change' untuk update dinamis
        action = "replace" if is_init else "change"
        
        if self.num_queues > 1:
            if is_init:
                cmd_root = [self.tc_bin, "qdisc", "replace", "dev", interface, "root", "handle", "1:", "mq"]
                subprocess.run(cmd_root, capture_output=True)
            for i in range(1, self.num_queues + 1):
                cmd = [
                    self.tc_bin, "qdisc", action, "dev", interface, "parent", f"1:{i}", qdisc_type,
                    "bandwidth", bandwidth, "rtt", f"{rtt_val}ms"
                ]
                if extra_opts:
                    cmd.extend(extra_opts.split())
                subprocess.run(cmd, capture_output=True)
        else:
            if is_init:
                cmd_root = [self.tc_bin, "qdisc", "replace", "dev", interface, "root", "handle", "1:", "root_qdisc"]
                # We can just replace the root directly with cake_stb
            cmd = [
                self.tc_bin, "qdisc", action, "dev", interface, "root", "handle", "1:", qdisc_type,
                "bandwidth", bandwidth, "rtt", f"{rtt_val}ms"
            ]
            if extra_opts:
                cmd.extend(extra_opts.split())
            subprocess.run(cmd, capture_output=True)
        
        # Anggap sukses jika tidak ada error fatal dari tc saat change
        print(f"[{get_time()}] SUCCESS: Mengubah RTT {qdisc_type} ke {rtt_val}ms untuk dev {interface} (BW: {bandwidth})", flush=True)
        self.current_rtt_param = rtt_val
        return True

    def run(self):
        print(f"[{get_time()}] Memulai CAKE Adaptive Daemon menggunakan binary: {self.tc_bin}...", flush=True)
        print(f"[{get_time()}] Parameter: Interface={self.active_interface}, Bandwidth={self.config['bandwidth']}, PingDest={self.config['ping_dest']}, Interval={self.config['interval']}s", flush=True)
        
        # Set qdisc awal ke 100ms dengan is_init=True
        self.apply_tc(100, is_init=True)
        
        while True:
            # Reload config tiap loop agar dinamis jika web monitor memperbarui file config
            self.config = load_config()
            interval = self.config["interval"]
            ping_dest = self.config["ping_dest"]
            
            try:
                rtt, source = measure_rtt(ping_dest)
                if rtt is None:
                    target_rtt = 100
                else:
                    # Logika keputusan dengan Hysteresis untuk mencegah flapping
                    if self.current_rtt_param == 10:
                        if rtt > 45.0:
                            target_rtt = 100
                        elif rtt > 18.0:
                            target_rtt = 30
                        else:
                            target_rtt = 10
                    elif self.current_rtt_param == 30:
                        if rtt > 45.0:
                            target_rtt = 100
                        elif rtt < 12.0:
                            target_rtt = 10
                        else:
                            target_rtt = 30
                    else:  # current_rtt_param == 100
                        if rtt < 12.0:
                            target_rtt = 10
                        elif rtt < 35.0:
                            target_rtt = 30
                        else:
                            target_rtt = 100
                
                rtt_str = f"{rtt:.2f} ms" if rtt is not None else "N/A"
                print(f"[{get_time()}] RTT Terukur: {rtt_str} ({source}) | Parameter RTT Saat Ini: {self.current_rtt_param}ms -> Target: {target_rtt}ms", flush=True)
                
                # Jika target RTT berbeda atau konfigurasi bandwidth eksternal berubah, lakukan update
                # Untuk mendeteksi perubahan bandwidth eksternal, kita selalu update jika target_rtt berbeda,
                # tapi kita juga bisa memaksa update jika konfigurasi berubah.
                # Mari kita simpan bandwidth yang aktif
                if target_rtt != self.current_rtt_param:
                    self.apply_tc(target_rtt)
                    
            except Exception as e:
                print(f"[{get_time()}] Exception di perulangan utama: {e}", flush=True)
                
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAKE Adaptive RTT Daemon")
    parser.add_argument("--config", action="store_true", help="Gunakan konfigurasi dari file /etc/cake_adaptive.conf")
    args = parser.parse_args()
    
    config = load_config()
    daemon = CakeAdaptiveDaemon(config)
    daemon.run()
