import os

from opsbro.collector import Collector


class LoadAverage(Collector):
    def launch(self):
        self.logger.debug('getLoadAvrgs: start')
        
        # Get the triplet from the python function
        try:
            loadAvrgs_1, loadAvrgs_5, loadAvrgs_15 = os.getloadavg()
        except (AttributeError, OSError):
            self.set_not_eligible('Load average is only availabe on unix systems')
            return False
        
        self.logger.debug('getLoadAvrgs: parsing')
        
        loadavrgs = {'load1': loadAvrgs_1, 'load5': loadAvrgs_5, 'load15': loadAvrgs_15}
        
        self.logger.debug('getLoadAvrgs: completed, returning')
        
        return loadavrgs
