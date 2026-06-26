import paramiko
import sys

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ip, username=username, password=password, timeout=10)

cmd = "/sbin/tc qdisc show dev eth0"
stdin, stdout, stderr = client.exec_command(cmd)

print("--- STDOUT ---")
print(stdout.read().decode('utf-8'))
print("--- STDERR ---")
print(stderr.read().decode('utf-8'))

client.close()
