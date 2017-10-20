
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

# Setup logging
log = logging.getLogger('zen.PythonISAMFileSystem')


class ISAMFileSystem(PythonDataSourcePlugin):

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
        log.debug('Starting ISAMFileSystem params')
        params = {}
        log.debug(' params is {}'.format(params))
        return params

    def collect(self, config):
        log.debug('Starting ISAMFileSystem collect')

        ds0 = config.datasources[0]
        cycletime = ds0.cycletime
        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", config.id)
            returnValue(None)
        url = 'https://{}/statistics/systems/storage.json?timespan={}'.format(ip_address, 3*cycletime)
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zISAMUsername, ds0.zISAMPassword))
        authHeader = "Basic " + basicAuth.strip()
        log.debug('authHeader: {}'.format(authHeader))
        d = getPage(url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": authHeader,
                        "User-Agent": "Mozilla/3.0Gold",
                        }
                    )
        return d

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))

        result = json.loads(result)
        data = self.new_data()
        default_fs = ['root', 'boot']
        for fs in default_fs:
            fs_data = result.get(fs, '')
            used = float(fs_data.get('used'))
            size = float(fs_data.get('size'))
            data['values'][fs]['used'] = (used*1024*1024, 'N')
            data['values'][fs]['used_perc'] = (used/size*100, 'N')

        log.debug('ISAMFileSystem data: {}'.format(data))
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
