import shutil
import os
import time
import threading

from .now import NOW
from .stats import STATS
from .threadmgr import threader
from .dbwrapper import dbwrapper
from .log import LoggerFactory
from .stop import stopper

# Global logger for this part
logger = LoggerFactory.create_logger('key-value')


# This class manage the ttl entries for each key with a ttl. Each is with a 1hour precision idx key that we saved
# in the master db
# but with keeping a database by hour about the key for the housekeeping
class TTLDatabase(object):
    def __init__(self, ttldb_dir):
        self.lock = threading.RLock()
        self.dbs = {}
        self.db_cache_size = 100
        self.ttldb_dir = ttldb_dir
        if not os.path.exists(self.ttldb_dir):
            os.mkdir(self.ttldb_dir)
        # Launch a thread that will look once a minute the old entries
        threader.create_and_launch(self.ttl_cleaning_thread, name='Cleaning TTL expired key/values', essential=True, part='key-value')
    
    
    # Load the hour ttl/H base where we will save all master
    # key for the H hour
    def get_ttl_db(self, h):
        cdb = self.dbs.get(h, None)
        # If missing, look to load it but with a lock to be sure we load it only once
        if cdb is None:
            STATS.incr('ttl-db-cache-miss', 1)
            with self.lock:
                # Maybe during the lock get one other thread succedd in getting the cdb
                if h not in self.dbs:
                    # Ok really load it, but no more than self.db_cache_size
                    # databases (number of open files can increase quickly)
                    if len(self.dbs) > self.db_cache_size:
                        ttodrop = self.dbs.keys()[0]
                        del self.dbs[ttodrop]
                    _t = time.time()
                    cdb = dbwrapper.get_db(os.path.join(self.ttldb_dir, '%d' % h))  # leveldb.LevelDB(os.path.join(self.ttldb_dir, '%d' % h))
                    STATS.incr('ttl-db-open', time.time() - _t)
                    self.dbs[h] = cdb
                # Ok a malicious thread just go before us, good :)
                else:
                    cdb = self.dbs[h]
        # We alrady got it, thanks cache
        else:
            STATS.incr('ttl-db-cache-hit', 1)
        return cdb
    
    
    # Save a key in the good idx minute database
    def set_ttl(self, key, ttl_t):
        # keep keys saved by hour in the future
        ttl_t = divmod(ttl_t, 3600)[0] * 3600
        
        cdb = self.get_ttl_db(ttl_t)
        logger.debug("TTL save", key, "with ttl", ttl_t, "in", cdb)
        cdb.Put(key, '')
    
    
    # We already droped all entry in a db, so drop it from our cache
    def drop_db(self, h):
        # now remove the database
        with self.lock:
            try:
                del self.dbs[h]
            except (IndexError, KeyError):  # if not there, not a problem...
                pass
        
        # And remove the files of this database
        p = os.path.join(self.ttldb_dir, '%d' % h)
        logger.log("Deleting ttl database tree", p)
        shutil.rmtree(p, ignore_errors=True)
    
    
    # Look at the available dbs and clean all olds dbs that time are lower
    # than current hour
    def clean_old(self):
        from .kv import kvmgr  # avoid recursive import
        
        logger.debug("TTL clean old")
        now = NOW.now + 3600
        h = divmod(now, 3600)[0] * 3600
        # Look at the databses directory that have the hour time set
        subdirs = os.listdir(self.ttldb_dir)
        
        for d in subdirs:
            try:
                bhour = int(d)
            except ValueError:  # who add a dir that is not a int here...
                continue
            # Is the hour available for cleaning?
            if bhour < h:
                logger.log("TTL bhour is too low!", bhour)
                # take the database and dump all keys in it
                cdb = self.get_ttl_db(bhour)
                to_del = cdb.RangeIter()
                # Now ask the cluster to delete the key, whatever it is
                for (k, v) in to_del:
                    kvmgr.delete(k)
                
                # now we clean all old entries, remove the idx database
                self.drop_db(bhour)
    
    
    # Thread that will manage the delete of the ttld-die key
    def ttl_cleaning_thread(self):
        while not stopper.is_stop():
            time.sleep(5)
            self.clean_old()
