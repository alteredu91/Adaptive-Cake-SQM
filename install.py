#!/usr/bin/env python3
"""
QoS CAKE Adaptive - Local STB Installer Script
Skrip ini dijalankan langsung di dalam STB (misalnya melalui SSH atau terminal STB).
Harus dijalankan dengan hak akses root (sudo python3 install.py).

Fungsi:
1. Menginstal dependensi build secara lokal.
2. Mengunduh, mempatch, dan mengompilasi modul kernel sch_cake.ko.
3. Mengunduh dan mengompilasi iproute2 tc-mq kustom.
4. Menyalin daemon, service systemd, dan file web monitor ke direktori sistem STB.
5. Mengaktifkan layanan di systemd.
"""

import os
import sys
import shutil
import subprocess
import time

compatibility_header = """
/* Compatibility Header for Kernel 6.x / 6.1 (Armbian) */
#ifndef SKB_DROP_REASON_QDISC_CONGESTED
#define SKB_DROP_REASON_QDISC_CONGESTED SKB_DROP_REASON_QDISC_DROP
#endif

#ifndef SKB_DROP_REASON_CAKE_FLOOD
#define SKB_DROP_REASON_CAKE_FLOOD SKB_DROP_REASON_QDISC_DROP
#endif

#ifndef SKB_DROP_REASON_QDISC_OVERLIMIT
#define SKB_DROP_REASON_QDISC_OVERLIMIT SKB_DROP_REASON_QDISC_DROP
#endif

#ifndef SKB_DROP_REASON_QUEUE_PURGE
#define SKB_DROP_REASON_QUEUE_PURGE SKB_DROP_REASON_QDISC_DROP
#endif

#ifndef qdisc_drop_reason
#define qdisc_drop_reason(skb, sch, to_free, reason) qdisc_drop(skb, sch, to_free)
#endif

#ifndef MODULE_ALIAS_NET_SCH
#define MODULE_ALIAS_NET_SCH(id) MODULE_ALIAS("sch_" id)
#endif

/* Define missing TCA_CAKE enums */
#ifndef TCA_CAKE_FWMARK
#define TCA_CAKE_FWMARK 19
#endif

enum {
    TCA_CAKE_SYNC_TIME = TCA_CAKE_FWMARK + 1,
    TCA_CAKE_ACTIVE_QUEUES,
    TCA_CAKE_MIN_TIMER_SLACK,
    TCA_CAKE_MAX_TIMER_SLACK,
    TCA_CAKE_AVG_TIMER_SLACK,
    __TCA_CAKE_MAX_NEW
};
#undef TCA_CAKE_MAX
#define TCA_CAKE_MAX (__TCA_CAKE_MAX_NEW - 1)
"""

def is_root():
    return os.geteuid() == 0

def run_cmd(cmd, cwd=None, shell=False):
    print(f"--> Menjalankan: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] Gagal: {res.stderr.strip()}")
        return False, res.stdout, res.stderr
    if res.stdout:
        print(res.stdout.strip())
    return True, res.stdout, res.stderr

def main():
    if not is_root():
        print("[-] Error: Skrip instalasi ini harus dijalankan sebagai ROOT (sudo python3 install.py)!")
        sys.exit(1)

    # Dapatkan path asal (current directory repositori)
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(repo_dir, "src")
    web_dir = os.path.join(repo_dir, "web_monitor")

    # Validasi struktur folder lokal repositori
    if not os.path.exists(src_dir) or not os.path.exists(web_dir):
        print(f"[-] Error: Folder 'src' atau 'web_monitor' tidak ditemukan di {repo_dir}!")
        print("Tolong pastikan Anda menjalankan skrip ini dari dalam folder repositori hasil clone.")
        sys.exit(1)

    print("=================================================================")
    print("   QoS CAKE Adaptive - LOCAL INSTALLER SCRIPT FOR STB ROUTER    ")
    print("=================================================================")
    print(f"Direktori Proyek: {repo_dir}")
    print("=================================================================\n")

    # --- LANGKAH 1: Install Dependensi Sistem ---
    print("\n=== LANGKAH 1: Menginstal Dependensi Sistem ===")
    ok, _, _ = run_cmd(["apt-get", "update"])
    if not ok:
        print("[-] Gagal memperbarui repositori apt. Melanjutkan...")
    
    dependencies = [
        "build-essential", f"linux-headers-{os.uname().release}", "git", "bison", "flex", 
        "libdb-dev", "libelf-dev", "pkg-config", "libcap-dev", "libmnl-dev", 
        "python3", "python3-pip", "python3-flask"
    ]
    ok, _, _ = run_cmd(["apt-get", "install", "-y"] + dependencies)
    if not ok:
        print("[-] Beberapa dependensi gagal diinstal secara otomatis. Mencoba kompilasi tetap berjalan...")

    # --- LANGKAH 2: Kompilasi Kernel Module sch_cake.ko ---
    print("\n=== LANGKAH 2: Kompilasi Modul Jaringan Kernel sch_cake.ko ===")
    build_dir = "/tmp/mq-cake-build"
    git_dir = "/tmp/linux-mq-cake"
    
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir)

    print("[*] Mengkloning repositori linux-mq-cake...")
    ok, _, _ = run_cmd(["git", "clone", "--depth", "1", "https://github.com/mq-cake/linux-mq-cake.git", git_dir])
    if not ok:
        print("[-] Gagal mengkloning repositori linux-mq-cake.")
        sys.exit(1)

    os.makedirs(build_dir, exist_ok=True)
    shutil.copy(os.path.join(git_dir, "net/sched/sch_cake.c"), os.path.join(build_dir, "sch_cake.c"))

    # Patch compatibility header ke sch_cake.c
    print("[*] Melakukan patch compatibility header ke sch_cake.c...")
    try:
        sch_cake_path = os.path.join(build_dir, "sch_cake.c")
        with open(sch_cake_path, "r", encoding="utf-8") as f:
            content = f.read()

        idx = content.find("#include <net/flow_dissector.h>")
        if idx != -1:
            end_line = content.find("\n", idx)
            new_content = content[:end_line+1] + compatibility_header + content[end_line+1:]
        else:
            new_content = compatibility_header + content

        with open(sch_cake_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[+] Patch sch_cake.c berhasil diterapkan secara lokal!")
    except Exception as e:
        print(f"[-] Gagal mem-patch sch_cake.c: {e}")
        sys.exit(1)

    # Tulis Makefile build modul
    makefile_content = f"""obj-m += sch_cake.o
all:
	make -C /lib/modules/{os.uname().release}/build M=$(PWD) modules
clean:
	make -C /lib/modules/{os.uname().release}/build M=$(PWD) clean
"""
    with open(os.path.join(build_dir, "Makefile"), "w") as f:
        f.write(makefile_content)

    # Kompilasi modul
    print("[*] Mengompilasi modul kernel sch_cake.ko...")
    ok, _, _ = run_cmd(["make", "clean"], cwd=build_dir)
    ok, _, _ = run_cmd(["make"], cwd=build_dir)

    ko_path = os.path.join(build_dir, "sch_cake.ko")
    if not os.path.exists(ko_path):
        print("[-] Kompilasi sch_cake.ko GAGAL!")
        sys.exit(1)

    # Pasang modul kernel ke sistem
    print("[*] Memasang modul kernel sch_cake ke kernel sistem...")
    dest_ko_dir = f"/lib/modules/{os.uname().release}/kernel/net/sched/"
    os.makedirs(dest_ko_dir, exist_ok=True)
    shutil.copy(ko_path, os.path.join(dest_ko_dir, "sch_cake.ko"))
    
    run_cmd(["depmod", "-a"])
    run_cmd(["modprobe", "sch_cake"])

    # Cek apakah modul terload
    ok, stdout, _ = run_cmd(["lsmod"])
    if "sch_cake" in stdout:
        print("[+] Modul kernel sch_cake.ko berhasil dimuat!")
    else:
        print("[-] Gagal memuat modul kernel sch_cake ke kernel!")

    # --- LANGKAH 3: Kompilasi iproute2 tc Kustom ---
    print("\n=== LANGKAH 3: Kompilasi Utilitas tc (iproute2) Kustom ===")
    iproute_git = "/tmp/iproute2-mq"
    if os.path.exists(iproute_git):
        shutil.rmtree(iproute_git)

    print("[*] Mengkloning repositori iproute2-mq...")
    ok, _, _ = run_cmd(["git", "clone", "--depth", "1", "https://github.com/mq-cake/iproute2.git", iproute_git])
    if not ok:
        print("[-] Gagal mengkloning repositori iproute2.")
        sys.exit(1)

    print("[*] Mengonfigurasi dan mengompilasi iproute2...")
    ok, _, _ = run_cmd(["./configure"], cwd=iproute_git)
    if not ok:
        print("[-] Gagal mengonfigurasi iproute2.")
        sys.exit(1)
        
    ok, _, _ = run_cmd(["make", "-j" + str(os.cpu_count() or 2)], cwd=iproute_git)
    if not ok:
        print("[-] Gagal mengompilasi iproute2.")
        sys.exit(1)

    # Pasang tc kustom ke /usr/local/sbin/tc
    shutil.copy(os.path.join(iproute_git, "tc/tc"), "/usr/local/sbin/tc")
    os.chmod("/usr/local/sbin/tc", 0o755)

    # Verifikasi utilitas kustom tc
    ok, stdout, _ = run_cmd(["/usr/local/sbin/tc", "-V"])
    if ok:
        print(f"[+] Versi tc kustom terpasang: {stdout.strip()}")

    # --- LANGKAH 4: Menyalin Core Daemon & Web Monitor ---
    print("\n=== LANGKAH 4: Menyalin Core Daemon & Web Monitor ke Sistem ===")
    
    # 1. Salin script daemon ke /usr/local/bin
    print("[*] Memasang cake_adaptive.py ke /usr/local/bin...")
    shutil.copy(os.path.join(src_dir, "cake_adaptive.py"), "/usr/local/bin/cake_adaptive.py")
    os.chmod("/usr/local/bin/cake_adaptive.py", 0o755)

    # 2. Salin file service systemd
    print("[*] Memasang service unit ke /etc/systemd/system...")
    shutil.copy(os.path.join(src_dir, "cake-adaptive.service"), "/etc/systemd/system/cake-adaptive.service")
    shutil.copy(os.path.join(src_dir, "web-monitor.service"), "/etc/systemd/system/web-monitor.service")

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
        default_conf_str = '{\n    "interface": "veth_rtr_lan",\n    "ping_dest": "10.0.2.2",\n    "bandwidth": "150mbit",\n    "interval": 1.0,\n    "extra_opts": "diffserv4 sync 500us"\n}'
        with open(config_file, "w") as f:
            f.write(default_conf_str)
        print("[+] Konfigurasi default dibuat di /etc/cake_adaptive.conf")

    # --- LANGKAH 5: Registrasi & Jalankan Service ---
    print("\n=== LANGKAH 5: Mendaftarkan & Menjalankan Service Systemd ===")
    run_cmd(["systemctl", "daemon-reload"])
    
    print("[*] Mengaktifkan & menjalankan service cake-adaptive...")
    run_cmd(["systemctl", "enable", "cake-adaptive"])
    run_cmd(["systemctl", "restart", "cake-adaptive"])

    print("[*] Mengaktifkan & menjalankan service web-monitor...")
    run_cmd(["systemctl", "enable", "web-monitor"])
    run_cmd(["systemctl", "restart", "web-monitor"])

    # --- SELESAI ---
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
