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

    # TODO : firmware and additional data ?
    components = [
        ['ifaces', 'https://{}/net/ifaces'],
        ['health', 'https://{}/wga/widgets/health.json'],
        ['storage', 'https://{}/statistics/systems/storage.json?timespan=600s'],
        ]

    @staticmethod
    def add_tag(result, label):
        return tuple((label, result))

    @inlineCallbacks
    def collect(self, device, log):
        log.debug('{}: Modeling collect'.format(device.id))

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
                            "User-Agent": "Mozilla/3.0Gold",
                        },
                        )
            d.addCallback(self.add_tag, comp[0])
            deferreds.append(d)

        results = yield DeferredList(deferreds, consumeErrors=True)
        for success, result in results:
            if not success:
                log.error('{}: {}'.format(device.id, result.getErrorMessage()))
                #returnValue(None)

        log.debug('Collected: {}'.format(results))
        returnValue(results)

    def process(self, device, results, log):
        """
        Must return one of :
            - None, changes nothing. Good in error cases.
            - A RelationshipMap, for the device to component information
            - An ObjectMap, for the device device information
            - A list of RelationshipMaps and ObjectMaps, both
        """

        self.result_data = {}
        for success, result in results:
            if success:
                if result[1]:
                    content = json.loads(result[1])
                else:
                    content = {}
                self.result_data[result[0]] = content

        maps = []
        maps.extend(self.get_reverse_proxies(log))
        maps.append(self.get_ifaces(log))
        maps.append(self.get_filesystems(log))

        log.debug('{}: process maps:{}'.format(device.id, maps))
        return maps

    def get_reverse_proxies(self, log):
        data = self.result_data.get('health', '')
        if data:
            data = data.get('items', '')
        else:
            return []
        rproxy_maps = []
        rm_jservers = []
        rm_junctions = []
        rm = []
        for r in data:
            # Reverse Proxy ObjectMap
            om_rproxy = ObjectMap()
            om_rproxy.id = self.prepId(r['name'])
            log.info('RProxy ID: {}'.format(om_rproxy.id))
            om_rproxy.title = r['label']
            log.info('RProxy ID: {}'.format(om_rproxy.id))
            log.info('RProxy Title: {}'.format(om_rproxy.title))
            log.info('RProxy Label: {}'.format(r['label']))
            rproxy_maps.append(om_rproxy)
            # Junction RelationshipMaps
            compname_rp = 'isamreverseProxys/{}'.format(om_rproxy.id)
            junction_maps = []
            rproxy_junctions = r['children']
            for j in rproxy_junctions:
                om_junction = ObjectMap()
                om_junction.id = self.prepId('{}_{}'.format(om_rproxy.id, j['name']))
                om_junction.title = '{}{}'.format(om_rproxy.title, str(j['label']))
                log.info('Junction ID: {}'.format(om_junction.id))
                log.info('Junction Title: {}'.format(om_junction.title))
                log.info('Junction Label: {}'.format(j['label']))
                junction_maps.append(om_junction)
                # Junctioned Server RelationshipMaps
                compname_j = '{}/isamjunctions/{}'.format(compname_rp, om_junction.id)
                jserver_maps = []
                junctioned_servers = j.get('children', [])
                for s in junctioned_servers:
                    om_jserver = ObjectMap()
                    om_jserver.id = self.prepId('{}_{}'.format(om_junction.id, s['name']))
                    om_junction.id = self.prepId('{}_{}'.format(om_rproxy.id, j['name']))
                    if om_junction.title.endswith('/'):
                        om_jserver.title = '{}{}'.format(om_junction.title, str(s['label']))
                    else:
                        om_jserver.title = '{}/{}'.format(om_junction.title, str(s['label']))
                    log.info('JunctionServer ID: {}'.format(om_jserver.id))
                    log.info('JunctionServer Title: {}'.format(om_jserver.title))
                    log.info('JunctionServer Label: {}'.format(s['label']))
                    jserver_maps.append(om_jserver)
                rm_jservers.append(RelationshipMap(relname='isamjunctionServers',
                                                   modname='ZenPacks.community.ISAM.ISAMJunctionServer',
                                                   compname=compname_j,
                                                   objmaps=jserver_maps))

            rm_junctions.append(RelationshipMap(relname='isamjunctions',
                                                modname='ZenPacks.community.ISAM.ISAMJunction',
                                                compname=compname_rp,
                                                objmaps=junction_maps
                                                ))

        rm.append(RelationshipMap(relname='isamreverseProxys',
                                    modname='ZenPacks.community.ISAM.ISAMReverseProxy',
                                    compname='',
                                    objmaps=rproxy_maps))
        rm.extend(rm_junctions)
        rm.extend(rm_jservers)
        return rm

    def get_ifaces(self, log):
        data = self.result_data.get('ifaces', '')
        if data:
            data = data.get('interfaces', '')
        else:
            return []
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

    def get_filesystems(self, log):
        data = self.result_data.get('storage', '')
        if not data:
            return []
        fs_maps = []
        default_fs = ['root', 'boot']
        for fs in default_fs:
            if fs in data:
                om_fs = ObjectMap()
                om_fs.id = self.prepId(fs)
                om_fs.title = fs
                om_fs.size = int(1024*1024*float(data[fs]['size']))
                fs_maps.append(om_fs)
        rm = RelationshipMap(relname='isamfileSystems',
                             modname='ZenPacks.community.ISAM.ISAMFileSystem',
                             compname='',
                             objmaps=fs_maps)
        return rm
