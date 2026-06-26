import paramiko

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=5)
    # Gunakan kill -9 pada PID sudo yang menggantung
    stdin, stdout, stderr = client.exec_command("kill -9 4364")
    print("Kill command sent.")
    client.close()
except Exception as e:
    print(f"Error: {e}")
