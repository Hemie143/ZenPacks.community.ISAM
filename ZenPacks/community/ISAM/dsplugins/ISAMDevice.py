
# stdlib Imports
import json
import logging
import base64

# Twisted Imports
from twisted.internet.defer import returnValue, DeferredSemaphore, DeferredList
from twisted.web.client import getPage

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin

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
        'storage': 'https://{}/statistics/systems/storage.json?timespan={}s',
    }

    @staticmethod
    def add_tag(result, label):
        return tuple((label, result))

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
        log.debug('Starting ISAMDevice params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    def collect(self, config):
        log.debug('Starting ISAM Device collect')

        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        deferreds = []
        sem = DeferredSemaphore(1)
        for datasource in config.datasources:
            timespan = max(120, 2 * datasource.cycletime)
            url = self.urls[datasource.datasource].format(ip_address, timespan)
            basicAuth = base64.encodestring('{}:{}'.format(datasource.zISAMUsername, datasource.zISAMPassword))
            authHeader = "Basic " + basicAuth.strip()
            d = sem.run(getPage, url,
                        headers={
                            "Accept": "application/json",
                            "Authorization": authHeader,
                            "User-Agent": "Mozilla/3.0Gold",
                        },
                        )
            d.addCallback(self.add_tag, datasource.datasource)
            deferreds.append(d)
        return DeferredList(deferreds)

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))

        ds_data = {}
        for success, ddata in result:
            if success:
                ds = ddata[0]
                metrics = json.loads(ddata[1])
                ds_data[ds] = metrics

        data = self.new_data()
        for datasource in config.datasources:
            for point in datasource.points:
                # TODO: handle failures, try except and fill in data['events']
                # TODO Following isn't that nice...
                if datasource.datasource == 'memory' and point.dpName == 'memory_used_perc':
                    value = float(ds_data['memory']['used'])/float(ds_data['memory']['total'])*100
                else:
                    value = float(ds_data[datasource.datasource][point.id])
                    if datasource.datasource in ['memory']:
                        value *= 1024*1024
                data['values'][None][point.dpName] = (value, 'N')

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
