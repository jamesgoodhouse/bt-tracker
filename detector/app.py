import asyncio
import confuse
import logging
import paho.mqtt.client as mqtt

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from detector.bluetooth import BluetoothDeviceConfuseTemplate
from detector.detector import Detector
from detector.killer import GracefulKiller

DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_MQTT_ENABLED = False
DEFAULT_MQTT_HOST = 'localhost'
DEFAULT_MQTT_LOG_LEVEL = None
DEFAULT_MQTT_PORT = 1833
DEFAULT_MQTT_PROTOCOL = 'MQTTv311'
DEFAULT_SCHEDULER_LOG_LEVEL = None

class FakeBluetoothScanner:
    def __init__(self, mac):
        self.mac = mac

    def request_rssi(self):
        return (42,)

    def close(self):
        return

async def main():
    log_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    config_template = {
        'devices': confuse.Sequence(
            BluetoothDeviceConfuseTemplate(),
        ),
        'log_level': confuse.Choice(log_levels, default=DEFAULT_LOG_LEVEL),
        'mqtt': {
            'enabled': confuse.Choice([True, False], default=DEFAULT_MQTT_ENABLED),
            'host': confuse.String(default=DEFAULT_MQTT_HOST),
            'log_level': confuse.Choice(['ERROR', 'WARNING', 'INFO', 'DEBUG'], default=DEFAULT_MQTT_LOG_LEVEL),
            'port': confuse.Integer(default=DEFAULT_MQTT_PORT),
            'protocol': confuse.String(default=DEFAULT_MQTT_PROTOCOL),
        },
        'scheduler': {
            'log_level': confuse.Choice(log_levels, default=DEFAULT_SCHEDULER_LOG_LEVEL),
        },
    }
    config = confuse.Configuration('bluetooth_tracker', __name__).get(config_template)

    kwargs = {}
    kwargs['bluetooth_rssi_scanner'] = FakeBluetoothScanner
    kwargs['bluetooth_lookup_name_func'] = lambda *_: 'test'
    detector = Detector(
        config,
        mqtt.Client(),
        AsyncIOScheduler(),
        **kwargs,
    )
    detector.start_detecting()

    killer = GracefulKiller()
    while not killer.kill_now:
        await asyncio.sleep(1)

    logging.info('shutting down')
    detector.stop_detecting()

if __name__ == "__main__":
    asyncio.run(main())
