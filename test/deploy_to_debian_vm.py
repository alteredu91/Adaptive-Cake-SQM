import paramiko
import os
import tarfile
import sys

ip = "192.168.182.131"
username = "osboxes"
password = "osboxes.org"

# Gunakan absolute path direktori utama
local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
tar_path = "qos-cake-full.tar.gz"

print(f"[*] Membuat arsip tar dari proyek di {local_dir}...")
with tarfile.open(tar_path, "w:gz") as tar:
    for root, dirs, files in os.walk(local_dir):
        # Abaikan folder yang tidak perlu dikirim
        if ".git" in root or "simulasi_komputasi" in root or "archive" in root:
            continue
        for file in files:
            # Abaikan file tar itu sendiri
            if file == tar_path:
                continue
            full_path = os.path.join(root, file)
            # Buat path relatif untuk di dalam tar
            arcname = os.path.relpath(full_path, local_dir)
            tar.add(full_path, arcname=f"qos-cake-adaptive/{arcname}")

print(f"[*] Menghubungkan ke Debian VM di {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    
    print("[*] Mengunggah file (SFTP)...")
    sftp = client.open_sftp()
    sftp.put(tar_path, f"/home/{username}/qos-cake-full.tar.gz")
    sftp.close()
    
    print("[*] Mengekstrak dan menjalankan install.py (membutuhkan waktu untuk kompilasi)...")
    # Ekstrak lalu jalankan install.py sebagai sudo
    cmd = (
        f"cd /home/{username} && "
        f"tar -xzf qos-cake-full.tar.gz && "
        f"cd qos-cake-adaptive && "
        f"echo {password} | sudo -S python3 install.py"
    )
    
    # Gunakan unbuffered pty agar kita bisa membaca output secara realtime
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    
    # Cetak output instalasi baris demi baris agar tidak terlihat ngehang
    for line in iter(stdout.readline, ""):
        print(line, end="")
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"\n[+] Selesai dengan status kode: {exit_status}")
    
    client.close()
    
    # Hapus file tar lokal agar bersih
    if os.path.exists(tar_path):
        os.remove(tar_path)
        
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
