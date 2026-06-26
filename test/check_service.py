import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ip, username=username, password=password, timeout=10)

cmd = f"echo {password} | sudo -S journalctl -u cake-adaptive -n 20 --no-pager"
stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode('utf-8'))

client.close()
