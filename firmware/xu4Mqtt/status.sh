#!/bin/bash
#
sleep 1
echo "IPS7100"
echo $(pgrep -f 'ips7100ReaderV1.py')
sleep 2

echo "i2c"
echo  $(pgrep -f 'i2cReader.py')
sleep 2

echo "GPS"
echo $(pgrep -f 'gpsReader.py')
sleep 2

echo "battery reader"
echo $(pgrep -f 'batteryReader.py')
sleep 2
