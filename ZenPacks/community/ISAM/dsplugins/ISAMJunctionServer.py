
# stdlib Imports
import json
import logging
import base64
import time

# Twisted Imports
from twisted.internet.defer import returnValue
from twisted.web.client import getPage

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenUtils.Utils import prepId

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

    def collect(self, config):
        log.debug('Starting ISAMJunctionServer collect')

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
        result = json.loads(result)
        items = result.get('items')
        data = self.new_data()
        for rproxy in items:
            r_proxy_id = rproxy['name']
            for junction in rproxy.get('children', []):
                junction_id = junction['name']
                for jserver in junction.get('children', []):
                    # TODO: prepId the name ?
                    # component = jserver['name']
                    if junction_id.endswith('/'):
                        component = prepId('{}_{}{}'.format(r_proxy_id, junction_id, jserver['name']))
                    else:
                        component = prepId('{}_{}_{}'.format(r_proxy_id, junction_id, jserver['name']))
                    value = float(jserver['health'])
                    data['values'][component]['status'] = (value, 'N')
                    # TODO: event
        log.debug('JSStatus data: {}'.format(data))
        return data