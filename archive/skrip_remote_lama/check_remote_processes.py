import paramiko

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=5)
    stdin, stdout, stderr = client.exec_command("ps aux | grep -E 'make|gcc|install|python' | grep -v grep")
    print("Running processes on STB:")
    print(stdout.read().decode('utf-8').strip())
    client.close()
except Exception as e:
    print(f"Error checking processes: {e}")
