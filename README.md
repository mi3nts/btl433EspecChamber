# btl433EspecChamber
Contains firmware to run the ESPEC BTL433 Chmaber 

## Operation


### The water supply 
* Pressurize the tank to 18 psi using an air pump
* Fill in the tank (5% Distilled water)
* Connect the appropriate tubing
* Turn the pump on using the toggle switch on top

### Dry Air Purge 




The chamber can handle 2 different modes. Firstly the static mode where you can just assign specific temperature and humidities for it to aim for. Secondly a programmable mode where we can program it to got to different climatic conditions at given time stamps dynamicallly. 

**FYI: Make sure humidity mode is enabled if planning on working with assigned humidities.** 

## Firmware 
Check logs to examine what needs to be put on influx - 
How can I carefully control the chamber to achive the walk in Temperature and Humidity space 

# BTL433 ESPEC Chamber Operating Instructions

## Startup Procedure

1. **Enable Dry Air Purge:**
   - Turn on the air supply to the dry air purge system.
   - Plug in the dry air purge unit.

2. **Prepare Pressurized Water Tank:**
   - Check the water level in the pressurized water tank.
   - Plug in the pressurized water tank.
   - Turn on the pressurized water tank.

3. **Power the Chamber:**
   - Plug in the ESPEC chamber.
   - Log in to the chamber interface via the SBC (Single Board Computer).
   - Upload and start the desired recipe.

---

## Shutdown Procedure

1. **Stop Chamber Operation:**
   - Log in to the chamber interface and stop any running recipe.

2. **Power Down and Disconnect:**
   - Turn off the pressurized water tank.
   - Unplug the pressurized water tank.
   - Unplug the dry air purge unit.
   - Unplug the chamber.
