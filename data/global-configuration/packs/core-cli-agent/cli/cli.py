#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import sys
import base64
import uuid
import time
import os

if os.name == 'nt':
    import win32serviceutil
    import win32api
    from opsbro.windows_service.windows_service import Service

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.launcher import Launcher
from opsbro.unixclient import request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, print_2tab, CONFIG
from opsbro.cli_display import print_h1
from opsbro.defaultpaths import DEFAULT_LOCK_PATH
from opsbro.configurationmanager import configmgr

NO_ZONE_DEFAULT = '(no zone)'


############# ********************        MEMBERS management          ****************###########



def __call_service_handler():
    def __ctrlHandler(ctrlType):
        return True
    
    
    win32api.SetConsoleCtrlHandler(__ctrlHandler, True)
    win32serviceutil.HandleCommandLine(Service)


def do_service_install():
    # hack argv for the install
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'install']
    __call_service_handler()


def do_service_remove():
    # hack argv for the remove
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'remove']
    __call_service_handler()


def do_info(show_logs):
    try:
        d = get_opsbro_json('/agent/info')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    logs = d.get('logs')
    version = d.get('version')
    pid = d.get('pid')
    name = d.get('name')
    display_name = d.get('display_name', '')
    # A failback to display name is the name (hostname)
    if not display_name:
        display_name = name
    else:  # show it's a display name
        display_name = '[ ' + display_name + ' ]'
    port = d.get('port')
    addr = d.get('addr')
    zone = d.get('zone')
    zone_color = 'green'
    if not zone:
        zone = NO_ZONE_DEFAULT
        zone_color = 'red'
    zone_value = {'value': zone, 'color': zone_color}
    nb_threads = d.get('threads')['nb_threads']
    httpservers = d.get('httpservers', {'internal': None, 'external': None})
    socket_path = d.get('socket')
    _uuid = d.get('uuid')
    graphite = d.get('graphite')
    statsd = d.get('statsd')
    websocket = d.get('websocket')
    dns = d.get('dns')
    # Get groups as sorted
    groups = d.get('groups')
    groups.sort()
    groups = ','.join(groups)
    _docker = d.get('docker')
    collectors = d.get('collectors')
    
    e = [('name', name), ('display name', display_name), ('uuid', _uuid), ('groups', groups), ('version', version), ('pid', pid), ('port', port), ('addr', addr),
         ('zone', zone_value), ('socket', socket_path), ('threads', nb_threads)]
    
    # Normal agent information
    print_info_title('OpsBro Daemon')
    print_2tab(e)
    
    # Normal agent information
    int_server = httpservers.get('external', None)
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (LAN)')
        print_2tab(e)
    else:
        print_info_title('HTTP (LAN) info not available')
    
    # Unix socket http daemon
    int_server = httpservers.get('internal', None)
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (Unix Socket)')
        print_2tab(e)
    else:
        print_info_title('HTTP (Unix Socket) info not available')
    
    # Now DNS part
    print_info_title('DNS')
    if not dns or 'dns_configuration' not in dns:
        cprint('No dns configured')
    else:
        w = dns['dns_configuration']
        e = [('enabled', w['enabled']), ('port', w['port']), ('domain', w['domain'])]
        print_2tab(e)
    
    # Now websocket part
    print_info_title('Websocket')
    if not websocket or 'websocket_configuration' not in websocket:
        cprint('No websocket configured')
    else:
        w = websocket['websocket_configuration']
        st = websocket.get('websocket_info', None)
        e = [('enabled', w['enabled']), ('port', w['port'])]
        if st:
            e.append(('Nb connexions', st.get('nb_connexions')))
        print_2tab(e)
    
    # Now graphite part
    print_info_title('Graphite')
    if not graphite or 'graphite_configuration' not in graphite:
        cprint('No graphite configured')
    else:
        g = graphite['graphite_configuration']
        e = [('enabled', g['enabled']), ('port', g['port']), ('udp', g['udp']), ('tcp', g['tcp'])]
        print_2tab(e)
    
    # Now statsd part
    print_info_title('Statsd')
    if not statsd or 'statsd_configuration' not in statsd:
        cprint('No statsd configured')
    else:
        s = statsd['statsd_configuration']
        e = [('enabled', s['enabled']), ('port', s['port']), ('interval', s['interval'])]
        print_2tab(e)
    
    # Now collectors part
    print_info_title('Collectors')
    cnames = collectors.keys()
    cnames.sort()
    e = []
    for cname in cnames:
        v = collectors[cname]
        color = 'green'
        if not v['active']:
            color = 'grey'
        e.append((cname, {'value': v['active'], 'color': color}))
    print_2tab(e, capitalize=False)
    
    # Now statsd part
    print_info_title('Docker')
    _d = _docker
    if _d['connected']:
        e = [('enabled', _d['enabled']), ('connected', _d['connected']),
             ('version', _d['version']), ('api', _d['api']),
             ('containers', len(_d['containers'])),
             ('images', len(_d['images'])),
             ]
    else:
        e = [
            ('enabled', {'value': _d['enabled'], 'color': 'grey'}),
            ('connected', {'value': _d['connected'], 'color': 'grey'}),
        ]
    
    print_2tab(e)
    
    # Show errors logs if any
    print_info_title('Logs')
    errors = logs.get('ERROR')
    warnings = logs.get('WARNING')
    
    # Put warning and errors in red/yellow if need only
    e = []
    if len(errors) > 0:
        e.append(('error', {'value': len(errors), 'color': 'red'}))
    else:
        e.append(('error', len(errors)))
    if len(warnings) > 0:
        e.append(('warning', {'value': len(warnings), 'color': 'yellow'}))
    else:
        e.append(('warning', len(warnings)))
    
    print_2tab(e)
    
    if show_logs:
        if len(errors) > 0:
            print_info_title('Error logs')
            for s in errors:
                cprint(s, color='red')
        
        if len(warnings) > 0:
            print_info_title('Warning logs')
            for s in warnings:
                cprint(s, color='yellow')
    
    logger.debug('Raw information: %s' % d)


# Main daemon function. Currently in blocking mode only
def do_start(daemon, cfg_dir):
    cprint('Starting opsbro daemon', color='green')
    cprint('%s' % cfg_dir)
    lock_path = CONFIG.get('lock', DEFAULT_LOCK_PATH)
    l = Launcher(lock_path=lock_path, cfg_dir=cfg_dir)
    l.do_daemon_init_and_start(is_daemon=daemon)
    # Here only the last son reach this
    l.main()


def do_stop():
    try:
        (code, r) = get_opsbro_local('/stop')
    except request_errors, exp:
        logger.error(exp)
        return
    cprint(r, color='green')


def do_keygen():
    k = uuid.uuid1().hex[:16]
    cprint('UDP Encryption key: (aka encryption_key)', end='')
    cprint(base64.b64encode(k), color='green')
    print ''
    try:
        import rsa
    except ImportError:
        logger.error('Missing python-rsa module for RSA keys generation, please install it')
        return
    pubkey, privkey = rsa.newkeys(2048)
    
    print "Private RSA key (2048). (aka master_key_priv for for file mfkey.priv)"
    s_privkey = privkey.save_pkcs1()
    cprint(s_privkey, color='green')
    print ''
    print "Public RSA key (2048). (aka master_key_pub for file mfkey.pub)"
    s_pubkey = pubkey.save_pkcs1()
    cprint(s_pubkey, color='green')
    print ''


# Sort threads by user time, if same, sort by name
def _sort_threads(t1, t2):
    t1_cpu = t1['user_time']
    t2_cpu = t2['user_time']
    t1_name = t1['name']
    t2_name = t2['name']
    if t1_cpu == t2_cpu:
        return cmp(t1_name, t2_name)
    else:  # bigger first
        return -cmp(t1_cpu, t2_cpu)


def __get_cpu_time_percent_display(t, age):
    thread_user = t['user_time']
    thread_system = t['system_time']
    if thread_system == -1 or thread_user == -1:
        return ('unknown', 'unknown')
    if age == 0:
        return ('unknown', 'unknown')
    # ok we are good :)
    return ('%.2f' % (100 * thread_user / age), '%.3f' % (100 * thread_system / age))


def do_show_threads():
    try:
        data = get_opsbro_json('/threads/')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    all_threads = data['threads']
    process = data['process']
    age = data['age']
    
    # Cut the threads into 2 lists: always here, and the others
    all_daemon_threads = [t for t in all_threads if t['essential']]
    all_not_daemon_threads = [t for t in all_threads if not t['essential']]
    
    # Put essential ones into part
    threads_into_parts = {}
    for t in all_daemon_threads:
        part = t['part'].capitalize()
        if not t:
            part = '(unknown)'
        if part not in threads_into_parts:
            threads_into_parts[part] = {'name': part, 'user_time': 0.0, 'system_time': 0.0, 'threads': []}
        e = threads_into_parts[part]
        e['user_time'] += t['user_time']
        e['system_time'] += t['system_time']
        e['threads'].append(t)
    
    # Sort threads inside the parts
    for (pname, e) in threads_into_parts.iteritems():
        e['threads'].sort(_sort_threads)
    
    # Now have parts sort by their times (from bigger to min)
    parts_sorts_by_cpu_usage = threads_into_parts.values()
    parts_sorts_by_cpu_usage = sorted(parts_sorts_by_cpu_usage, key=lambda e: -e['user_time'])
    
    # Then by name
    parts_sorts_by_name = threads_into_parts.values()
    parts_sorts_by_name = sorted(parts_sorts_by_name, key=lambda e: e['name'])
    
    all_daemon_threads.sort(_sort_threads)
    
    all_not_daemon_threads.sort(_sort_threads)
    upercent, syspercent = __get_cpu_time_percent_display(process, age)
    cprint('Total process CPU consumption:  ', color='blue', end='')
    cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
    cprint('cpu(system):%s%%' % syspercent)
    print "\n"
    
    print "Summary of CPU consumption based on opsbro parts:"
    for p in parts_sorts_by_cpu_usage:
        upercent, syspercent = __get_cpu_time_percent_display(p, age)
        cprint('  * [ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ', end='')
        cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
        cprint('cpu(system):%s%%' % syspercent)
    print ""
    print "Daemon threads (persistent):"
    for p in parts_sorts_by_name:
        cprint('[ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ')
        for t in p['threads']:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            print '   * %-55s  thread id:%5d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent)
    if all_not_daemon_threads:
        print "\nTemporary threads:"
        for t in all_not_daemon_threads:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            print '   Name:%-55s  id:%d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent)


def do_list_follow_log():
    try:
        parts = get_opsbro_json('/log/parts/')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    parts.sort()
    print "Available parts to follow logs:"
    for p in parts:
        print "  * %s" % p


def do_follow_log(part=''):
    if not part:
        return
    try:
        import fcntl
    except ImportError:
        print "Error: this action is not availabe on your OS."
        return
    
    print 'Try to follow log part %s' % part
    p = '/tmp/opsbro-follow-%s' % part
    
    # Clean fifo to be sure to clean previous runs
    if os.path.exists(p):
        os.unlink(p)
    
    if not os.path.exists(p):
        os.mkfifo(p)
    
    colors = {'DEBUG': 'magenta', 'INFO': 'blue', 'WARNING': 'yellow', 'ERROR': 'red'}
    try:
        w = 0.001
        while True:
            with open(p, 'rb', 0) as fifo:
                fd = fifo.fileno()
                flag = fcntl.fcntl(fd, fcntl.F_GETFD)
                fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
                while True:
                    try:
                        data = fifo.read()
                    except IOError:
                        w *= 2
                        w = min(w, 0.1)
                        time.sleep(w)
                        continue
                    if len(data) == 0:
                        break
                    w = 0.001
                    for line in data.splitlines():
                        already_print = False
                        for (k, color) in colors.iteritems():
                            if k in line:
                                cprint(line, color=color)
                                already_print = True
                                break
                        if not already_print:
                            print line
    finally:
        try:
            print "\nDisabling log dumping for the part %s" % part
            os.unlink(p)
        except:
            pass


def do_agent_parameters_show():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
    # print "Local parameters", parameters_from_local_configuration
    print_h1('Local agent parameters')
    key_names = parameters_from_local_configuration.keys()
    key_names.sort()
    for k in key_names:
        v = parameters_from_local_configuration[k]
        cprint('  * ', end='')
        cprint('%-15s' % k, color='magenta', end='')
        cprint(' %s ' % CHARACTERS.arrow_left, end='')
        cprint('%s\n' % v, color='green', end='')


exports = {
    
    do_start                : {
        'keywords'   : ['agent', 'start'],
        'args'       : [
            {'name': '--daemon', 'type': 'bool', 'default': False, 'description': 'Start opsbro into the background'},
            {'name': '--cfg-dir', 'default': '/etc/opsbro', 'description': 'Set a specifc configuration file'},
        ],
        'description': 'Start the opsbro daemon'
    },
    
    do_stop                 : {
        'keywords'   : ['agent', 'stop'],
        'args'       : [],
        'description': 'Stop the opsbro daemon'
    },
    
    do_service_install      : {
        'keywords'   : ['agent', 'windows', 'service-install'],
        'args'       : [],
        'description': 'Install windows service'
    },
    
    do_service_remove       : {
        'keywords'   : ['agent', 'windows', 'service-remove'],
        'args'       : [],
        'description': 'Remove windows service'
    },
    
    do_info                 : {
        'keywords'   : ['agent', 'info'],
        'args'       : [
            {'name': '--show-logs', 'default': False, 'description': 'Dump last warning & error logs', 'type': 'bool'},
        ],
        'description': 'Show info af a daemon'
    },
    
    do_keygen               : {
        'keywords'   : ['agent', 'keygen'],
        'args'       : [],
        'description': 'Generate a encryption key'
    },
    
    do_show_threads         : {
        'keywords'   : ['agent', 'internal', 'show-threads'],
        'args'       : [],
        'description': 'List all internal threads of the agent.'
    },
    
    do_follow_log           : {
        'keywords'   : ['agent', 'log', 'follow'],
        'args'       : [
            {'name': 'part', 'default': '', 'description': 'Follow log part (with debug)'},
        ],
        'description': 'Show info af a daemon'
    },
    
    do_list_follow_log      : {
        'keywords'   : ['agent', 'log', 'list'],
        'args'       : [
        ],
        'description': 'List available logs parts to follow'
    },
    
    do_agent_parameters_show: {
        'keywords'   : ['agent', 'parameters', 'show'],
        'args'       : [
        ],
        'description': 'Show the agent parameters (pid, ...)'
    },
}
