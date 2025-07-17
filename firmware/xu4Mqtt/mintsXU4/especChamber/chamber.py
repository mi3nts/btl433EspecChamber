import json, requests
import time
import sys
from datetime import datetime, timezone
from collections import OrderedDict
from mintsXU4 import mintsSensorReader as mSR
import requests
import pprint
import os
import logging
from typing import List, Dict  # For Python 3.8 compatibility

from mintsXU4 import mintsDefinitions as mD

dataFolder          = mD.dataFolder 
nodeID              = mD.macAddress

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
            12: "Temperature and Humidity Set",            
            20: "Constant Run",
            30: "Operation Set",
            40: "Operation Run",
            50: "Routine Initiated",
            51: "Routine Started",
            52: "Routine Incrimented",            
        }

        time.sleep(5)

        self.get_and_write_summary(expanded=True)

        print("Chamber Initiated with IP:"\
               + self.url + " at chamber index:" \
                + str(chamber_index))


    def get_and_write_summary(self, expanded=False):
       # Execute command and retrieve data
        self.validity, data = self.execute_command("")
        # print(data)

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
            if expanded:
                self.write_time_signal_set(dateTime,time_signal_set)
                self.write_dap_set(dateTime,dap_set)
                self.write_program_set(dateTime,program_set)
        
        else:
            print("Chamber data invalid")


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
                ("operation"            ,int(self.operation)),          
                ("operationLabel"       ,str(self.operationLabel)),             
                ("programStep"          ,int(self.program_step)),          
                ("programTime"          ,int(self.program_time)),       
                ("programKey"           ,int(self.program_key)),       
                ("programName"          ,str(self.program_name)),       
                ("program"              ,int(self.program)),    
                ("program_counters"     ,str(self.program_counters)),    
                ("running"              ,int(self.running)),    
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
        pprint.pprint(response)
        time.sleep(1)

        sensorIDPost            = "CHNG"
        self.change_ID           = 1

        print("Valid Chamber Data found")
        dateTime            = datetime.now(timezone.utc)
        sensorDictionary = OrderedDict([
            ("dateTime"             ,str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"             ,self.change_ID),
            ("changeLabel"          ,self.change_mapping.get(self.change_ID)),
            ("newValue"             ,-100),   
            ("success"              ,self.bool_to_int(success)),
            ])
        mSR.sensorFinisher(dateTime,"BTL433ESC001" + sensorIDPost ,sensorDictionary)
        self.get_and_write_summary()



        return success


    def set_temperature_value(self, temp_value):
        """
        Updates the temperature set value.

        :param temp_value: The new temperature set value.
        """
        data = {
            "temp": {
                "group": "loop",
                "set_value": temp_value,
                "range": [-20, 180]
            }
        }

        success, response          = self.execute_command("constants/constant_1", data=data, method="POST")
        pprint.pprint(response)
        time.sleep(1)

        dateTime          = datetime.now(timezone.utc)
        sensorIDPost      = "CHNG"

        self.change_ID    = 10  # Change ID for Temperature Set

        # Log the change
        sensorDictionary = OrderedDict([
            ("dateTime"     , str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"     , self.change_ID),
            ("changeLabel"  , self.change_mapping.get(self.change_ID)),
            ("newValue"     , temp_value),
            ("success"      , self.bool_to_int(success)),
        ])
        mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

        return success


    def set_humidity_value(self, humi_value):
        """
        Updates the humidity set value.

        :param humi_value: The new humidity set value.
        """
        data = {
            "humi": {
                "group": "loop",
                "enable": True,
                "set_value": humi_value,
                "range": [10, 95]  # Assuming valid humidity range
            }
        }

        success, response = self.execute_command("constants/constant_1", data=data, method="POST")
        pprint.pprint(response)
        time.sleep(1)

        dateTime = datetime.now(timezone.utc)
        sensorIDPost = "CHNG"
        self.change_ID = 11  # Change ID for Humidity Set

        # Log the change
        sensorDictionary = OrderedDict([
            ("dateTime"     , str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"     , self.change_ID),
            ("changeLabel"  , self.change_mapping.get(self.change_ID)),
            ("newValue"     , humi_value),
            ("success"      , self.bool_to_int(success)),
        ])
        mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

        return success


    def start_constant_mode(self):
        """
        Starts the chamber in Constant Mode.

        :return: Success status (True/False)
        """
        data = {"group": "constant"}

        success, response = self.execute_command("operations/start_constant", data=data, method="POST")
        pprint.pprint(response)
        time.sleep(1)

        dateTime       = datetime.now(timezone.utc)
        sensorIDPost   = "CHNG"
        self.change_ID = 20  # Change ID for Constant Mode Start

        # Log the change
        sensorDictionary = OrderedDict([
            ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"     , self.change_ID),
            ("changeLabel"  , self.change_mapping.get(self.change_ID)),
            ("newValue"     , -100),
            ("success"      , self.bool_to_int(success)),
            ])

        mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

        return success


    def change_temperature(self,temp_value):
        self.set_temperature_value( temp_value)
        self.start_constant_mode()
        self.get_and_write_summary()


    def change_humdity(self,humi_value):
        self.set_humidity_value(humi_value)
        self.start_constant_mode()
        self.get_and_write_summary()


    def change_temperature_and_humdity(self,temp_value,humi_value):
        self.set_temperature_value( temp_value)
        self.set_humidity_value(humi_value)
        self.start_constant_mode()
        self.get_and_write_summary()


    class Routine:
        """Routine for controlling temperature and humidity."""

        def __init__(self,*,
                    chamber, 
                    mode: str,  # "uniform" or "custom"
                    symmetrical_converging: bool = False,
                    major_variable: str,
                    temperature_padding: float,
                    humidity_padding: float,
                    still_time: int = 10,
                    wait_time: int = 5,
                    is_forced: bool,
                    **kwargs
                    ):
    

            
            if major_variable.lower() not in ["temperature", "humidity"]:
                raise ValueError("major_variable must be 'temperature' or 'humidity'.")       
            
            if mode.lower() not in ["uniform", "custom"]:
                raise ValueError("mode must be 'uniform' or 'custom'.") 


            self.mode                   = mode
            self.symmetrical_converging = symmetrical_converging
            self.major_variable         = major_variable.lower()
            self.temperature_padding    = temperature_padding
            self.humidity_padding       = humidity_padding
            self.is_forced              = is_forced
            self.still_time             = still_time
            self.wait_time              = wait_time



            self.routine_mapping = {
                    0: "Routine Initiated",
                    1: "Routine Started",
                    2: "Routine Ended",            
                    10: "Routine Holding",            
                    11: "Routine Holding – Waypoint Unreached",
                }
            
            dateTime              = datetime.now(timezone.utc)
            sensorIDPost          = "RTNCHG"
            self.change_ID        = 0  
            self.routine_iteraion = 0

            # Log the change
            sensorDictionary = OrderedDict([
                ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("changeID"     , self.change_ID),
                ("changeLabel"  , self.routine_mapping.get(self.change_ID)),
                ("iteration"    , self.routine_iteraion),
                ("success"      , 1),
                ])
            mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

            if mode.lower() == "uniform":
                print()
                print("Chamber in Uniform Mode")
                print()
                
                
                self.uniform_mode = True
                print("Generating uniform waypoints...")

                temperature_start      = kwargs.get("temperature_start")
                temperature_end        = kwargs.get("temperature_end")
                temperature_increment  = kwargs.get("temperature_increment")

                humidity_start         = kwargs.get("humidity_start")
                humidity_end           = kwargs.get("humidity_end")
                humidity_increment     = kwargs.get("humidity_increment")


            if mode.lower() == "custom":
                print()
                print("Chamber in Custom Mode")
                print()

                self.uniform_mode = False
                print("Generating custom waypoints...")

                temperature_list    = kwargs.get("temperature_list")
                humidity_list       = kwargs.get("humidity_list")
                
                print(f"Temperature List: {temperature_list}")
                print(f"Humidity List: {humidity_list}")

                temperature_start     = temperature_list[0]
                temperature_end       = temperature_list[-1]
                temperature_increment = round((temperature_end - temperature_start) / (len(temperature_list) - 1), 2)

                humidity_start      = humidity_list[0]
                humidity_end        = humidity_list[-1]
                humidity_increment  = round((humidity_end - humidity_start) / (len(humidity_list) - 1), 2)

                self.temperature_list = temperature_list
                self.humidity_list    = humidity_list



            # Validate temperature and humidity ranges  
            if temperature_increment == 0 or humidity_increment == 0:
                raise ValueError("Increment values cannot be zero.")

            # Check temperature increment direction
            if (temperature_end - temperature_start) * temperature_increment < 0:
                raise ValueError("Temperature increment direction does not match start and end values.")

            # Check humidity increment direction
            if (humidity_end - humidity_start) * humidity_increment < 0:
                raise ValueError("Humidity increment direction does not match start and end values.")

            self.temperature_start      = temperature_start
            self.temperature_end        = temperature_end
            self.temperature_increment  = temperature_increment

            self.humidity_start         = humidity_start
            self.humidity_end           = humidity_end
            self.humidity_increment     = humidity_increment

            sensorIDPost     = "RTNDT"
            sensorDictionary = OrderedDict([
                ("dateTime"            ,  str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("majorVariable"       ,  major_variable.lower()),
                ("temperatureStart"    ,  temperature_start),
                ("temperatureEnd"      ,  temperature_end),
                ("temperatureIncrement",  temperature_increment),
                ("temperaturePadding"  ,  temperature_padding),
                ("humidityStart"       ,  humidity_start),
                ("humidityEnd"         ,  humidity_end),
                ("humidityIncrement"   ,  humidity_increment),
                ("humidityPadding"     ,  humidity_padding),
                ("isForced"            ,  chamber.bool_to_int(is_forced)),
                ("stillTime"           ,  still_time),
                ("waitTime"            ,  wait_time),
                ])
            
            mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)
            time.sleep(1)
            self._generate_waypoints()


        def _create_log_entry(self, temperature: float, humidity: float, humidity_controlled: bool) -> Dict:
            """Creates a log entry with padding and control parameters."""
            return {
                'temperature': temperature,
                'humidity': humidity,
                'humidity_controlled': humidity_controlled,                
                'temperature_padding': self.temperature_padding,
                'humidity_padding': self.humidity_padding,
                'is_forced': self.is_forced,
                'still_time': self.still_time,       
                'wait_time': self.wait_time
            }


        def append_entry(self, temp: float, humid: float) -> None:
            if self.check_entry_validity(temp,humid):
                humidity_controlled = self.check_humidity_controlled(temp, humid)
                entry = self._create_log_entry(temp, humid,humidity_controlled)
                print(f"Generating entry for Temperature: {temp}, Humidity: {humid}, Humidity Controlled: {humidity_controlled}")
                self.routine_log.append(entry)
            else: 
                print(f"Skipping entry for Temperature: {temp}, Humidity: {humid} due to invalidity.")            

        def _generate_waypoints(self) -> None:
            """Generates the list of control waypoints."""

            print("Generating control routine waypoints...")
            self.routine_log = []
         

            # THIS IS ALL YOU NEED
            temp_range  = self._generate_range(variable="temperature")
            humid_range = self._generate_range(variable="humidity")
            print(temp_range)
            print(humid_range)

            print(f"Generating control routine. Major variable: {self.major_variable}")

            if self.major_variable == "temperature":
                for temp in temp_range:
                    for humid in humid_range:
                        self.append_entry(temp, humid)

            if self.major_variable == "humidity":
                for humid in humid_range:
                    for temp in temp_range:
                        self.append_entry(temp, humid)

            print("Waypoints generated.\n")


        def _generate_range(self, variable: str) -> List[float]:

            if variable == "temperature":
                start = self.temperature_start
                end   = self.temperature_end
                step  = self.temperature_increment
            
            if variable == "humidity":
                start = self.humidity_start
                end   = self.humidity_end
                step  = self.humidity_increment


            """Helper to generate inclusive ranges safely."""
            if step == 0:
                raise ValueError("Step size cannot be zero.")
            if (start < end and step < 0) or (start > end and step > 0):
                raise ValueError("Step size sign does not move towards end value.")

      
            if self.mode== "uniform":
                current = start
                max_iterations = 10000
                iterations = 0
                range_list = []

                if step > 0:    
                    while current <= end:
                        range_list.append(round(current, 2))
                        current += step
                        iterations += 1
                        if iterations > max_iterations:
                            raise RuntimeError("Exceeded maximum iterations (possible infinite loop).")
                else:
                    while current >= end:
                        range_list.append(round(current, 2))
                        current += step
                        iterations += 1
                        if iterations > max_iterations:
                            raise RuntimeError("Exceeded maximum iterations (possible infinite loop).")

            if self.mode == "custom":
                if variable == "temperature":
                    range_list =   self.temperature_list
                if variable == "humidity":
                    range_list =   self.humidity_list

            if len(range_list) == 1:
                return range_list  # Return single value as a list
            
            if self.symmetrical_converging:
                # Ensure the last value is included if it matches the end
                values = list(range_list)
                result = []

                left = 0
                right = len(values) - 1
                while left <= right:
                    if right != left:
                        result.append(values[right])
                    result.append(values[left])
                    left += 1
                    right -= 1
                return result
            
            else:
                return range_list


        def print_routine(self) -> None:
            dateTime          = datetime.now(timezone.utc)
            # Format the timestamp for filename use
            timestamp = dateTime.strftime('%Y%m%d%H%M%S%f')  # safer filename format
            filename = f"routine{timestamp}.json"

            print("Routine Waypoints:")
            print(f"Routine Log Filename: {filename}")

            # Ensure the output directory exists
            output_dir = os.path.join(dataFolder, nodeID, "routines")
            os.makedirs(output_dir, exist_ok=True)

            # Construct the full output path
            output_path_timestamped = os.path.join(output_dir, filename)

            try:
                with open(output_path_timestamped, 'w') as f:
                    json.dump(self.routine_log, f, indent=2)
                print(f"Routine log saved to {output_path_timestamped}")
            except Exception as e:
                print(f"❌ Failed to save file: {e}")
            
            for entry in self.routine_log:
                print(entry)
            

        def check_entry_validity(self,temp,hum) -> bool:
            """Check if the entry is valid based on padding and forced conditions."""
            # Major Square for viabile climate conditions 
            return self.is_inside_square((-20,10), (40,95), (temp,hum),include_border=True)
                
        def check_humidity_controlled(self,temp,hum) -> bool:
            return any([\
                        self.is_inside_square(          (15,15), (85,95), (temp,hum)), 
                        self.is_inside_square(          (40,10), (85,15), (temp,hum)),
                        self.is_inside_square(           (5,15), (15,40), (temp,hum)),
                        self.is_inside_triangle((5,40), (15,40), (15,60), (temp,hum)),
                        self.is_inside_triangle((5,15), (15,40), (40,10), (temp,hum)),
                        ])

        def is_inside_square(self, climateBL, climateTR, climateTest, include_border=True):
            """
            Parameters:
            - climateBL: Bottom-left corner (minTemp, minHum)
            - climateTR: Top-right corner (maxTemp, maxHum)
            - climateTest: Point to check (temp, hum)
            - include_border: If True, borders are considered inside
            """
            # Normalize coordinates in case corners are swapped
            minTemp = min(climateBL[0], climateTR[0])
            maxTemp = max(climateBL[0], climateTR[0])
            minHum  = min(climateBL[1], climateTR[1])
            maxHum  = max(climateBL[1], climateTR[1])
            testTemp, testHum = climateTest

            if include_border:
                return (minTemp <= testTemp <= maxTemp) and (minHum <= testHum <= maxHum)
            else:
                return (minTemp < testTemp < maxTemp) and (minHum < testHum < maxHum)

        def area(self, temp1, hum1, temp2, hum2, temp3, hum3):
            return abs((temp1 * (hum2 - hum3) +
                        temp2 * (hum3 - hum1) +
                        temp3 * (hum1 - hum2)) / 2.0)

        def is_inside_triangle(self, climate01, climate02, climate03, climateTest,include_border=True):
            temp01, hum01 = climate01
            temp02, hum02 = climate02
            temp03, hum03 = climate03
            tempTest, humTest = climateTest

            total_area = self.area(temp01, hum01, temp02, hum02, temp03, hum03)
            area1 = self.area(tempTest, humTest, temp02, hum02, temp03, hum03)
            area2 = self.area(temp01, hum01, tempTest, humTest, temp03, hum03)
            area3 = self.area(temp01, hum01, temp02, hum02, tempTest, humTest)

            if include_border:
                return abs((area1 + area2 + area3) - total_area) <= 0
            else:
                return abs((area1 + area2 + area3) - total_area) < 0

        def run_summary_during_sleep(self, chamber, sleepTime):
            start_time = time.time()
            time.sleep(10)
            while (time.time() - start_time) < sleepTime:
                chamber.get_and_write_summary()
                print(f"Sleeping for {sleepTime} seconds, elapsed: {time.time() - start_time:.2f} seconds")
                time.sleep(10)
      

        def run_routine(self,chamber) -> None:
            """Run the generated routine log."""
            print("Routine Waypoints:")
            self.routine_iteraion = 0


            dateTime          = datetime.now(timezone.utc)
            sensorIDPost      = "RTNCHG"
            self.change_ID    = 1 

            # Log the change
            sensorDictionary = OrderedDict([
                ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("changeID"     , self.change_ID),
                ("changeLabel"  , self.routine_mapping.get(self.change_ID)),
                ("iteration"    , self.routine_iteraion),
                ("success"      , 1),
                ])

            mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)
            self.routine_length = len(self.routine_log)

            for entry in self.routine_log:
                
                self.routine_iteraion = self.routine_iteraion +1
                print("--------------------------------------------------------------------------")
                print("Setting Way Point #: " + str(self.routine_iteraion) + "/" + str(self.routine_length) + " " +  str(entry))


                dateTime          = datetime.now(timezone.utc)
                sensorIDPost      = "RTNPRGV2"

                # Log the change
                sensorDictionary = OrderedDict([
                    ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                    ("rotuingPercentage" , 100*(self.routine_iteraion/self.routine_length)),
                    ("rotuingIteration"  , self.routine_iteraion),
                    ("rotuingLength"     , self.routine_length),
                    ("entryTemperature"  , entry['temperature']),
                    ("entryHumidity"     , entry['humidity']),       
                    ("entryHC"           , chamber.bool_to_int(entry['humidity_controlled'])),      # This is 1 or Zero but given in as True or False              
                    ("success"           , 1),
                    ])

                mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

                chamber.change_temperature_and_humdity(entry['temperature'],entry['humidity'])
                
                startTime = time.time()
                wayPointAchieved = True

                if entry['humidity_controlled']:
                    while (abs(entry['temperature'] - chamber.temperature_process_value) > entry['temperature_padding'] or \
                        abs(entry['humidity'] - chamber.humidity_process_value) > entry['humidity_padding']):
                        print(
                            f"Still Seeking Waypoint #{self.routine_iteraion}/{self.routine_length} "
                            f"@ elapsed Time: {time.time() - startTime:.2f}/{self.wait_time} secs - Entry: {entry}"
                        )
                        time.sleep(10)
                        chamber.get_and_write_summary()
                        if time.time() - startTime > self.wait_time:
                            print("Wait time exceeded, Way point not achieved: breaking out of loop.")
                            wayPointAchieved = False
                            break

                else:
                    while (abs(entry['temperature'] - chamber.temperature_process_value) > entry['temperature_padding']) :
                        print(
                            f"Still Seeking Waypoint #{self.routine_iteraion}/{self.routine_length} "
                            f"@ elapsed Time: {time.time() - startTime:.2f}/{self.wait_time} secs - Entry: {entry}"
                        )
                        time.sleep(10)
                        chamber.get_and_write_summary()

                        if time.time() - startTime > self.wait_time:
                            print("Wait time exceeded, Way point not achieved: breaking out of loop.")
                            wayPointAchieved = False
                            break
                
                if wayPointAchieved:              
                    print("Way point achieved: ")
                    self.change_ID    = 10 
                else:
                    print("Way point not achieved: ")
                    self.change_ID    = 11


                dateTime          = datetime.now(timezone.utc)
                sensorIDPost      = "RTNCHG"

                # Log the change
                sensorDictionary = OrderedDict([
                    ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                    ("changeID"     , self.change_ID),
                    ("changeLabel"  , self.routine_mapping.get(self.change_ID)),
                    ("iteration"    , self.routine_iteraion),
                    ("success"      , 1),
                    ])

                mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)
                
                self.run_summary_during_sleep(chamber, entry['still_time'])


            dateTime          = datetime.now(timezone.utc)
            sensorIDPost      = "RTNCHG"
            self.change_ID    = 2 

            # Log the change
            sensorDictionary = OrderedDict([
                ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
                ("changeID"     , self.change_ID),
                ("changeLabel"  , self.routine_mapping.get(self.change_ID)),
                ("iteration"    , self.routine_iteraion),
                ("success"      , 1),
                ])

            mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)
            
            print("Routine Ran")

            time.sleep(30)
            
            chamber.stop_chamber()
            print("Chamber Stopped")