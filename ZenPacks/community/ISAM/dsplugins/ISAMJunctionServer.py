
# stdlib Imports
import base64
import json
import logging

# Zenoss imports
from Products.ZenUtils.Utils import prepId
from ZenPacks.community.DataPower.lib.utils import SkipCertifContextFactory
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

# Setup logging
log = logging.getLogger('zen.PythonISAMJunctionServer')
isam_cycle = 600

class ISAMJunctionServer(PythonDataSourcePlugin):

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
        log.debug('Starting ISAMJunctionServer params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ISAMJunctionServer collect')

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


class JSStatus(ISAMJunctionServer):

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
            r_proxy_id = rproxy['name']
            for junction in rproxy.get('children', []):
                junction_id = junction['name']
                for jserver in junction.get('children', []):
                    if junction_id.endswith('/'):
                        junction_label = '{}{}'.format(junction_id, jserver['name'])
                        component = prepId('{}_{}{}'.format(r_proxy_id, junction_id, jserver['name']))
                        junction_field = junction_id[:-1]
                    else:
                        junction_label = '{}/{}'.format(junction_id, jserver['name'])
                        component = prepId('{}_{}_{}'.format(r_proxy_id, junction_id, jserver['name']))
                        junction_field = junction_id
                    value = int(jserver['health'])
                    data['values'][component]['jsstatus_jsstatus'] = value
                    data['events'].append({
                        'device': config.id,
                        'component': component,
                        'severity': 2,
                        'measured_severity': map_status[value][0],
                        'eventKey': 'JSStatus',
                        'eventClassKey': 'ISAMJSStatusTest',
                        'summary': 'Junction Server {} - Status is {}'.format(junction_label, map_status[value][1]),
                        'eventClass': '/Status/ISAMJunctionServer',
                        'isamRP': prepId(r_proxy_id),
                        'isamJ': prepId(junction_field),
                        'isamJS': prepId(jserver['name']),
                    })

        log.debug('JSStatus data: {}'.format(data))
        return data
