# Strange file to to fine tuning. Gettimeofday can be CPU (%sys) consuming
# if call 100K/s, so if you need only a "somewhat now", call, like with a 1/100s
# precision, you can call this lib object NOW that will be updated 100time a sec

import time

from .threadmgr import threader
from .misc.monotonic import monotonic as f_monotonic


class QuickNow(object):
    def __init__(self):
        self.now = int(time.time())
    
    
    def do_thread(self):
        while True:
            self.now = int(time.time())
            time.sleep(0.01)  # update each 10ms
    
    
    def launch(self):
        threader.create_and_launch(self.do_thread, name='Time getter', essential=True, part='agent')
    
    
    def monotonic(self):
        return f_monotonic()


NOW = QuickNow()
