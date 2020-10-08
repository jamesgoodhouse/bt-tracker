import confuse
import re

class BluetoothDevice:
    def __init__(
        self,
        address,
        scan_interval,
        lookup_timeout,
        lookup_rssi,
        publish_to_mqtt,
        rssi=None,
        name=None,
        present=False,
        last_seen=None,
    ):
        self.address = address
        self.scan_interval = scan_interval
        self.lookup_timeout = lookup_timeout
        self.lookup_rssi = lookup_rssi
        self.publish_to_mqtt = publish_to_mqtt
        self.name = name
        self.rssi = rssi
        self.last_seen = last_seen
        self.present = present

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

        return BluetoothDevice(address, scan_interval, lookup_timeout, lookup_rssi, publish_to_mqtt)
