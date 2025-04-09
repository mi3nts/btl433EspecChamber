#!/bin/bash
#
sleep 1
echo "Routine status check"
echo "===================="
echo $(pgrep -f 'runRoutine.py')
sleep 2

