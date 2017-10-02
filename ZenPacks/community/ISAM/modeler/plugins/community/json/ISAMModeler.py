# stdlib Imports
import json
#import urllib

# Twisted Imports
#from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredSemaphore, DeferredList
from twisted.web.client import getPage

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin

import base64

class ISAMModeler(PythonPlugin):

    #relname = 'iSAMReverseProxys'
    relname = 'isamreverseProxys'
    # TODO : change the relationship name, or at least rename, ending with Proxies
    modname = 'ZenPacks.community.ISAM.ISAMReverseProxy'

    requiredProperties = (
        'zISAMUsername',
        'zISAMPassword',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        log.info('{}: ***collecting data***'.format(device.id))

        username = getattr(device, 'zISAMUsername', None)
        password = getattr(device, 'zISAMPassword', None)

        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss https://10.0.50.142/reverseproxy
        ip_address = device.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        urls = [
            'https://{}/reverseproxy'.format(ip_address),
            ]

        basicAuth = base64.encodestring('{}:{}'.format(username, password))
        authHeader = "Basic " + basicAuth.strip()

        deferreds = []
        sem = DeferredSemaphore(1)
        for url in urls:
            d = sem.run(getPage, url,
                        headers={
                            "Accept": "application/json",
                            "Authorization": authHeader,
                        },
                        )
            deferreds.append(d)

            # callbacks ?

        results = yield DeferredList(deferreds, consumeErrors=True)
        for success, result in results:
            if not success:
                log.error('{}: {}'.format(device.id, result.getErrorMessage()))
                returnValue(None)

        log.info('Collected: {}'.format(results))
        returnValue(results)

    def process(self, device, results, log):
        log.info('{}: ***processing data***'.format(device.id))

        rm = self.relMap()
        for success, result in results:
            if success:
                log.info('Result: {}'.format(result))
                result = json.loads(result)
                log.info('Result JSON: {}'.format(result))
                for r in result:
                    rm.append(self.objectMap({
                        'id': self.prepId(r['instance_name']),
                        'title': r['instance_name'],
                        'started': r['started'],
                        'enabled': r['enabled'],
                    }))

        log.info('{}: ***processed***:{}'.format(device.id, rm))
        return rm
