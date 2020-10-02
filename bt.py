import bluetooth
from bt_proximity import BluetoothRSSI
import confuse
import paho.mqtt.client as mqtt
from time import sleep
import threading

DEFAULT_SCAN_INTERVAL = 10
DEFAULT_DEVICE_LOOKUP_TIMEOUT = 5
DEFAULT_DEVICE_LOOKUP_RSSI = False
MAC_ADDRESS_PATTERN = '([0-9a-fA-F]:?){12}'

_config_template = {
    'devices': confuse.Sequence(
        {
            'address': confuse.String(pattern=MAC_ADDRESS_PATTERN),
            'lookup_rssi': confuse.Choice(choices=[True, False], default=DEFAULT_DEVICE_LOOKUP_RSSI),
            'timeout': confuse.Integer(default=DEFAULT_DEVICE_LOOKUP_TIMEOUT),
        }
    ),
    'scan_interval': confuse.Integer(default=DEFAULT_SCAN_INTERVAL),
}

class FakeBluetoothScanner:
    def __init__(self, mac):
        self.mac = mac

    def request_rssi(self):
        return 42

class BluetoothTracker:
    def __init__(self, config, rssi_scanner=BluetoothRSSI, lookup_func=bluetooth.lookup_name):
        self.lookup_name_func = lookup_func
        self.__config = config
        self.__rssi_scanner = rssi_scanner
        self.__threads = []

    def listen(self, device, callback):
        rssi_scanner = self.__rssi_scanner(device.address)
        while True:
            name = self.lookup_name_func(device.address, device.timeout)
            rssi = rssi_scanner.request_rssi()
            if name is None and rssi is None:
                sleep(self.__config.scan_interval)
                continue
            callback(name, rssi)
            sleep(self.__config.scan_interval)

    def __start_thread(self, device, callback):
        thread = threading.Thread(
            target=self.listen,
            args=(),
            kwargs={
                'device': device,
                'callback': callback,
            }
        )
        # Daemonize
        thread.daemon = True
        print('starting thread')
        # Start the threau
        thread.start()
        return thread

    def start(self, callback):
        for device in self.__config.devices:
            th = self.__start_thread(device=device, callback=callback)
            self.__threads.append(th)

    def track_devices(self):
        for device in self.__config.devices:
            print("looking up '{}'".format(device.address))
            name = self.lookup_name_func(device.address, device.timeout)

            if name != None:
                print("found '{}'".format(name))

                if device.lookup_rssi:
                    rssi = self.__rssi_scanner(device.address).request_rssi()
                    print("'{}' has RSSI of '{}'".format(name, rssi))
            else:
                print("'{}' not found".format(device.address))

def lookup(addr, timeout):
    print("looking up '{}' with '{}' timeout".format(addr, timeout))
    return "balls"

def balls(name, rssi):
    print("callback for '{}' with rssi of '{}'".format(name, rssi))

def main():
    config = confuse.Configuration('bluetooth_tracker', __name__)
    bt = BluetoothTracker(config.get(_config_template), mqtt_client, rssi_scanner=FakeBluetoothScanner, lookup_func=lookup)
    # bt = BluetoothTracker(config.get(_config_template), mqtt_client)

    bt.start(balls)

    # bt.track_devices()
    # sleep(15)
    while True:
        sleep(1)

if __name__ == "__main__":
    main()
