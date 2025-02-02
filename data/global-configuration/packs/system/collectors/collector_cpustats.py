import os
import sys
import time

from opsbro.collector import Collector
from opsbro.now import NOW


if os.name == 'nt':
    import opsbro.misc.wmi as wmi


class CpuStats(Collector):
    def __init__(self):
        super(CpuStats, self).__init__()
        self.prev_linux_stats = {}
        self.prev_linux_time = 0
    
    
    def _get_linux_abs_stats(self):
        r = {}
        with open('/proc/stat') as procfile:
            lines = procfile.readlines()
        
        for line in lines:
            # Example of line:
            # cat /proc/stat
            # cpu  16495 72 13812 1662977 894 0 160 0 0 0
            # cpu0 16495 72 13812 1662977 894 0 160 0 0 0
            
            if not line.startswith('cpu'):
                continue
            elts = line.split(' ')
            h_name = elts[0]
            if h_name == 'cpu':
                h_name = 'cpu_all'
            r[h_name] = {}
            values = [int(v.strip()) for v in elts[1:] if v.strip()]
            columns = (r'%user', r'%nice', r'%system', r'%idle', r'%iowait', r'%irq', r'%softirq', r'%steal', r'%guest', r'%guest_nice')
            for i in xrange(0, len(columns)):
                r[h_name][columns[i]] = values[i]
        
        return r
    
    
    def compute_linux_cpu_stats(self, new_cpu_raw_stats, diff_time):
        r = {}
        for (k, new_stats) in new_cpu_raw_stats.iteritems():
            old_stats = self.prev_linux_stats.get(k, None)
            # A new cpu did spawn? wait a loop to compute it
            if old_stats is None:
                continue
            r[k] = {}
            for (t, new_v) in new_stats.iteritems():
                old_v = old_stats[t]
                this_type_consumed = (new_v - old_v) / float(diff_time)
                r[k][t] = this_type_consumed
        return r
    
    
    def launch(self):
        logger = self.logger
        logger.debug('getCPUStats: start')
        
        cpuStats = {}
        
        if os.name == 'nt':
            counters = [
                (r'cpu usage %', r'\Processor(_Total)\% Processor Time', 100),
                (r'cpu_kernel_%', r'\Processor(_Total)\% Privileged Time', 100),
                (r'cpu_user_%', r'\Processor(_Total)\% User Time', 100)
            ]
            for c in counters:
                _label = c[0]
                _query = c[1]
                _delay = c[2]
                v = wmi.wmiaccess.get_perf_data(_query, unit='double', delay=_delay)
                cpuStats[_label] = v
            return cpuStats
        
        if sys.platform == 'linux2':
            # /proc/stat columns:
            # user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
            logger.debug('getCPUStats: linux2')
            new_stats = self._get_linux_abs_stats()
            new_time = NOW.monotonic()
            # First loop: do a 1s loop an compute it, to directly have results
            if self.prev_linux_time == 0:
                self.prev_linux_time = NOW.monotonic()
                self.prev_linux_stats = new_stats
                time.sleep(1)
                new_stats = self._get_linux_abs_stats()
                new_time = NOW.monotonic()
                
            # NOTE: thanks to monotonic time, we cannot get back in time for diff

            # So let's compute
            r = self.compute_linux_cpu_stats(new_stats, new_time - self.prev_linux_time)
            self.prev_linux_stats = new_stats
            self.prev_linux_time = new_time
            return r
        else:
            logger.debug('getCPUStats: unsupported platform')
            return False
        
        self.logger.debug('getCPUStats: completed, returning')
        return cpuStats
