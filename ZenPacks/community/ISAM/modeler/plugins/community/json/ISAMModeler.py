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

    # relname = 'isamreverseProxys'
    # TODO : change the relationship name, or at least rename, ending with Proxies
    # modname = 'ZenPacks.community.ISAM.ISAMReverseProxy'

    requiredProperties = (
        'zISAMUsername',
        'zISAMPassword',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    # rproxies & junction from health.json
    # interfaces
    # firmware ??
    components = [
        ['ifaces', 'https://{}/net/ifaces'],
        ['health', 'https://{}/wga/widgets/health.json'],
        ]

    def add_rel(self, result, label):
        print('We got:{}'.format(result))

        # return dict([(test, result)])

        return tuple((label, result))

    @inlineCallbacks
    def collect(self, device, log):
        log.info('{}: ***collecting data***'.format(device.id))

        username = getattr(device, 'zISAMUsername', None)
        password = getattr(device, 'zISAMPassword', None)

        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss https://10.0.50.142/reverseproxy
        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss "https://10.0.50.142/analysis/reverse_proxy_traffic/reqtime?duration=1&date=1506902400&instance=intranet"
        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss https://10.0.50.142/wga/widgets/health.json
        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss https://10.0.50.142/net/ifaces
        # curl -s -S -k -H "Accept:application/json" --user cs_monitoring:zenoss https://10.0.50.142/firmware_settings

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
            d.addCallback(self.add_rel, comp[0])
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
        log.info('{}: ***processing data***'.format(device.id))

        self.result_data = {}
        for success, result in results:
            if success:
                self.result_data[result[0]] = json.loads(result[1])
        log.info('result_data:{}'.format(self.result_data))

        maps = []
        maps.extend(self.get_reverse_proxies(log))

        log.info('{}: ***processed***:{}'.format(device.id, maps))
        return maps

    def get_reverse_proxies(self, log):

        data = self.result_data.get('health').get('items')

        log.info('rProxy data: {}'.format(data))

        rproxy_maps = []

        rm_junctions = []

        rm = []

        for r in data:
            om_rproxy = ObjectMap()
            om_rproxy.id = self.prepId(r['name'])
            om_rproxy.title = r['name']
            rproxy_maps.append(om_rproxy)
            '''
            rm.append(RelationshipMap(relname='isamreverseProxys',
                                      modname='ZenPacks.community.ISAM.ISAMReverseProxy',
                                      compname='',
                                      objmaps=[om_rproxy]))
            '''

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

            '''
            rproxy_maps.append(ObjectMap({
                'id': self.prepId(r['name']),
                'title': r['name'],
            }))
            '''

        log.info('RProxies: {}'.format(rproxy_maps))

        # also return junctions ?

        rm.append(RelationshipMap(relname='isamreverseProxys',
                                    modname='ZenPacks.community.ISAM.ISAMReverseProxy',
                                    compname='',
                                    objmaps=rproxy_maps))
        '''
        rm_junction = RelationshipMap(relname='isamjunctions',
                                      modname='ZenPacks.community.ISAM.ISAMJunction',
                                      objmaps=junction_maps)
        '''

        # log.info('Junctions: {}'.format(rm_junctions))
        # log.info('rm_rproxy1: {}'.format(rm_rproxy))
        # log.info('rm_rproxy1b: {}'.format((rm_rproxy)))
        #rm_rproxy.extend(rm_junctions)
        # log.info('rm_rproxy2: {}'.format(rm_rproxy))
        # log.info('rm_rproxy3: {}'.format((rm_rproxy)))
        log.info('rm: {}'.format((rm)))
        log.info('rm_junctions: {}'.format((rm_junctions)))
        rm.extend(rm_junctions)

        # return [rm_rproxy, rm_junction]

        # return rm_rproxy
        return rm
