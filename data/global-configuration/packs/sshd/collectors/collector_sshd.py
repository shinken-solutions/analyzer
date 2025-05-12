import os

from opsbro.collector import Collector


class Sshd(Collector):
    def launch(self):
        self.logger.debug('get_sshd: starting')
        if not os.path.exists('/etc/ssh'):
            self.set_not_eligible('There is no ssh server. Missing /etc/ssh directory.')
            return
        res = {}
        if os.path.exists('/etc/ssh/ssh_host_rsa_key.pub'):
            f = open('/etc/ssh/ssh_host_rsa_key.pub', 'r')
            buf = f.read().strip()
            f.close()
            res['host_rsa_key_pub'] = buf.replace('ssh-rsa ', '')
        if os.path.exists('/etc/ssh/ssh_host_dsa_key.pub'):
            f = open('/etc/ssh/ssh_host_dsa_key.pub', 'r')
            buf = f.read().strip()
            f.close()
            res['host_dsa_key_pub'] = buf.replace('ssh-dss ', '')
        
        return res
