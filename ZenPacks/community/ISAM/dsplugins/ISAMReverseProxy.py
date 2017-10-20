
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
log = logging.getLogger('zen.PythonISAMReverseProxy')
isam_cycle = 600

class ISAMReverseProxy(PythonDataSourcePlugin):

    proxy_attributes = (
        'zISAMUsername',
        'zISAMPassword',
        )

    def ws_url_get(config):
        return

    @classmethod
    def config_key(cls, datasource, context):
        """
        Return a tuple defining collection uniqueness.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.

        This example implementation is the default. Split configurations by
        device, cycle time, template id, datasource id and the Python data
        source's plugin class name.

        You can omit this method from your implementation entirely if this
        default uniqueness behavior fits your needs. In many cases it will.
        """

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
        """
        Return params dictionary needed for this plugin.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.

        You have access to the dmd object database here and any attributes
        and methods for the context (either device or component).

        You can omit this method from your implementation if you don't require
        any additional information on each of the datasources of the config
        parameter to the collect method below. If you only need extra
        information at the device level it is easier to just use
        proxy_attributes as mentioned above.
        """
        log.debug('Starting ISAMReverseProxy params')
        params = {}
        log.debug(' params is %s \n' % (params))
        return params

    def collect(self, config):
        """
        No default collect behavior. You must implement this method.

        This method must return a Twisted deferred. The deferred results will
        be sent to the onResult then either onSuccess or onError callbacks
        below.

        This method really is run by zenpython daemon. Check zenpython.log
        for any log messages.
        """

        log.debug('Starting ISAM Reverse Proxy collect')
        log.debug('config:{}'.format(config.__dict__))

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

        result = json.loads(result)
        items = result.get('items')

        data = self.new_data()
        for rproxy in items:
            component = rproxy['name']
            value = rproxy['health']
            # log.info('RPStatus onSuccess - {} status: {}'.format(component, value))
            data['values'][component]['status'] = (value, 'N')
            # TODO: event
        log.info('RPStatus data: {}'.format(data))
        return data


class RPThroughput(ISAMReverseProxy):

    def ws_url_get(self, config):
        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)
        # Data is sampled every 10 minutes on the ISAM device
        # isam_cycle = 600

        # cycletime = config.datasources[0].cycletime
        now_time = int(time.time())     # Time in GMT, as on device
        # start_time = now_time - 5 * cycletime
        start_time = int(now_time - now_time % isam_cycle) - isam_cycle
        # log.info('time_10: {}'.format(start_time))
        # midnight = int(now_time - now_time % 86400)
        url = 'https://{}/analysis/reverse_proxy_traffic/throughput_widget?date={}&duration={}'.format(ip_address,
                                                                                                       start_time,
                                                                                                       3*isam_cycle)
        log.info('URL: {}'.format(url))
        return url

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))

        result = json.loads(result)
        #items = result.get('items')
        data = self.new_data()
        now_time = time.time()  # Time in GMT, as on device
        current_window_start = now_time - now_time % isam_cycle
        prev_window_start = current_window_start - isam_cycle

        for rproxy in result:
            component = rproxy['instance']
            # records could be a dictionary, not a list ???
            # records holds values collected for each window of 10 minutes
            # the current window sees its value raising during the current interval of 10 minutes
            # this means that the current window has its value reset every 10 minutes
            records = rproxy['records']
            # log.info('records: {}'.format(records))
            if records == 0:
                data['values'][component]['requests'] = (0, 'N')
            elif len(records)==1:
                log.error('onSucces: records not a list: {}'.format(recods))
            else:
                # TODO: keep only most recent poll ?
                for poll in records:
                    poll_time = float(poll['t'])
                    if poll_time == prev_window_start:
                        # log.info('Writing data for {} - t={} - val={}'.format(component, current_window_start, poll['e']))
                        data['values'][component]['requests'] = (poll['e'], current_window_start)
                        break

        log.info('RPThroughput data: {}'.format(data))
        return data


