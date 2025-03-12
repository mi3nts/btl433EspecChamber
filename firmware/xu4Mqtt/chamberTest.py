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

chamber.stop_chamber()

# API details

# print("TEST 1")
# url = "http://192.168.20.113/api/v4/chambers/1/constants/constant_1"
# headers = {
#     "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzg4MjMxNTMsIm5iZiI6MTczODgyMzE1MywianRpIjoiYWZmOGE5ODYtOTc0Ny00MGQ0LWFjYjgtYzI0NGY4NzU3ZmJmIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.zWMTeiVwyahVfqFhIva2z5-I00PwGBFBnj4YONDvQgo",
#     "Content-Type": "application/json"
# }
# data = {
#     "temp": {"group": "loop", "set_value": 25, "range": [-20, 180]},
#     "humi": {"group": "loop", "enable": True, "set_value": 43, "range": [10, 95]},
#     "time_signal_1": {"group": "output", "value": True},
#     "dap": {"group": "output", "value": False}
# }
# try:
#     response = requests.post(url, headers=headers, json=data)
#     print(response)
#     response.raise_for_status()
#     print("Response:", response.json())
# except requests.exceptions.HTTPError as err:
#     print("HTTP Error:", err)
# except Exception as e:
#     print("Error:", e)


# GETS CURRENT TEMPERATURE SETTINGS - EVEN THE ONES THAT I CANT CONTROL = Enabled, Power  - These I save at Initialization - Better to loop it too
# curl -X GET \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      http://192.168.20.113/api/v4/chambers/1/conditions/temp
# {
#     "temp": {
#         "group": "loop",
#         "enable": false,
#         "set_value": 25.0,
#         "process_value": 24.96561622619629,
#         "power": 0.0,
#         "units": "\u00b0C"
#     },
#     "_errors": []
# }%    


# GETS CURRENT HUMIDITY SETTINGS - EVEN THE ONES THAT I CANT CONTROL = Enabled, Power - Better to loop it too
# curl -X GET \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      http://192.168.20.113/api/v4/chambers/1/conditions/humi
# {
#     "humi": {
#         "group": "loop",
#         "enable": false,
#         "set_value": 43.0,
#         "process_value": 42.01858901977539,
#         "power": 0.0,
#         "units": "%RH"
#     },
#     "_errors": []
# }%          



# STOPS WHAT EVER CURRENT OPERATION 
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"group":"standby"}' \
#      http://192.168.20.113/api/v4/chambers/1/operations/stop_chamber


# RUN  Constant - Everything must be set 
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"group":"constant"}' \
#      http://192.168.20.113/api/v4/chambers/1/operations/start_constant



# Only one constant mode available - so both these are identical - I would just update the second one 
# Constant Modes List
# Retrieve a list of available constant mode settings.
# request will update the running constant mode.
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"temp":{"group":"loop","set_value":23,"range":[-20,180]},"humi":{"group":"loop","enable":true,"set_value":42,"range":[10,95]},"time_signal_1":{"group":"output","value":true},"dap":{"group":"output","value":false}}' \
#      http://192.168.20.113/api/v4/chambers/1/constants


# Constant Mode
# Get the constant mode for a specified mode.
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"temp":{"group":"loop","set_value":22,"range":[-20,180]},"humi":{"group":"loop","enable":true,"set_value":44,"range":[10,95]},"time_signal_1":{"group":"output","value":true},"dap":{"group":"output","value":false}}' \
#      http://192.168.20.113/api/v4/chambers/1/constants/constant_1

# Run Operation
# Operations: Run Constant Mode
# Issue the command "Run Constant Mode" to the chamber.
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"group":"constant"}' \
#      http://192.168.20.113/api/v4/chambers/1/operations/start_constant

# Operations: Stop Operation
# Issue the command "Stop Operation" to the chamber.
# curl -X POST \
#      -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Mzk4NTE4OTMsIm5iZiI6MTczOTg1MTg5MywianRpIjoiNmY1MmZlNTItYTljYi00NzA2LTg1YmQtNzg1ZWFiNGYxZjJiIiwiaWRlbnRpdHkiOiJhZG1pbiIsImZyZXNoIjpmYWxzZSwidHlwZSI6ImFjY2VzcyIsInVzZXJfY2xhaW1zIjp7InJvbGVzIjpbImNvbmRpdGlvbnNfcnciLCJvcGVyYXRpb25zX3J3IiwiZmVhdHVyZXNfcnciLCJjb25zdGFudHNfcnciLCJwcm9ncmFtc19ydyIsInNldHVwX3J3Il19fQ.eRfrrVUtq9BD0tZH7nwzhsHHNQ0i479Tu668B_pmf2E" \
#      -H "Content-Type: application/json;charset=utf-8" \
#      -d '{"group":"standby"}' \
#      http://192.168.20.113/api/v4/chambers/1/operations/stop_chamber