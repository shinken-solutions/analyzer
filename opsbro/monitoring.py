import re
import os
import tempfile
import shutil
import copy
import time
import random
import socket
import hashlib

from .log import LoggerFactory
from .gossip import gossiper
from .kv import kvmgr
from .stop import stopper
from .threadmgr import threader
from .perfdata import PerfDatas
from .evaluater import evaluater
from .ts import tsmgr
from .handlermgr import handlermgr
from .topic import topiker, TOPIC_MONITORING
from .basemanager import BaseManager
from .jsonmgr import jsoner
from .util import exec_command

# Global logger for this part
logger = LoggerFactory.create_logger('monitoring')

CHECK_STATES = ['ok', 'warning', 'critical', 'unknown', 'pending']
STATE_ID_COLORS = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}
STATE_COLORS = {'ok': 'green', 'warning': 'yellow', 'critical': 'red', 'unknown': 'grey', 'pending': 'grey'}


class MonitoringManager(BaseManager):
    history_directory_suffix = 'monitoring'
    
    
    def __init__(self):
        super(MonitoringManager, self).__init__()
        self.logger = logger
        
        self.checks = {}
        self.services = {}
        
        # keep a list of the checks names that match our groups
        self.active_checks = []
        
        # Compile the macro pattern once
        self.macro_pat = re.compile(r'(\$ *(.*?) *\$)+')
    
    
    def load(self, cfg_dir, cfg_data):
        self.cfg_dir = cfg_dir
        self.cfg_data = cfg_data
    
    
    # Load and sanatize a check object in our configuration
    def import_check(self, check, fr, name, mod_time=0, service='', pack_name='', pack_level=''):
        check['from'] = fr
        check['pack_name'] = pack_name
        check['pack_level'] = pack_level
        check['id'] = check['name'] = name
        defaults_ = {'interval'       : '10s', 'script': '', 'ok_output': '', 'critical_if': '',
                     'critical_output': '', 'warning_if': '', 'warning_output': '', 'last_check': 0,
                     'notes'          : ''}
        for (k, v) in defaults_.items():
            if k not in check:
                check[k] = v
        if service:
            check['service'] = service
        if 'if_group' not in check:
            # we take the basename of this check directory for the if_group
            # and if /, take *  (aka means all)
            if_group = os.path.basename(os.path.dirname(name))
            if not if_group:
                if_group = '*'
            check['if_group'] = if_group
        if 'display_name' in check:
            check['display_name'] = '[%s]' % check.get('display_name')
        else:
            check['display_name'] = name.split('/')[-1]
        check['modification_time'] = mod_time
        check['state'] = 'pending'
        check['state_id'] = 3
        check['old_state'] = 'pending'
        check['old_state_id'] = 3
        check['output'] = ''
        check['variables'] = check.get('variables', {})
        check['computed_variables'] = {}
        self.checks[check['id']] = check
    
    
    # We have a new check from the HTTP, save it where it need to be
    def delete_check(self, cname):
        p = os.path.normpath(os.path.join(self.cfg_dir, cname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        # clean on disk
        if os.path.exists(p):
            os.unlink(p)
        # Now clean in memory too
        if cname in self.checks:
            del self.checks[cname]
        self.link_checks()
    
    
    # We have a new check from the HTTP, save it where it need to be
    def save_check(self, cname, check):
        p = os.path.normpath(os.path.join(self.cfg_dir, cname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        
        # Look if the file directory exists or if not cannot be created
        p_dir = os.path.dirname(p)
        if not os.path.exists(p_dir):
            os.makedirs(p_dir)
        
        # import a copy, so we don't mess with the fields we need to save
        to_import = copy.copy(check)
        # Now import it in our running part
        self.import_check(to_import, 'from:http', cname)
        # and put the new one in the active running checks, maybe
        self.link_checks()
        
        # Now we can save the received entry, but first clean unless props
        to_remove = ['from', 'last_check', 'modification_time', 'state', 'output', 'state_id', 'id', 'old_state', 'old_state_id']
        for prop in to_remove:
            try:
                del check[prop]
            except KeyError:
                pass
        
        o = {'check': check}
        logger.debug('HTTP check saving the object %s into the file %s' % (o, p))
        buf = jsoner.dumps(o, sort_keys=True, indent=4)
        tempdir = tempfile.mkdtemp()
        f = open(os.path.join(tempdir, 'temp.json'), 'w')
        f.write(buf)
        f.close()
        shutil.move(os.path.join(tempdir, 'temp.json'), p)
        shutil.rmtree(tempdir)
    
    
    def import_service(self, service, fr, sname, mod_time=0, pack_name='', pack_level=''):
        service['from'] = fr
        service['pack_name'] = pack_name
        service['pack_level'] = pack_level
        service['name'] = service['id'] = sname
        if 'notes' not in service:
            service['notes'] = ''
        if 'if_group' not in service:
            # we take the basename of this check directory for the if_group
            # and if /, take the service name
            if_group = os.path.basename(os.path.dirname(sname))
            if not if_group:
                if_group = service['name']
            service['if_group'] = service['name']
        if_group = service['if_group']
        if 'check' in service:
            check = service['check']
            cname = 'service:%s' % sname
            # for the same if_group of the check as ourself
            check['if_group'] = if_group
            self.import_check(check, fr, cname, mod_time=mod_time, service=service['id'], pack_name=pack_name, pack_level=pack_level)
        
        # Put the default state to unknown, retention will load
        # the old data
        service['state_id'] = 3
        service['modification_time'] = mod_time
        service['incarnation'] = 0
        
        # Add it into the services list
        self.services[service['id']] = service
    
    
    def load_check_retention(self, check_retention):
        if not os.path.exists(check_retention):
            return
        
        logger.log('CHECK loading check retention file %s' % check_retention)
        with open(check_retention, 'r') as f:
            loaded = jsoner.loads(f.read())
            for (cid, c) in loaded.items():
                if cid in self.checks:
                    check = self.checks[cid]
                    to_load = ['last_check', 'output', 'state', 'state_id', 'old_state', 'old_state_id']
                    for prop in to_load:
                        check[prop] = c[prop]
    
    
    def load_service_retention(self, service_retention):
        if not os.path.exists(service_retention):
            return
        
        logger.log('Service loading service retention file %s' % service_retention)
        with open(service_retention, 'r') as f:
            loaded = jsoner.loads(f.read())
            for (cid, c) in loaded.items():
                if cid in self.services:
                    service = self.services[cid]
                    to_load = ['state_id', 'incarnation']
                    for prop in to_load:
                        service[prop] = c[prop]
    
    
    # We have a new service from the HTTP, save it where it need to be
    def save_service(self, sname, service):
        p = os.path.normpath(os.path.join(self.cfg_dir, sname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        
        # Look if the file directory exists or if not cannot be created
        p_dir = os.path.dirname(p)
        if not os.path.exists(p_dir):
            os.makedirs(p_dir)
        
        # import a copy, so we dont mess with the fieldsweneed to save
        to_import = copy.copy(service)
        # Now import it in our running part
        self.import_service(to_import, 'from:http', sname)
        # and put the new one in the active running checks, maybe
        self.link_services()
        
        # We maybe got a new service, so export this data to every one in the gossip way :)
        gossiper.increase_incarnation_and_broadcast()
        
        # Now we can save the received entry, but first clean unless props
        to_remove = ['from', 'last_check', 'modification_time', 'state', 'output', 'state_id', 'id']
        for prop in to_remove:
            try:
                del service[prop]
            except KeyError:
                pass
        
        o = {'service': service}
        logger.debug('HTTP service saving the object %s into the file %s' % (o, p))
        buf = jsoner.dumps(o, sort_keys=True, indent=4)
        tempdir = tempfile.mkdtemp()
        f = open(os.path.join(tempdir, 'temp.json'), 'w')
        f.write(buf)
        f.close()
        shutil.move(os.path.join(tempdir, 'temp.json'), p)
        shutil.rmtree(tempdir)
    
    
    # We have a new check from the HTTP, save it where it need to be
    def delete_service(self, sname):
        p = os.path.normpath(os.path.join(self.cfg_dir, sname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        # clean on disk
        if os.path.exists(p):
            os.unlink(p)
        # Now clean in memory too
        if sname in self.services:
            del self.services[sname]
        self.link_services()
        # We maybe got a less service, so export this data to every one in the gossip way :)
        gossiper.increase_incarnation_and_broadcast()
    
    
    # Look at our services dict and link the one we are if_group
    # so the other nodes are aware about our groups/service
    def link_services(self):
        logger.debug('LINK my services and my node entry')
        node = gossiper.get(gossiper.uuid)
        with gossiper.nodes_lock:
            groups = node['groups']
            for (sname, service) in self.services.items():
                if_group = service.get('if_group', '')
                if if_group and if_group in groups:
                    node['services'][sname] = service
    
    
    # For checks we will only populate our active_checks list
    # with the name of the checks we are if_group about
    def link_checks(self):
        logger.debug('LOOKING FOR our checks that match our groups')
        node = gossiper.get(gossiper.uuid)
        with gossiper.nodes_lock:
            groups = node['groups']
            active_checks = []
            for (cname, check) in self.checks.items():
                if_group = check.get('if_group', '*')
                if if_group == '*' or if_group in groups:
                    active_checks.append(cname)
            self.active_checks = active_checks
            # Also update our checks list in KV space
            self.update_checks_kv()
            # and in our own node object
            checks_entry = {}
            for (cname, check) in self.checks.items():
                if cname not in active_checks:
                    continue
                checks_entry[cname] = {'state_id': check['state_id']}  # by default state are unknown
            node['checks'] = checks_entry
    
    
    def __get_variables(self, check):
        variables = check['variables']
        
        # We need to evaluate our variables if there are some
        computed_variables = {}
        for (k, expr) in variables.items():
            try:
                computed_variables[k] = evaluater.eval_expr(expr)
            except Exception as exp:
                raise Exception('the variable %s expr %s did fail to evaluate: %s' % (k, expr, exp))
        return computed_variables
    
    
    # Try to find the params for a macro in the foloowing objets, in that order:
    # * check
    # * service
    # * main configuration
    def _found_params(self, m, check):
        parts = [m]
        # if we got a |, we got a default value somewhere
        if '|' in m:
            parts = m.split('|', 1)
        change_to = ''
        for p in parts:
            elts = [p]
            if '.' in p:
                elts = p.split('.')
            elts = [e.strip() for e in elts]
            
            # we will try to grok into our cfg_data for the k1.k2.k3 =>
            # self.cfg_data[k1][k2][k3] entry if exists
            d = None
            founded = False
            
            # We will look into the check>service>global order
            # but skip serviec if it's not related with the check
            sname = check.get('service', '')
            
            find_into = [check, self.cfg_data]
            if sname and sname in self.services:
                service = self.services.get(sname)
                find_into = [check, service, self.cfg_data]
            
            for tgt in find_into:
                (lfounded, ld) = self._found_params_inside(elts, tgt)
                if not lfounded:
                    continue
                if lfounded:
                    founded = True
                    d = ld
                    break
            if not founded:
                continue
            change_to = str(d)
            break
        return change_to
    
    
    # Try to found a elts= k1.k2.k3 => d[k1][k2][k3] entry
    # if exists
    def _found_params_inside(self, elts, d):
        founded = False
        for e in elts:
            if e not in d:
                founded = False
                break
            d = d[e]
            founded = True
        return (founded, d)
    
    
    # Launch a check sub-process as a thread
    def launch_check(self, check):
        # If critical_if available, try it
        critical_if = check.get('critical_if')
        warning_if = check.get('warning_if')
        rc = 3  # by default unknown state and output
        output = 'Check not configured'
        err = ''
        if critical_if or warning_if:
            b = False
            try:
                computed_variables = self.__get_variables(check)
            except Exception as exp:
                output = "ERROR: the variable expression fail: %s" % exp
                b = True
                rc = 2
                computed_variables = {}
            if critical_if:
                try:
                    b = evaluater.eval_expr(critical_if, check=check, variables=computed_variables)
                except Exception as exp:
                    output = "ERROR: the critical_if expression fail: %s : %s" % (critical_if, exp)
                    b = False
                    rc = 2
                if b:
                    output = evaluater.eval_expr(check.get('critical_output', ''), variables=computed_variables)
                    rc = 2
            if not b and warning_if:
                try:
                    b = evaluater.eval_expr(warning_if, check=check, variables=computed_variables)
                except Exception as exp:
                    output = "ERROR: the warning_if expression fail: %s : %s" % (warning_if, exp)
                    b = False
                    rc = 2
                if b:
                    output = evaluater.eval_expr(check.get('warning_output', ''), variables=computed_variables)
                    rc = 1
            # if unset, we are in OK
            if rc == 3:
                rc = 0
                try:
                    output = evaluater.eval_expr(check.get('ok_output', ''), variables=computed_variables)
                except Exception as exp:
                    output = "ERROR: the ok_output expression fail: %s : %s" % (check.get('ok_output', ''), exp)
                    rc = 2
        else:
            script = check['script']
            logger.debug("CHECK start: MACRO launching %s" % script)
            # First we need to change the script with good macros (between $$)
            it = self.macro_pat.finditer(script)
            macros = [m.groups() for m in it]
            # can be ('$ load.warning | 95$', 'load.warning | 95') for example
            for (to_repl, m) in macros:
                change_to = self._found_params(m, check)
                script = script.replace(to_repl, change_to)
            logger.debug("MACRO finally computed", script)
            
            rc, output, err = exec_command(script)
            # not found error like (127) should be catch as unknown check
            if rc > 3:
                rc = 3
        logger.debug("CHECK RETURN %s : %s %s %s" % (check['id'], rc, output, err))
        did_change = (check['state_id'] != rc)
        if did_change:
            # Then save the old state values
            check['old_state'] = check['state']
            check['old_state_id'] = check['state_id']
            
            check['state'] = {0: 'ok', 1: 'warning', 2: 'critical', 3: 'unknown'}.get(rc, 'unknown')
            if 0 <= rc <= 3:
                check['state_id'] = rc
            else:
                check['state_id'] = 3
        
        check['output'] = output + err
        check['last_check'] = int(time.time())
        self.__analyse_check(check, did_change)
        
        # Launch the handlers, some need the data if the element did change or not
        handlermgr.launch_check_handlers(check, did_change)
    
    
    def __get_history_entry_from_check(self, check):
        r = {}
        fields = ['name', 'pack_name', 'pack_level', 'output', 'last_check', 'display_name', 'state', 'state_id', 'old_state', 'old_state_id']
        for field in fields:
            r[field] = check[field]
        return r
    
    
    # get a check return and look it it did change a service state. Also save
    # the result in the __health KV
    def __analyse_check(self, check, did_change):
        logger.debug('CHECK we got a check return, deal with it for %s' % check)
        
        # if did change, update the node check entry about it
        if did_change:
            gossiper.update_check_state_id(check['name'], check['state_id'])
            # and save a history entry about it
            history_entry = self.__get_history_entry_from_check(check)
            self.add_history_entry(history_entry)
        
        # by default warn others nodes if the check did change
        warn_about_our_change = did_change
        
        # If the check is related to a service, import the result into the service
        # and look for a service state change
        sname = check.get('service', '')
        if sname and sname in self.services:
            service = self.services.get(sname)
            logger.debug('CHECK is related to a service, deal with it! %s => %s' % (check, service))
            sstate_id = service.get('state_id')
            cstate_id = check.get('state_id')
            if cstate_id != sstate_id:
                service['state_id'] = cstate_id
                logger.log('CHECK: we got a service state change from %s to %s for %s' % (sstate_id, cstate_id, service['name']))
                warn_about_our_change = True
            else:
                logger.debug('CHECK: service %s did not change (%s)' % (service['name'], sstate_id))
        
        # If our check or service did change, warn thers nodes about it
        if warn_about_our_change:
            gossiper.increase_incarnation_and_broadcast()
        
        # We finally put the result in the KV database
        self.put_check(check)
    
    
    # Save the check as a jsono object into the __health/ KV part
    def put_check(self, check):
        value = jsoner.dumps(check)
        key = '__health/%s/%s' % (gossiper.uuid, check['name'])
        logger.debug('CHECK SAVING %s:%s(len=%d)' % (key, value, len(value)))
        kvmgr.put_key(key, value, allow_udp=True)
        
        # Now groking metrics from check
        elts = check['output'].split('|', 1)
        
        try:
            perfdata = elts[1]
        except IndexError:
            perfdata = ''
        
        # if not perfdata, bail out
        if not perfdata:
            return
        
        datas = []
        cname = check['name'].replace('/', '.')
        now = int(time.time())
        perfdatas = PerfDatas(perfdata)
        for m in perfdatas:
            if m.name is None or m.value is None:
                continue  # skip this invalid perfdata
            
            logger.debug('GOT PERFDATAS', m)
            logger.debug('GOT PERFDATAS', m.name)
            logger.debug('GOT PERFDATAS', m.value)
            e = {'mname': '.'.join([gossiper.name, cname, m.name]), 'timestamp': now, 'value': m.value}
            logger.debug('PUT PERFDATA', e)
            datas.append(e)
        
        self.put_graphite_datas(datas)
    
    
    def do_update_checks_kv(self):
        logger.info("CHECK UPDATING KV checks")
        names = []
        for (cid, check) in self.checks.items():
            # Only the checks that we are really managing
            if cid in self.active_checks:
                names.append(check['name'])
                self.put_check(check)
        all_checks = jsoner.dumps(names)
        key = '__health/%s' % gossiper.uuid
        kvmgr.put_key(key, all_checks)
    
    
    # Main thread for launching checks (each with its own thread)
    def do_check_thread(self):
        # Before run, be sure we have a history directory ready
        self.prepare_history_directory()
        
        logger.log('CHECK thread launched')
        cur_launchs = {}
        while not stopper.is_stop():
            # If we are not allowed to do monitoring stuff, do nothing
            if not topiker.is_topic_enabled(TOPIC_MONITORING):
                time.sleep(1)
                continue
            now = int(time.time())
            for (cid, check) in self.checks.items():
                # maybe this chck is not a activated one for us, if so, bail out
                if cid not in self.active_checks:
                    continue
                # maybe a check is already running
                if cid in cur_launchs:
                    continue
                # else look at the time
                last_check = check['last_check']
                interval = int(check['interval'].split('s')[0])  # todo manage like it should
                # in the conf reading phase
                interval = random.randint(int(0.9 * interval), int(1.1 * interval))
                
                if last_check < now - interval:
                    # randomize a bit the checks
                    script = check['script']
                    logger.debug('CHECK: launching check %s:%s' % (cid, script))
                    t = threader.create_and_launch(self.launch_check, name='check-%s' % cid, args=(check,), part='monitoring')
                    cur_launchs[cid] = t
            
            to_del = []
            for (cid, t) in cur_launchs.items():
                if not t.is_alive():
                    t.join()
                    to_del.append(cid)
            for cid in to_del:
                del cur_launchs[cid]
            
            # each seconds we try to look if there are history info to save
            self.write_history_entry()
            
            time.sleep(1)
    
    
    # Will delete all checks into the kv and update new values, but in a thread
    def update_checks_kv(self):
        # Ok go launch it :)
        threader.create_and_launch(self.do_update_checks_kv, name='do_update_checks_kv', essential=True, part='key-values')
    
    
    # TODO: RE-factorize with the TS code part
    def put_graphite_datas(self, datas):
        forwards = {}
        for e in datas:
            mname, value, timestamp = e['mname'], e['value'], e['timestamp']
            hkey = hashlib.sha1(mname).hexdigest()
            ts_node_manager = gossiper.find_group_node('ts', hkey)
            # if it's me that manage this key, I add it in my backend
            if ts_node_manager == gossiper.uuid:
                logger.debug("I am the TS node manager")
                tsmgr.tsb.add_value(timestamp, mname, value)
            # not me? stack a forwarder
            else:
                logger.debug("The node manager for this Ts is ", ts_node_manager)
                l = forwards.get(ts_node_manager, [])
                # Transform into a graphite line
                line = '%s %s %s' % (mname, value, timestamp)
                l.append(line)
                forwards[ts_node_manager] = l
        
        for (uuid, lst) in forwards.items():
            node = gossiper.get(uuid)
            # maybe the node disapear? bail out, we are not lucky
            if node is None:
                continue
            packets = []
            # first compute the packets
            buf = ''
            for line in lst:
                buf += line + '\n'
                if len(buf) > 1024:
                    packets.append(buf)
                    buf = ''
            if buf != '':
                packets.append(buf)
            
            # UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for packet in packets:
                # do NOT use the node['port'], it's the internal communication, not the graphite one!
                sock.sendto(packet, (node['addr'], 2003))
            sock.close()
    
    
    def get_infos(self):
        counts = {}
        for state in CHECK_STATES:
            counts[state] = 0
        checks = self.checks.values()
        for check in checks:
            counts[check['state']] += 1
        return counts
    
    
    def export_http(self):
        from .httpdaemon import http_export, response, request, abort
        
        @http_export('/monitoring/state/:nuuid')
        @http_export('/monitoring/state')
        def get_state(nuuid=''):
            response.content_type = 'application/json'
            r = {'checks': {}, 'services': {}}
            # by default it's us
            # maybe its us, maybe not
            if nuuid == '' or nuuid == gossiper.uuid:
                for (cid, check) in self.checks.items():
                    # maybe this chck is not a activated one for us, if so, bail out
                    if cid not in self.active_checks:
                        continue
                    r['checks'][cid] = check
                # NOTE: we do not want services object from gossiper to be access in //
                # after we return it
                with gossiper.nodes_lock:
                    r['services'] = copy.deepcopy(gossiper.get(gossiper.uuid)['services'])
                return r
            else:  # find the elements
                node = gossiper.get(nuuid)
                if node is None:
                    return abort(404, 'This node is not found')
                # NOTE: we do not want services object from gossiper to be access in //
                # after we return it
                with gossiper.nodes_lock:
                    r['services'] = copy.deepcopy(node['services'])
                # checks are harder, we must find them in the kv nodes
                v = kvmgr.get_key('__health/%s' % node['uuid'])
                if v is None or v == '':
                    logger.error('Cannot access to the checks list for', nuuid)
                    return r
                
                lst = jsoner.loads(v)
                for cid in lst:
                    v = kvmgr.get_key('__health/%s/%s' % (node['uuid'], cid))
                    if v is None:  # missing check entry? not a real problem
                        continue
                    check = jsoner.loads(v)
                    r['checks'][cid] = check
                return r
        
        
        @http_export('/monitoring/checks')
        def agent_checks():
            response.content_type = 'application/json'
            return self.checks
        
        
        @http_export('/monitoring/checks/:cname#.+#')
        def agent_check(cname):
            response.content_type = 'application/json'
            if cname not in self.checks:
                return abort(404, 'check not found')
            return self.checks[cname]
        
        
        @http_export('/monitoring/checks/:cname#.+#', method='DELETE')
        def agent_DELETE_check(cname):
            if cname not in self.checks:
                return
            self.delete_check(cname)
            return
        
        
        @http_export('/monitoring/checks/:cname#.+#', method='PUT')
        def interface_PUT_agent_check(cname):
            value = request.body.getvalue()
            try:
                check = jsoner.loads(value)
            except ValueError:  # bad json
                return abort(400, 'Bad json entry')
            self.save_check(cname, check)
            return
        
        
        @http_export('/monitoring/services')
        def agent_services():
            response.content_type = 'application/json'
            return self.services
        
        
        @http_export('/monitoring/services/:sname#.+#')
        def agent_service(sname):
            response.content_type = 'application/json'
            if sname not in self.services:
                return abort(404, 'service not found')
            return self.services[sname]
        
        
        @http_export('/monitoring/services/:sname#.+#', method='PUT')
        def interface_PUT_agent_service(sname):
            value = request.body.getvalue()
            try:
                service = jsoner.loads(value)
            except ValueError:  # bad json
                return abort(400, 'Bad json entry')
            self.save_service(sname, service)
            return
        
        
        @http_export('/monitoring/services/:sname#.+#', method='DELETE')
        def agent_DELETE_service(sname):
            if sname not in self.services:
                return
            self.delete_service(sname)
            return
        
        
        # We want a state of all our services, with the members
        @http_export('/state/services')
        def state_services():
            response.content_type = 'application/json'
            # We don't want to modify our services objects
            services = copy.deepcopy(self.services)
            for service in services.values():
                service['members'] = []
                service['passing-members'] = []
                service['passing'] = 0
                service['failing-members'] = []
                service['failing'] = 0
            with gossiper.nodes_lock:
                for (uuid, node) in gossiper.nodes.items():
                    for (sname, service) in node['services'].items():
                        if sname not in services:
                            continue
                        services[sname]['members'].append(node['name'])
                        if service['state_id'] == 0:
                            services[sname]['passing'] += 1
                            services[sname]['passing-members'].append(node['name'])
                        else:
                            services[sname]['failing'] += 1
                            services[sname]['failing-members'].append(node['name'])
            
            return services
        
        
        # We want a state of all our services, with the members
        @http_export('/state/services/:sname')
        def state_service(sname):
            response.content_type = 'application/json'
            # We don't want to modify our services objects
            services = copy.deepcopy(self.services)
            service = services.get(sname, {})
            if not service:
                return {}
            service['members'] = []
            service['passing-members'] = []
            service['passing'] = 0
            service['failing-members'] = []
            service['failing'] = 0
            sname = service.get('name')
            with gossiper.nodes_lock:
                for (uuid, node) in gossiper.nodes.items():
                    if sname not in node['services']:
                        continue
                    service['members'].append(node['name'])
                    if service['state_id'] == 0:
                        service['passing'] += 1
                        service['passing-members'].append(node['name'])
                    else:
                        service['failing'] += 1
                        service['failing-members'].append(node['name'])
            
            return service
        
        
        @http_export('/monitoring/history/checks', method='GET')
        def get_monitoring_history_checks():
            response.content_type = 'application/json'
            r = self.get_history()
            return jsoner.dumps(r)


monitoringmgr = MonitoringManager()
