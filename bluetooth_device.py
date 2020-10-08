import asyncio
import bluetooth
import confuse
import logging
import re

from bt_proximity import BluetoothRSSI
from datetime import datetime

class BluetoothDevice:
    DEFAULT_LOOKUP_RSSI = False
    DEFAULT_LOOKUP_TIMEOUT = 10
    DEFAULT_PUBLISH_TO_MQTT = False
    DEFAULT_SCAN_INTERVAL = 60

    def __init__(
        self,
        address,
        last_seen=None,
        logger=logging.getLogger('bluetooth'),
        lookup_rssi=DEFAULT_LOOKUP_RSSI,
        lookup_timeout=DEFAULT_LOOKUP_TIMEOUT,
        name=None,
        present=False,
        publish_to_mqtt=DEFAULT_PUBLISH_TO_MQTT,
        rssi=None,
        scan_interval=DEFAULT_SCAN_INTERVAL,
    ):
        self.address = address
        self.last_seen = last_seen
        self.logger = logger
        self.lookup_rssi = lookup_rssi
        self.lookup_timeout = lookup_timeout
        self.name = name
        self.present = present
        self.publish_to_mqtt = publish_to_mqtt
        self.rssi = rssi
        self.scan_interval = scan_interval

    async def lookup_device(
        self,
        lookup_name_func=bluetooth.lookup_name,
        rssi_scanner=BluetoothRSSI,
    ):
        async def lookup_device_name(addr, timeout):
            return lookup_name_func(addr, timeout)

        async def lookup_device_rssi(addr):
            client = rssi_scanner(addr)
            rssi = client.request_rssi()
            client.close()
            return rssi

        tasks = [asyncio.create_task(lookup_device_name(self.address, self.lookup_timeout))]
        if self.lookup_rssi:
            tasks.append(asyncio.create_task(lookup_device_rssi(self.address)))
        self.name, self.rssi = await asyncio.gather(*tasks)

        if self.name == None:
            self.logger.debug("no name found for device '{}'".format(self.address))
        else:
            self.logger.debug("name '{}' found for device '{}'".format(self.name, self.address))
        if self.rssi == None:
            self.logger.debug("no rssi found for device '{}'".format(self.address))
        else:
            self.logger.debug("rssi '{}' found for device '{}'".format(self.rssi, self.address))

        if self.name != None or self.rssi != None:
            self.logger.info("device '{}' found".format(self.address))
            self.last_seen = datetime.now()
            self.present = True
        else:
            self.logger.info("device '{}' not found".format(self.address))
            self.present = False

class BluetoothDeviceConfuseTemplate(confuse.Template):
    DEFAULT_SCAN_INTERVAL = 10
    DEFAULT_LOOKUP_TIMEOUT = 5
    DEFAULT_LOOKUP_RSSI = False
    DEFAULT_PUBLISH_TO_MQTT = True
    MAC_ADDRESS_PATTERN = '([0-9a-fA-F]:?){12}'

    def __init__(
        self,
        default_scan_interval=DEFAULT_SCAN_INTERVAL,
        default_lookup_timeout=DEFAULT_LOOKUP_TIMEOUT,
        default_lookup_rssi=DEFAULT_LOOKUP_RSSI,
        default_publish_to_mqtt=DEFAULT_PUBLISH_TO_MQTT,
    ):
        self.default_scan_interval = default_scan_interval
        self.default_lookup_rssi = default_lookup_rssi
        self.default_lookup_timeout = default_lookup_timeout
        self.default_publish_to_mqtt = default_publish_to_mqtt

    # FIXME: this is kinda rough
    def convert(self, value, view):
        if 'address' not in value:
            raise confuse.exceptions.NotFoundError(u'\'address\' is required')
        if not re.match(self.MAC_ADDRESS_PATTERN, value['address']):
            raise confuse.exceptions.ConfigValueError(u'\'address\' not a valid MAC address')

        address = value['address']

        scan_interval = self.default_scan_interval
        if 'scan_interval' in value:
            si = value['scan_interval']
            if isinstance(si, int):
                scan_interval = si
            elif isinstance(si, float):
                return int(si)
            else:
                raise confuse.exceptions.ConfigValueError(u'\'scan_interval\' must be an integer')

        lookup_timeout = self.default_lookup_timeout
        if 'lookup_timeout' in value:
            lt = value['lookup_timeout']
            if isinstance(lt, int):
                lookup_timeout = lt
            elif isinstance(lt, float):
                return int(lt)
            else:
                raise confuse.exceptions.ConfigValueError(u'\'lookup_timeout\' must be an integer')

        lookup_rssi = self.default_lookup_rssi
        if 'lookup_rssi' in value:
            lr = value['lookup_rssi']
            if isinstance(lr, bool):
                lookup_rssi = lr
            else:
                raise confuse.exceptions.ConfigValueError(u'\'lookup_rssi\' must be a boolean')

        publish_to_mqtt = self.default_publish_to_mqtt
        if 'publish_to_mqtt' in value:
            ptm = value['publish_to_mqtt']
            if isinstance(ptm, bool):
                publish_to_mqtt = ptm
            else:
                raise confuse.exceptions.ConfigValueError(u'\'publish_to_mqtt\' must be a boolean')

        return BluetoothDevice(
            address,
            scan_interval=scan_interval,
            lookup_timeout=lookup_timeout,
            lookup_rssi=lookup_rssi,
            publish_to_mqtt=publish_to_mqtt,
        )
