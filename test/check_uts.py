import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ip, username=username, password=password, timeout=10)

cmd = f"cat /usr/src/linux-headers-6.18.35-current-meson64/include/generated/utsrelease.h"
stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode('utf-8'))

client.close()
