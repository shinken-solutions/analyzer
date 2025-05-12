from opsbro.evaluater import export_evaluater_function
from opsbro.gossip import gossiper

FUNCTION_GROUP = 'gossip'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_in_group(group):
    """**is_in_group(group)** -> return True if the node have the group, False otherwise.

 * group: (string) group to check.


<code>
    Example:
        is_in_group('linux')
    Returns:
        True
</code>
    """
    return gossiper.is_in_group(group)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def is_in_static_group(group):
    """**is_in_static_group(group)** -> return True if the node have the group but was set in the configuration, not from discovery False otherwise.

 * group: (string) group to check.


<code>
    Example:
        is_in_static_group('linux')
    Returns:
        True
</code>
    """
    return gossiper.is_in_group(group)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_get_zone(node_uuid=''):
    """**gossip_get_zone(node_uuid='')** -> return the zone (as string) of the node with the uuid node_uuid. If uset, get the current node.

 * node_uuid: (string) uuid of the element to get zone.


<code>
    Example:
        gossip_get_zone()
    Returns:
        'internet'
</code>
    """
    return gossiper.get_zone_from_node(node_uuid)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_count_nodes(group='', state=''):
    """**gossip_count_nodes(group='', state='')** -> return the number of known nodes that match group and state

 * group: (string) if set, count only the members of this group.
 * state: (string) if set, count only the members with this state.


<code>
    Example:
        gossip_count_nodes(group='linux', state='ALIVE')
    Returns:
        3
</code>
    """
    return gossiper.count(group=group, state=state)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def gossip_have_event_type(event_type):
    """**gossip_have_event(event_type)** -> return True if an event of event_type is present in the node

 * event_type: (string) type of event to detect.


<code>
    Example:
        gossip_have_event_type('shinken-restart')
    Returns:
        False
</code>
    """
    return gossiper.have_event_type(event_type)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def compliance_get_state_of_rule(rule_name):
    """**compliance_get_state_of_rule(rule_name)** -> return the state of the rule with the name rule_name

 * rule_name: (string) name of the rule to get. If wrong, state will be UNKNOWN.


<code>
    Example:
        compliance_get_state_of_rule('Install mongodb')
    Returns:
        'COMPLIANT'
</code>
    """
    from opsbro.compliancemgr import compliancemgr
    return compliancemgr.get_rule_state(rule_name)
