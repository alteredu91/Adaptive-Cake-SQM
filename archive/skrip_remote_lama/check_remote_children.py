import paramiko

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=5)
    stdin, stdout, stderr = client.exec_command("pstree -p 4364")
    print("Process Tree for PID 4364:")
    print(stdout.read().decode('utf-8').strip())
    
    stdin, stdout, stderr = client.exec_command("ps -o ppid,pid,cmd -A | grep 4364")
    print("\nParent-Child Processes:")
    print(stdout.read().decode('utf-8').strip())
    
    client.close()
except Exception as e:
    print(f"Error: {e}")
