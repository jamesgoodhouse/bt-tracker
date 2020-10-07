from apscheduler.job import Job
from apscheduler.jobstores.base import BaseJobStore
from apscheduler.schedulers.background import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
import bluetooth
from bt_proximity import BluetoothRSSI
import confuse
from datetime import datetime
import logging
import paho.mqtt.client as mqtt
import re

DEFAULT_MQTT_HOST = 'localhost'
DEFAULT_MQTT_PORT = 1833
DEFAULT_MQTT_PROTOCOL = 'MQTTv311'

class BluetoothDevice:
    def __init__(self, address, scan_interval, lookup_timeout, lookup_rssi):
        self.address = address
        self.scan_interval = scan_interval
        self.lookup_timeout = lookup_timeout
        self.lookup_rssi = lookup_rssi

class BluetoothDeviceConfuseTemplate(confuse.Template):
    DEFAULT_SCAN_INTERVAL = 10
    DEFAULT_LOOKUP_TIMEOUT = 5
    DEFAULT_LOOKUP_RSSI = False
    MAC_ADDRESS_PATTERN = '([0-9a-fA-F]:?){12}'

    # FIXME: this is kinda rough
    def convert(self, value, view):
        if 'address' not in value:
            raise confuse.exceptions.NotFoundError(u'\'address\' is required')
        if not re.match(self.MAC_ADDRESS_PATTERN, value['address']):
            raise confuse.exceptions.ConfigValueError(u'\'address\' not a valid MAC address')

        address = value['address']

        scan_interval = self.DEFAULT_SCAN_INTERVAL
        if 'scan_interval' in value:
            si = value['scan_interval']
            if isinstance(si, int):
                scan_interval = si
            elif isinstance(si, float):
                return int(si)
            else:
                raise confuse.exceptions.ConfigValueError(u'\'scan_interval\' must be an integer')

        lookup_timeout = self.DEFAULT_LOOKUP_TIMEOUT
        if 'lookup_timeout' in value:
            lt = value['lookup_timeout']
            if isinstance(lt, int):
                lookup_timeout = lt
            elif isinstance(lt, float):
                return int(lt)
            else:
                raise confuse.exceptions.ConfigValueError(u'\'lookup_timeout\' must be an integer')

        lookup_rssi = self.DEFAULT_LOOKUP_RSSI
        if 'lookup_rssi' in value:
            lr = value['lookup_rssi']
            if isinstance(lr, bool):
                lookup_rssi = lr
            else:
                raise confuse.exceptions.ConfigValueError(u'\'lookup_rssi\' must be a boolean')

        return BluetoothDevice(address, scan_interval, lookup_timeout, lookup_rssi)

class BluetoothInfoRetriever:
    def __init__(self, rssi_scanner=BluetoothRSSI, lookup_name_func=bluetooth.lookup_name):
        self.rssi_scanner = rssi_scanner
        self.lookup_name_func = lookup_name_func

    def lookup_bluetooth_device(self, device: BluetoothDevice):
        def lookup_device_name(addr, timeout):
            return self.lookup_name_func(addr, timeout)

        def lookup_device_rssi(addr):
            client = self.rssi_scanner(addr)
            rssi = client.request_rssi()
            client.close()
            logging.warning(rssi)
            return rssi

        bt_device_info = {}

        device_name = lookup_device_name(device.address, device.lookup_timeout)
        if device_name != None:
            bt_device_info['name'] = device_name
            logging.error(device_name)
        else:
            logging.debug("device '{}' not found".format(device.address))

        if device.lookup_rssi:
            rssi = lookup_device_rssi(device.address)
            logging.error(rssi)
            if rssi != None:
                bt_device_info['rssi'] = rssi
            else:
                logging.debug("no rssi value found for device '{}'".format(device.address))

        if not bool(bt_device_info):
            return None
        else:
            return bt_device_info

class BluetoothDeviceProcessor:
    def __init__(self, device: BluetoothDevice, bt: BluetoothInfoRetriever):
        self.device = device
        self.bt = bt

    def update_device_presence(self):
        d = self.lookup_bluetooth()
        # print(d)

    def lookup_bluetooth(self):
        return self.bt.lookup_bluetooth_device(self.device)


config_template = {
    'devices': confuse.Sequence(
        # BluetoothDeviceConfuseTemplate(default_scan_interval=15, default_lookup_rssi=True),
        BluetoothDeviceConfuseTemplate(),
    ),
    'mqtt': {
        'host': confuse.String(default=DEFAULT_MQTT_HOST),
        'port': confuse.Integer(default=DEFAULT_MQTT_PORT),
        'protocol': confuse.String(default=DEFAULT_MQTT_PROTOCOL),
    },
}

class FakeBluetoothScanner:
    def __init__(self, mac):
        self.mac = mac

    def request_rssi(self):
        return 59

    def close(self):
        return

def lookup(addr, timeout):
    return 'tacobell'

def main():
    logging.basicConfig()
    logging.getLogger('apscheduler').setLevel(logging.INFO)

    config = confuse.Configuration('bluetooth_tracker', __name__).get(config_template)

    mqtt_client = mqtt.Client()
    mqtt_client.connect(host=config.mqtt.host, port=config.mqtt.port)
    mqtt_client.loop_start()

    scheduler = BlockingScheduler()

    for device in config.devices:
        # bt_tracker = BluetoothInfoRetriever(rssi_scanner=FakeBluetoothScanner, lookup_name_func=lookup)
        bt_tracker = BluetoothInfoRetriever()
        btdp = BluetoothDeviceProcessor(device, bt_tracker)
        scheduler.add_job(
            name = device.address,
            func = btdp.update_device_presence,
            trigger = 'interval',
            seconds = device.scan_interval,
            next_run_time = datetime.now(),
        )

    scheduler.start()

if __name__ == "__main__":
    main()
