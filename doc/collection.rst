
Device
======

CPU
---
'https://{}/statistics/systems/cpu.json?timespan={}s'

Memory
------
'https://{}/statistics/systems/memory.json?timespan={}s'

File Systems
------------
'https://{}/statistics/systems/storage.json?timespan={}s'

Reverse Proxy
=============

Status
------
'https://{}/wga/widgets/health.json'.format(ip_address)'

Throughput
----------
'https://{}/analysis/reverse_proxy_traffic/throughput_widget?date={}&duration={}'

Output: List of dictionaries

    *   start_time - Integer - Start time as given in query
    *   instance - String - Reverse Proxy instance name
    *   offset - Integer - ???
    *   total_hits - Integer - Number of hits since start time
    *   tzname - String - Timezone: "GMT"
    *   bucket_size - Integer - interval duration ???
    *   records - Dictionary or list of dictionary
        * t - Integer - timestamp
        * e - Integer - number of hits during interval ???
