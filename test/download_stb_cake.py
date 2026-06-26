import paramiko

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    print("[+] Connected to STB. Downloading sch_cake.c...")
    
    sftp = client.open_sftp()
    sftp.get("/home/freischutz/linux-mq-cake/net/sched/sch_cake.c", "C:\\Users\\ASUS\\Documents\\Skripsi\\skripsi2\\qos-cake-adaptive\\sch_cake_stb_mq.c")
    sftp.close()
    
    print("[+] Download complete!")
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
