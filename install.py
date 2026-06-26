import os
import sys
import subprocess
import shutil

def run_cmd(cmd, cwd=None):
    print(f"--> Menjalankan: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True, result.stdout, result.stderr
        else:
            print(f"[-] Gagal: {result.stderr.strip()}")
            return False, result.stdout, result.stderr
    except Exception as e:
        print(f"[-] Error: {e}")
        return False, "", str(e)

def get_default_network_info():
    iface = "auto"
    ip = "192.168.1.1"
    try:
        res = subprocess.run(["ip", "-o", "-4", "route", "show", "to", "default"], capture_output=True, text=True)
        if res.stdout:
            parts = res.stdout.split()
            if "dev" in parts:
                iface = parts[parts.index("dev") + 1]
        
        if iface != "auto":
            res_ip = subprocess.run(["ip", "-o", "-4", "addr", "show", "dev", iface], capture_output=True, text=True)
            if res_ip.stdout:
                parts = res_ip.stdout.split()
                if "inet" in parts:
                    ip = parts[parts.index("inet") + 1].split("/")[0]
    except Exception:
        pass
    return iface, ip

def main():
    if os.geteuid() != 0:
        print("[-] Skrip ini harus dijalankan dengan hak akses root (sudo).")
        sys.exit(1)

    script_path = os.path.realpath(__file__)
    src_dir = os.path.dirname(script_path)
    web_dir = os.path.join(src_dir, "web_monitor")
    
    print("\n=================================================================")
    print("   QoS CAKE Adaptive - LOCAL INSTALLER SCRIPT FOR STB ROUTER    ")
    print("=================================================================")
    
    print("\n=== LANGKAH 1: Menginstal Dependensi Sistem ===")
    run_cmd(["apt-get", "update"])
    run_cmd(["apt-get", "install", "-y", "python3", "python3-pip", "python3-flask", "iproute2", "dnsmasq", "iptables"])
    
    print("\n=== LANGKAH 2: Menggunakan Modul QoS CAKE ===")
    
    custom_c = os.path.join(src_dir, "src", "sch_cake_stb_mq.c")
    custom_module = os.path.join(src_dir, "src", "sch_cake_stb_mq.ko")
    
    # Kompilasi otomatis jika file .c ada tapi file .ko belum ada
    if os.path.exists(custom_c) and not os.path.exists(custom_module):
        print("[*] Mengompilasi modul kustom sch_cake_stb_mq.c menjadi .ko...")
        run_cmd(["apt-get", "install", "-y", "build-essential", "bc", "bison", "flex", "libssl-dev"])
        # Coba install linux-headers dan kbuild untuk kernel yang sedang berjalan
        kbuild_pkg = f"linux-kbuild-{os.uname().release.split('-')[0][:3]}"
        run_cmd(["apt-get", "install", "-y", f"linux-headers-{os.uname().release}", kbuild_pkg])
        
        makefile_path = os.path.join(src_dir, "src", "Makefile")
        with open(makefile_path, "w") as f:
            f.write("obj-m += sch_cake_stb_mq.o\n")
            f.write("all:\n")
            f.write("\tmake -C /lib/modules/$(shell uname -r)/build M=$(CURDIR) modules\n")
            f.write("clean:\n")
            f.write("\tmake -C /lib/modules/$(shell uname -r)/build M=$(CURDIR) clean\n")
        
        ok, stdout, stderr = run_cmd(["make", "clean"], cwd=os.path.join(src_dir, "src"))
        ok, stdout, stderr = run_cmd(["make"], cwd=os.path.join(src_dir, "src"))
        
        if not ok:
            print(f"[-] Gagal mengompilasi modul custom: {stderr.strip()}")
            print("[-] Pastikan linux-headers terinstal dengan benar di STB Anda!")
            sys.exit(1)
        print("[+] Kompilasi berhasil! File .ko terbentuk.")

    # Periksa apakah modul kustom tersedia setelah dicompile
    if os.path.exists(custom_module):
        print("[*] Mendaftarkan modul sch_cake_stb_mq ke /lib/modules secara permanen...")
        kernel_ver = subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip()
        mod_dir = f"/lib/modules/{kernel_ver}/kernel/net/sched"
        os.makedirs(mod_dir, exist_ok=True)
        shutil.copy(custom_module, mod_dir)
        run_cmd(["depmod", "-a"])
        
        # Tambahkan ke /etc/modules agar dimuat saat boot
        with open("/etc/modules", "r") as f:
            modules_content = f.read()
        if "sch_cake_stb_mq" not in modules_content:
            with open("/etc/modules", "a") as f:
                f.write("\nsch_cake_stb_mq\n")
        
        print("[*] Ditemukan modul kernel kustom sch_cake_stb_mq.ko, sedang memuat...")
        run_cmd(["rmmod", "sch_cake_stb_mq"])
        run_cmd(["modprobe", "sch_cake_stb_mq"])
        print("[+] Modul custom sch_cake_stb_mq berhasil dimuat secara permanen!")
    else:
        # Pastikan modul native dimuat (fallback statis jika .c memang tidak disediakan)
        run_cmd(["modprobe", "sch_cake"])
        print("[+] Modul sch_cake native berhasil dipastikan aktif!")

    print("\n=== LANGKAH 3: Menyalin Core Daemon & Web Monitor ke Sistem ===")
    
    # 1. Salin script daemon ke /usr/local/bin
    print("[*] Memasang cake_adaptive.py ke /usr/local/bin...")
    shutil.copy(os.path.join(src_dir, "src", "cake_adaptive.py"), "/usr/local/bin/cake_adaptive.py")
    os.chmod("/usr/local/bin/cake_adaptive.py", 0o755)

    # 2. Salin file service systemd
    print("[*] Memasang service unit ke /etc/systemd/system...")
    shutil.copy(os.path.join(src_dir, "src", "cake-adaptive.service"), "/etc/systemd/system/cake-adaptive.service")
    shutil.copy(os.path.join(src_dir, "src", "web-monitor.service"), "/etc/systemd/system/web-monitor.service")

    # 3. Salin source code Web Monitor Flask
    flask_dest = "/usr/local/share/qos-cake-monitor"
    if os.path.exists(flask_dest):
        shutil.rmtree(flask_dest)
    
    os.makedirs(os.path.join(flask_dest, "templates"), exist_ok=True)
    shutil.copy(os.path.join(web_dir, "app.py"), os.path.join(flask_dest, "app.py"))
    os.chmod(os.path.join(flask_dest, "app.py"), 0o755)
    
    shutil.copy(os.path.join(web_dir, "templates/index.html"), os.path.join(flask_dest, "templates/index.html"))
    print("[+] File Web Monitor Flask berhasil disalin!")

    # 4. Tulis file konfigurasi default /etc/cake_adaptive.conf jika belum ada
    config_file = "/etc/cake_adaptive.conf"
    if not os.path.exists(config_file):
        auto_iface, auto_ip = get_default_network_info()
        default_conf_str = f'''{{
    "interface": "{auto_iface}",
    "ping_dest": "1.1.1.1",
    "bandwidth": "150mbit",
    "interval": 1.0,
    "extra_opts": "diffserv4",
    "qdisc_type": "cake_stb",
    "wan_interface": "auto",
    "lan_ip": "{auto_ip}",
    "lan_netmask": "255.255.255.0",
    "dhcp_enabled": false,
    "dhcp_start": "192.168.10.10",
    "dhcp_end": "192.168.10.100"
}}'''
        with open(config_file, "w") as f:
            f.write(default_conf_str)
        print("[+] Konfigurasi default dibuat di /etc/cake_adaptive.conf")

    print("\n=== LANGKAH 4: Konfigurasi Jaringan (Router) ===")
    sysctl_file = "/etc/sysctl.conf"
    with open(sysctl_file, "r") as f:
        sysctl_content = f.read()
    if "net.ipv4.ip_forward=1" not in sysctl_content.replace(" ", ""):
        with open(sysctl_file, "a") as f:
            f.write("\nnet.ipv4.ip_forward=1\n")
        print("[+] IP Forwarding diaktifkan permanen di /etc/sysctl.conf")
    run_cmd(["sysctl", "-p"])

    print("\n=== LANGKAH 5: Mendaftarkan & Menjalankan Service Systemd ===")
    run_cmd(["systemctl", "daemon-reload"])
    
    print("[*] Mengaktifkan & menjalankan service cake-adaptive...")
    run_cmd(["systemctl", "enable", "cake-adaptive"])
    run_cmd(["systemctl", "restart", "cake-adaptive"])

    print("[*] Mengaktifkan & menjalankan service web-monitor...")
    run_cmd(["systemctl", "enable", "web-monitor"])
    run_cmd(["systemctl", "restart", "web-monitor"])

    print("\n=================================================================")
    print("   PROSES INSTALASI DAN ATURAN QOS CAKE ADAPTIVE SELESAI!")
    print("=================================================================")
    print("Dashboard Web Monitor sekarang berjalan langsung di STB.")
    print("Dapat diakses melalui browser Anda di:")
    print("  --> http://localhost:5000  (atau melalui IP STB Anda di port 5000)")
    print("\nLayanan background aktif:")
    print("  1. cake-adaptive  : Daemon auto-RTT (latency controller)")
    print("  2. web-monitor    : Monitoring Dashboard & Bandwidth Limiter")
    print("=================================================================\n")

if __name__ == "__main__":
    main()
