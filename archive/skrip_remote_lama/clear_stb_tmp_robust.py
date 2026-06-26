import paramiko
import time
import sys

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    print("Connected. Clearing /tmp...")
    
    channel = client.get_transport().open_session()
    channel.get_pty()
    channel.exec_command("sudo rm -rf /tmp/linux-mq-cake /tmp/iproute2-mq /tmp/mq-cake-build")
    
    time.sleep(1)
    if channel.recv_ready():
        out = channel.recv(1024).decode('utf-8', errors='ignore')
        print(out, end="")
        if "sandi" in out.lower() or "password" in out.lower() or ":" in out:
            channel.send(f"{password}\n")
            print("Password sent.")
            
    # Tunggu sampai selesai
    while not channel.exit_status_ready():
        if channel.recv_ready():
            sys.stdout.write(channel.recv(1024).decode('utf-8', errors='ignore'))
        time.sleep(0.2)
        
    print(f"Clear finished with exit status: {channel.recv_exit_status()}")
    client.close()
except Exception as e:
    print(f"Error: {e}")
