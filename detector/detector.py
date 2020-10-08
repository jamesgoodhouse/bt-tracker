import asyncio
import bluetooth
import logging

from apscheduler.triggers.interval import IntervalTrigger
from bt_proximity import BluetoothRSSI
from datetime import datetime
from detector.bluetooth import BluetoothDevice

class Detector:
    def __init__(
        self,
        config,
        mqtt_client,
        scheduler,
        bluetooth_lookup_name_func=bluetooth.lookup_name,
        bluetooth_rssi_scanner=BluetoothRSSI,
    ):
        self.config = config
        self.mqtt = mqtt_client
        self.scheduler = scheduler
        self.bluetooth_lookup_name_func = bluetooth_lookup_name_func
        self.bluetooth_rssi_scanner = bluetooth_rssi_scanner

        # setup root logger
        log_level = getattr(logging, config.log_level) # logging.getLevelName works, but that func shouldnt do what it does
        logging.basicConfig(level=log_level)

        # setup mqtt client
        mqtt_log_level = log_level
        if config.mqtt.log_level != None:
            mqtt_log_level = getattr(logging, config.mqtt.log_level)
        self.mqtt_logger = logging.getLogger('mqtt')
        self.mqtt_logger.setLevel(mqtt_log_level)
        self.mqtt.enable_logger(logger=self.mqtt_logger)
        self.mqtt.on_connect = self.mqtt_on_connect
        self.mqtt.on_message = self.mqtt_on_message
        self.mqtt.on_publish = self.mqtt_on_publish

        # configure scheduler
        scheduler_log_level = log_level
        if config.scheduler.log_level != None:
            scheduler_log_level = getattr(logging, config.scheduler.log_level)
        logging.getLogger('apscheduler').setLevel(scheduler_log_level)

        # schedule a job per device
        for device in config.devices:
            self.scheduler.add_job(
                name = device.address,
                func = self.detect_device,
                args = [device],
                trigger = IntervalTrigger(seconds=device.scan_interval),
                next_run_time = datetime.now(),
            )

    def mqtt_on_connect(self, client, userdata, flags, rc):
        self.mqtt_logger.debug("Connected with result code "+str(rc))

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
        topic_prefix = 'bluetooth/'+device.address
        await asyncio.gather(
            asyncio.create_task(self.publish(topic_prefix+'/rssi', device.rssi, True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'/last_seen', int(device.last_seen.timestamp()), True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'/present', device.present, True, 1)),
            asyncio.create_task(self.publish(topic_prefix+'/name', device.name, True, 1)),
        )

    async def detect_device(self, device: BluetoothDevice):
        await device.lookup_device(
            lookup_name_func=self.bluetooth_lookup_name_func,
            rssi_scanner=self.bluetooth_rssi_scanner,
        )

        if self.config.mqtt.enabled and device.publish_to_mqtt:
            await asyncio.create_task(self.publish_device(device))
