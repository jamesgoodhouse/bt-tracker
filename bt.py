import asyncio
import bluetooth
import confuse
import logging
import paho.mqtt.client as mqtt
import signal

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from bluetooth_device import BluetoothDevice
from bluetooth_device import BluetoothDeviceConfuseTemplate
from bt_proximity import BluetoothRSSI
from datetime import datetime
from time import sleep

DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_MQTT_HOST = 'localhost'
DEFAULT_MQTT_PORT = 1833
DEFAULT_MQTT_PROTOCOL = 'MQTTv311'
DEFAULT_SCHEDULER_LOG_LEVEL = None

class BluetoothInfoRetriever:
    def __init__(self, rssi_scanner=BluetoothRSSI, lookup_name_func=bluetooth.lookup_name):
        self.logger = logging.getLogger('bluetooth')
        self.rssi_scanner = rssi_scanner
        self.lookup_name_func = lookup_name_func

    async def lookup_bluetooth_device(self, device: BluetoothDevice):
        async def lookup_device_name(addr, timeout):
            return self.lookup_name_func(addr, timeout)

        async def lookup_device_rssi(addr):
            client = self.rssi_scanner(addr)
            rssi = client.request_rssi()
            client.close()
            return rssi

        tasks = [asyncio.create_task(lookup_device_name(device.address, device.lookup_timeout))]
        if device.lookup_rssi:
            tasks.append(asyncio.create_task(lookup_device_rssi(device.address)))
        device.name, device.rssi = await asyncio.gather(*tasks)

        if device.name == None:
            self.logger.debug("no name found for device '{}'".format(device.address))
        else:
            self.logger.debug("name '{}' found for device '{}'".format(device.name, device.address))
        if device.rssi == None:
            self.logger.debug("no rssi found for device '{}'".format(device.address))
        else:
            self.logger.debug("rssi '{}' found for device '{}'".format(device.rssi, device.address))

        if device.name != None or device.rssi != None:
            self.logger.info("device '{}' found".format(device.address))
            device.last_seen = datetime.now()
            device.present = True
        else:
            self.logger.info("device '{}' not found".format(device.address))
            device.present = False

class BluetoothDeviceProcessor:
    def __init__(self, device: BluetoothDevice, bt: BluetoothInfoRetriever):
        self.device = device
        self.bt = bt

    async def update_device_presence(self):
        await self.lookup_device()

    async def lookup_device(self):
        await self.bt.lookup_bluetooth_device(self.device)

class GracefulKiller:
    kill_now = False

    def __init__(self):
        for signame in {'SIGINT', 'SIGTERM'}:
            signal.signal(
                getattr(signal, signame),
                self.exit_gracefully,
            )

    def exit_gracefully(self, signum, frame):
        logging.debug("received '{}' signal".format(signal.strsignal(signum)))
        self.kill_now = True

class FakeBluetoothScanner:
    def __init__(self, mac):
        self.mac = mac

    def request_rssi(self):
        return 42

    def close(self):
        return

class BluetoothPresenceDetector:
    def __init__(
        self,
        config,
        bt: BluetoothInfoRetriever,
        mqtt_client,
        scheduler: AsyncIOScheduler,
    ):
        self.config = config
        self.bt = bt
        self.mqtt = mqtt_client
        self.scheduler = scheduler

        self.mqtt.enable_logger(logger=logging.getLogger('mqtt'))
        self.mqtt.on_connect = self.mqtt_on_connect
        self.mqtt.on_message = self.mqtt_on_message
        self.mqtt.on_publish = self.mqtt_on_publish

        log_level = getattr(logging, config.log_level) # logging.getLevelName works, but that func shouldnt do what it does
        logging.basicConfig(level=log_level)

        scheduler_log_level = log_level
        if config.scheduler.log_level != None:
            scheduler_log_level = config.scheduler.log_level
        logging.getLogger('apscheduler').setLevel(scheduler_log_level)

        for device in config.devices:
            self.scheduler.add_job(
                name = device.address,
                func = self.detect_device,
                args = [device],
                trigger = IntervalTrigger(seconds=device.scan_interval),
                next_run_time = datetime.now(),
            )

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logging.getLogger('mqtt').debug("Connected with result code "+str(rc))

    def mqtt_on_message(self, client, userdata, msg):
        return
        # logging.getLogger('mqtt').debug(msg.topic+" "+str(msg.payload))

    def mqtt_on_publish(self, client, userdata, mid):
        return
        # logging.getLogger('mqtt').debug(msg.topic+" "+str(msg.payload))

    def start_detecting(self):
        if self.config.mqtt.enabled:
            self.mqtt.connect(host=self.config.mqtt.host, port=self.config.mqtt.port)
            self.mqtt.loop_start()

        self.scheduler.start()

    def stop_detecting(self):
        self.scheduler.shutdown()

        if self.config.mqtt.enabled:
            self.mqtt.loop_stop()

    async def publish(self, topic, payload=None, retain=False, qos=0):
        self.mqtt.publish(topic, payload, retain, qos)

    async def publish_device(self, device: BluetoothDevice):
        topic_prefix = 'bluetooth/'+device.address+'/'
        await asyncio.gather(
            asyncio.create_task(self.publish(topic_prefix+'rssi', device.rssi, True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'last_seen', int(device.last_seen.timestamp()), True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'present', device.present, True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'name', device.name, True, 1)),
        )

    async def detect_device(self, device: BluetoothDevice):
        await self.bt.lookup_bluetooth_device(device)

        if self.config.mqtt.enabled and device.publish_to_mqtt:
            await asyncio.create_task(self.publish_device(device))

def lookup(*_):
    return 'test'

async def main():
    log_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    config_template = {
        'devices': confuse.Sequence(
            BluetoothDeviceConfuseTemplate(),
        ),
        'log_level': confuse.Choice(log_levels, default=DEFAULT_LOG_LEVEL),
        'mqtt': {
            'enabled': confuse.Choice([True, False], default=False),
            'host': confuse.String(default=DEFAULT_MQTT_HOST),
            'port': confuse.Integer(default=DEFAULT_MQTT_PORT),
            'protocol': confuse.String(default=DEFAULT_MQTT_PROTOCOL),
        },
        'scheduler': {
            'log_level': confuse.Choice(log_levels, default=DEFAULT_SCHEDULER_LOG_LEVEL),
        },
    }
    config = confuse.Configuration('bluetooth_tracker', __name__).get(config_template)

    bt_tracker = BluetoothInfoRetriever()
    bt_tracker = BluetoothInfoRetriever(rssi_scanner=FakeBluetoothScanner, lookup_name_func=lookup)
    detector = BluetoothPresenceDetector(
        config,
        bt_tracker,
        mqtt.Client(),
        AsyncIOScheduler(),
    )
    detector.start_detecting()

    killer = GracefulKiller()
    while not killer.kill_now:
        await asyncio.sleep(1)

    logging.info('shutting down')
    detector.stop_detecting()

if __name__ == "__main__":
    asyncio.run(main())
