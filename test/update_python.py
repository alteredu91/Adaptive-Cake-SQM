import paramiko
import os
import tarfile
import sys

ip = "192.168.1.8"
username = "freischutz"
password = "kiken"

local_dir = "C:\\Users\\ASUS\\Documents\\Skripsi\\skripsi2\\qos-cake-adaptive"
tar_path = "qos-cake.tar.gz"

print("Creating tar archive of the project...")
with tarfile.open(tar_path, "w:gz") as tar:
    for item in ["src/cake_adaptive.py", "web_monitor/app.py"]:
        full_path = os.path.join(local_dir, item)
        tar.add(full_path, arcname=f"qos-cake-adaptive/{item}")

print(f"Connecting to STB at {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    
    sftp = client.open_sftp()
    sftp.put(tar_path, "/home/freischutz/qos-cake.tar.gz")
    sftp.close()
    
    conf = '{\\n    "interface": "eth0",\\n    "ping_dest": "1.1.1.1",\\n    "bandwidth": "150mbit",\\n    "interval": 1.0,\\n    "extra_opts": "diffserv4",\\n    "qdisc_type": "cake"\\n}'
    cmd = f"cd /home/freischutz && tar -xzf qos-cake.tar.gz && echo {password} | sudo -S cp qos-cake-adaptive/src/cake_adaptive.py /usr/local/bin/cake_adaptive.py && echo {password} | sudo -S cp qos-cake-adaptive/web_monitor/app.py /usr/local/share/qos-cake-monitor/app.py && echo {password} | sudo -S bash -c 'echo -e \"{conf}\" > /etc/cake_adaptive.conf' && echo {password} | sudo -S systemctl restart cake-adaptive && echo {password} | sudo -S systemctl restart web-monitor"
    stdin, stdout, stderr = client.exec_command(cmd)
    
    # Wait for the command to finish and print output
    exit_status = stdout.channel.recv_exit_status()
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
