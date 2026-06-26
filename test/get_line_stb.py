import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    # Get lines 1030 to 1060 in /home/freischutz/linux-mq-cake/include/uapi/linux/pkt_sched.h
    cmd = "sed -n '1030,1060p' /home/freischutz/linux-mq-cake/include/uapi/linux/pkt_sched.h"
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode('utf-8'))
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
