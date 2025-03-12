import json, requests
import time
import sys
from datetime import datetime, timezone
from collections import OrderedDict
from mintsXU4 import mintsSensorReader as mSR
import requests
import pprint
# Create a class named chamber where it initially checks 
# the availabiltu of the chamber and then creates an object 
# with the input values the available chamber will give 
# Initially read how many chambers and then create an 
# object with the chamber index as an input if available 
# Have 2 sensor IDs one with variable values and one with 
# default constants 

# Through out the firmware the humidity and temperature set values are continually monitored 




#  This function just reads how many chambers are availbale 
def get_available_chamber_index(url, token, chamberWanted=0, timeout=5):
    """
    Retrieves the available chamber index from the API with a timeout and handles keyboard interrupts.

    :param url: Base URL of the API.
    :param token: Authorization token.
    :param chamberWanted: Index of the chamber to retrieve (default is 0).
    :param timeout: Maximum time (in seconds) to wait for the API response (default is 5 seconds).
    :return: The available chamber index or None if not found.
    """
    headers = {"Authorization": f"Bearer {token}"}

    try:
        rsp = requests.get(f"{url}/api/v4/", headers=headers, timeout=timeout)

        if rsp.status_code == 200:
            data = rsp.json()
            chambers = data.get("chambers", {}).get("uri", [])
            print(chambers)
            if chambers and chamberWanted < len(chambers):
                # Extract the chamber index from the URI
                chamber_uri = chambers[chamberWanted]
                chamber_index = chamber_uri.strip("/").split("/")[-1]
                return int(chamber_index)

    except requests.exceptions.Timeout:
        print("Request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        return None  # Gracefully handle exit

    return None

class Chamber:
    def __init__(self, url, chamber_index, token):
        """
        Initializes a Chamber instance.
        :param url: Base URL of the API.
        :param chamber_index: Index of the chamber.
        :param token: Authorization token.
        """
        self.url = url
        self.chamber_index = chamber_index
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}"
        }

        self.operation_mapping = {
            "standby": 0,
            "constant": 1,
            "program": 2
        }

        self.change_mapping = {
            0: "Start Up",
            1: "Stop and Stand By",
            10: "Temperature Set",
            11: "Humidity Set",
            20: "Constant Run",
            30: "Operation Set",
            40: "Operation Run",
        }


       # Execute command and retrieve data
        self.validity, data = self.execute_command("")
        print(data)

        if self.validity:
            print("Valid Chamber Data found")
            dateTime            = datetime.now(timezone.utc)

            status              = data["conditions"]["status"]
            temperature_set     = data["conditions"]["temp"]
            humidity_set        = data["conditions"]["humi"]
            time_signal_set     = data["conditions"]["time_signal_1"]
            dap_set             = data["conditions"]["dap"]
            program_set         = data["programs"]

            self.write_status(dateTime,status)
            self.write_temperature_set(dateTime,temperature_set)
            self.write_humidity_set(dateTime,humidity_set)
            self.write_time_signal_set(dateTime,time_signal_set)
            self.write_dap_set(dateTime,dap_set)
            self.write_program_set(dateTime,program_set)
        
        else:
            print("Chamber data invalid")

              
    def  write_program_set(self,dateTime,status):
            sensorIDPost                = "PRGRM"
            self.program_name_1         = status["1"]["name"]
            self.program_name_2         = status["2"]["name"]
            self.program_name_3         = status["3"]["name"]
            self.program_name_4         = status["4"]["name"]
            self.program_name_5         = status["5"]["name"]                                                

            sensorDictionary = OrderedDict([
                ("dateTime"         ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("programName1"         ,str(self.program_name_1)),                
                ("programName2"         ,str(self.program_name_2)),      
                ("programName3"         ,str(self.program_name_3)),      
                ("programName4"         ,str(self.program_name_4)),      
                ("programName5"         ,str(self.program_name_5)),                      
                ])
            mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)    

    def  write_dap_set(self,dateTime,status):
            sensorIDPost                     = "DAP"
            self.dap_group              = status["group"]
            self.dap_enable             = self.bool_to_int(status["value"])

            sensorDictionary = OrderedDict([
                ("dateTime"         ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("dapGroup"         ,str(self.dap_group)),                
                ("enabled"          ,int(self.dap_enable)),             
                ])
            mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)

    def  write_time_signal_set(self,dateTime,status):
            sensorIDPost                        = "DAP"
            self.time_signal_group              = status["group"]
            self.time_signal_enabled            = self.bool_to_int(status["value"])

            sensorDictionary = OrderedDict([
                ("dateTime"         ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("timeSignalGroup"  ,str(self.time_signal_group)),                
                ("enabled"          ,int(self.time_signal_enabled)),             
                ])
            mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)

    def  write_humidity_set(self,dateTime,status):
            sensorIDPost                     = "HMDTY"
            self.humidity_group              = status["group"]
            self.humidity_enable             = self.bool_to_int(status["enable"])
            self.humidity_set_value          = status["set_value"]
            self.humidity_process_value      = status["process_value"]
            self.humidity_power              = status["power"]

            sensorDictionary = OrderedDict([
                ("dateTime"         ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("humidityGroup"    ,str(self.humidity_group)),                
                ("enabled"          ,int(self.humidity_enable)),             
                ("setValue"         ,self.humidity_set_value),          
                ("processValue"     ,self.humidity_process_value),       
                ("power"            ,self.humidity_power),       
                ])
            mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)

    def  write_temperature_set(self,dateTime,status):
            sensorIDPost                        = "TMPRT"
            self.temperature_group              = status["group"]
            self.temperature_enable             = self.bool_to_int(status["enable"])
            self.temperature_set_value          = status["set_value"]
            self.temperature_process_value      = status["process_value"]
            self.temperature_power              = status["power"]

            sensorDictionary = OrderedDict([
                ("dateTime"         ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("temperatureGroup" ,str(self.temperature_group)),                
                ("enabled"          ,int(self.temperature_enable)),             
                ("setValue"         ,self.temperature_set_value),          
                ("processValue"     ,self.temperature_process_value),       
                ("power"            ,self.temperature_power),       
                ])
            mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)


    def  write_status(self,dateTime,status):
            sensorIDPost            = "STATUS"
            self.chamber_time       = status["datetime"]
            self.operationLabel     = status["operation"]
            self.operation          = self.operation_mapping.get(self.operationLabel,-1)
            self.constant_key       = status["constant_key"]
            self.program_step       = self.default_if_none(status["program_step"])
            self.program_time_step  = self.default_if_empty(status['program_time_step'])
            self.program_time       = self.default_if_empty(status["program_time"])
            self.program_key        = self.default_if_none(status["program_key"])
            self.program_name       = status["program_name"]
            self.program            = self.default_if_none(status["program"])
            self.program_counters   = ", ".join(status["program_counters"])
            self.running            = self.bool_to_int(status["running"])

            sensorDictionary = OrderedDict([
                ("dateTime"             ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("hostIP"               ,str(self.url)),
                ("chamberTime"          ,str(self.chamber_time)),                
                ("operation"            ,str(self.operation)),          
                ("operationLabel"       ,str(self.operationLabel)),             
                ("programStep"          ,int(self.program_step)),          
                ("programTime"          ,int(self.program_time)),       
                ("programKey"           ,int(self.program_key)),       
                ("programName"          ,str(self.program_name)),       
                ("program"              ,str(self.program)),    
                ("program_counters"     ,str(self.program_counters)),    
                ("running"              ,int(self.running)),    
                ])

            mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)

    def bool_to_int(self,value):
        return 1 if value is True else 0 if value is False else -1

    def default_if_none(self,value, default=-1):
        return value if value is not None else default

    def default_if_empty(self,value, default=-1):
        return value if value is " " else default


    def execute_command(self, command, data=None, method="GET"):
        """
        Executes a command on the chamber.

        :param command: The command to execute.
        :param data: Optional JSON data to send with the request.
        :param method: HTTP method (GET or POST). Defaults to GET.
        :return: Tuple (success: bool, response JSON or error message).
        """
        full_url = f"{self.url}/api/v4/chambers/{self.chamber_index}/{command}"
        print(f"Executing {method} request: {full_url}")

        headers = self.headers.copy()  # Ensure headers are not modified externally
        if data:
            headers["Content-Type"] = "application/json"

        try:
            if method.upper() == "POST":
                rsp = requests.post(full_url, headers=headers, json=data)
            else:  # Default to GET
                rsp = requests.get(full_url, headers=headers)

            if rsp.status_code == 200:
                return True, rsp.json()  # Return JSON response
            else:
                error_msg = f"Error: {rsp.status_code}, {rsp.text}"
                print(error_msg)
                return False, error_msg
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return False, str(e)

    def stop_chamber(self):
        data = {"group": "standby"}
        success, response = self.execute_command(\
             "operations/stop_chamber",\
                  data=data, method="POST")
        
        print(response)


        sensorIDPost            = "CHNG"
        self.change_ID           = 1

        print("Valid Chamber Data found")
        dateTime            = datetime.now(timezone.utc)
        sensorDictionary = OrderedDict([
            ("dateTime"             ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"             ,self.change_ID),
            ("changeLabel"          ,self.change_mapping.get(self.change_ID)),                
            ("success"              ,self.bool_to_int(success)),
            ])
        mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)

# change_temperature
# change_humidity
# set_constant (inputs should have setTemperature True or false)
# activate_constant_mode
# write_change t

