import paramiko
import sys

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ip, username=username, password=password, timeout=10)

sftp = client.open_sftp()
sftp.put("valid_conf.json", "/tmp/cake_adaptive.conf")
sftp.close()

cmd = f"echo {password} | sudo -S cp /tmp/cake_adaptive.conf /etc/cake_adaptive.conf && echo {password} | sudo -S systemctl restart cake-adaptive && echo {password} | sudo -S systemctl restart web-monitor"
stdin, stdout, stderr = client.exec_command(cmd)

print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
client.close()
