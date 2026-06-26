import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect("192.168.182.131", username="root", password="osboxes.org", timeout=10)
    
    print("\n--- 1. Cek Modul Kernel ---")
    stdin, stdout, stderr = client.exec_command("lsmod | grep cake")
    print(stdout.read().decode())
    
    print("\n--- 2. Cek Interface Default ---")
    stdin, stdout, stderr = client.exec_command("ip -o -4 route show to default | awk '{print $5}'")
    default_iface = stdout.read().decode().strip()
    print(f"Default Interface: {default_iface}")
    
    print("\n--- 3. Cek Status TC Qdisc ---")
    if default_iface:
        stdin, stdout, stderr = client.exec_command(f"tc -s qdisc show dev {default_iface}")
        print(stdout.read().decode())
        print(stderr.read().decode())
    
    print("\n--- 4. Cek Log Daemon Python (cake-adaptive) ---")
    stdin, stdout, stderr = client.exec_command("journalctl -u cake-adaptive -n 15 --no-pager")
    print(stdout.read().decode())
    
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
