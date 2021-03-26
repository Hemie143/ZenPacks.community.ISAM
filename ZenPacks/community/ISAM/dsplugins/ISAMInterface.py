
# stdlib Imports
import json
import logging
import base64
import time

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from ZenPacks.community.DataPower.lib.utils import SkipCertifContextFactory

# Twisted Imports
from twisted.internet.defer import returnValue, DeferredSemaphore, DeferredList, inlineCallbacks
from twisted.web.client import getPage, Agent, readBody
from twisted.internet import reactor
from twisted.web.http_headers import Headers


# Setup logging
log = logging.getLogger('zen.PythonISAMInterface')


class ISAMInterface(PythonDataSourcePlugin):

    proxy_attributes = (
        'zISAMUsername',
        'zISAMPassword',
        )

    @classmethod
    def config_key(cls, datasource, context):
        log.debug(
            'In config_key context.device().id is %s datasource.getCycleTime(context) is %s datasource.rrdTemplate().id is %s datasource.id is %s datasource.plugin_classname is %s  ' % (
            context.device().id, datasource.getCycleTime(context), datasource.rrdTemplate().id, datasource.id,
            datasource.plugin_classname))
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.rrdTemplate().id,
            datasource.id,
            datasource.plugin_classname,
        )

    @classmethod
    def params(cls, datasource, context):
        log.debug('Starting ISAMInterface params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ISAM Interface collect')

        ds0 = config.datasources[0]
        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)
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
            component = datasource.component
            cycletime = datasource.cycletime
            url = 'https://{}/analysis/interface_statistics.json?prefix={}&timespan={}s'.format(ip_address,
                                                                                                component,
                                                                                                3*cycletime
                                                                                                )
            try:
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                results[datasource.component] = json.loads(response_body)
            except Exception as e:
                log.error('{}: {}'.format(datasource, e))
        returnValue(results)

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))

        data = self.new_data()
        now_time = time.time()  # Time in GMT, as on device
        cycletime = config.datasources[0].cycletime
        current_window_start = now_time - now_time % cycletime
        prev_window_start = current_window_start - cycletime

        for datasource in config.datasources:
            component = datasource.component
            if component in result:
                inbytes = 0
                outbytes = 0
                for item in result[component]['items']:
                    timestamp = item['x']
                    if prev_window_start <= float(timestamp) < current_window_start:
                        if 'inbytes' in item['set']:
                            inbytes += item['y']
                        elif 'outbytes' in item['set']:
                            outbytes += item['y']
                        else:
                            log.error('Unknown set for component {}: {}'.format(component, item['set']))
                    else:
                        pass
                data['values'][component]['inbound'] = (float(inbytes)*8/cycletime, current_window_start)
                data['values'][component]['outbound'] = (float(outbytes) * 8 / cycletime, current_window_start)

        log.debug('ISAMInterface data: {}'.format(data))
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
