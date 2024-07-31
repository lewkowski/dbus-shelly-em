#!/usr/bin/env python
 
# import normal packages
import platform 
import logging
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file
 
# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

# Class to handle information for each Shelly EM Channel
class ShellyEMChannel:
  def __call__(self, config, shellynum, channel, shellyserial):


    self.channel = channel
    customname = config['DEFAULT']['CustomName']
    
    # Read the config and set up variables
    shellysectionname = 'ShellyEM' + shellynum
    channelsectionname = 'ShellyEM' + shellynum + 'Ch' + channel

    servicename = config[channelsectionname]['DbusService']
    deviceinstance = config[shellysectionname]['Deviceinstance']
                                       
    self._connection = 'Shelly EM HTTP JSON service'
    self._productname = 'Shelly EM'
    self._shellyserial = shellyserial

    # Create the DbusService Object
    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._paths = paths
    
    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', self._connection)
    
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
    #self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
    self._dbusservice.add_path('/ProductId', 45069) # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
    #self._dbusservice.add_path('/ProductId', 0xB023) # id needs to be assigned by Victron Support current value for testing
    self._dbusservice.add_path('/DeviceType', 345) # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
    self._dbusservice.add_path('/ProductName', self._productname)
    self._dbusservice.add_path('/CustomName', customname)    
    self._dbusservice.add_path('/Latency', None)    
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)
    self._dbusservice.add_path('/Role', 'grid')
    self._dbusservice.add_path('/Position', 0) # normaly only needed for pvinverter
    self._dbusservice.add_path('/Serial', self._shellyserial)
    self._dbusservice.add_path('/UpdateIndex', 0)
    
    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
    pass    


# Reads both channels of the Shelly EM and updates the configured dbus service
class DbusShellyEMService:

  def __init__(self, config, shellynum, productname='Shelly EM', connection='Shelly EM HTTP JSON service'):
  
    # Set the shellysectionname for this Shelly EM service
    shellysection = 'ShellyEM' + str(shellynum)
    
    # Create the URL to retrieve the Shelly EM Status JSON packet
    self._URL = self._getShellyStatusUrl()

    # Get the Shelly MAC address as serial number
    shellyserial = self._getShellySerial()

    # Store our Shelly Channels in a list of channels 
    self._shellychannels = []
    # Create the Shelly Channels and store in the list, the device supports up to 2 channels
    if (config[shellysection]['Channel1Active']):
      self._shellychannels.append(ShellyEMChannel(config, shellynum, 1, shellyserial))
    if (config[shellysection]['Channel2Active']):
      self._shellychannels.append(ShellyEMChannel(config, shellynum, 2, shellyserial))

    # last update
    self._lastUpdate = 0
    # add _update function 'timer'
    gobject.timeout_add(1000, self._update) # pause 1000ms before the next request
    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)
 
  # Get the Shelly EM Serial number from the Shelly EM device
  def _getShellySerial(self):
    meter_data = self._getShellyData()  

    if not meter_data['mac']:
        raise ValueError("Response does not contain 'mac' attribute")
    serial = meter_data['mac']

    return serial
 
  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']
    
    if not value: 
        value = 0
    
    return int(value)
  
  # Creates the URL to use to connect to the Shelly EM and retrieve the status information
  def _getShellyStatusUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    
    if accessType == 'OnPremise': 
        URL = "http://%s:%s@%s/status" % (config['ONPREMISE']['Username'], config['ONPREMISE']['Password'], config['ONPREMISE']['Host'])
        URL = URL.replace(":@", "")
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    
    return URL
    
  # Connects to the Shelly EM via the URL and returns the JSON status packet
  def _getShellyData(self):
    meter_data = None

    # Make HTTP request to Shelly EM
    meter_r = requests.get(url = self._URL)
    
    # Check for response
    if not meter_r:
        raise ConnectionError("No response from Shelly EM - %s" % (self._URL))
    
    # Pull out JSON response from HTTP request
    meter_data = meter_r.json()     
    
    # Check for JSON packet
    if not meter_data:
        raise ValueError("Converting response to JSON failed")
    
    return meter_data
 
 
  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):  

    try:
       #get data from Shelly em
       meter_data = self._getShellyData()
      
      # Call update() on Shelly Channel(s) to update
      
       
       
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True
 
  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change
 


def main():
  #configure logging
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.INFO,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])
 
  try:
      logging.info("Start")
  
      # Retrive the configuration information
      config = configparser.ConfigParser()
      config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

      numberofshellys = config['DEFAULT']['NumberOfShellys']

      if (numberofshellys <= 0):
        # No Shelly devices assigned, throw an exception
        raise ValueError("Number of Shelly devices specified in config file is not allowed")

      from dbus.mainloop.glib import DBusGMainLoop

      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)
     
      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + 'KWh')
      _a = lambda p, v: (str(round(v, 1)) + 'A')
      _w = lambda p, v: (str(round(v, 1)) + 'W')
      _v = lambda p, v: (str(round(v, 1)) + 'V')   
     
      ### Start our Shelly EM Service(s)

      ShellyEMServices = []
      # Create a list of our Shelly Service(s)
      for i in range(1, numberofshellys+1):
        ShellyEMServices.append(DbusShellyEMService (config, ShellyNum = i))

      if (numberofshellys > 1):
        pass
        
      # pvac_output = DbusShellyemService(
      #   servicename='com.victronenergy.pvinverter',
      #   paths={
      #     '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh}, # energy bought from the grid
      #     '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh}, # energy sold to the grid
      #     '/Ac/Power': {'initial': 0, 'textformat': _w},
          
      #     '/Ac/Current': {'initial': 0, 'textformat': _a},
      #     '/Ac/Voltage': {'initial': 0, 'textformat': _v},
          
      #     '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
      #     #'/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
      #     #'/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
      #     '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
      #     #'/Ac/L2/Current': {'initial': 0, 'textformat': _a},
      #     #'/Ac/L3/Current': {'initial': 0, 'textformat': _a},
      #     '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
      #     #'/Ac/L2/Power': {'initial': 0, 'textformat': _w},
      #     #'/Ac/L3/Power': {'initial': 0, 'textformat': _w},
      #     '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
      #     #'/Ac/L2/Energy/Forward': {'initial': 0, 'textformat': _kwh},
      #     #'/Ac/L3/Energy/Forward': {'initial': 0, 'textformat': _kwh},
      #     '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
      #     #'/Ac/L2/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
      #     #'/Ac/L3/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
      #   })
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()    

  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
