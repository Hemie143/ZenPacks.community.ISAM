
# stdlib Imports
import base64
import json
import logging
import time

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenUtils.Utils import prepId
from ZenPacks.community.DataPower.lib.utils import SkipCertifContextFactory

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

# Setup logging
log = logging.getLogger('zen.PythonISAMReverseProxy')
isam_cycle = 600

class ISAMReverseProxy(PythonDataSourcePlugin):

    proxy_attributes = (
        'zISAMUsername',
        'zISAMPassword',
        )

    def ws_url_get(self, config):
        return

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
        log.debug('Starting ISAMReverseProxy params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ISAM Reverse Proxy collect')

        ds0 = config.datasources[0]
        url = self.ws_url_get(config)

        basicAuth = base64.encodestring('{}:{}'.format(ds0.zISAMUsername, ds0.zISAMPassword))
        authHeader = "Basic " + basicAuth.strip()
        headers = {
            "Accept": ["application/json"],
            "Authorization": [authHeader],
            "User-Agent": ["Mozilla/3.0Gold"],
        }
        agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
        results = {}
        try:
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            results = json.loads(response_body)
        except Exception as e:
            log.error('{}: {}'.format(ds0, e))
        returnValue(results)

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}


class RPStatus(ISAMReverseProxy):

    def ws_url_get(self, config):
        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)
        url = 'https://{}/wga/widgets/health.json'.format(ip_address)
        return url

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))
        map_status = {0: [0, 'OK'], 1: [3, 'unhealthy'], 2: [5, 'in failure']}
        items = result.get('items')
        data = self.new_data()
        for rproxy in items:
            component = prepId(rproxy['name'])
            value = int(rproxy['health'])
            # data['values'][component]['status'] = (float(value), 'N')
            data['values'][component]['rpstatus_rpstatus'] = value
            data['events'].append({
                'device': config.id,
                'component': component,
                'severity': 2,
                'measured_severity': map_status[value][0],
                'eventKey': 'RPStatus',
                'eventClassKey': 'RPStatusTest',
                'summary': 'Reverse Proxy {} - Status is {}'.format(component, map_status[value][1]),
                'eventClass': '/Status/ISAMReverseProxy',
                'isamRP': component,
                'isamJ': None,
                'isamJS': None,
            })

        log.debug('RPStatus data: {}'.format(data))
        return data


class RPThroughput(ISAMReverseProxy):

    def ws_url_get(self, config):
        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        now_time = int(time.time())     # Time in GMT, as on device
        start_time = int(now_time - now_time % isam_cycle) - isam_cycle
        url = 'https://{}/analysis/reverse_proxy_traffic/throughput_widget?date={}&duration={}'.format(ip_address,
                                                                                                       start_time,
                                                                                                       3*isam_cycle)
        return url

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))
        data = self.new_data()
        now_time = time.time()  # Time in GMT, as on device
        current_window_start = now_time - now_time % isam_cycle
        prev_window_start = current_window_start - isam_cycle
        cycletime = config.datasources[0].cycletime
        for rproxy in result:
            component = prepId(rproxy['instance'])
            # records could be a dictionary, not a list ???
            # records holds values collected for each window of 10 minutes
            # the current window sees its value raising during the current interval of 10 minutes
            # this means that the current window has its value reset every 10 minutes
            records = rproxy['records']
            if records == 0:
                data['values'][component]['rpthroughput_requests'] = 0
            elif len(records) == 1:
                log.error('onSuccess: records not a list: {}'.format(recods))
            else:
                for poll in records:
                    poll_time = float(poll['t'])
                    if poll_time == prev_window_start:
                        # Divide value by cycletime and multiply by 60 to get number of requests per minute
                        data['values'][component]['rpthroughput_requests'] = (float(poll['e'])/cycletime*60,
                                                                              current_window_start)
                        break

        log.debug('RPThroughput data: {}'.format(data))
        return data


