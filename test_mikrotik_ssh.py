import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('idn23.tunnel.id', port=3228, username='admin', password='K4lib4t4', timeout=5)
stdin, stdout, stderr = client.exec_command('/interface print')
print(stdout.read().decode())
client.close()
