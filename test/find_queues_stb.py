import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    print("[+] Connected!")
    
    # Grep in the linux-mq-cake folder
    cmd = "grep -rn 'ACTIVE_QUEUES' /home/freischutz/linux-mq-cake/"
    print(f"Running: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode('utf-8'))
    
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
