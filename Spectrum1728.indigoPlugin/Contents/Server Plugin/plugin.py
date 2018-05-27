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
import array

from ghpu import GitHubPluginUpdater

try:
    import indigo
except:
    pass

# Establish default plugin prefs; create them if they don't already exist.
kDefaultPluginPrefs = {
    u'configMenuPollInterval': "300",  # Frequency of refreshes.
    u'configMenuServerTimeout': "15",  # Server timeout limit.
    # u'refreshFreq': 300,  # Device-specific update frequency
    u'showDebugInfo': False,  # Verbose debug logging?
    u'configUpdaterForceUpdate': False,
    u'configUpdaterInterval': 24,
    u'updaterEmail': "",  # Email to notify of plugin updates.
    u'updaterEmailsEnabled': False  # Notification of plugin updates wanted.
}


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"logLevel"])
        except:
            self.logLevel = logging.INFO

        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))

        self.debugLog(u"Initializing Spectrum/Paradox Alarm plugin.")

        self.updater = GitHubPluginUpdater(self)
        self.configUpdaterInterval = self.pluginPrefs.get('configUpdaterInterval', 24)
        self.configUpdaterForceUpdate = self.pluginPrefs.get('configUpdaterForceUpdate', False)
        self.connected = False
        self.deviceUpdate = False
        self.devicetobeUpdated =''


        self.socket = self.connectToSocket()
        self.bytes = []
        self.triggers = {}

    def __del__(self):

        self.debugLog(u"__del__ method called.")
        indigo.PluginBase.__del__(self)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:

            self.debugLog(u"User prefs saved.")


        return True

    # Start 'em up.
    def deviceStartComm(self, dev):

        self.debugLog(u"deviceStartComm() method called.")
        dev.updateStateOnServer("onOffState", value="off")
        dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)

    # Shut 'em down.
    def deviceStopComm(self, dev):

        self.debugLog(u"deviceStopComm() method called.")
        indigo.server.log(u"Stopping  device: " + dev.name)
        dev.updateStateOnServer("onOffState", value="off")
        dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)


    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    def checkForUpdates(self):
        if self.updater.checkForUpdate() == False:
            indigo.server.log(u"No Updates are Available")

    def updatePlugin(self):
        self.updater.update()

    def runConcurrentThread(self):
        x =0


        try:

            if self.connected == False:
                self.socket = self.connectToSocket()
                self.sleep(5)

            while self.connected:
                x = x +1
                response = ''
                morebytes = []
                #Catch Timeouts
                try:
                    data = self.socket.recvfrom(1016)
                    response = data[0]
                except socket.error,msg:
                    self.logger.debug(u'Timeout: Expected error'+unicode(msg))
                    self.connected= False
                    pass
                except Exception as error:
                    self.logger.debug(u'Exception Not Expected:'+unicode(error))
                    self.connected = False
                    pass

                try:
                    if response != '':
                        #self.logger.debug(unicode(response))
                        morebytes = map(ord, response)
                        #self.bytes = morebytes

                        #self.logger.info(unicode(morebytes))
                        start = next((i for i,v in enumerate(morebytes) if v !=0), None )
                        #if start != None:
                            #self.logger.debug(u'start equals:'+unicode(start))

                        if start != None:
                            count =0
                            if __name__ == '__main__':
                                if len(morebytes) >= start+8:  # check for index out of range and ignore that data
                                    bytes8 = []
                                    for bytes in morebytes[start-1:start+8]:
                                        #self.logger.debug(u'Byte:'+str(count)+" equals:"+str(hex(bytes)))
                                        bytes8.append(hex(bytes))
                                        count = count +1
                                    # Need to count number of values -3 or less false/wrong data

                                    numberofvalues = sum(i != '0x0' for i in bytes8)
                                    #self.logger.debug(u'Number of Values:'+unicode(numberofvalues))

                                    if numberofvalues >= 4:


                                        # OK - Now have the returned data in a new array bytes8 with the most important byte currently
                                        # being start +1
                                        # must end in 'd'  for it to be valid motion on response
                                        # Need to check ending in d hex data ..... somehow...
                                        # and then run check against devices for the same address code - if found activate

                                        byte2str = bytes8[2]
                                        #self.logger.debug(u'Bytes8 number2:'+unicode(byte2str))
                                        endcharacter = byte2str[-1:]
                                        self.logger.debug(u'Bytes 8 2: End Character ='+endcharacter)

                                        # Okay if end of hex d - continue

                                        if endcharacter == "d":
                                            # Device should be updated
                                            self.deviceUpdate = True
                                            self.devicetobeUpdated = bytes8[2][-2:]

                except Exception as error:
                    self.logger.debug(u'Exception in Data Collection:'+unicode(error.message))

                try:
                    if self.deviceUpdate:
                        for dev in indigo.devices.itervalues('self'):

                            if dev.enabled and dev.configured and (dev.pluginProps['address']==self.devicetobeUpdated):
                                #self.debugLog(u"Checking Devices:  {0}:".format(dev.name))
                                #deviceaddress = dev.pluginProps['address']
                                self.logger.debug(unicode(dev.name)+u' is the Device to be Updated Address Given:'+unicode(self.devicetobeUpdated))
                                #if deviceaddress == :
                                self.logger.debug(u'Found Matching Device! Updating')
                                if dev.states['onOffState']==False:
                                    self.triggerCheck(dev)
                                dev.updateStateOnServer("onOffState", value="on")
                                dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensorTripped)
                            self.deviceUpdate = False

                    self.sleep(0.5)

                      # Check for length of time since updated within here as well
                     #  Now Check for time since motion and re-sensor
                    #  Needs to be selectable time in seconds
                    if x > 10:
                        for dev in indigo.devices.itervalues('self'):
                            if dev.enabled and dev.configured and dev.states['onOffState']:

                                timeDifference = int(t.time() - t.mktime(dev.lastChanged.timetuple()))
                                self.logger.debug(u'Device Last Changed (secs ago):'+ unicode(dev.name) +":"+ str(timeDifference) +" secs")

                                if timeDifference >= int(dev.pluginProps['timeout']):
                                    # Time completed for this device
                                    # reset motion to off
                                    self.logger.debug(u'Device Timed out setting motion to Off')
                                    dev.updateStateOnServer("onOffState", value="off")
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.MotionSensor)
                        x = 0

                except self.StopThread:
                    self.logger.debug(u'Ending... Devices Update')
                    break
        # CHECK COMPLETED
                except Exception as error:
                    self.logger.error(u'Error within Devices Update:'+unicode(error))
                    pass



            self.sleep(0.5)

        except self.StopThread:
            self.debugLog(u'Restarting/or error. Stopping thread.')
            pass


    def connectToSocket(self):

         host='192.168.1.253'
         port=5000

         try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.bind(('', port))
            self.logger.info(u'Socket Connected:'+unicode(host)+":"+unicode(port))
            self.connected = True
            return sock

         except socket.error as msg:
            self.logger.debug( u'Failed to create socket'+unicode(msg))
            self.connected = False
            self.sleep(60)






    def shutdown(self):

         self.debugLog(u"shutdown() method called.")

    def startup(self):

        self.debugLog(u"Starting Plugin. startup() method called.")

        # See if there is a plugin update and whether the user wants to be notified.
        try:
            if self.configUpdaterForceUpdate:
                self.updatePlugin()

            else:
                #self.checkForUpdates()
                self.logger.debug(u'Delete update check')
                self.sleep(1)
        except Exception as error:
            self.errorLog(u"Update checker error: {0}".format(error))


        # Attempt Socket Connection here


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