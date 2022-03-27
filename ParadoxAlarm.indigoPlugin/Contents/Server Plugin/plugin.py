#! /usr/bin/env python2.6
# -*- coding: utf-8 -*-

"""
Author: GlennNZ

"""

import threading
import time as t
import asyncio
import logging
import builtins
import sys

from paradox import VERSION
from paradox.config import config
from paradox.exceptions import PAICriticalException
from paradox.interfaces.interface_manager import InterfaceManager
from paradox.lib.encodings import register_encodings
from paradox.paradox import Paradox

try:
    import indigo
except:
    pass



logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("Plugin.PAI")



class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"showDebugLevel"])
        except:
            self.logLevel = logging.INFO

        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))

        self.prefsUpdated = False
        self.logger.info(u"")
        self.logger.info(u"{0:=^130}".format(" Initializing New Plugin Session "))
        self.logger.info(u"{0:<30} {1}".format("Plugin name:", pluginDisplayName))
        self.logger.info(u"{0:<30} {1}".format("Plugin version:", pluginVersion))
        self.logger.info(u"{0:<30} {1}".format("Plugin ID:", pluginId))
        self.logger.info(u"{0:<30} {1}".format("Indigo version:", indigo.server.version))
        self.logger.info(u"{0:<30} {1}".format("Python version:", sys.version.replace('\n', '')))
        self.logger.info(u"{0:<30} {1}".format("Python Directory:", sys.prefix.replace('\n', '')))

        # Change to logging
        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self._paradox = Paradox(self)
        self._interface_manager = None

        ## sorry hacky !:)
        builtins.IPModule = ""


        self.connected = False
        self.deviceUpdate = False
        self.devicetobeUpdated =''

        self.ipaddress = self.pluginPrefs.get('ipaddress', '')
        self.port = self.pluginPrefs.get('port', 10000)
        self.ip150password = self.pluginPrefs.get('ip150password', 'paradox')
        self.pcpassword = self.pluginPrefs.get('pcpassword', 1234)

        self.labelsdueupdate = True
        self.debug1 = self.pluginPrefs.get('debug1', False)
        self.debug2 = self.pluginPrefs.get('debug2', False)
        self.debug3 = self.pluginPrefs.get('debug3', False)
        self.debug4 = self.pluginPrefs.get('debug4',False)
        self.debug5 = self.pluginPrefs.get('debug5', False)

        self.allSetUp = self.pluginPrefs.get("allSetUp", False)
        self.able_to_connect = self.allSetUp

        # main device to be updated as needed
        self.paneldate = ""
        self.battery = float(0)
        self.PowerVolts_DC = float(0)
        self.batterydc = float(0)
        self.area1Arm = "Disarmed"
        self.area2Arm = "Disarmed"
        self.producttype = ""
        self.firmware = ""
        self.IPModule = "Unknown"
        self.panelID = ""
        self.zoneNames = None

        self.triggers = {}

        self.add_config()


      #  self.connectAlarm()


        self.logger.info(u"{0:=^130}".format(" End Initializing New Plugin  "))
        ## Thread the paradox Library off...
        t = threading.Thread(target=self.connectAlarm,  daemon=True)
        t.start()


    async def exit_handler(self, signame=None):
        if signame is not None:
            logger.info(f"Captured signal {signame}. Exiting")
        if self._paradox:
            await self._paradox.disconnect()
            self._paradox = None
        if self._interface_manager:
            self._interface_manager.stop()
            self._interface_manager = None
        logger.info("Good bye!")

    async def run_loop(self):
        retry = 10
        while self._paradox is not None and self.able_to_connect:
            logger.debug("Starting. Run_Loop..")
            retry_time_wait = 10 ^ retry
            retry_time_wait = 30 if retry_time_wait > 30 else retry_time_wait

            try:
                if await self._paradox.full_connect():
                    retry = 1
                    await self._paradox.loop()
                else:
                    logger.error("Unable to connect to alarm")

                if self._paradox:
                    await asyncio.sleep(retry_time_wait)
            except ConnectionError as e:  # Connection to IP Module or MQTT lost
                self.logger.debug("Connection to panel lost: %s. Restarting" % str(e))
                await asyncio.sleep(retry_time_wait)
            except OSError:  # Connection to IP Module or MQTT lost
                self.logger.exception("Restarting")
                await asyncio.sleep(retry_time_wait)
            except PAICriticalException:
                self.logger.exception("PAI Critical exception. Stopping PAI")
                break
            except (KeyboardInterrupt, SystemExit):
                break  # break exits the retry loop
            except:
                self.logger.exception("Restarting")
                await asyncio.sleep(retry_time_wait)

            retry += 1

        self.logger.error("Exit run loop")
        if self._paradox:
            await self.exit_handler()

    def __del__(self):

        self.debugLog(u"__del__ method called.")
        indigo.PluginBase.__del__(self)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:
            self.logLevel = int(valuesDict.get("showDebugLevel", '5'))
            self.ipaddress = valuesDict.get('ipaddress', '')
            self.port = valuesDict.get('port', False)
            self.ip150password = valuesDict.get('ip150password', 'paradox')
            self.pcpassword = valuesDict.get('pcpassword', 1234)
            self.debugLog(u"User prefs saved.")

            self.able_to_connect = valuesDict.get('startConnection', False)
            self.allSetUp = valuesDict.get("allSetUp", False)
            self.debug1 = valuesDict.get('debug1', False)
            self.debug2 = valuesDict.get('debug2', False)
            self.debug3 = valuesDict.get('debug3', False)
            self.debug4 = valuesDict.get('debug4', False)
            self.debug5 = valuesDict.get('debug5', False)
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))
            self.logger.debug(u"User prefs saved.")
            self.logger.debug(u"Debugging on (Level: {0})".format(self.logLevel))
            self.add_config()




        return True


    # Start 'em up.
    def add_config(self):
    # IP connection, e.g. 192.168.1.2:10000:paradox
        config.load()
        #self.logger.debug(config)
        config.CONNECTION_TYPE = 'IP'
        if self.debug1 or self.debug2:
            config.LOGGING_LEVEL_CONSOLE = logging.DEBUG
            config.LOGGING_LEVEL_FILE = logging.DEBUG
        else:
            config.LOGGING_LEVEL_CONSOLE = logging.INFO
            config.LOGGING_LEVEL_FILE = logging.INFO

        if self.debug1:
            config.LOGGING_DUMP_PACKETS = True
            config.LOGGING_DUMP_MESSAGES = True
        else:
            config.LOGGING_DUMP_PACKETS = False
            config.LOGGING_DUMP_MESSAGES = False

        if self.debug2:
            config.LOGGING_DUMP_STATUS = True
            config.LOGGING_DUMP_EVENTS = True
        else:
            config.LOGGING_DUMP_STATUS = False
            config.LOGGING_DUMP_EVENTS = False

        config.IP_CONNECTION_HOST = str(self.ipaddress)
        config.IP_CONNECTION_PORT = int(self.port)
        config.IP_CONNECTION_PASSWORD = str(self.ip150password) #"paradox" #.encode("utf-8") #str(self.ip150password) #.encode()
        config.PASSWORD = str(self.pcpassword) # '1234'

       # self.logger.debug('using IP connection on %s:%s pass:%s', config.IP_CONNECTION_HOST, config.IP_CONNECTION_PORT, config.IP_CONNECTION_PASSWORD)

    # Shut 'em down.
    def deviceStopComm(self, dev):

        self.debugLog(u"deviceStopComm() method called.")
        #indigo.server.log(u"Stopping  device: " + dev.name)
        if dev.deviceTypeId == 'ParadoxMain':
            dev.updateStateOnServer('deviceIsOnline', value=False)
            self.able_to_connect = False    ## Disconnect from panel
            #self.logger.info("Disconnecting Alarm panel (if connected) given Main Device Stopping. ")
        if dev.deviceTypeId == "paradoxalarmMotion":
            if dev.enabled:
                dev.updateStateOnServer(key="onOffState", value=False)

    def connectAlarm(self):
        try:
            y = 0
            if self.able_to_connect == False:
                self.logger.info("Please setup connection settings in Plugin Config and enable Connection checkbox.")
            while True:
                self.sleep(0.5)
                y = y +1
                if y % 20 == 0:
                    self.logger.debug("Waiting Connection to be Enabled to start connection...")
                if y % 200 == 0:
                    self.logger.info(  "Please setup connection settings in Plugin Config and enable Connection checkbox.")
                    y = 0
                while self.able_to_connect:
                    self.logger.debug("Connecting Alarm in Alarm Thread")
                    self.logger.info(f"Starting Paradox Alarm Interface {VERSION}")
                    self.logger.debug(f"Config loaded from {config.CONFIG_FILE_LOCATION}")
                    self.logger.debug(f"Console Log level set to {config.LOGGING_LEVEL_CONSOLE}")
                    #self.logger.debug(f"Whole Config File Equal to {config}")
                    register_encodings()

                    interface_manager = InterfaceManager(self._paradox, config=config)
                    interface_manager.start()

                    self.logger.info("Started Interface Manager")
                    self._paradox.work_loop.run_until_complete(self.run_loop())
        except self.StopThread:
            self.logger.debug("StopThread send.  Ending")
        except:
            self.logger.exception("Caught Exception in Connect-Alarm Thread.  Restarting.")

    def dict_to_list(self, dic):  ##
        listdicts = []
        for k, v in dic.items():
            if isinstance(v, dict):
                listdicts.append(v)
        return listdicts

    def upzoneNames(self):
        panel = ""
        if self._paradox.panel != None:
            panel = self._paradox.panel.panel_labels
        if panel != "":
            if 'zone' in panel:
                self.zoneNames = self.dict_to_list(panel['zone'])
                #self.logger.debug("Zone:{}".format(self.zoneNames))
        if self.debug3:
            self.logger.debug("{}".format(self.zoneNames))

    ## Action Groups

    def runConcurrentThread(self):

        x =0
        updatemaindevice = t.time() + 15
        loginretry = 0
        try:

            while True:
                self.sleep(5)
                if self.zoneNames == None:
                    self.upzoneNames()
                self.updatemainDevice()
                self.sleep(30)
               # x =x +1
               # run_state = self._paradox.run_state
                #self.logger.info("RunState: "+str(run_state))
                #connection = self._paradox.connection
                #self.logger.info("Connection.connection: " + str(connection.connected))
                #if self._paradox != None:

                  #  if x % 10 == 0:
                     #   status = self._paradox.indigo_status
                    #    if status != None:
                            #self.logger.info("\nStatus: ".join([f'{key}: {value}' for key, value in status.items()]))
                          #  self.logger.info("\nStatus:  {} ".format(status))
                          #  self.logger.info("\nTroubles:  {}".format(status["troubles"]))
                           # self.logger.info("\nSystem:  {}".format(status["system"]))
                          #  self.logger.info("Zone Open:  {}".format(status["zone_open"]))
                  #  if x % 5 ==0:
                       # self.logger.debug("Running Partition Control")
                       # self.updatemainDevice()
                       # self.logger.info("{}".format(self._paradox.storage.get_container_object("partition", 1).items() ))
                       # self._paradox.work_loop.create_task(self._paradox.control_partition("1","DISARM"))

               # _paradox.handle_error_message("This is Error Message")
              #  loop.create_task()
               # _paradox.que_panel_command()
              #  completed = loop.run_until_complete(_paradox.control_partition("1","DISARM"))
              #  self.logger.info("Command Feedback:"+str(completed))
               # _paradox.que_panel_command("Spare_Bedroom","DISARM")
                # if self.connected == False:
                #     self.socket = self.connect_ip150socket(str(self.ipaddress), str(self.port))
                #     self.sleep(1)
                #     self.logger.info("Connecting to IP Module:" + self.ipaddress + " with Port:" + str(self.port))
                #     self.sleep(3)
                #
                # if self.connected:
                #     #    paradox.paradox(self, self.socket, "", 0, 3, Alarm_Event_Map, Alarm_Registry_Map)
                #     self.sleep(1)
                #     if not self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0):
                #         loginretry = loginretry +1
                #         self.logger.info(
                #             u"Failed to login & unlock to IP module, check if another app is using the port. Retrying... Attempt number: "+str(loginretry))
                #         self.socket.close()
                #         self.sleep(int(10*loginretry))
                #         self.connected = False
                #     else:
                #         self.logger.info("Logged into IP module successfully")
                #         self.connected = True
                #         loginretry = 0
                #
                # if self.connected:
                #     if self.labelsdueupdate:
                #         self.myAlarm.updateAllLabels("True", "True", 0)
                #         self.labelsdueupdate = False
                #     self.logger.debug(str(self.myAlarm.returnZoneNames()))
                #     self.myAlarm.updateZoneAndAlarmStatus("True", 0)
                #
                # while self.connected:
                #     self.myAlarm.keepAlive(0)
                #     #self.zoneNames = ""
                #     if self.labelsdueupdate:
                #         self.myAlarm.updateAllLabels("True","True",0)
                #         self.labelsdueupdate = False
                #         self.logger.debug("myAlarm.returnZoneNames"+str(self.myAlarm.returnZoneNames()))
                #     interrupt = self.myAlarm.testForEvents(0, 1, 0)
                #     #self.sleep(1)
                #     if interrupt == 1:
                #         interruptCountdown = 5
                #         interrupt = 0
                #         for x in range(0, interruptCountdown):
                #             if x % 5 == 0:
                #                 self.logger.info("Delay remaining: " + str(interruptCountdown - x) + " seconds")
                #             t.sleep(1)
                #     if t.time() > updatemaindevice:
                #         self.updatemainDevice()
                #         updatemaindevice = t.time()+30
                #     self.sleep(0.05)


            self.logger.info("Error occurred.  Reconnecting.")
            self.sleep(60)


        except self.StopThread:
            self.debugLog(u'Restarting/or error. Stopping thread.')
            pass

        except Exception as e:
            self.logger.exception("Main RunConcurrent error Caught:")
            self.sleep(5)
    # manage states - below called from asyncio paradox thread
    def manage_event(self, event):
        try:
            selectedzone = {}
            if self.debug3:
            #    self.logger.debug("Event Key: {}".format(event.key))
                self.logger.debug("Event Property: {}".format(event.property))
                self.logger.debug("Type Property: {}".format(event.type))

                self.logger.debug("Msg Property: {}".format(event.message))
               # self.logger.debug("Props Property: {}".format(event.props))
               # self.logger.debug("Label Property: {}".format(event.label))
                self.logger.debug("Change Property: {}".format(event.change))

            if self.debug4:
                self.logger.info("Received Update: {}".format(event.message))
            if event == None:
                self.logger.debug("managed event called, event is None. ending.  ?Not connected")
                return
            if event.type == None:
                self.logger.debug("managed event called event.type is None.  ending.  ?Not connected.")
                return
            if self.zoneNames == None:
                self.logger.debug("ZoneNames empty.  Likely just startup issue.")
                return
            if str(event.type)== "zone":
                if self.zoneNames != None:
                    #self.logger.debug("{}".format(self.zoneNames))
                    selectedzone = next((item for item in self.zoneNames if item["key"] == str(event.label)), None)
                if selectedzone != None:
                    if self.debug3:
                        self.logger.debug("Zone Involved: {}".format(selectedzone))
                    self.zoneMotionFound(selectedzone['id'],event.change['open'])

            elif str(event.type)=="system":

                if str(event.property) == "vdc":  ## Voltage event happen all the time...
                    if "vdc" in event.change:
                        self.PowerVolts_DC = float(event.change["vdc"])
                elif str(event.property) == "dc":  ## Voltage event happen all the time...
                    if "dc" in event.change:
                        self.batterydc = float(event.change["dc"])
                elif str(event.property) == "battery":  ## Voltage event happen all the time...
                    if "battery" in event.change:
                        self.battery = float(event.change["battery"])
                elif str(event.property) == "trouble":  ## Voltage event happen all the time...
                    if "trouble" in event.change:
                        trouble = event.change['trouble']
                        if trouble:
                            ## System has Trouble
                            self.system_trouble(True)
                        else:
                            self.system_trouble(False)
                elif str(event.property) == "time":
                    if "time" in event.change:  ## this is a datetime object
                        try:
                            paneldt = event.change["time"]
                            self.paneldate = paneldt.strftime("%c")
                        except:
                            self.logger.debug("error datetime:",exc_info=True)
                            pass


        except:
            self.logger.exception("Exception manage event")


    def system_trouble(self, introuble):
        self.logger.debug("System Trouble Called.")
        for dev in indigo.devices.itervalues(filter="self"):
            if dev.deviceTypeId == "ParadoxMain":
                if dev.enabled:
                    dev.updateStateOnServer('systemTrouble', value=introuble)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.debugLog(u"validateDeviceConfigUi called")


        return (True, valuesDict)

    def deviceStartComm(self, device):
        self.logger.debug(u"deviceStartComm called for " + device.name)
        device.stateListOrDisplayStateIdChanged()
        if device.deviceTypeId == 'ParadoxMain':
            device.updateStateOnServer('deviceIsOnline', value=True)
        if device.deviceTypeId == "paradoxalarmMotion":
            if device.enabled:
                device.updateStateOnServer(key="onOffState", value=False)

##
    def generateLabels(self, device,valuesDict, somethingunused):
        self.logger.info("Updating Zone and other Labels")
        self.labelsdueupdate = True
        return

    def updatemainDevice(self):
        #self.logger.debug("Update Main Device Called")
        for dev in indigo.devices.itervalues(filter="self"):
            if dev.deviceTypeId == "ParadoxMain":

                if dev.enabled:
                    if self._paradox != None:
                        currentstate= ""
                        troublestring = ""
                        paritionnumber = int(dev.pluginProps.get("zonePartition",1))
                        if self._paradox.storage != None:
                            partitiondict = self._paradox.storage.get_container_object("partition", paritionnumber)
                            if partitiondict != None:
                                #self.logger.error("{}".format(partitiondict))
                                if 'current_state' in partitiondict:
                                    currentstate = partitiondict['current_state']
                        if self._paradox.indigo_status != None:
                            if "troubles" in self._paradox.indigo_status:
                                for t_key, t_status in self._paradox.indigo_status['troubles'].items():
                                    if not isinstance(t_status, bool):
                                        #self.logger.error("Trouble %s has not boolean state: %s", t_key, t_status)
                                        continue
                                    if t_status:
                                        troublestring = troublestring +str(t_key)+ ","
                                troublestring = troublestring[:-1]  # remove last ,
                                 #self._paradox.indigo_status["troubles"]
                        stateList = [
                                {'key': 'deviceIsOnline', 'value': self.connected},
                                {'key': 'battery', 'value': self.battery},
                                {'key': 'batterydc', 'value': self.batterydc},
                                {'key': 'PowerVolts_DC', 'value': self.PowerVolts_DC},
                                {'key': 'paneldate', 'value': self.paneldate},
                                {'key': 'ipaddress', 'value': self.ipaddress},
                            {'key': 'TroubleState', 'value': troublestring},
                            {'key': 'Current_State', 'value': currentstate},
                            {'key': 'IPModule', 'value': builtins.IPModule},
                            {'key': 'panelID', 'value': self.panelID}
                            ]
                        dev.updateStatesOnServer(stateList)

    def shutdown(self):
         self.debugLog(u"shutdown() method called.")
         self.able_to_connect = False ## Disconnects panel thread
         self.sleep(2)

    def startup(self):
        self.debugLog(u"Starting Plugin. startup() method called.")

    ## Motion Detected

    def zoneMotionFound(self, zoneNumber, status):
        if self.debug3:
            self.logger.debug("zoneMotionFound for zone:"+str(zoneNumber)+" and status:"+str(status))
        for dev in indigo.devices.itervalues(filter="self"):
            if dev.deviceTypeId == "paradoxalarmMotion":
                if dev.enabled:
                    #self.logger.error("zonenumber dev pluginprops:."+str(dev.pluginProps['zonenumber']))
                    if int(dev.pluginProps['zonenumber']) == int(zoneNumber):
                        if status == False:
                            dev.updateStateOnServer(key="onOffState", value=False)
                            #self.triggerCheck(dev,"motion")
                        elif status == True:
                            dev.updateStateOnServer(key="onOffState", value=True)
                            self.triggerCheck(dev,"motion")


    def partitionstatusChange(self, status):
        if self.debug1:
            self.logger.debug("partitionstatusChange status:"+str(status))
        dev = next(indigo.devices.itervalues(filter="self.ParadoxMain"))
        # return first paradoxmain device only
        # should not be two but if there are will be problem.

        idofevent = int(status)
        event,nameofevent = self.eventmap.getEventDescription(2, idofevent)
        self.logger.debug("Name of Event: "+str(nameofevent))
        self.triggerCheck(dev,"partitionstatuschange",0,idofevent)
        dev.updateStateOnServer(key="alarmState", value=nameofevent)
        self.logger.debug("Partition Status Change/Event is:"+str(nameofevent))
        ## message[7] always 2
        ## trigger check for all _partition status

    def bellstatusChange(self, status):
        if self.debug1:
            self.logger.debug("Bell statusChange status:"+str(status))
        dev = next(indigo.devices.itervalues(filter="self.ParadoxMain"))
        # return first paradoxmain device only
        # should not be two but if there are will be problem.
        idofevent = int(status)
        event,nameofevent = self.eventmap.getEventDescription(3, idofevent)
        self.logger.debug("Name of Event: "+str(nameofevent))
        self.triggerCheck(dev,"bellstatuschange",0,idofevent)

        dev.updateStateOnServer(key="BellState", value=nameofevent)
        self.logger.debug("Bell Status Change/Event is:"+str(nameofevent))
        ## message[7] always 2
        ## trigger check for all _partition status

    def newtroublestatusChange(self, status):
        if self.debug1:
            self.logger.debug("New Trouble statusChange status:" + str(status))
        dev = next(indigo.devices.itervalues(filter="self.ParadoxMain"))
        # return first paradoxmain device only
        # should not be two but if there are will be problem.

        idofevent = int(status)
        event, nameofevent = self.eventmap.getEventDescription(44, idofevent)
        self.logger.debug("Name of Event: " + str(nameofevent))
        self.triggerCheck(dev, "newtroublestatuschange", 0, idofevent)
        dev.updateStateOnServer(key="TroubleState", value=nameofevent)
        self.logger.debug("Trouble Status Change/Event is:" + str(nameofevent))
        ## message[7] always 2
        ## trigger check for all _partition status

    def validatePrefsConfigUi(self, valuesDict):

        self.debugLog(u"validatePrefsConfigUi() method called.")

        error_msg_dict = indigo.Dict()
        if valuesDict.get("ipaddress") != "" and valuesDict.get("ipaddress") != "":
            valuesDict["allSetUp"] = True
            return (True, valuesDict)
        else:
            return (False, valuesDict)

        # self.errorLog(u"Plugin configuration error: ")

       # return True, valuesDict



    def setStatestonil(self, dev):

         self.debugLog(u'setStates to nil run')


    def refreshDataAction(self, valuesDict):
        """
        The refreshDataAction() method refreshes data for all devices based on
        a plugin menu call.
        """

        self.debugLog(u"refreshDataAction() method called.")
        self.refreshData()
        return True

    def refreshData(self):
        """
        The refreshData() method controls the updating of all plugin
        devices.
        """
        self.debugLog(u"refreshData() method called.")
        try:
            # Check to see if there have been any devices created.
            if indigo.devices.itervalues(filter="self"):
                self.debugLog(u"Updating data...")
                for dev in indigo.devices.itervalues(filter="self"):
                    self.refreshDataForDev(dev)
            else:
                indigo.server.log(u"No Client devices have been created.")
            return True
        except Exception as error:
            self.errorLog(u"Error refreshing devices. Please check settings.")
            self.errorLog("Exception:",exc_info=True)
            return False
    ## zonelist return

    def zoneList(self, filter='',valuesDict=None, typeId="", targetId=0):
        endArray = []
        x =0
        if self.zoneNames == None:
            self.logger.info("Please wait for initialisation of plugin and try again..")
            self.logger.info("Should be reading zone Names...")
            return endArray
        if len(self.zoneNames)==0:
            self.logger.info("Please wait for initialisation of plugin and try again..")
            self.logger.info("Should be reading zone Names...")
            return endArray
        for zones in self.zoneNames:
            #x = x +1
            zoneid = zones['id']
            zonekey = zones['label']
            endArray.append( (zoneid,zonekey) )
        self.logger.debug("Returning:  {} ".format(endArray))
        return endArray

    def paritionstatusList(self, filter='', valuesDict=None, typeId="", targetId=0):
        endArray = []
        subevent =""
        partitionstatus = self.eventmap.getAllpartitionStatus()
        for key,value in partitionstatus.items():
            self.logger.debug("Key/SubEvent:"+str(key)+":"+str(value))
            if key==99 or str(value)=='N/A':
                continue
            endArray.append((str(key), value))
        return endArray

    def bellstatusList(self, filter='', valuesDict=None, typeId="", targetId=0):
        endArray = []
        subevent =""
        partitionstatus = self.eventmap.getAllbellStatus()
        for key,value in partitionstatus.items():
            self.logger.debug("Key/SubEvent:"+str(key)+":"+str(value))
            if key==99 or str(value)=='N/A':
                continue
            endArray.append((str(key), value))
        return endArray

    def troublestatusList(self, filter='', valuesDict=None, typeId="", targetId=0):
        endArray = []
        subevent =""
        partitionstatus = self.eventmap.getAllnewtroubleStatus()
        for key,value in partitionstatus.items():
            self.logger.debug("Key/SubEvent:"+str(key)+":"+str(value))
            if key==99 or str(value)=='N/A':
                continue
            endArray.append((str(key), value))
        return endArray


    def toggleDebugEnabled(self):
        """
        Toggle debug on/off.
        """
        self.debugLog(u"toggleDebugEnabled() method called.")
        if self.logLevel == logging.INFO:
             self.logLevel = logging.DEBUG

             self.indigo_log_handler.setLevel(self.logLevel)
             indigo.server.log(u'Set Logging to DEBUG')
        else:
            self.logLevel = logging.INFO
            indigo.server.log(u'Set Logging to INFO')
            self.indigo_log_handler.setLevel(self.logLevel)

        self.pluginPrefs[u"logLevel"] = self.logLevel
        return
## Triggers

    def triggerStartProcessing(self, trigger):
        self.logger.debug("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device, event, partition=0, idofevent=0):
        try:
            for triggerId, trigger in sorted(self.triggers.items()):
                self.logger.debug("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

                if trigger.pluginTypeId=="partitionstatuschange" and event=="partitionstatuschange":
                    #self.logger.error("Trigger paritionStatusChange Found: Idofevent:"+str(idofevent))
                    #self.logger.error(str(trigger))
                    if str(idofevent) in trigger.pluginProps["paritionstatus"]:
                        self.logger.debug("Trigger being run: idofevent: " + str(idofevent) + " event: " + str(event) )
                        indigo.trigger.execute(trigger)
                if trigger.pluginTypeId=="bellstatuschange" and event=="bellstatuschange":
                    #self.logger.error("Trigger paritionStatusChange Found: Idofevent:"+str(idofevent))
                    #self.logger.error(str(trigger))
                    if str(idofevent) in trigger.pluginProps["bellstatus"]:
                        self.logger.debug("Trigger being run: idofevent: " + str(idofevent) + " event: " + str(event) )
                        indigo.trigger.execute(trigger)
                if trigger.pluginTypeId=="newtroublestatuschange" and event=="newtroublestatuschange":
                    #self.logger.error("Trigger paritionStatusChange Found: Idofevent:"+str(idofevent))
                    #self.logger.error(str(trigger))
                    if str(idofevent) in trigger.pluginProps["troublestatus"]:
                        self.logger.debug("Trigger being run: idofevent: " + str(idofevent) + " event: " + str(event) )
                        indigo.trigger.execute(trigger)
                if trigger.pluginTypeId == "failedCommand" and event == "failedCommand":
                    if trigger.pluginProps["zonePartition"] == int(partition):
                        self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                        indigo.trigger.execute(trigger)


                if trigger.pluginTypeId=="motion" and event=="motion":
                    if trigger.pluginProps["deviceID"] == str(device.id):
                        self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                        indigo.trigger.execute(trigger)
                if trigger.pluginTypeId=="alarmstatus" and event =="alarmstatus":
                    if trigger.pluginProps["zonePartition"] == int(partition):
                        if trigger.pluginProps["alarmstate"] == trigger.pluginProps["deviceID"]:
                            self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                            indigo.trigger.execute(trigger)

                    #self.logger.debug("\tUnknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
            return

        except Exception as error:
            self.logger.error(u"Error Trigger. Please check settings.")
            self.logger.exception("Error:")
            return False

    ## Actions

    def syncPanelTime(self, action):
        self.logger.debug("syncPanelTime called")
        if self._paradox != None:
            if self._paradox.run_state == 3:  # RUN
                self._paradox.work_loop.create_task(self._paradox.sync_time())

    def controlPGM(self, action):
        self.logger.debug(u"controlPGM Called as Action.")
        pgm = int(action.props.get('pgm',1))
        command = action.props.get("action","OFF")
        #self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0)
        ##self.myAlarm.login(str(self.ip150password), str(self.pcpassword))
        if self._paradox != None:
            if self._paradox.run_state == 3:  # RUN
                # control_output(self, output, command) -> bool:
                self._paradox.work_loop.create_task(self._paradox.control_output(pgm, command))
        #self.myAlarm.controlPGM(pgm,command, 50)
        return

    def controlPanic(self, action):
        self.logger.debug(u"controlAlarm Called as Action.")
        partition = int(action.props.get('partition',1))

        if self._paradox != None:
            if self._paradox.run_state == 3:  # RUN
                # control_output(self, output, command) -> bool:
                self._paradox.work_loop.create_task(self._paradox.send_panic(partition,0, 1))

       #self.myAlarm.controlAlarm(partition,command, 50)
        return

    def controlAlarm(self, action):
        self.logger.debug(u"controlAlarm Called as Action.")
        partition = int(action.props.get('partition',1))
        command = action.props.get("action","DISARM")

        #self.myAlarm.login(str(self.ip150password),str(self.pcpassword))
        #self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0)
        if self._paradox != None:
            if self._paradox.run_state == 3:  # RUN
                # control_output(self, output, command) -> bool:
                self._paradox.work_loop.create_task(self._paradox.control_partition(partition, command))

       #self.myAlarm.controlAlarm(partition,command, 50)
        return