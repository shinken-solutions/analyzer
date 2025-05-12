import sys
import os

from opsbro.collector import Collector
from opsbro.now import NOW

if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class KernelStats(Collector):
    def __init__(self):
        super(KernelStats, self).__init__()
        self.store = {}
        self.last_launch = 0.0
    
    
    def launch(self):
        logger = self.logger
        now = int(NOW.monotonic())
        diff = now - self.last_launch  # note: thanks to monotonic, diff cannot be negative
        self.last_launch = now
        
        logger.debug('getKernelStats: start')
        
        if os.name == 'nt':
            data = {}
            counters = [
                ('ctx switches/sec', r'\System\Context Switches/sec', 100),
                (r'interrupts/sec', r'\Processor(_Total)\Interrupts/sec', 100),
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                data[_label] = v
            return data
        
        if sys.platform.startswith('linux'):
            logger.debug('getKernelStats: linux2')
            
            try:
                logger.debug('getKernelStats: attempting open')
                lines = []
                with open('/proc/stat', 'r') as stats:
                    lines.extend(stats.readlines())
                with open('/proc/vmstat', 'r') as vmstat:
                    lines.extend(vmstat.readlines())
            except IOError as e:
                logger.error('getKernelStat: exception = %s', e)
                return False
            
            logger.debug('getKernelStat: open success, parsing')
            
            data = {}
            for line in lines:
                elts = line.split(' ', 1)
                # only look at keys
                if len(elts) != 2:
                    continue
                try:
                    data[elts[0]] = int(elts[1])
                except ValueError:  # not an int? skip this value
                    continue
            
            # Now loop through each interface
            by_sec_keys = ['ctxt', 'processes', 'pgfault', 'pgmajfault']
            to_add = {}
            for (k, v) in data.items():
                if k in by_sec_keys:
                    if k in self.store:
                        to_add['%s/s' % k] = (v - self.store[k]) / diff
                    else:
                        to_add['%s/s' % k] = 0
                    self.store[k] = data[k]
            for k in by_sec_keys:
                del data[k]
            data.update(to_add)
            logger.debug('getKernelStats: completed, returning')
            
            return data
        
        else:
            self.set_not_eligible('This system is not managed')
            return False
