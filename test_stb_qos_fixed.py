import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("[*] Menyambungkan ke STB 192.168.1.11...")
    client.connect("192.168.1.11", username="freischutz", password="kiken", timeout=15)
    
    commands = [
        ("Cek Modul Kernel", "lsmod | grep sch_cake"),
        ("Cek Service cake-adaptive", "systemctl status cake-adaptive --no-pager | head -n 10"),
        ("Cek Log QoS (10 baris terakhir)", "journalctl -u cake-adaptive -n 10 --no-pager"),
        ("Cek Qdisc TC", "tc -s qdisc show")
    ]
    
    for title, cmd in commands:
        print(f"\n=== {title} ===")
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        time.sleep(1) # Beri waktu sebentar
        out = stdout.read().decode(errors='ignore').strip()
        if out:
            print(out)
        else:
            print("(Tidak ada output / kosong)")

except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
