# stdlib Imports
import json

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredSemaphore, DeferredList
from twisted.web.client import getPage

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap

import base64


class ISAMModeler(PythonPlugin):

    requiredProperties = (
        'zISAMUsername',
        'zISAMPassword',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    # firmware ??
    components = [
        ['ifaces', 'https://{}/net/ifaces'],
        ['health', 'https://{}/wga/widgets/health.json'],
        ]

    @staticmethod
    def add_tag(result, label):
        return tuple((label, result))

    @inlineCallbacks
    def collect(self, device, log):
        log.info('{}: ***collecting data***'.format(device.id))

        username = getattr(device, 'zISAMUsername', None)
        password = getattr(device, 'zISAMPassword', None)

        ip_address = device.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        basicAuth = base64.encodestring('{}:{}'.format(username, password))
        authHeader = "Basic " + basicAuth.strip()

        deferreds = []
        sem = DeferredSemaphore(1)
        for comp in self.components:
            url = comp[1].format(ip_address)
            d = sem.run(getPage, url,
                        headers={
                            "Accept": "application/json",
                            "Authorization": authHeader,
                            },
                        )
            d.addCallback(self.add_tag, comp[0])
            deferreds.append(d)

        results = yield DeferredList(deferreds, consumeErrors=True)
        for success, result in results:
            if not success:
                log.error('{}: {}'.format(device.id, result.getErrorMessage()))
                returnValue(None)

        log.info('Collected: {}'.format(results))
        returnValue(results)

    def process(self, device, results, log):
        """
        Must return one of :
            - None, changes nothing. Good in error cases.
            - A RelationshipMap, for the device to component information
            - An ObjectMap, for the device device information
            - A list of RelationshipMaps and ObjectMaps, both
        """
        #log.info('{}: ***processing data***'.format(device.id))

        self.result_data = {}
        for success, result in results:
            if success:
                self.result_data[result[0]] = json.loads(result[1])
        log.info('result_data:{}'.format(self.result_data))

        maps = []
        maps.extend(self.get_reverse_proxies(log))
        maps.append(self.get_ifaces(log))

        log.info('{}: ***processed***:{}'.format(device.id, maps))
        return maps

    def get_reverse_proxies(self, log):
        data = self.result_data.get('health').get('items')
        rproxy_maps = []
        rm_junctions = []
        rm = []
        for r in data:
            # Reverse Proxy ObjectMap
            om_rproxy = ObjectMap()
            om_rproxy.id = self.prepId(r['name'])
            om_rproxy.title = r['name']
            rproxy_maps.append(om_rproxy)
            # Junction RelationshipMaps
            compname = 'isamreverseProxys/{}'.format(om_rproxy.id)
            junction_maps = []
            rproxy_junctions = r['children']
            for j in rproxy_junctions:
                om_junction = ObjectMap()
                om_junction.id = self.prepId(j['name'])
                om_junction.title = j['name']
                junction_maps.append(om_junction)
            rm_junctions.append(RelationshipMap(relname='isamjunctions',
                                                modname='ZenPacks.community.ISAM.ISAMJunction',
                                                compname=compname,
                                                objmaps=junction_maps
                                                ))

        rm.append(RelationshipMap(relname='isamreverseProxys',
                                    modname='ZenPacks.community.ISAM.ISAMReverseProxy',
                                    compname='',
                                    objmaps=rproxy_maps))
        rm.extend(rm_junctions)
        return rm

    def get_ifaces(self, log):
        data = self.result_data.get('ifaces').get('interfaces')
        log.info('ifaces: {}'.format(data))
        if_maps = []
        for iface in data:
            om_if = ObjectMap()
            name = iface.get('label')
            om_if.id = self.prepId(name)
            om_if.title = name
            om_if.enabled = iface.get('enabled')
            address_list = []
            addresses = iface.get('ipv4').get('addresses')
            for address in addresses:
                address_list.append(address.get('address'))
            om_if.ipv4 = ','.join(address_list)
            if_maps.append(om_if)
        rm = RelationshipMap(relname='isaminterfaces',
                             modname='ZenPacks.community.ISAM.ISAMInterface',
                             compname='',
                             objmaps=if_maps)
        return rm
