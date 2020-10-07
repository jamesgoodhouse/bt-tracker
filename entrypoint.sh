#!/bin/bash

mkdir -p /var/run/dbus/

echo starting dbus
/usr/bin/dbus-daemon --system
sleep 5

echo starting bluetoothd
/usr/lib/bluetooth/bluetoothd --debug &
sleep 5

exec python3 /bt.py
