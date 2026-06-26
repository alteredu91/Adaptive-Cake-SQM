import paramiko
ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.31', username='freischutz', password='kiken')
stdin, stdout, stderr = ssh.exec_command('find /lib/modules -name "*cake*.ko"')
print(stdout.read().decode())
