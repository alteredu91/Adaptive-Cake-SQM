import paramiko
import os
import tarfile
import sys

ip = "192.168.1.11"
username = "freischutz"
password = "kiken"
remote_dir = "/home/freischutz/qos-cake-adaptive"
src_dir = os.path.dirname(os.path.realpath(__file__))

print(f"[*] Membuat arsip tar dari proyek di {src_dir}...")
tar_path = "qos-cake-adaptive.tar.gz"
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(".", arcname=os.path.basename(src_dir), filter=lambda x: None if '.git' in x.name or '.ko' in x.name or '.o' in x.name else x)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print(f"[*] Menghubungkan ke STB di {ip}...")
    client.connect(ip, username=username, password=password, timeout=10)
    
    print("[*] Mengunggah file (SFTP)...")
    sftp = client.open_sftp()
    sftp.put(tar_path, "/tmp/qos-cake-adaptive.tar.gz")
    sftp.close()
    
    print("[*] Mengekstrak dan menjalankan install.py (membutuhkan sudo)...")
    cmd = f"rm -rf {remote_dir} && tar -xzf /tmp/qos-cake-adaptive.tar.gz -C /home/{username} && cd {remote_dir} && echo '{password}' | sudo -S python3 install.py"
    
    # Use get_pty=True to support sudo password prompt correctly
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    
    for line in iter(stdout.readline, ""):
        print(line, end="")
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"\n[+] Selesai dengan status kode: {exit_status}")

except Exception as e:
    print(f"[-] Gagal: {e}")
finally:
    client.close()
    if os.path.exists(tar_path):
        os.remove(tar_path)
