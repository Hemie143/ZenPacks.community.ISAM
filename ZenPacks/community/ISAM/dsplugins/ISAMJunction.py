
# stdlib Imports
import json
import logging
import base64
import time
from random import randint

# Twisted Imports
from twisted.internet.defer import returnValue
from twisted.web.client import getPage

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenUtils.Utils import prepId

# Setup logging
log = logging.getLogger('zen.PythonISAMJunction')
isam_cycle = 600

class ISAMJunction(PythonDataSourcePlugin):

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
        log.debug('Starting ISAMJunction params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    def collect(self, config):
        log.debug('Starting ISAMJunction collect')

        ds0 = config.datasources[0]
        url = self.ws_url_get(config)
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zISAMUsername, ds0.zISAMPassword))
        authHeader = "Basic " + basicAuth.strip()
        d = getPage(url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": authHeader,
                        "User-Agent": "Mozilla/3.0Gold",
                        }
                    )
        return d

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}


class JStatus(ISAMJunction):

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
        result = json.loads(result)
        items = result.get('items')
        data = self.new_data()
        for rproxy in items:
            for junction in rproxy.get('children', []):
                component = prepId('{}_{}'.format(rproxy['name'], junction['name']))
                value = int(junction['health'])
                if junction['name'] == 'intranet/tb':
                    value = 1
                # value = randint(0, 2)
                data['values'][component]['status'] = (float(value), 'N')
                data['events'].append({
                    'device': config.id,
                    'component': component,
                    'severity': map_status[value][0],
                    'eventKey': 'JStatus',
                    'eventClassKey': 'ISAMJStatusTest',
                    'summary': 'Junction {} - Status is {}'.format(junction['name'], map_status[value][1]),
                    'eventClass': '/Status/ISAMJunction',
                    'isamRP': prepId(rproxy['name']),
                    'isamJ': prepId(junction['name']),
                    'isamJS': None,
                })

        log.debug('JStatus data: {}'.format(data))
        return data
