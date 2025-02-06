#!/bin/bash

sleep 10 
sudo chmod 777 /dev/tty*
sleep 2
sudo chmod 777 /dev/vid*
sleep 2
sudo chmod 777 /dev/i2c*
sleep 3
sudo chmod -R 777 /dev/gpiomem*