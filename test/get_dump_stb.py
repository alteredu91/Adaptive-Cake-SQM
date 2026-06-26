import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    # Get lines 2920 to 2950 in /home/freischutz/linux-mq-cake/net/sched/sch_cake.c
    cmd = "sed -n '2920,2950p' /home/freischutz/linux-mq-cake/net/sched/sch_cake.c"
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode('utf-8'))
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
