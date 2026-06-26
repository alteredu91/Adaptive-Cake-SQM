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
    "interface": "eth0",
    "ping_dest": "10.0.2.2",
    "bandwidth": "150mbit",
    "interval": 1.0,
    "extra_opts": "diffserv4",
    "qdisc_type": "cake_stb",
    "wan_interface": "auto",
    "lan_ip": "192.168.10.1",
    "lan_netmask": "255.255.255.0",
    "dhcp_enabled": False,
    "dhcp_start": "192.168.10.10",
    "dhcp_end": "192.168.10.100"
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

def get_wan_interface(config=None):
    if config is None:
        config = get_config()
    
    wan_if = config.get("wan_interface", "auto")
    if wan_if and wan_if != "auto":
        return wan_if

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
    import os
    for p in ["/usr/local/sbin/tc", "/usr/sbin/tc", "/sbin/tc"]:
        if os.path.exists(p):
            return p
    import shutil
    tc_path = shutil.which("tc")
    return tc_path if tc_path else "tc"

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

def apply_network_settings(config):
    import ipaddress
    lan_if = config.get("interface", "eth0")
    wan_if = get_wan_interface(config)
    lan_ip = config.get("lan_ip", "192.168.10.1")
    lan_mask = config.get("lan_netmask", "255.255.255.0")
    dhcp_enabled = config.get("dhcp_enabled", False)
    dhcp_start = config.get("dhcp_start", "192.168.10.10")
    dhcp_end = config.get("dhcp_end", "192.168.10.100")

    try:
        # Enable IP Forwarding
        subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=False)
        
        # Calculate CIDR
        try:
            net = ipaddress.IPv4Network(f"{lan_ip}/{lan_mask}", strict=False)
            prefix = net.prefixlen
        except:
            prefix = 24
            
        # Configure LAN IP
        subprocess.run(["ip", "addr", "replace", f"{lan_ip}/{prefix}", "dev", lan_if], check=False)
        subprocess.run(["ip", "link", "set", lan_if, "up"], check=False)
        
        # Configure NAT (Masquerade)
        if wan_if and wan_if != "auto":
            subprocess.run(["iptables", "-t", "nat", "-D", "POSTROUTING", "-o", wan_if, "-j", "MASQUERADE"], check=False)
            subprocess.run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", wan_if, "-j", "MASQUERADE"], check=False)
        
        # Configure DHCP
        if dhcp_enabled:
            dnsmasq_conf = f"""
# Auto-generated by QoS CAKE Adaptive
interface={lan_if}
dhcp-range={dhcp_start},{dhcp_end},{lan_mask},12h
dhcp-option=3,{lan_ip}
dhcp-option=6,8.8.8.8,1.1.1.1
            """
            os.makedirs("/etc/dnsmasq.d", exist_ok=True)
            with open("/etc/dnsmasq.d/qos_cake_dhcp.conf", "w") as f:
                f.write(dnsmasq_conf)
            subprocess.run(["systemctl", "restart", "dnsmasq"], check=False)
        else:
            if os.path.exists("/etc/dnsmasq.d/qos_cake_dhcp.conf"):
                os.remove("/etc/dnsmasq.d/qos_cake_dhcp.conf")
            subprocess.run(["systemctl", "restart", "dnsmasq"], check=False)
            
        return True
    except Exception as e:
        app.logger.error(f"Error applying network: {e}")
        return False

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    config = get_config()
    lan_if = config.get("interface", "eth0")
    wan_if = get_wan_interface(config)
    
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
        
    def apply_90_percent_rule(val_str):
        if val_str in ["disable", "uncapped"]: return val_str
        num_str = val_str.replace("mbit", "").strip()
        try:
            val_float = float(num_str)
            adjusted_val = val_float * 0.90
            return f"{int(adjusted_val)}mbit" if adjusted_val.is_integer() else f"{adjusted_val:.1f}mbit"
        except ValueError:
            return val_str

    download = apply_90_percent_rule(data.get("download", "disable").lower())
    upload = apply_90_percent_rule(data.get("upload", "disable").lower())
    
    config = get_config()
    lan_if = config.get("interface", "eth0")
    wan_if = get_wan_interface(config)
    tc_bin = find_tc_binary()
    
    try:
        if download == "disable" or download == "uncapped":
            # Matikan pembatasan: set LAN bandwidth ke 150mbit (kecepatan sumber asli)
            config["bandwidth"] = "150mbit"
            save_config(config)
            
            # Restart daemon QoS agar memuat ulang bandwidth baru di LAN
            subprocess.run(["systemctl", "restart", "cake-adaptive"], check=True)
            
            # Hapus pembatasan pada WAN dan IFB lama
            subprocess.run([tc_bin, "qdisc", "del", "dev", wan_if, "root"], capture_output=True)
            subprocess.run([tc_bin, "qdisc", "del", "dev", lan_if, "ingress"], capture_output=True)
            subprocess.run([tc_bin, "qdisc", "del", "dev", "ifb1", "root"], capture_output=True)
            
            return jsonify({"status": "success", "message": "Limiter dinonaktifkan (Kecepatan penuh 150 Mbps)"})
        else:
            # Terapkan pembatasan download di LAN dengan mengubah parameter daemon
            config["bandwidth"] = download
            save_config(config)
            subprocess.run(["systemctl", "restart", "cake-adaptive"], check=True)
            
            # Siapkan IFB1 untuk Upload Ingress dari LAN
            subprocess.run([tc_bin, "qdisc", "del", "dev", wan_if, "root"], capture_output=True)
            subprocess.run([tc_bin, "qdisc", "del", "dev", lan_if, "ingress"], capture_output=True)
            subprocess.run([tc_bin, "qdisc", "del", "dev", "ifb1", "root"], capture_output=True)
            
            if upload != "disable":
                subprocess.run(["ip", "link", "set", "dev", "ifb1", "up"], capture_output=True)
                subprocess.run([tc_bin, "qdisc", "add", "dev", lan_if, "handle", "ffff:", "ingress"], capture_output=True)
                subprocess.run([tc_bin, "filter", "add", "dev", lan_if, "parent", "ffff:", "matchall", "action", "mirred", "egress", "redirect", "dev", "ifb1"], capture_output=True)
                
                # Tambahkan CAKE qdisc di IFB1 untuk membatasi upload klien
                res = subprocess.run([
                    tc_bin, "qdisc", "add", "dev", "ifb1", "root", "cake",
                    "bandwidth", upload, "diffserv4", "nat", "ack-filter"
                ], capture_output=True, text=True)
                if res.returncode != 0:
                    return jsonify({"status": "error", "message": f"Gagal limit WAN upload: {res.stderr.strip()}"}), 500
                    
            return jsonify({"status": "success", "message": f"Limiter diaktifkan (Pengurangan 10% limit). Download: {download}, Upload: {upload}"})
            
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

@app.route("/api/config/interfaces", methods=["POST"])
def api_config_interfaces():
    data = request.json
    lan_if = data.get("lan_interface")
    wan_if = data.get("wan_interface")

    config = get_config()
    if lan_if:
        config["interface"] = lan_if
    if wan_if:
        config["wan_interface"] = wan_if

    if save_config(config):
        # Apply network and restart daemon
        apply_network_settings(config)
        try:
            subprocess.run(["systemctl", "restart", "cake-adaptive"], check=False)
        except:
            pass
        return jsonify({"status": "success", "message": "Interface & Network berhasil diperbarui!"})
    else:
        return jsonify({"status": "error", "message": "Gagal menyimpan konfigurasi"}), 500

@app.route("/api/network", methods=["GET", "POST"])
def api_network():
    if request.method == "GET":
        config = get_config()
        return jsonify({
            "lan_ip": config.get("lan_ip", "192.168.10.1"),
            "lan_netmask": config.get("lan_netmask", "255.255.255.0"),
            "dhcp_enabled": config.get("dhcp_enabled", False),
            "dhcp_start": config.get("dhcp_start", "192.168.10.10"),
            "dhcp_end": config.get("dhcp_end", "192.168.10.100")
        })
    else:
        data = request.json
        config = get_config()
        config["lan_ip"] = data.get("lan_ip", config.get("lan_ip"))
        config["lan_netmask"] = data.get("lan_netmask", config.get("lan_netmask"))
        config["dhcp_enabled"] = data.get("dhcp_enabled", config.get("dhcp_enabled"))
        config["dhcp_start"] = data.get("dhcp_start", config.get("dhcp_start"))
        config["dhcp_end"] = data.get("dhcp_end", config.get("dhcp_end"))
        
        if save_config(config):
            apply_network_settings(config)
            return jsonify({"status": "success", "message": "Pengaturan Jaringan (Router) berhasil diterapkan!"})
        else:
            return jsonify({"status": "error", "message": "Gagal menyimpan pengaturan"}), 500

if __name__ == "__main__":
    # Flask berjalan pada port 5000 dan mendengarkan di semua interface
    app.run(host="0.0.0.0", port=5000, debug=False)
