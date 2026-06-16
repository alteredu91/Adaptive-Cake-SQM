#!/usr/bin/env python3
"""
QoS CAKE Web Monitor Backend
Flask application running on the STB to monitor active connections, live speed,
and dynamically control bandwidth limits on LAN and WAN.
"""

import os
import sys
import time
import subprocess
import re
import json
from flask import Flask, jsonify, request, render_template

app = Flask(__name__, template_folder="templates")

CONFIG_PATH = "/etc/cake_adaptive.conf"
DEFAULT_CONFIG = {
    "interface": "veth_rtr_lan",
    "ping_dest": "10.0.2.2",
    "bandwidth": "150mbit",
    "interval": 1.0,
    "extra_opts": "diffserv4 sync 500us"
}

# Inisialisasi statistik jaringan global
class NetworkSpeedMonitor:
    def __init__(self):
        self.last_stats = {} # interface -> {rx_bytes, tx_bytes, timestamp}

    def get_rates(self, interfaces):
        now = time.time()
        rates = {}
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
            for line in lines[2:]:
                parts = line.strip().split()
                if not parts:
                    continue
                ifname = parts[0].strip(":")
                if ifname in interfaces:
                    # rx_bytes adalah indeks 1, tx_bytes adalah indeks 9
                    rx_bytes = int(parts[1])
                    tx_bytes = int(parts[9])
                    
                    if ifname in self.last_stats:
                        last = self.last_stats[ifname]
                        dt = now - last["timestamp"]
                        if dt > 0.05: # Minimal selisih 50ms untuk akurasi
                            # Konversi ke Mbps (Megabit per second)
                            rx_rate = (rx_bytes - last["rx_bytes"]) * 8 / dt / 1_000_000
                            tx_rate = (tx_bytes - last["tx_bytes"]) * 8 / dt / 1_000_000
                            rates[ifname] = {
                                "rx_mbps": round(max(0.0, rx_rate), 2),
                                "tx_mbps": round(max(0.0, tx_rate), 2)
                            }
                        else:
                            rates[ifname] = last.get("rates", {"rx_mbps": 0.0, "tx_mbps": 0.0})
                    else:
                        rates[ifname] = {"rx_mbps": 0.0, "tx_mbps": 0.0}
                    
                    self.last_stats[ifname] = {
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "timestamp": now,
                        "rates": rates[ifname]
                    }
        except Exception as e:
            app.logger.error(f"Gagal membaca statistik /proc/net/dev: {e}")
        return rates

monitor = NetworkSpeedMonitor()

def get_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception:
            pass
    return config

def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        app.logger.error(f"Gagal menulis file konfigurasi: {e}")
        return False

def get_wan_interface():
    # Gunakan veth_rtr_wan jika di simulasi
    if os.path.exists("/sys/class/net/veth_rtr_wan"):
        return "veth_rtr_wan"
    # Auto-detect via route default
    try:
        with open("/proc/net/route") as f:
            for line in f:
                fields = line.strip().split()
                if len(fields) >= 2 and fields[1] == '00000000':
                    return fields[0]
    except Exception:
        pass
    return "eth0"

def find_tc_binary():
    paths = ["/usr/local/sbin/tc", "/usr/sbin/tc", "/sbin/tc", "tc"]
    for path in paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return "tc"

def get_daemon_logs():
    try:
        # Mengambil 20 baris log terakhir dari service cake-adaptive
        res = subprocess.run(
            ["journalctl", "-u", "cake-adaptive", "-n", "20", "--no-pager"],
            capture_output=True, text=True
        )
        return res.stdout.strip()
    except Exception as e:
        return f"Gagal mengambil log daemon: {e}"

def is_service_active(service_name):
    try:
        res = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
        return res.stdout.strip() == "active"
    except Exception:
        return False

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    config = get_config()
    lan_if = config["interface"]
    wan_if = get_wan_interface()
    
    # Hitung kecepatan transfer saat ini
    rates = monitor.get_rates([lan_if, wan_if])
    
    # Status services
    daemon_active = is_service_active("cake-adaptive")
    
    # Ambil RTT parameter CAKE saat ini pada LAN
    tc_bin = find_tc_binary()
    current_cake_rtt = "Unknown"
    try:
        res = subprocess.run([tc_bin, "qdisc", "show", "dev", lan_if], capture_output=True, text=True)
        if "cake" in res.stdout:
            # Cari kata 'rtt Xms'
            match = re.search(r'\brtt\s+(\d+ms)', res.stdout)
            if match:
                current_cake_rtt = match.group(1)
    except Exception:
        pass

    # Baca limit upload saat ini pada WAN (jika terpasang cake/htb)
    current_wan_limit = "Uncapped"
    try:
        res = subprocess.run([tc_bin, "qdisc", "show", "dev", wan_if], capture_output=True, text=True)
        if "cake" in res.stdout:
            match = re.search(r'\bbandwidth\s+([\d\w]+)', res.stdout)
            if match:
                current_wan_limit = match.group(1)
    except Exception:
        pass
        
    return jsonify({
        "timestamp": time.time(),
        "interfaces": {
            "lan": {
                "name": lan_if,
                "rx_mbps": rates.get(lan_if, {}).get("rx_mbps", 0.0), # Client Upload ke router
                "tx_mbps": rates.get(lan_if, {}).get("tx_mbps", 0.0), # Client Download dari router
                "cake_rtt": current_cake_rtt
            },
            "wan": {
                "name": wan_if,
                "rx_mbps": rates.get(wan_if, {}).get("rx_mbps", 0.0), # Router Download dari internet
                "tx_mbps": rates.get(wan_if, {}).get("tx_mbps", 0.0), # Router Upload ke internet
                "limit": current_wan_limit
            }
        },
        "config": config,
        "daemon_status": "Running" if daemon_active else "Stopped",
        "logs": get_daemon_logs()
    })

@app.route("/api/connections", methods=["GET"])
def api_connections():
    conns = []
    try:
        # ss -taunp menampilkan semua koneksi TCP & UDP beserta nama proses (memerlukan root)
        res = subprocess.run(["ss", "-taunp"], capture_output=True, text=True, check=True)
        lines = res.stdout.splitlines()
        
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
                
            netid = parts[0] # tcp/udp
            state = parts[1] # ESTAB, UNCONN, etc.
            local = parts[4]
            peer = parts[5]
            
            def split_addr_port(ap_str):
                if ap_str.startswith("["):
                    c_idx = ap_str.find("]")
                    if c_idx != -1:
                        return ap_str[1:c_idx], ap_str[c_idx+2:]
                if ":" in ap_str:
                    r_idx = ap_str.rfind(":")
                    return ap_str[:r_idx], ap_str[r_idx+1:]
                return ap_str, "-"

            local_ip, local_port = split_addr_port(local)
            peer_ip, peer_port = split_addr_port(peer)
            
            process = "-"
            if len(parts) >= 7:
                proc_str = " ".join(parts[6:])
                match = re.search(r'"([^"]+)"', proc_str)
                if match:
                    process = match.group(1)
            
            # Skip loopback localhost untuk visualisasi bersih
            if peer_ip in ["127.0.0.1", "::1", "*"] or peer_ip.startswith("127."):
                continue
                
            conns.append({
                "proto": netid.upper(),
                "state": state,
                "local": f"{local_ip}:{local_port}",
                "peer": f"{peer_ip}:{peer_port}",
                "process": process
            })
    except Exception as e:
        app.logger.error(f"Gagal mengambil koneksi: {e}")
        
    return jsonify(conns)

@app.route("/api/limit", methods=["POST"])
def api_limit():
    """
    Endpoint untuk menerapkan batas bandwidth simulasi ISP.
    Menerima JSON: { "download": "50mbit", "upload": "10mbit" }
    Atau "download": "disable" untuk mematikan limit.
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Body kosong"}), 400
        
    download = data.get("download", "disable").lower()
    upload = data.get("upload", "disable").lower()
    
    config = get_config()
    lan_if = config["interface"]
    wan_if = get_wan_interface()
    tc_bin = find_tc_binary()
    
    try:
        if download == "disable" or download == "uncapped":
            # Matikan pembatasan: set LAN bandwidth ke 150mbit (kecepatan sumber asli)
            config["bandwidth"] = "150mbit"
            save_config(config)
            
            # Restart daemon QoS agar memuat ulang bandwidth baru di LAN
            subprocess.run(["systemctl", "restart", "cake-adaptive"], check=True)
            
            # Hapus pembatasan pada WAN
            subprocess.run([tc_bin, "qdisc", "del", "dev", wan_if, "root"], capture_output=True)
            
            return jsonify({"status": "success", "message": "Limiter dinonaktifkan (Kecepatan penuh 150 Mbps)"})
        else:
            # Terapkan pembatasan download di LAN dengan mengubah parameter daemon
            config["bandwidth"] = download
            save_config(config)
            subprocess.run(["systemctl", "restart", "cake-adaptive"], check=True)
            
            # Terapkan pembatasan upload di WAN menggunakan CAKE
            subprocess.run([tc_bin, "qdisc", "del", "dev", wan_if, "root"], capture_output=True)
            
            if upload != "disable":
                # Tambahkan CAKE qdisc di WAN untuk membatasi upload
                res = subprocess.run([
                    tc_bin, "qdisc", "add", "dev", wan_if, "root", "cake",
                    "bandwidth", upload, "diffserv4", "sync"
                ], capture_output=True, text=True)
                if res.returncode != 0:
                    return jsonify({"status": "error", "message": f"Gagal limit WAN upload: {res.stderr.strip()}"}), 500
                    
            return jsonify({"status": "success", "message": f"Limiter diaktifkan. Download: {download}, Upload: {upload}"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/daemon", methods=["POST"])
def api_daemon():
    data = request.json
    action = data.get("action", "").lower()
    if action not in ["start", "stop", "restart"]:
        return jsonify({"status": "error", "message": "Aksi tidak dikenal"}), 400
        
    try:
        subprocess.run(["systemctl", action, "cake-adaptive"], check=True)
        return jsonify({"status": "success", "message": f"Daemon cake-adaptive berhasil di-{action}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Flask berjalan pada port 5000 dan mendengarkan di semua interface
    app.run(host="0.0.0.0", port=5000, debug=False)
