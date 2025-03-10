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
            sensorIDPost                        = "HMDTY"
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
            self.operation          = status["operation"]
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

    def recordChamberData(self,data): 
       # Execute command and retrieve data

        print(json.dumps(data, indent=4))
        print("---------------------------------------")
        self.chamberDateTime = data["conditions"]["status"]["datetime"]


    def execute_command(self, command):
        """
        Executes a command on the chamber.

        :param command: The command to execute.
        :return: Response JSON data or error message.
        """
        full_url = f"{self.url}/api/v4/chambers/{self.chamber_index}/{command}"
        print(full_url)

        rsp = requests.get(full_url, headers=self.headers)

        if rsp.status_code == 200:
            return True, rsp.json()  # Return JSON data
        else:
            print({"error": f"Failed with status code {rsp.status_code}"})

            return False, "";

    def extract_dap(self, data):
        """Extracts and stores the dap data from the API response."""
        try:
            dap_data = data["conditions"]["dap"]

            # Extract and convert 'type' to 1 (digital) or 0 (analog)
            self.dap_type = 1 if dap_data.get("type") == "digital" else 0

            # Extract and convert 'value' to 1 (true) or 0 (false)
            self.dap_value = 1 if dap_data.get("value") else 0

            # Extract 'group' (no conversion needed for 'group')
            self.dap_group = dap_data.get("group", None)

            # Print extracted dap data
            print("\nExtracted DAP Data:")
            print(f"Group: {self.dap_group}")
            print(f"Type (converted): {self.dap_type}")
            print(f"Value (converted): {self.dap_value}")

        except KeyError as e:
            print(f"Error extracting dap data: {e}")
            self.dap_group = self.dap_type = self.dap_value = None


    def extract_time_signal_1(self, data):
        """Extracts and stores the time_signal_1 data from the API response."""
        try:
            time_signal_data = data["conditions"]["time_signal_1"]

            # Extract and convert 'type' to 1 (digital) or 0 (analog)
            self.time_signal_type = 1 if time_signal_data.get("type") == "digital" else 0

            # Extract and convert 'value' to 1 (true) or 0 (false)
            self.time_signal_value = 1 if time_signal_data.get("value") else 0

            # Extract 'group' (no conversion needed for 'group')
            self.time_signal_group = time_signal_data.get("group", None)

            # Print extracted time signal data
            print("\nExtracted Time Signal 1 Data:")
            print(f"Group: {self.time_signal_group}")
            print(f"Type (converted): {self.time_signal_type}")
            print(f"Value (converted): {self.time_signal_value}")

        except KeyError as e:
            print(f"Error extracting time_signal_1 data: {e}")
            self.time_signal_group = self.time_signal_type = self.time_signal_value = None

    def extract_humidity(self, data):
        """Extracts humidity data and stores it in individual variables."""
        try:
            humidity_data = data["conditions"]["humi"]

            # Store individual humidity components
            self.humi_set_value = humidity_data.get("set_value", None)
            self.humi_process_value = humidity_data.get("process_value", None)
            self.humi_power = humidity_data.get("power", None)
            self.humi_units = humidity_data.get("units", None)
            
            # Convert enable to 1 or 0
            self.humi_enable = 1 if humidity_data.get("enable", False) else 0

            # Print extracted humidity data
            print("\nExtracted Humidity Data:")
            print(f"Set Value: {self.humi_set_value}")
            print(f"Process Value: {self.humi_process_value}")
            print(f"Power: {self.humi_power}")
            print(f"Units: {self.humi_units}")
            print(f"Enable (converted): {self.humi_enable}")

        except KeyError as e:
            print(f"Error extracting humidity data: {e}")
            self.humi_set_value = self.humi_process_value = self.humi_power = self.humi_units = self.humi_enable = None

    def extract_temp(self, data):
        """Extracts temperature data and stores it in individual variables."""
        try:
            temp_data = data["conditions"]["temp"]

            # Store individual temp components
            self.temp_set_value = temp_data.get("set_value", None)
            self.temp_process_value = temp_data.get("process_value", None)
            self.temp_power = temp_data.get("power", None)
            self.temp_units = temp_data.get("units", None)
            
            # Convert enable to 1 or 0
            self.temp_enable = 1 if temp_data.get("enable", False) else 0

            # Print extracted temperature data
            print("\nExtracted Temperature Data:")
            print(f"Set Value: {self.temp_set_value}")
            print(f"Process Value: {self.temp_process_value}")
            print(f"Power: {self.temp_power}")
            print(f"Units: {self.temp_units}")
            print(f"Enable (converted): {self.temp_enable}")

        except KeyError as e:
            print(f"Error extracting temp data: {e}")
            self.temp_set_value = self.temp_process_value = self.temp_power = self.temp_units = self.temp_enable = None
    
    
    def extract_constant_key(self, data):
        """Extracts and stores the numeric part of the constant key from API response."""
        try:
            constant_key = data["conditions"]["status"].get("constant_key", "N/A")
            # Extract the numeric part after the underscore
            if constant_key != "N/A":
                self.constant_key = constant_key.split('_')[-1]
            else:
                self.constant_key =  None
            
            print(f"\nExtracted Constant Key ID: {self.constant_key}")
        except KeyError as e:
            print(f"Error extracting constant key: {e}")
            self.constant_key = None
            

    
    def extract_datetime(self, data):
        """Extracts and stores datetime components from API response."""
        try:
            datetime_str = data["conditions"]["status"]["datetime"]
            dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

            # Store extracted values
            self.year = dt.year
            self.month = dt.month
            self.day = dt.day
            self.hour = dt.hour
            self.minute = dt.minute
            self.second = dt.second

            # Print extracted values
            print("\nExtracted Datetime Components:")
            print(f"Year: {self.year}")
            print(f"Month: {self.month}")
            print(f"Day: {self.day}")
            print(f"Hour: {self.hour}")
            print(f"Minute: {self.minute}")
            print(f"Second: {self.second}")

        except (KeyError, ValueError) as e:
            print(f"Error extracting datetime: {e}")
            self.year = self.month = self.day = self.hour = self.minute = self.second = None

    def extract_operation(self, data):
        """Extracts and stores the operation mode from the API response."""
        try:
            operation = data["conditions"]["status"]["operation"]

            if operation == "standby":
                self.operation = 0
            elif operation == "constant":
                self.operation = 1
            elif operation == "program":
                self.operation = 2
            else:
                self.operation = None  # Handle unexpected values

            # Print extracted status data
            print("\nExtracted Operation Data:")
            print(f"Operation (converted): {self.operation}")


        except KeyError as e:
            print(f"Error extracting status data: {e}")
            self.operation = None


