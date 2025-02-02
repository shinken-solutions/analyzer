#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import sys
import json
import time
import itertools

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger, sprintf
from opsbro.library import libstore
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, put_opsbro_json, wait_for_agent_started
from opsbro.cli_display import print_h1
from opsbro.threadmgr import threader

NO_ZONE_DEFAULT = '(no zone)'


############# ********************        MEMBERS management          ****************###########

def do_members(detail=False):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        members = get_opsbro_json('/agent/members').values()
    except get_request_errors(), exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    members = sorted(members, key=lambda e: e['name'])
    pprint = libstore.get_pprint()
    logger.debug('Raw members: %s' % (pprint.pformat(members)))
    # If there is a display_name, use it
    max_name_size = max([max(len(m['name']), len(m.get('display_name', '')) + 4) for m in members])
    max_addr_size = max([len(m['addr']) + len(str(m['port'])) + 1 for m in members])
    zones = set()
    for m in members:
        mzone = m.get('zone', '')
        if mzone == '':
            mzone = NO_ZONE_DEFAULT
        m['zone'] = mzone  # be sure to fix broken zones
        zones.add(mzone)
    zones = list(zones)
    zones.sort()
    for z in zones:
        z_display = z
        if not z:
            z_display = NO_ZONE_DEFAULT
        z_display = z_display.ljust(15)
        title_s = '%s: %s' % (sprintf('Zone', color='yellow', end=''), sprintf(z_display, color='blue', end=''))
        print_h1(title_s, raw_title=True)
        for m in members:
            zone = m.get('zone', NO_ZONE_DEFAULT)
            if zone != z:
                continue
            name = m['name']
            if m.get('display_name', ''):
                name = '[ ' + m.get('display_name') + ' ]'
            groups = m.get('groups', [])
            port = m['port']
            addr = m['addr']
            state = m['state']
            is_proxy = m.get('is_proxy', False)
            if not detail:
                cprint('  - %s > ' % zone, color='blue', end='')
                cprint('%s  ' % name.ljust(max_name_size), color='magenta', end='')
            else:
                cprint(' %s  %s  ' % (m['uuid'], name.ljust(max_name_size)), end='')
            c = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(state, 'cyan')
            state_prefix = {'alive': CHARACTERS.check, 'dead': CHARACTERS.cross, 'suspect': CHARACTERS.double_exclamation, 'leave': CHARACTERS.arrow_bottom}.get(state, CHARACTERS.double_exclamation)
            cprint(('%s %s' % (state_prefix, state)).ljust(9), color=c, end='')  # 7 for the maximum state string + 2 for prefix
            s = ' %s:%s ' % (addr, port)
            s = s.ljust(max_addr_size + 2)  # +2 for the spaces
            cprint(s, end='')
            if is_proxy:
                cprint('proxy ', end='')
            else:
                cprint('      ', end='')
            if detail:
                cprint('%5d' % m['incarnation'])
            cprint(' %s ' % ','.join(groups))


def do_leave(nuuid=''):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    # Lookup at the localhost name first
    if not nuuid:
        try:
            (code, r) = get_opsbro_local('/agent/uuid')
        except get_request_errors(), exp:
            logger.error(exp)
            return
        nuuid = r
    try:
        (code, r) = get_opsbro_local('/agent/leave/%s' % nuuid)
    except get_request_errors(), exp:
        logger.error(exp)
        return
    
    if code != 200:
        logger.error('Node %s is missing' % nuuid)
        print r
        return
    cprint('Node %s is set to leave state' % nuuid, end='')
    cprint(': OK', color='green')


def do_join(seed=''):
    if seed == '':
        logger.error('Missing target argument. For example 192.168.0.1:6768')
        return
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        (code, r) = get_opsbro_local('/agent/join/%s' % seed)
    except get_request_errors(), exp:
        logger.error(exp)
        return
    try:
        b = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    cprint('Joining %s : ' % seed, end='')
    if b:
        cprint('OK', color='green')
    else:
        cprint('FAILED', color='red')


def do_zone_change(name=''):
    if not name:
        print "Need a zone name"
        return
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    print "Switching to zone", name
    try:
        r = put_opsbro_json('/agent/zone', name)
    except get_request_errors(), exp:
        logger.error(exp)
        return
    print_info_title('Result')
    print r


def __print_detection_spinner():
    spinners = itertools.cycle(CHARACTERS.spinners)
    start = time.time()
    for c in spinners:
        will_quit = False
        elapsed = time.time() - start
        # exit after 2.8 s (we did have 3s max)
        if elapsed > 2.8:
            will_quit = True
            elapsed = 3
        cprint('\r %s ' % c, color='blue', end='')
        cprint('UDP detection in progress. %.1fs/3s.' % (elapsed), end='')
        # As we do not print the line, be sure to display it by flushing to display
        sys.stdout.flush()
        if will_quit:
            break
        time.sleep(0.25)
    # Be sure to have a void line before the other thread print
    cprint("")


def do_detect_nodes(auto_join):
    print_h1('UDP broadcast LAN detection')
    print "Trying to detect other nodes on the network thanks to a UDP broadcast. Will last 3s."
    cprint(' * The detection scan will be ', end='')
    cprint('3s', color='magenta', end='')
    cprint(' long.')
    threader.create_and_launch(__print_detection_spinner, (), 'spinner', essential=False)
    
    # Send UDP broadcast packets from the daemon
    try:
        network_nodes = get_opsbro_json('/agent/detect')
    except get_request_errors(), exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    cprint(" * Detection is DONE")
    print_h1('Detection result')
    if len(network_nodes) == 0:
        cprint(' ERROR: ', color='red', end='')
        cprint("cannot detect (broadcast UDP) other nodes")
        sys.exit(1)
    print "Other network nodes detected on this network:"
    print '  Name                                 Zone        Address:port          Proxy    Groups'
    for node in network_nodes:
        print '  %-35s  %-10s  %s:%d  %5s     %s' % (node['name'], node['zone'], node['addr'], node['port'], node['is_proxy'], ','.join(node['groups']))
    if not auto_join:
        cprint('NOTICE: ', color='blue', end='')
        cprint("Auto join (--auto-join) is not enabled, so don't try to join theses nodes")
        return
    # try to join theses nodes so :)
    all_proxys = [node for node in network_nodes if node['is_proxy']]
    not_proxys = [node for node in network_nodes if not node['is_proxy']]
    if all_proxys:
        node = all_proxys.pop()
        print "A proxy node is detected, using it: %s (%s:%d)" % (node['name'], node['addr'], node['port'])
        to_connect = '%s:%d' % (node['addr'], node['port'])
    else:
        node = not_proxys.pop()
        print "No proxy node detected. Using a standard one: %s (%s:%d)" % (node['name'], node['addr'], node['port'])
        to_connect = '%s:%d' % (node['addr'], node['port'])
    do_join(to_connect)


exports = {
    do_members     : {
        'keywords'   : ['gossip', 'members'],
        'args'       : [
            {'name': '--detail', 'type': 'bool', 'default': False, 'description': 'Show detail mode for the cluster members'},
        ],
        'description': 'List the cluster members'
    },
    
    do_join        : {
        'keywords'   : ['gossip', 'join'],
        'description': 'Join another node cluster',
        'args'       : [
            {'name': 'seed', 'default': '', 'description': 'Other node to join. For example 192.168.0.1:6768'},
        ],
    },
    
    do_leave       : {
        'keywords'   : ['gossip', 'leave'],
        'description': 'Put in leave a cluster node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'UUID of the node to force leave. If void, leave our local node'},
        ],
    },
    
    do_zone_change : {
        'keywords'   : ['gossip', 'zone', 'change'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Change to the zone'},
        ],
        'description': 'Change the zone of the node'
    },
    
    do_detect_nodes: {
        'keywords'   : ['gossip', 'detect'],
        'args'       : [
            {'name': '--auto-join', 'default': False, 'description': 'Try to join the first detected proxy node. If no proxy is founded, join the first one.', 'type': 'bool'},
        ],
        'description': 'Try to detect (broadcast) others nodes in the network'
    },
    
}
