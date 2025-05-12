import re
import traceback

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.collector import Collector
from opsbro.parameters import StringParameter


class Nginx(Collector):
    parameters = {
        'uri': StringParameter(default='http://localhost/nginx_status'),
    }
    
    def __init__(self):
        super(Nginx, self).__init__()
        self.nginxRequestsStore = None
        
    
    def launch(self):
        logger = self.logger
        
        if not self.is_in_group('nginx'):
            self.set_not_eligible('Please add the nginx group to enable this collector.')
            return
        
        logger.debug('getNginxStatus: start')
        
        logger.debug('getNginxStatus: config set')
        
        try:
            response = httper.get(self.get_parameter('uri'), timeout=3)
        except get_http_exceptions() as exp:
            self.set_error('Unable to get Nginx status - HTTPError = %s' % exp)
            return False
            
        logger.debug('getNginxStatus: urlopen success, start parsing')
        
        # Thanks to http://hostingfu.com/files/nginx/nginxstats.py for this code
        
        logger.debug('getNginxStatus: parsing connections')
        
        try:
            # Connections
            parsed = re.search(r'Active connections:\s+(\d+)', response)
            connections = int(parsed.group(1))
            
            logger.debug('getNginxStatus: parsed connections')
            logger.debug('getNginxStatus: parsing reqs')
            
            # Requests per second
            parsed = re.search(r'\s*(\d+)\s+(\d+)\s+(\d+)', response)
            
            if not parsed:
                logger.debug('getNginxStatus: could not parse response')
                return False
            
            requests = int(parsed.group(3))
            
            logger.debug('getNginxStatus: parsed reqs')
            
            if self.nginxRequestsStore == None or self.nginxRequestsStore < 0:
                logger.debug('getNginxStatus: no reqs so storing for first time')
                self.nginxRequestsStore = requests
                requestsPerSecond = 0
            else:
                logger.debug('getNginxStatus: reqs stored so calculating')
                logger.debug('getNginxStatus: self.nginxRequestsStore = %s', self.nginxRequestsStore)
                logger.debug('getNginxStatus: requests = %s', requests)
                
                requestsPerSecond = float(requests - self.nginxRequestsStore) / 60
                logger.debug('getNginxStatus: requestsPerSecond = %s', requestsPerSecond)
                self.nginxRequestsStore = requests
            
            if connections != None and requestsPerSecond != None:
                logger.debug('getNginxStatus: returning with data')
                return {'connections': connections, 'reqPerSec': requestsPerSecond}
            else:
                logger.debug('getNginxStatus: returning without data')
                return False
        
        except Exception:
            self.set_error('Unable to get Nginx status - %s - Exception = %s' % (response, traceback.format_exc()))
            return False
