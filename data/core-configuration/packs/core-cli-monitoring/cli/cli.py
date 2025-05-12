#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import time
import sys

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local
from opsbro.cli_display import print_h1, print_h2
from opsbro.monitoring import STATE_ID_COLORS
from opsbro.jsonmgr import jsoner

NO_ZONE_DEFAULT = '(no zone)'

STATE_ID_STRINGS = {0: '%s OK' % CHARACTERS.check, 2: '%s CRITICAL' % CHARACTERS.cross, 1: '%s WARNING' % CHARACTERS.double_exclamation, 3: '%s UNKNOWN' % CHARACTERS.double_exclamation}


def do_state(name=''):
    uri = '/monitoring/state/%s' % name
    if not name:
        uri = '/monitoring/state'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        d = jsoner.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    services = d['services']
    print_h1('Services')
    if len(services) == 0:
        cprint('No services', color='grey')
    else:
        for (sname, service) in services.items():
            state = service['state_id']
            cprint('\t%s ' % sname.ljust(20), end='')
            c = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}.get(state, 'cyan')
            state = {0: 'OK', 2: 'CRITICAL', 1: 'WARNING', 3: 'UNKNOWN'}.get(state, 'UNKNOWN')
            cprint('%s - ' % state.ljust(8), color=c, end='')
            output = service['check']['output']
            cprint(output.strip(), color='grey')
    
    checks = d['checks']
    if len(checks) == 0:
        cprint('No checks', color='grey')
        return  # nothing to do more
    
    print_h1('Checks')
    packs = {}
    for (cname, check) in checks.items():
        pack_name = check['pack_name']
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][cname] = check
    pnames = list(packs.keys())
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        cprint('* Pack %s' % pname, color='blue')
        cnames = list(pack_entries.keys())
        cnames.sort()
        for cname in cnames:
            check = pack_entries[cname]
            check_display_name = check['display_name']
            
            cprint('  - %s' % pname, color='blue', end='')
            cprint(' > checks > ', color='grey', end='')
            cprint('%s ' % (check_display_name.ljust(30)), color='magenta', end='')
            
            state = check['state_id']
            c = STATE_ID_COLORS.get(state, 'cyan')
            state = STATE_ID_STRINGS.get(state, 'UNKNOWN')
            cprint('%s' % state.ljust(10), color=c)
            # Now print output the line under
            output = check['output']
            output_lines = output.strip().splitlines()
            for line in output_lines:
                cprint(' ' * 4 + '| ' + line, color='grey')


def do_history():
    uri = '/monitoring/history/checks'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        history_entries = jsoner.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    print_h1('History')
    for history_entry in history_entries:
        epoch_date = history_entry['date']
        entries = history_entry['entries']
        print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch_date)))
        for entry in entries:
            pname = entry['pack_name']
            
            check_display_name = entry['display_name']
            
            cprint('  - %s' % pname, color='blue', end='')
            cprint(' > checks > ', color='grey', end='')
            cprint('%s ' % (check_display_name.ljust(30)), color='magenta', end='')
            
            old_state = entry['old_state_id']
            c = STATE_ID_COLORS.get(old_state, 'cyan')
            old_state = STATE_ID_STRINGS.get(old_state, 'UNKNOWN')
            cprint('%s' % old_state.ljust(10), color=c, end='')
            
            cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
            
            state = entry['state_id']
            c = STATE_ID_COLORS.get(state, 'cyan')
            state = STATE_ID_STRINGS.get(state, 'UNKNOWN')
            cprint('%s' % state.ljust(10), color=c)
            
            # Now print output the line under
            output = entry['output']
            output_lines = output.strip().splitlines()
            for line in output_lines:
                cprint(' ' * 4 + '| ' + line, color='grey')


def do_wait_ok(check_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    name = check_name
    
    state_string = 'UNKNOWN'
    for i in range(timeout):
        
        uri = '/monitoring/state'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        try:
            states = jsoner.loads(r)
        except ValueError as exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        checks = states['checks']
        check = None
        for (cname, c) in checks.items():
            if c['display_name'] == name:
                check = c
        if not check:
            logger.error("Cannot find the check '%s'" % name)
            sys.exit(2)
        state_id = check['state_id']
        
        c = STATE_ID_COLORS.get(state_id, 'cyan')
        state_string = STATE_ID_STRINGS.get(state_id, 'UNKNOWN')
        
        cprint('\r %s ' % next(spinners), color='blue', end='')
        cprint('%s' % name, color='magenta', end='')
        cprint(' is ', end='')
        cprint('%s' % state_string.ljust(10), color=c, end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        if state_id == 0:
            cprint("\nThe check %s is OK" % name)
            sys.exit(0)
        logger.debug("Current state %s" % state_id)
        
        time.sleep(1)
    cprint("\nThe check %s is not OK after %s seconds (currently %s)" % (name, timeout, state_string))
    sys.exit(2)


exports = {
    do_state  : {
        'keywords'             : ['monitoring', 'state'],
        'description'          : 'Print the monitoring state of a node',
        'args'                 : [
            {'name'       : 'name', 'default': '',
             'description': 'Name of the node to print state. If void, take our localhost one'},
        ],
        'allow_temporary_agent': {'enabled': True, },
    },
    
    do_history: {
        'keywords'             : ['monitoring', 'history'],
        'description'          : 'Print the history of the monitoring',
        'args'                 : [],
        'allow_temporary_agent': {'enabled': True, },
    },
    
    do_wait_ok: {
        'keywords'             : ['monitoring', 'wait-ok'],
        'args'                 : [
            {'name': 'check-name', 'description': 'Name of the check to wait for OK state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the check rule is in OK state'
    },
}
