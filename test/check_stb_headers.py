import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

print(f"Connecting to {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ip, username=username, password=password, timeout=10)

commands = [
    "uname -r",
    "ls -la /lib/modules/$(uname -r)/build",
    "find /home/freischutz -name Makefile -maxdepth 2"
]

for cmd in commands:
    print(f"\n--- RUNNING: {cmd} ---")
    stdin, stdout, stderr = client.exec_command(cmd)
    print("STDOUT:")
    print(stdout.read().decode('utf-8'))
    print("STDERR:")
    print(stderr.read().decode('utf-8'))

client.close()
