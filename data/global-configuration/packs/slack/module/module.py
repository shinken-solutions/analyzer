import time
import os

from slacker import Slacker

from opsbro.module import HandlerModule
from opsbro.gossip import gossiper
from opsbro.parameters import StringParameter, StringListParameter
from opsbro.compliancemgr import COMPLIANCE_STATE_COLORS


class SlackHandlerModule(HandlerModule):
    implement = 'slack'
    
    parameters = {
        'enabled_if_group': StringParameter(default='slack'),
        'severities'      : StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'token'           : StringParameter(default=''),
        'channel'         : StringParameter(default='#alerts'),
    }
    
    
    def __init__(self):
        super(SlackHandlerModule, self).__init__()
        self.enabled = False
    
    
    def prepare(self):
        if_group = self.get_parameter('enabled_if_group')
        self.enabled = gossiper.is_in_group(if_group)
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}
    
    
    def __try_to_send_message(self, slack, attachments, channel):
        r = slack.chat.post_message(channel=channel, text='', as_user=True, attachments=attachments)
        self.logger.debug('[SLACK] return of the send: %s %s %s' % (r.successful, r.__dict__['body']['channel'], r.__dict__['body']['ts']))
    
    
    def __get_token(self):
        token = self.get_parameter('token')
        if not token:
            token = os.environ.get('SLACK_TOKEN', '')
        return token
    
    
    def __send_slack_check(self, check):
        token = self.__get_token()
        
        if not token:
            self.logger.error('[SLACK] token is not configured on the slack module. skipping slack messages.')
            return
        slack = Slacker(token)
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = check['output']
        channel = self.get_parameter('channel')
        colors = {'ok': 'good', 'warning': 'warning', 'critical': 'danger'}
        node_name = '%s (%s)' % (gossiper.name, gossiper.addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        attachment = {"pretext": ' ', "text": content, 'color': colors.get(check['state'], '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        fields = [
            {"title": "Node", "value": node_name, "short": True},
            {"title": "Check", "value": check['name'], "short": True},
        ]
        attachment['fields'] = fields
        attachments = [attachment]
        self.__do_send_message(slack, attachments, channel)
    
    
    def __send_slack_group(self, group, group_modification):
        token = self.__get_token()
        
        if not token:
            self.logger.error('[SLACK] token is not configured on the slack module. skipping slack messages.')
            return
        slack = Slacker(token)
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = 'The group %s was %s' % (group, group_modification)
        channel = self.get_parameter('channel')
        colors = {'remove': 'danger', 'add': 'good'}
        node_name = '%s (%s)' % (gossiper.name, gossiper.addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        attachment = {"pretext": ' ', "text": content, 'color': colors.get(group_modification, '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        fields = [
            {"title": "Node", "value": node_name, "short": True},
            {"title": "Group:%s" % group_modification, "value": group, "short": True},
        ]
        attachment['fields'] = fields
        attachments = [attachment]
        self.__do_send_message(slack, attachments, channel)
    
    
    def __send_slack_compliance(self, compliance):
        token = self.__get_token()
        
        if not token:
            self.logger.error('[SLACK] token is not configured on the slack module. skipping slack messages.')
            return
        slack = Slacker(token)
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = 'The compliance %s changed from %s to %s' % (compliance.get_name(), compliance.get_state(), compliance.get_old_state())
        channel = self.get_parameter('channel')
        state_color = COMPLIANCE_STATE_COLORS.get(compliance.get_state())
        color = {'magenta': '#221220', 'green': 'good', 'cyan': '#cde6ff', 'red': 'danger', 'grey': '#cccccc'}.get(state_color, '#cccccc')
        node_name = '%s (%s)' % (gossiper.name, gossiper.addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        attachment = {"pretext": ' ', "text": content, 'color': color, 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        fields = [
            {"title": "Node", "value": node_name, "short": True},
            {"title": "Compliance:%s" % compliance.get_name(), "value": compliance.get_state(), "short": True},
        ]
        attachment['fields'] = fields
        attachments = [attachment]
        self.__do_send_message(slack, attachments, channel)
    
    
    def __do_send_message(self, slack, attachments, channel):
        try:
            self.__try_to_send_message(slack, attachments, channel)
        except Exception as exp:
            self.logger.error('[SLACK] Cannot send alert: %s (%s) %s %s %s' % (exp, type(exp), str(exp), str(exp) == 'channel_not_found', exp.__dict__))
            # If it's just that the channel do not exists, try to create it
            if str(exp) == 'channel_not_found':
                try:
                    self.logger.info('[SLACK] Channel %s do no exists. Trying to create it.' % channel)
                    slack.channels.create(channel)
                except Exception as exp:
                    self.logger.error('[SLACK] Cannot create channel %s: %s' % (channel, exp))
                    return
                # Now try to resend the message
                try:
                    self.__try_to_send_message(slack, attachments, channel)
                except Exception as exp:
                    self.logger.error('[SLACK] Did create channel %s but we still cannot send the message: %s' % (channel, exp))
    
    
    def handle(self, obj, event):
        if_group = self.get_parameter('enabled_if_group')
        self.enabled = gossiper.is_in_group(if_group)
        if not self.enabled:
            self.logger.debug('Slack module is not enabled, skipping check alert sent')
            return
        
        self.logger.debug('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.__send_slack_check(obj)
        
        if evt_type == 'group_change':
            evt_data = event['evt_data']
            group_modification = evt_data['modification']
            self.__send_slack_group(obj, group_modification)
        
        # Compliance: only when change, and only some switch cases should be
        # notify (drop useless changes)
        if evt_type == 'compliance_execution':
            evt_data = event['evt_data']
            compliance_did_change = evt_data['compliance_did_change']
            if compliance_did_change:
                self.__send_slack_compliance(obj)
