
from getmac import get_mac_address
import serial.tools.list_ports


def findPort(find):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        currentPort = str(p)
        if(currentPort.endswith(find)):
            return(currentPort.split(" ")[0])


def findDuePort():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        currentPort = str(p[2])
        if(currentPort.find("PID=2341")>=0):
            return(p[0])

def findNanoPorts():
    ports = list(serial.tools.list_ports.comports())
    outPorts = []
    for p in ports:
        currentPort = str(p)
        if(currentPort.endswith("FT232R USB UART")):
            outPorts.append(currentPort.split(" ")[0])

    return outPorts

def findSabrentPorts():
    ports = list(serial.tools.list_ports.comports())
    outPorts = []
    for p in ports:
        currentPort = str(p[2])
        if(currentPort.find("PID=067B")>=0):
            outPorts.append(str(p[0]).split(" ")[0])
    return outPorts

def findOzonePort():
    ports = list(serial.tools.list_ports.comports())
    ozonePort = []
    for p in ports:
        currentPort = str(p[2])
        if(currentPort.find("PID=067B")>=0):
            ozonePort.append(str(p[0]).split(" ")[0])
    return ozonePort

def findIPSPorts():
    ports = list(serial.tools.list_ports.comports())
    ipsPorts = []
    for p in ports:
        currentPort = str(p[2])
        if(currentPort.find("PID=10C4")>=0):
            ipsPorts.append(str(p[0]).split(" ")[0])
    return ipsPorts
  
def findAirmarPort():
    ports = list(serial.tools.list_ports.comports())
    ozonePort = []
    for p in ports:
        currentPort = str(p[2])
        if(currentPort.find("PID=067B")>=0):
            ozonePort.append(str(p[0]).split(" ")[0])
    return ozonePort
  


def find_serial_port_by_location(target_location):
    """Finds the serial port associated with a given USB physical location.

    Args:
        target_location: The USB physical location string (e.g., '1-1.1').

    Returns:
        The serial port device name (e.g., '/dev/ttyUSB0') or None if not found.
    """
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if hasattr(port, 'location') and port.location == target_location:
            print(f"Found matching port: {port.device}")
            print(f"Description: {port.description}")
            print(f"HWID: {port.hwid}")
            print(f"Serial Number: {port.serial_number}")
            return port.device

    print(f"No port found for location: {target_location}")
    return None





def findMacAddress():
    macAddress= get_mac_address(interface="eth0")
    if (macAddress!= None):
        return macAddress.replace(":","")

    macAddress= get_mac_address(interface="docker0")
    if (macAddress!= None):
        return macAddress.replace(":","")

    macAddress= get_mac_address(interface="enp1s0")
    if (macAddress!= None):
        return macAddress.replace(":","")

    macAddress= get_mac_address(interface="wlan0")
    if (macAddress!= None):
        return macAddress.replace(":","")

    macAddress= get_mac_address(interface="en0")
    if (macAddress!= None):
        return macAddress.replace(":","")

    return "xxxxxxxx"


macAddress            = findMacAddress()


baseFolder                = "/home/teamlary/"

if macAddress == "2ed3ff75af22":
    baseFolder                = "/Users/lakitha/"



dataFolderReference       = baseFolder + "mintsData/reference"
dataFolderMQTTReference   = baseFolder + "mintsData/referenceMQTT"
dataFolder                = baseFolder + "mintsData/raw"
hostsDataFolder           = baseFolder + "mintsDataHosts/raw"
dataFolderMQTT            = baseFolder + "mintsData/rawMQTT"
statusJsonFile            = baseFolder + "status/status.json"
hostsStatusJsonFile       = baseFolder + "hostStatus/status.json"
gpsOnJsonFile             = baseFolder + "statusFiles/gpsOn.json"
gpsOffJsonFile            = baseFolder + "statusFiles/gpsOff.json"


# duePort               = findDuePort()
# nanoPorts             = findNanoPorts()
# ozonePort             = findOzonePort()
# # ipsPorts              = findIPSPorts()
# show2Port             = findPort("CP2104 USB to UART Bridge Controller")


latestOn              = True
airmarPort            = find_serial_port_by_location('1-1.1')
inir2me5Port          = find_serial_port_by_location('1-1.2')
sjh5Port              = find_serial_port_by_location('1-1.3')


# For MQTT 
mqttOn                = True

mqttCredentialsFile   = 'mintsXU4/credentials.yml'
hostsFile             = 'mintsXU4/hosts.yml'
locationsFile         = 'mintsXU4/locations.yml'

mqttBroker            = "mqtt.circ.utdallas.edu"
mqttPort              =  8883  # Secure port

gpsPort               = findPort("GPS/GNSS Receiver")




if __name__ == "__main__":
    # the following code is for debugging
    # to make sure everything is working run python3 mintsDefinitions.py 
    print("Mac Address                : {0}".format(macAddress))
    print("Data Folder Reference      : {0}".format(dataFolderReference))
    print("Data Folder Raw            : {0}".format(dataFolder))
    print("Latest On                  : {0}".format(latestOn))
    print("MQTT On                    : {0}".format(mqttOn))
    print("MQTT Credentials File      : {0}".format(mqttCredentialsFile))
    print("MQTT Broker and Port       : {0}, {1}".format(mqttOn,mqttPort))
    
    print()
    print("#-------------------------------------------#")
    print("Airmar Port                : {0}".format(airmarPort))
    print("SJH5 Port                  : {0}".format(sjh5Port))
    print("INIR2ME5 Port              : {0}".format(inir2me5Port))
