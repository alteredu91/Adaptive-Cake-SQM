import paramiko
ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.31', username='freischutz', password='kiken')
stdin, stdout, stderr = ssh.exec_command('echo kiken | sudo -S /sbin/tc qdisc add dev lo root cake && /sbin/tc qdisc show dev lo; echo kiken | sudo -S /sbin/tc qdisc del dev lo root')
print(stdout.read().decode())
print(stderr.read().decode())
