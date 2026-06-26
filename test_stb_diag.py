import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect("192.168.1.11", username="freischutz", password="kiken", timeout=15)
    
    print("\n--- 1. Cek Load CPU ---")
    stdin, stdout, stderr = client.exec_command("top -b -n 1 | head -n 15")
    print(stdout.read().decode())
    
    print("\n--- 2. Cek Pesan Kernel (dmesg) ---")
    stdin, stdout, stderr = client.exec_command("dmesg | tail -n 20")
    print(stdout.read().decode())
    
    print("\n--- 3. Cek Log cake-adaptive ---")
    stdin, stdout, stderr = client.exec_command("journalctl -u cake-adaptive -n 20 --no-pager")
    print(stdout.read().decode())
    
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
