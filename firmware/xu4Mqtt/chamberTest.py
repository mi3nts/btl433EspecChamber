import json, requests
import time
import sys
from datetime import datetime
import yaml
# Create a class named chamber where it initially checks 
# the availabilty of the chamber and then creates an object 
# with the input values the available chamber will give 
# Initially read how many chambers and then create an 
# object with the chamber index as an input if available 
# Have 2 sensor IDs one with variable values and one with 
# default constants 

import json, requests
import mintsXU4.especChamber.chamber as eC
from  mintsXU4.especChamber.chamber import Chamber
from mintsXU4 import mintsDefinitions as mD

credentials         = mD.credentials
token               = credentials['chamber']['token']  

# Example usage:
url   = "http://192.168.20.113"

# Check for available chamber index
chamber_index = eC.get_available_chamber_index(url, token)

if chamber_index is None:
    print("No available chamber found. Exiting...")
    sys.exit(1)  # Quit the program

# Create the chamber object only if an index is available
chamber = Chamber(url, chamber_index, token)
# data = chamber.execute_command("")
# print(json.dumps(data, indent=4))




# rsp = requests.get(
#     "http://192.168.20.113/api/v4/chambers/1/operations",
#     headers={
#         "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E"
#     },
# )
# data = json.dumps(rsp.json(), indent=4)
# print(f"StatusCode={rsp.status_code}\n\n{data}")