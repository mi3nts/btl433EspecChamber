#!/bin/bash
#
sleep 60

kill $(pgrep -f 'airMarReader.py')
sleep 5
python3 airMarReader.py &
sleep 5

kill $(pgrep -f 'inir2me5Reader.py')
sleep 5
python3 inir2me5Reader.py &
sleep 5

kill $(pgrep -f 'sjh5Reader.py')
sleep 5
python3 sjh5Reader.py &
sleep 5


kill $(pgrep -f 'tgs2611c00Reader.py')
sleep 5
python3 tgs2611c00Reader.py &
sleep 5


python3 ipReader.py
sleep 5