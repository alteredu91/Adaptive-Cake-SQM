import paramiko
ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.31', username='freischutz', password='kiken')
ssh.exec_command('echo kiken | sudo -S sed -i \'s/ sync 500us//g\' /etc/cake_adaptive.conf && echo kiken | sudo -S systemctl restart cake-adaptive')
