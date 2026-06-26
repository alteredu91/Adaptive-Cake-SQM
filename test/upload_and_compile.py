import paramiko
import sys

ip = "192.168.1.16"
username = "freischutz"
password = "kiken"

local_path = "C:\\Users\\ASUS\\Documents\\Skripsi\\skripsi2\\qos-cake-adaptive\\src\\sch_cake.c"
remote_path = "/home/freischutz/mq-cake-build/sch_cake.c"
kernel_dir = "/home/freischutz/mq-cake-build"

print(f"Connecting to STB at {ip}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(ip, username=username, password=password, timeout=10)
    print("[+] Connected successfully.")
    
    print(f"[*] Uploading {local_path} to {remote_path}...")
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("[+] Upload complete.")
    
    print("[*] Compiling kernel module on STB...")
    compile_cmd = f"cd {kernel_dir} && make clean && make"
    stdin, stdout, stderr = client.exec_command(compile_cmd)
    
    # Wait for the command to finish and print output
    exit_status = stdout.channel.recv_exit_status()
    
    print("--- STDOUT ---")
    print(stdout.read().decode('utf-8'))
    
    print("--- STDERR ---")
    print(stderr.read().decode('utf-8'))
    
    if exit_status == 0:
        print("\n[+] Compilation SUCCESSFUL!")
    else:
        print(f"\n[-] Compilation FAILED with exit code {exit_status}.")
        
    client.close()
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)
