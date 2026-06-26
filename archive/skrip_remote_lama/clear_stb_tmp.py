import paramiko
import time

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=5)
    
    # Bersihkan file kompilasi yang menggantung di /tmp
    print("[*] Membersihkan file sementara di /tmp STB...")
    stdin, stdout, stderr = client.exec_command("sudo rm -rf /tmp/linux-mq-cake /tmp/iproute2-mq /tmp/mq-cake-build")
    # Sudo password input
    time.sleep(0.5)
    # Check if sudo asks password
    # (Since this is simple command, it should execute if password was cached or via stdin)
    # Let's send password anyway to stdin just in case
    stdin.write(f"{password}\n")
    stdin.flush()
    
    # Tunggu selesai
    stdout.read()
    
    # Jalankan df -h untuk melihat space baru di /tmp
    stdin, stdout, stderr = client.exec_command("df -h | grep /tmp")
    print("\nSisa ruang disk /tmp setelah pembersihan:")
    print(stdout.read().decode('utf-8').strip())
    
    client.close()
except Exception as e:
    print(f"Error: {e}")
