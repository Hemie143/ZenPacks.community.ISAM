
# stdlib Imports
import json
import logging
import base64
import time

# Twisted Imports
from twisted.internet.defer import returnValue, DeferredSemaphore, DeferredList
from twisted.web.client import getPage

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin

# Setup logging
log = logging.getLogger('zen.PythonISAMInterface')


class ISAMInterface(PythonDataSourcePlugin):

    proxy_attributes = (
        'zISAMUsername',
        'zISAMPassword',
        )

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
        log.debug('Starting ISAMInterface params')
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

        log.debug('Starting ISAM Interface collect')
        # log.debug('config:{}'.format(config.__dict__))

        ds0 = config.datasources[0]
        # url = self.ws_url_get(config)

        ip_address = config.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        basicAuth = base64.encodestring('{}:{}'.format(ds0.zISAMUsername, ds0.zISAMPassword))
        authHeader = "Basic " + basicAuth.strip()

        deferreds = []
        sem = DeferredSemaphore(1)
        for datasource in config.datasources:
            component = datasource.component
            cycletime = datasource.cycletime

            url = 'https://{}/analysis/interface_statistics.json?prefix={}&timespan={}s'.format(ip_address,
                                                                                                component,
                                                                                                3*cycletime
                                                                                                )
            log.info('url: {}'.format(url))
            d = sem.run(getPage, url,
                        headers={
                            "Accept": "application/json",
                            "Authorization": authHeader,
                            "User-Agent": "Mozilla/3.0Gold",
                        },
                        )
            #d.addCallback(self.add_tag, datasource.datasource)
            deferreds.append(d)
        return DeferredList(deferreds)

    def onSuccess(self, result, config):
        log.debug('Success - result is {}'.format(result))
        #log.debug('Success - config is {}'.format(config.datasources))

        # result = json.loads(result)
        data = self.new_data()

        now_time = time.time()  # Time in GMT, as on device
        cycletime = config.datasources[0].cycletime
        current_window_start = now_time - now_time % cycletime
        prev_window_start = current_window_start - cycletime
        log.info('current_window_start: {}'.format(current_window_start))
        log.info('prev_window_start   : {}'.format(prev_window_start))

        for success, comp_data in result:
            #log.info('success:{}'.format(success))
            if success:
                comp_data = json.loads(comp_data)
                #log.info('comp_data:{}'.format(comp_data))
                component = comp_data['label']
                # log.info('component:{}'.format(component))
                inbytes = 0
                outbytes = 0
                for item in comp_data['items']:
                    timestamp = item['x']
                    if prev_window_start <= float(timestamp) < current_window_start:
                        if 'inbytes' in item['set']:
                            inbytes += item['y']
                        elif 'outbytes' in item['set']:
                            outbytes += item['y']
                        else:
                            log.error('Unknown set for component {}: {}'.format(component, item['set']))
                    else:
                        # log.info('out x: {}'.format(item['x']))
                        pass
                data['values'][component]['inbound'] = (float(inbytes)*8/cycletime, current_window_start)
                data['values'][component]['outbound'] = (float(outbytes) * 8 / cycletime, current_window_start)


        log.info('ISAMInterface data: {}'.format(data))
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
