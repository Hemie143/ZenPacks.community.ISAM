
# stdlib Imports
import base64
import json
import logging

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from ZenPacks.community.DataPower.lib.utils import SkipCertifContextFactory

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

# Setup logging
log = logging.getLogger('zen.PythonISAMDevice')


class ISAMDevice(PythonDataSourcePlugin):

    proxy_attributes = (
        'zISAMUsername',
        'zISAMPassword',
        )

    urls = {
        'cpu' : 'https://{}/statistics/systems/cpu.json?timespan={}s',
        'memory': 'https://{}/statistics/systems/memory.json?timespan={}s',
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.debug('In config_key: {} - {} - {} - {}'.format(context.device().id,
                                                            datasource.getCycleTime(context),
                                                            context.id,
                                                            'ISAMDevice'))
        return (
            context.device().id,
            datasource.getCycleTime(context),
            context.id,
            'ISAMDevice',
        )

    @classmethod
    def params(cls, datasource, context):
        log.debug('Starting ISAMDevice params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ISAM Device collect')

        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        log.debug('ds: {}'.format(config.datasources))
        ds0 = config.datasources[0]
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zISAMUsername, ds0.zISAMPassword))
        authHeader = "Basic " + basicAuth.strip()
        headers = {
            "Accept": ["application/json"],
            "Authorization": [authHeader],
            "User-Agent": ["Mozilla/3.0Gold"],
        }
        agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
        results = {}
        for datasource in config.datasources:
            timespan = max(120, 2 * datasource.cycletime)
            url = self.urls[datasource.datasource].format(ip_address, timespan)
            try:
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                results[datasource.datasource] = json.loads(response_body)
            except Exception as e:
                log.error('{}: {}'.format(datasource, e))
        returnValue(results)

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))

        data = self.new_data()
        if 'cpu' in result:
            data['values'][None]['cpu_idle_cpu'] = float(result['cpu']['idle_cpu'])
            data['values'][None]['cpu_system_cpu'] = float(result['cpu']['system_cpu'])
            data['values'][None]['cpu_user_cpu'] = float(result['cpu']['user_cpu'])
            data['values'][None]['cpu_total_cpu'] = float(result['cpu']['user_cpu']) + \
                                                    float(result['cpu']['system_cpu'])
        if 'memory' in result:
            # Values are provided in MB
            data['values'][None]['memory_free'] = float(result['memory']['free']) * 1024 * 1024
            data['values'][None]['memory_used'] = float(result['memory']['used']) * 1024 * 1024
            data['values'][None]['memory_total'] = float(result['memory']['total']) * 1024 * 1024
            data['values'][None]['memory_used_perc'] = float(result['memory']['used']) / \
                                                       float(result['memory']['total']) * 100
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
