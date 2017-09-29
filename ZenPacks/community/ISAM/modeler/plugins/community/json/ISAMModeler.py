# stdlib Imports
import json
import urllib

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue
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

        rproxy_url = 'https://{}/reverseproxy'.format(ip_address)
        basicAuth = base64.encodestring('{}:{}'.format(username, password))
        authHeader = "Basic " + basicAuth.strip()
        try:
            response = yield getPage(
                rproxy_url,
                headers={
                    "Accept": "application/json",
                    "Authorization": authHeader,
                    },
            )
            response = json.loads(response)
            log.info('Collect response for {}: {}'.format(device.id, response))
        except Exception, e:
            log.error('{}: {}'.format(device.id, e))
            returnValue(None)

        log.info('Collected: {}'.format(response))
        returnValue(response)

    def process(self, device, results, log):
        log.info('{}: ***processing data***'.format(device.id))

        rm = self.relMap()
        for result in results:
            rm.append(self.objectMap({
                'id': self.prepId(result['instance_name']),
                'title': result['instance_name'],
                'started': result['started'],
                'enabled': result['enabled'],
            }))

        log.info('{}: ***processed***:{}'.format(device.id, rm))
        return rm
