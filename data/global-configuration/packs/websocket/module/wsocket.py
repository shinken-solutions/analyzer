from __future__ import print_function
import json
from opsbro.misc.websocketserver import WebSocket, SimpleWebSocketServer
from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('websocket')


class WebExporter(WebSocket):
    def handleMessage(self):
        if self.data is None:
            self.data = ''
    
    
    def handleConnected(self):
        logger.debug(self.address, 'connected')
    
    
    def handleClose(self):
        logger.debug(self.address, 'closed')


class WebSocketBackend(object):
    def __init__(self, mod_conf):
        port = mod_conf.get('port', 6769)
        listening_addr = mod_conf.get('address', '0.0.0.0')
        self.server = SimpleWebSocketServer(listening_addr, port, WebExporter)
        self.websocket_configuration = mod_conf
    
    
    def run(self):
        self.server.serveforever()
    
    
    def get_info(self):
        return {'nb_connexions': len(self.server.connections)}
    
    
    def send_all(self, o):
        try:
            msg = json.dumps(o)
        except ValueError:
            return
        
        # get in one show the connections because connections can change during send
        clients = list(self.server.connections.values())[:]  # note: python3 transform into a list
        for client in clients:
            try:
                client.sendMessage(msg)
            except Exception as exp:
                logger.error('Cannot send websocket message: %s' % exp)
