import paramiko

ip = "192.168.1.21"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=5)
    
    # 1. Cek apakah folder build link ada dan valid
    stdin, stdout, stderr = client.exec_command("ls -la /lib/modules/$(uname -r)/build")
    print("Check /lib/modules/$(uname -r)/build:")
    print(stdout.read().decode('utf-8').strip())
    print(stderr.read().decode('utf-8').strip())
    
    # 2. Cari nama package linux-headers di apt-cache
    stdin, stdout, stderr = client.exec_command("apt-cache search linux-headers | grep meson64")
    print("\nLinux Headers for meson64 in apt-cache:")
    print(stdout.read().decode('utf-8').strip())
    
    # 3. Cari all linux-headers
    stdin, stdout, stderr = client.exec_command("apt-cache search linux-headers-current")
    print("\nLinux Headers Current in apt-cache:")
    print(stdout.read().decode('utf-8').strip())
    
    client.close()
except Exception as e:
    print(f"Error: {e}")
