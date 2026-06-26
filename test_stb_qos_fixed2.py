import paramiko
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("[*] Menyambungkan ke STB 192.168.1.11...")
    client.connect("192.168.1.11", username="freischutz", password="kiken", timeout=15)
    
    commands = [
        ("Cek Modul Kernel", "lsmod"),
        ("Cek Service cake-adaptive", "systemctl status cake-adaptive --no-pager -n 10"),
        ("Cek Log QoS", "journalctl -u cake-adaptive -n 15 --no-pager"),
        ("Cek Qdisc TC", "tc -s qdisc show")
    ]
    
    for title, cmd in commands:
        print(f"\n=== {title} ===")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        
        if "lsmod" in cmd:
            lines = [line for line in out.split('\n') if 'cake' in line.lower()]
            if lines:
                print('\n'.join(lines))
            else:
                print("(Modul cake tidak ditemukan)")
        else:
            if out:
                print(out)
            else:
                print("(Tidak ada output / kosong)")

except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
