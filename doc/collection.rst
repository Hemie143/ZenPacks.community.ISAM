
Device
======

CPU
---

Memory
------

Reverse Proxy
=============

Status
------

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


[{"start_time":1507883825,"instance":"intranet","offset":7200000,"total_hits":25,"records":{"t":1507884000,"e":25},"tzname":"GMT","bucket_size":600}, {"start_time":1507883825,"instance":"lab","offset":7200000,"total_hits":25,"records":{"t":1507884000,"e":25},"tzname":"GMT","bucket_size":600}, {"start_time":1507883825,"instance":"internet","offset":7200000,"total_hits":0,"records":0,"tzname":"GMT","bucket_size":600}, {"start_time":1507883825,"instance":"extranet-level-2","offset":7200000,"total_hits":25,"records":{"t":1507884000,"e":25},"tzname":"GMT","bucket_size":600}, {"start_time":1507883825,"instance":"extranet","offset":7200000,"total_hits":102,"records":{"t":1507884000,"e":102},"tzname":"GMT","bucket_size":600}, {"start_time":1507883825,"instance":"mobile","offset":7200000,"total_hits":26,"records":{"t":1507884000,"e":26},"tzname":"GMT","bucket_size":600}]