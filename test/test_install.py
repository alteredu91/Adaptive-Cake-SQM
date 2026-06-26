import paramiko
import os
import tarfile
import sys

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

local_dir = "C:\\Users\\ASUS\\Documents\\Skripsi\\skripsi2\\qos-cake-adaptive"
tar_path = "qos-cake.tar.gz"

print("Creating tar archive of the project...")
with tarfile.open(tar_path, "w:gz") as tar:
    # Only include necessary files to avoid transferring useless logs/metadata
    for item in ["install.py", "src", "web_monitor"]:
        full_path = os.path.join(local_dir, item)
        tar.add(full_path, arcname=f"qos-cake-adaptive/{item}")

print(f"Connecting to STB at {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    print("[+] Connected successfully.")
    
    print("[*] Uploading tar archive...")
    sftp = client.open_sftp()
    sftp.put(tar_path, "/home/freischutz/qos-cake.tar.gz")
    sftp.close()
    
    print("[*] Extracting and running install.py on STB (via sudo)...")
    cmd = f"cd /home/freischutz && rm -rf qos-cake-adaptive && tar -xzf qos-cake.tar.gz && cd qos-cake-adaptive && echo {password} | sudo -S rm -f /etc/cake_adaptive.conf && echo {password} | sudo -S python3 install.py"
    stdin, stdout, stderr = client.exec_command(cmd)
    
    # Wait for the command to finish and print output
    exit_status = stdout.channel.recv_exit_status()
    
    print("--- STDOUT ---")
    print(stdout.read().decode('utf-8'))
    
    print("--- STDERR ---")
    print(stderr.read().decode('utf-8'))
    
    if exit_status == 0:
        print("\n[+] INSTALLATION SUCCESSFUL!")
    else:
        print(f"\n[-] INSTALLATION FAILED with exit code {exit_status}.")
        
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
