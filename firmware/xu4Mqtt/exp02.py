import json, requests
import time
import sys
from datetime import datetime
import yaml

import json, requests
import mintsXU4.especChamber.chamber as eC
from  mintsXU4.especChamber.chamber import Chamber

from mintsXU4 import mintsDefinitions as mD

credentials         = mD.credentials
token               = credentials['chamber']['token']  

# Example usage:
url   = "http://192.168.20.121"

# Check for available chamber index
chamber_index = eC.get_available_chamber_index(url, token)

if chamber_index is None:
    print("No available chamber found. Exiting...")
    sys.exit(1)  # Quit the program

# Create the chamber object only if an index is available
chamber = Chamber(url, chamber_index, token)

chamber.stop_chamber()
time.sleep(10)

# Running Routines 

## Things to modify 
#  Unreachable Areas 
#  Dont change the mode if it is in the cerrent mode 

routine = Chamber.Routine(
    chamber = chamber,
    mode="uniform",
    symmetrical_converging=True,
    major_variable="temperature",
    temperature_start=25,
    temperature_end=25,
    temperature_increment=10,
    temperature_padding=1,
    humidity_start=40,
    humidity_end=40,
    humidity_increment=10,
    humidity_padding=1,
    is_forced=True,
    still_time=28800, # Keep the chamber in the current state for this time - Keep it for 8 hours
    wait_time =3600 # if the chamber is not in the desired state, wait for this time before moving on   
)

routine.print_routine()

routine.run_routine(chamber)