import paramiko
import os
import tarfile
import sys

ip = "192.168.1.8"
username = "freischutz"
password = "kiken"

local_dir = "C:\\Users\\ASUS\\Documents\\Skripsi\\skripsi2\\qos-cake-adaptive"
tar_path = "qos-cake-router-update.tar.gz"

print("Creating tar archive of the project...")
with tarfile.open(tar_path, "w:gz") as tar:
    for item in ["src/cake_adaptive.py", "src/sch_cake.c", "web_monitor/app.py", "web_monitor/templates/index.html", "install.py"]:
        full_path = os.path.join(local_dir, item)
        tar.add(full_path, arcname=f"qos-cake-adaptive/{item}")

print(f"Connecting to STB at {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    
    sftp = client.open_sftp()
    sftp.put(tar_path, "/home/freischutz/qos-cake-router-update.tar.gz")
    sftp.close()
    
    # 1. Update files
    # 2. Install dependencies (dnsmasq, iptables)
    # 3. Enable IP forward
    # 4. Restart services
    
    cmds = [
        "cd /home/freischutz && tar -xzf qos-cake-router-update.tar.gz",
        f"echo {password} | sudo -S python3 /home/freischutz/qos-cake-adaptive/install.py"
    ]
    
    cmd = " && ".join(cmds)
    cmd = " && ".join(cmds)
    print("Executing update and installing router dependencies...\n")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    
    # Stream the output live
    for line in iter(stdout.readline, ""):
        print(line, end="")
    
    exit_status = stdout.channel.recv_exit_status()
    
    # Check for any remaining errors
    err = stderr.read().decode('utf-8')
    if err and err.strip():
        print("\n[ERROR OUTPUT]:", err)
        
    client.close()
    print("Update successful!")
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
