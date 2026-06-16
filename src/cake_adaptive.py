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

DEFAULT_CONFIG = {
    "interface": "veth_rtr_lan",
    "ping_dest": "10.0.2.2",
    "bandwidth": "90mbit",
    "interval": 1.0,
    "extra_opts": "diffserv4 sync 500us"
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print(f"[{get_time()}] Warning: Gagal membaca file config, menggunakan default. Error: {e}", flush=True)
    return config

def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def find_tc_binary():
    # Mengutamakan tc hasil kompilasi kustom di /usr/local/sbin/tc
    paths = ["/usr/local/sbin/tc", "/usr/sbin/tc", "/sbin/tc", "tc"]
    for path in paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return "tc"

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
    except Exception as e:
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
    except Exception:
        pass
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
        
    return None, "None"

class CakeAdaptiveDaemon:
    def __init__(self, config):
        self.config = config
        self.tc_bin = find_tc_binary()
        self.current_rtt_param = 100  # Default awal 100ms
        
    def apply_tc(self, rtt_val):
        interface = self.config["interface"]
        bandwidth = self.config["bandwidth"]
        extra_opts = self.config["extra_opts"]
        
        # Mengubah parameter rtt pada CAKE secara dinamis tanpa mereset qdisc
        cmd = [
            self.tc_bin, "qdisc", "change", "dev", interface, "root", "cake",
            "bandwidth", bandwidth, "rtt", f"{rtt_val}ms"
        ]
        if extra_opts:
            cmd.extend(extra_opts.split())
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[{get_time()}] SUCCESS: Mengubah RTT CAKE ke {rtt_val}ms untuk dev {interface} (BW: {bandwidth})", flush=True)
            self.current_rtt_param = rtt_val
            return True
        except subprocess.CalledProcessError as e:
            print(f"[{get_time()}] ERROR mengubah tc: {e.stderr.strip()}", flush=True)
            return False

    def run(self):
        print(f"[{get_time()}] Memulai CAKE Adaptive Daemon menggunakan binary: {self.tc_bin}...", flush=True)
        print(f"[{get_time()}] Parameter: Interface={self.config['interface']}, Bandwidth={self.config['bandwidth']}, PingDest={self.config['ping_dest']}, Interval={self.config['interval']}s", flush=True)
        
        # Set qdisc awal ke 100ms
        self.apply_tc(100)
        
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
