#! /usr/bin/env python2.6
# -*- coding: utf-8 -*-

"""
Author: GlennNZ

"""

import datetime
import time as t
import urllib2
import os
import shutil
import logging
import socket
import sys
import paradox

try:
    import indigo
except:
    pass


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

        self.connected = False
        self.deviceUpdate = False
        self.devicetobeUpdated =''

        self.ipaddress = self.pluginPrefs.get('ipaddress', '')
        self.port = self.pluginPrefs.get('port', 10000)
        self.ip150password = self.pluginPrefs.get('ip150password', 'paradox')
        self.pcpassword = self.pluginPrefs.get('pcpassword', 1234)

        self.labelsdueupdate = False
        self.debug1 = self.pluginPrefs.get('debug1', False)
        self.debug2 = self.pluginPrefs.get('debug2', False)
        self.debug3 = self.pluginPrefs.get('debug3', False)
        self.debug4 = self.pluginPrefs.get('debug4',False)
        self.debug5 = self.pluginPrefs.get('debug5', False)

        # main device to be updated as needed
        self.paneldate = ""
        self.battery = float(0)
        self.batteryvdc = float(0)
        self.batterydc = float(0)
        self.area1Arm = "Disarmed"
        self.area2Arm = "Disarmed"
        self.producttype = ""
        self.firmware = ""
        self.panelID = ""
        self.zoneNames = {}

        self.triggers = {}

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
            # self.logger.error(unicode(valuesDict))
            self.port = valuesDict.get('port', False)
            self.ip150password = valuesDict.get('ip150password', 'paradox')
            self.pcpassword = valuesDict.get('superCharge', 1234)
            self.debugLog(u"User prefs saved.")
            self.debug1 = valuesDict.get('debug1', False)
            self.debug2 = valuesDict.get('debug2', False)
            self.debug3 = valuesDict.get('debug3', False)
            self.debug4 = valuesDict.get('debug4', False)
            self.debug5 = valuesDict.get('debug5', False)
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))
            self.logger.debug(u"User prefs saved.")
            self.logger.debug(u"Debugging on (Level: {0})".format(self.logLevel))

        return True

    # Start 'em up.

    # Shut 'em down.
    def deviceStopComm(self, dev):

        self.debugLog(u"deviceStopComm() method called.")
        indigo.server.log(u"Stopping  device: " + dev.name)
        if dev.deviceTypeId == 'ParadoxMain':
            dev.updateStateOnServer('deviceIsOnline', value=False)
        if dev.deviceTypeId == "paradoxalarmMotion":
            if dev.enabled:
                dev.updateStateOnServer(key="onOffState", value=False)


    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    def checkForUpdates(self):
        if self.updater.checkForUpdate() == False:
            indigo.server.log(u"No Updates are Available")

    def updatePlugin(self):
        self.updater.update()

    def runConcurrentThread(self):
        x =0
        Alarm_Model = "ParadoxMG5050"
        Alarm_Registry_Map = "ParadoxMG5050"
        Alarm_Event_Map = "ParadoxMG5050"
        updatemaindevice = t.time() + 15
        try:

            if self.connected == False and self.ipaddress !='':
                self.socket = self.connect_ip150socket(str(self.ipaddress), str(self.port))
                self.sleep(3)
                self.logger.info("Connecting to IP Module:" + self.ipaddress + " with Port:" + str(self.port))
                self.myAlarm = paradox.paradox(self, self.socket, "", 0, 3, Alarm_Event_Map, Alarm_Registry_Map)
                if not self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0):
                    self.logger.info(
                        u"Failed to login & unlock to IP module, check if another app is using the port. Retrying... ")
                    self.socket.close()
                    self.sleep(20)
                    self.connected = False
                else:
                    # client.publish(Topic_Publish_AppState, "State Machine 2, Logged into IP Module successfully", 1, True)
                    self.logger.info("Logged into IP module successfully")
                    self.connected = True

            zoneNames = self.myAlarm.updateAllLabels("True", "True", 0)
            self.labelsdueupdate = False
            self.logger.info(unicode(self.myAlarm.returnZoneNames()))
            self.myAlarm.updateZoneAndAlarmStatus("True", 0)

            while self.connected:
                self.myAlarm.keepAlive(0)
                zoneNames = ""
                if self.labelsdueupdate:
                    zoneNames = self.myAlarm.updateAllLabels("True","True",0)
                    self.labelsdueupdate = False
                    self.logger.info(unicode(self.myAlarm.returnZoneNames()))


                interrupt = self.myAlarm.testForEvents(0, 1, 0)
                #self.sleep(1)
                if interrupt == 1:
                    interruptCountdown = 5
                    interrupt = 0
                    for x in range(0, interruptCountdown):
                        if x % 5 == 0:
                            self.logger.info("Delay remaining: " + str(interruptCountdown - x) + " seconds")
                        t.sleep(1)

                if t.time() > updatemaindevice:
                    self.updatemainDevice()
                    updatemaindevice = t.time()+20

            self.sleep(0.5)

        except self.StopThread:
            self.debugLog(u'Restarting/or error. Stopping thread.')
            pass

    def connect_ip150socket(self,address, port):

        try:
            self.logger.info( "trying to connect %s" % address)
            self.logger.info("Connecting to %s" % address)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((address, int(port)))
            self.logger.info("Connected")
            self.connected = True
        except Exception, e:
            self.logger.error("Error connecting to IP module (exiting): " + repr(e))
            self.logger.exception( "error connecting")
            self.connected = False

        return s

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.debugLog(u"validateDeviceConfigUi called")
        # User choices look good, so return True (client will then close the dialog window).
        return (True, valuesDict)

    def deviceStartComm(self, device):
        self.logger.info(u"deviceStartComm called for " + device.name)
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
                    stateList = [
                            {'key': 'deviceIsOnline', 'value': self.connected},
                            {'key': 'battery', 'value': self.battery},
                            {'key': 'batterydc', 'value': self.batterydc},
                            {'key': 'batteryvdc', 'value': self.batteryvdc},
                            {'key': 'paneldate', 'value': self.paneldate},
                            {'key': 'ipaddress', 'value': self.ipaddress},
                        {'key': 'firmware', 'value': self.firmware},
                        {'key': 'panelID', 'value': self.panelID},
                        {'key': 'producttype', 'value': self.producttype}
                        ]
                    dev.updateStatesOnServer(stateList)

    def shutdown(self):

         self.debugLog(u"shutdown() method called.")

    def startup(self):

        self.debugLog(u"Starting Plugin. startup() method called.")

        # See if there is a plugin update and whether the user wants to be notified.

        # Attempt Socket Connection here


    ## Motion Detected

    def zoneMotionFound(self, zoneNumber, status):
        if self.debug1:
            self.logger.debug("zoneMotionFound for zone:"+str(zoneNumber)+" and status:"+str(status))
        for dev in indigo.devices.itervalues(filter="self"):
            if dev.deviceTypeId == "paradoxalarmMotion":
                if dev.enabled:
                    #self.logger.error("zonenumber dev pluginprops:."+str(dev.pluginProps['zonenumber']))
                    if int(dev.pluginProps['zonenumber']) == int(zoneNumber):
                        if status == 0:
                            dev.updateStateOnServer(key="onOffState", value=False)
                        elif status ==1:
                            dev.updateStateOnServer(key="onOffState", value=True)

    def partitionstatusChange(self, partition, status):
        if self.debug1:
            self.logger.debug("partitionstatusChange for zone:"+str(partition)+" and status:"+str(status))
        for dev in indigo.devices.itervalues(filter="self"):
            if dev.deviceTypeId == "ParadoxMain":
                if dev.enabled:
                    #self.logger.error("zonenumber dev pluginprops:."+str(dev.pluginProps['zonenumber']))
                    if int(dev.pluginProps['zonePartition']) == int(partition):
                        dev.updateStateOnServer(key="alarmState", value=status)



    def validatePrefsConfigUi(self, valuesDict):

        self.debugLog(u"validatePrefsConfigUi() method called.")

        error_msg_dict = indigo.Dict()

        # self.errorLog(u"Plugin configuration error: ")

        return True, valuesDict



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
            self.errorLog(unicode(error.message))
            return False

    ## zonelist return

    def zoneList(self, filter='',valuesDict=None, typeId="", targetId=0):
        endArray = []
        x =0
        if len(self.zoneNames)==0:
            self.logger.info("Please wait for initialisation of plugin and try again..")
            self.logger.info("Should be reading zone Names...")
            return endArray
        for key,value in self.zoneNames.items():
            #x = x +1
            if value== "":
                zonename = "Zone "+str(key)
            else:
                zonename = value
            endArray.append((str(key),zonename))

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

    def triggerStartProcessing(self, trigger):
        self.logger.debug("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device):
        try:

            for triggerId, trigger in sorted(self.triggers.iteritems()):
                self.logger.debug("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

                if trigger.pluginProps["deviceID"] != str(device.id):
                    self.logger.debug("\t\tSkipping Trigger %s (%s), wrong device: %s" % (trigger.name, trigger.id, device.id))
                else:
                    if trigger.pluginTypeId == "motion":
                        self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                        indigo.trigger.execute(trigger)

                    else:
                        self.logger.debug("\tUnknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
            return
        except Exception as error:
            self.errorLog(u"Error Trigger. Please check settings.")
            self.errorLog(unicode(error.message))
            return False

    ## Actions

    def controlPGM(self, action):
        self.logger.debug(u"controlPGM Called as Action.")
        pgm = int(action.props.get('pgm',1))
        command = action.props.get("action","OFF")

        #self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0)
        ##self.myAlarm.login(str(self.ip150password), str(self.pcpassword))
        self.myAlarm.controlPGM(pgm,command, 50)

        return


    def controlAlarm(self, action):
        self.logger.debug(u"controlAlarm Called as Action.")
        partition = int(action.props.get('partition',1))
        command = action.props.get("action","DISARM")
        #self.myAlarm.login(str(self.ip150password),str(self.pcpassword))
        #self.myAlarm.login(str(self.ip150password), str(self.pcpassword), 0)
        self.myAlarm.controlAlarm(partition,command, 50)

        return