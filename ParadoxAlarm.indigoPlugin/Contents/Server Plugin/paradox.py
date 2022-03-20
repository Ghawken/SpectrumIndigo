
import socket
import time
import sys
import struct
import json
import logging
import binascii

class paradox:
    loggedin = 0
    aliveSeq = 0
    alarmName = None
    zoneTotal = 0
    zoneStatus = ['']
    #zoneNames = {}
    partitions = {}
    zonePartition = None
    partitionStatus = None
    partitionName = None
    ZonesOn = "ON"
    ZonesOff = "OFF"
    Publish_Static_Topic = 0
    Skip_Update_Labels = 0
    Error_Delay = 5
    Alarm_Partition_States = {'DISARMED':'DISARMED',
    'ARMED':'ARMED',
    'SLEEP':'SLEEP',  #ARMED_NIGHT
    'STAY':'STAY',  #ARMED_HOME
    'ARMING':'ARMING', #PENDING
    'TRIGGERED':'TRIGGERED'}
    keepalivecount = 1


    def __init__(self, plugin, _transport, client,_encrypted=0, _retries=10, _alarmeventmap="ParadoxMG5050",
                 _alarmregmap="ParadoxMG5050"):

        self.plugin = plugin
        self.comms = _transport  # instance variable unique to each instance
        self.retries = _retries
        self.encrypted = _encrypted
        self.alarmeventmap = _alarmeventmap
        self.alarmregmap = _alarmregmap
        self.zoneNames = []
        self.logger  = logging.getLogger('Plugin.password')
        #self.client = client

        # MyClass = getattr(importlib.import_module("." + self.alarmmodel + "EventMap", __name__))

        try:
            mod = __import__("ParadoxMap", fromlist=[self.alarmeventmap + "EventMap"])
            self.eventmap = getattr(mod, self.alarmeventmap + "EventMap")
        except Exception as e:
            self.logger.debug("Failed to load Event Map: %s " % repr(e))
            self.logger.debug("Defaulting to MG5050 Event Map...")
            try:
                mod = __import__("ParadoxMap", fromlist=["ParadoxMG5050EventMap"])
                self.eventmap = getattr(mod, "ParadoxMG5050EventMap")
            except Exception as e:
                self.logger.debug("Failed to load Event Map (exiting): %s" % repr(e))
                sys.exit()

        try:
            mod = __import__("ParadoxMap", fromlist=[self.alarmregmap + "Registers"])
            self.registermap = getattr(mod, self.alarmregmap + "Registers")
        except Exception as e:
            self.logger.debug("Failed to load Register Map (defaulting to not update labels from alarm): %s" % repr(e))
            self.Skip_Update_Labels = 1

            # self.eventmap = ParadoxMG5050EventMap  # Need to check panel type here and assign correct dictionary!
            # self.registermap = ParadoxMG5050Registers  # Need to check panel type here and assign correct dictionary!

    def skipLabelUpdate(self):
        return self.Skip_Update_Labels

    def returnZoneNames(self):
        return self.zoneNames

    def returnPartitionNames(self):
        return self.partitionName

    def saveState(self):
        self.eventmap.save()

    def loadState(self):
        self.logger.debug("Loading previous event states and labels from file")
        self.eventmap.load()

    def login(self, password,pcpassword, Debug_Mode=0):  # Construct the login message, 16 byte header +
        # 16byte [or multiple] payloading being the password
        self.logger.debug("Logging into alarm system...")

        header = b"\xaa"  # First construct the 16 byte header, starting with 0xaa

        header += bytes(bytearray([len(password)]))  # Add the length of the password which is appended after the header
        header += b"\x00\x03"  # No idea what this is

        if self.encrypted == 0:  # Encryption flag
            header += b"\x08"  # Encryption off [default for now]
        else:
            header += b"\x09"  # Encryption on

        header += b"\xf0\x00\x0a"  # No idea what this is, although the fist byte seems like a sequence number
        # header += "\xf0\x00\x0e\x00\x01"    # iParadox initial request

        header = header.ljust(16, b'\xee')  # The remained of the 16B header is filled with 0xee

        message = password  # Add the password as the start of the payload

        # FIXME: Add support for passwords longer than 16 characters
        message = message.ljust(16, b'\xee')  # The remainder of the 16B payload is filled with 0xee

        reply = self.readDataRaw(header + message, Debug_Mode)  # Send message to the alarm panel and read the reply

        if len(reply)>0 and reply[4] == b'\x38':
            self.logger.debug("Login to alarm panel successful")
            self.plugin.connected = True
            loggedin = 1
        else:
            self.plugin.connected = False
            loggedin = 0
            self.logger.debug(u"Login request unsuccessful")
            return

        header = list(header)

        header[1] = b'\x00'
        header[5] = b'\xf2'
        header2 = "".join(header)
        self.readDataRaw(header2, Debug_Mode)

        header[5] = b'\xf3'
        header2 = "".join(header)
        reply = self.readDataRaw(header2, Debug_Mode)

        reply = list(reply)  # Send "waiting" header until reply is at least 48 bytes in length indicating ready state

        header[1] = b'\x25'
        header[3] = b'\x04'
        header[5] = b'\x00'
        header2 = "".join(header)
        message = b'\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(header2 + message, Debug_Mode)

        # A - no sending after this
        header[1] = '\x26'
        header[3] = '\x03'
        header[5] = '\xf8'
        header2 = "".join(header)
        message = '\x50\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(header2 + message, Debug_Mode)

        header[1] = '\x25'
        header[3] = '\x04'
        header[5] = '\x00'
        header2 = "".join(header)
        #Command 0x5F : Start communication
        self.logger.debug( "Command 0x5F : Start communication")
        message = '\x5f\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(header2 + message, Debug_Mode)
        # pull from here, the panel pd, firmware version.
        header[1] = '\x25'
        header[3] = '\x04'
        header[5] = '\x00'
        header[7] = '\x14'
        header2 = "".join(header)
        # reply = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13\x14\x15\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13\x14\x15\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13\x14\x15\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'
        #          0xaa 0x25 0x0 0x2 0x72 0x0 0x0 0x0 0x0 0xee 0xee 0xee 0xee 0xee 0xee 0xee ### 0x0 0x0 0x0 0x0 0x16 0x6 0x10 0x2 0x27 0x29 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x0 0x7e
        #get the first half of the message with the prodct type and panel id into the new 00 request
        message = reply[16:26]

        self.logger.debug( "***********************************Product Type: {}".format((ord(message[4]))))
        self.logger.debug( "***********************************Firmware: {}.{}.{}".format((ord(message[5])),(ord(message[6])),(ord(message[7]))))
        self.logger.debug ("********************************Panel ID: {} {}".format((ord(message[8])),(ord(message[9]))))
        self.logger.debug ("COMMS MESSAGE  : " + " ".join(hex(ord(i)) for i in message))
        self.logger.debug ("********************************P")

        self.plugin.producttype = str(ord(message[4]))
        self.plugin.firmware = "{}.{}.{}".format( (ord(message[5])),(ord(message[6])),(ord(message[7])))
        self.plugin.panelID = "{} {}".format((ord(message[8])),(ord(message[9])))

        #need to work out how to get pcpassword (PIN) form Config which) to hex string.
        #eg PIN of 1234 should be added as b'\x12' b'\x34' not converted.
        hex_data = pcpassword.decode("hex")
        message += hex_data

        message += '\x19\x00\x00'
        message += reply[31:39]
        message += '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00'
        message = self.format37ByteMessage(message)
        self.logger.debug( "Command 0x00 : Initialize communication")
        reply = self.readDataRaw(header2 + message, Debug_Mode)

        #self.logger.debug "Command 0x50 : PC Status 0"
        header[1] = '\x25'
        header[3] = '\x04'
        header[5] = '\x00'
        header[7] = '\x14'
        header2 = "".join(header)
        message = '\x50\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(header2 + message, Debug_Mode)

        header[1] = '\x25'
        header[3] = '\x04'
        header[5] = '\x00'
        header[7] = '\x14'
        header2 = "".join(header)
        message = '\x50\x00\x0e\x52\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(header2 + message, Debug_Mode)
        self.logger.debug ("Reply MESSAGE  : " + " ".join(hex(ord(i)) for i in reply))
        return loggedin

    def format37ByteMessage(self, message):
        checksum = 0

        if len(message) % 37 != 0:

            for val in message:  # Calculate checksum
                checksum += ord(val)

            ##self.logger.debug "CS: " + str(checksum)
            while checksum > 255:
                checksum = checksum - (checksum / 256) * 256

            ##self.logger.debug "CS: " + str(checksum)

            message += bytes(bytearray([checksum]))  # Add check to end of message

            msgLen = len(message)  # Pad with 0xee till end of last 16 byte message

            if (msgLen % 16) != 0:
                message = message.ljust((msgLen / 16 + 1) * 16, '\xee')

        ##self.logger.debug " ".join(hex(ord(i)) for i in message)

        return message

    # Implementation inspired by https://github.com/bioego/Paradox-UWP
    def updateZoneAndAlarmStatus(self, Startup_Publish_All_Info="True", Debug_Mode=0):
        header = "\xaa\x25\x00\x04\x08\x00\x00\x14\xee\xee\xee\xee\xee\xee\xee\xee"
        message = "\x50\x00\x80"
        # reguest ID
        message += "\x00"
        #NU - 4 - 32  4   5   6   7   8   9  10   11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31  32  33
        message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        #source
        message += "\x00"
        #user id
        message += "\x00\x00"
        # 2nd byte was d0
        #message += "\xd0\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
        reply = self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)
        if len(reply) < 39:
          self.logger.debug ("Response without zone status: {}".format(len(reply)))
          return
        self.logger.debug ("***************************************************** self.logger.debuging values")
        data = reply[16:]
        self.logger.debug( str(len(reply)) + "<-   " + " ".join(hex(ord(i)) for i in reply))
        # 2019-04-04 - Switch to using the KeepAliveStatus1 reply processor rather than do it again
        #              helps with all the partition name names for 2.0.11




        self.logger.debug("heart beat status 0 reply: <--" + " ".join(bin(ord(i)) for i in reply))
        self.keepAliveStatus0(data,Debug_Mode,0)
        #
        #self.logger.debug "Value 16 ({}) and 17 ({}) ".format(ord(data[0]), ord(data[1]))
        # if data[1] == '\x00' and (data[0] == '\x50' or data[0] == '\x52'):
        #     #self.logger.debug "Year :  {}{}".format(ord(data[9]),ord(data[10]))
        #     #self.logger.debug "Month : {}".format( ord(data[11]))
        #     #self.logger.debug "Day :   {}".format(ord(data[12]))
        #     #self.logger.debug "Hour:   {}".format( ord(data[13]))
        #     #self.logger.debug "minute: {}".format( ord(data[14]))
        #     #self.logger.debug "ac:  {}".format( ord(data[15]))
        #     #self.logger.debug "DC:  {}".format( ord(data[16]))
        #     #self.logger.debug "BDC: {}".format(ord(data[17]))
        #     # Skip to zone status
        #     reply = reply[25:]
        #     reply = reply[1:]
        # else:
        #     #self.logger.debug "No 00 record found"
        #     # Skip to zone status
        #     reply = reply[25:]
        #     #reply = reply[10:] # skip date, time and voltages
        #     reply = reply[10:]




        # for x in range(4):
        #   data = ord(reply[x])
        #   for y in range(8):
        #     bit = data & 1
        #     data = data / 2
        #     itemNo = x * 8 + y + 1
        #     if itemNo in self.zoneNames.keys():
        #       location = self.zoneNames[itemNo]
        #       if len(location) > 0:
        #         zoneState = ZonesOn if bit else ZonesOff
        #         #self.logger.debug "Publishing initial zone state (state:" + zoneState + ", zone:" + location + ")"
        #         ##client.publish(Topic_Publish_ZoneState + "/" + location, "ON" if bit else "OFF", qos=1, retain=True)
        #         #self.client.publish(Topic_Publish_ZoneState + "/" + location, zoneState, qos=1, retain=True)
        time.sleep(0.3)
        message =  "\x50\x00\x80\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\xd1\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
        #self.logger.debug "heart beat status 1 request: -->" + " ".join(hex(ord(i)) for i in message)
        reply = self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)
        #self.logger.debug "heart beat reply status 1 : <--" + " ".join(hex(ord(i)) for i in reply)
        if len(reply) < 34:
          self.logger.debug("Response without zone status")
          return
        # Skip to alarm status
        data = reply[16:]

        # 2019-04-04 - Switch to using the KeepAliveStatus1 reply processor rather than do it again
        #              helps with all the partition name names for 2.0.11
        self.keepAliveStatus1(data,20,0)


        # reply = reply[33:]
        # alarmState = ord(reply[0])
        # alarmState = ZonesOn if (alarmState & 1) else ZonesOff
        # #self.logger.debug "Publishing initial alarm state (state:" + alarmState + ")"
        # if Debug_Mode >= 1:
        #     self.logger.debug("updateZoneAndAlarmStatus: Publishing initial alarm state (state:" + alarmState + ")")

        # ##client.publish(Topic_Publish_ArmState, alarmState, qos=1, retain=True)
        # if Startup_Publish_All_Info == "True":
        #     #self.client.publish(Topic_Publish_ArmState,  self.Alarm_Partition_States[alarmState], qos=1, retain=True)
        time.sleep(0.3)
        return

    def updateAllLabels(self, Startup_Publish_All_Info="True", Topic_Publish_Labels="True", Debug_Mode=0):

        for func in self.registermap.getsupportedItems():
            self.logger.debug("updateAllLabels: Reading from alarm: " + func)
            try:
                register_dict = getattr(self.registermap, "get" + func + "Register")()
                mapping_dict = getattr(self.eventmap, "set" + func)
                total = sum(1 for x in register_dict if isinstance(x, int))
                self.logger.debug("updateAllLabels: Amount of numeric items in dictionary to read: " + str(total))
                header = register_dict["Header"]
                skip_next = 0
                for x in range(1, total + 1):
                    if skip_next == 1:
                        skip_next = 0
                        continue

                    # #self.logger.debug "Update generic registers step: " + str(x)

                    message = register_dict[x]["Send"]
                    try:
                        next_message = register_dict[x + 1]["Send"]
                    except KeyError:
                        skip_next = 1
                        # #self.logger.debug "no next key"

                    # #self.logger.debug "Current msg " + " ".join(hex(ord(i)) for i in message)
                    # #self.logger.debug "Next msg    " + " ".join(hex(ord(i)) for i in next_message)

                    assert isinstance(message, basestring), "Message to be sent is not a string: %r" % message
                    message = message.ljust(36, '\x00')

                    # #self.logger.debug " ".join(hex(ord(i)) for i in message)

                    reply = self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)
                    start = register_dict[x]["Receive"]["Start"]
                    finish = register_dict[x]["Receive"]["Finish"]
                    # self.zoneNames.append(reply[start:finish].rstrip()) FIXME: remove all internal zoneNames references and only use the dict
                    # newzone = reply[start:finish].rstrip().translate(None, '\x00')
                    newzone = reply[start:finish].rstrip().translate(None, '\x00').decode('utf8', 'ignore').encode('utf8')
                    mapping_dict(x, newzone)

                    if (skip_next == 0) and (message[0:len(next_message)] == next_message):
                        # #self.logger.debug "Same"
                        start = register_dict[x + 1]["Receive"]["Start"]
                        finish = register_dict[x + 1]["Receive"]["Finish"]
                        #newzone = reply[start:finish].rstrip().translate(None, '\x00')
                        newzone = reply[start:finish].rstrip().translate(None, '\x00').decode('utf8', 'ignore').encode('utf8')
                        mapping_dict(x + 1, newzone)
                        skip_next = 1
                try:
                    completed_dict = getattr(self.eventmap, "getAll" + func)()
                    if Debug_Mode >= 1:
                        self.logger.debug("Labels detected for " + func + ":")
                        self.logger.debug(completed_dict)
                except Exception as e:
                    self.logger.debug("Failed to load supported function's completed mappings after updating: %s" % repr(e))


                topic = func.split("Label")[0]
                if Startup_Publish_All_Info == "True":
                    topic = func.split("Label")[0]
                    if topic[0].upper() + topic[1:] + "s" == "Zones":
                        self.zoneNames = completed_dict
                    elif topic.upper() == "PARTITION":
                        self.partitions = completed_dict

                    #self.logger.debug("updateAllLabels:  Topic being published " + Topic_Publish_Labels + "/" + topic[0].upper() + topic[1:] + "s" + ';'.join('{}{}'.format(key, ":" + val) for key, val in completed_dict.items()))
                    #self.client.publish(Topic_Publish_Labels + "/" + topic[0].upper() + topic[1:] + "s",
                    #';'.join('{}{}'.format(key, ":" + val) for key, val in completed_dict.items()), 1, True)
                else:
                    if topic[0].upper() + topic[1:] + "s" == "Zones":
                        self.zoneNames = completed_dict
                    elif topic.upper() == "PARTITION":
                        self.partitions = completed_dict

                self.plugin.zoneNames = self.zoneNames
                #self.logger.debug self.zoneNames


            except Exception as e:
                self.logger.debug("Failed to load supported function's mapping: %s" % repr(e))

        return

    def testForEvents(self, Events_Payload_Numeric=0, Publish_Static_Topic=0, Debug_Mode=0, data=None):

        if data is None:
            reply_amount, headers, messages = self.splitMessage(self.readDataRaw('', Debug_Mode))
        else:
            messages = data
            reply_amount = 1
        interrupt = 0  # Signal 3rd party connection interrupt
        #if Debug_Mode >= 1:
        #    self.logger.debug('.')
        reply = '.'
        if Debug_Mode > 1 and reply_amount > 1:
            self.logger.debug("Multiple data: " + repr(messages))
        self.retries = 10

        if reply_amount > 0:
            for message in messages:
                #if self.plugin.debug3:
                    #self.logger.debug("Event data: " + " ".join(hex(ord(i)) for i in message))

                if len(message) > 0:
                    # live event
                    if message[0] == '\xe2' or message[0] == '\xe0':

                        try:
                            location = ""
                            if 0 == 0:

                                event, subevent = self.eventmap.getEventDescription(ord(message[7]), ord(message[8]))
                                location = message[15:31].translate(None, '\x00').translate(None,'\x01').strip()
                                if location and self.plugin.debug3:
                                    self.logger.debug("Event location: \"%s\"" % location)
                                    #self.logger.debug "Event location: \"%s\"" % location

                                reply = str(ord(message[7])) + "=Event:" + event + " & " + str(ord(message[8]))+"=SubEvent:" + subevent

                                self.logger.debug(str(reply))
                                try:
                                    if (ord(message[7]) == 0 or ord(message[7]) ==1) and (self.zoneNames is not None and len(self.zoneNames) > 0):
                                        #self.logger.debug("Message is a 1 or 0, and self.Zonenames not empty")
                                        zonename = self.zoneNames[ord(message[8])]
                                        if zonename != location:
                                            self.logger.debug("Zonename from labels {0} does not match event location {1}, updating".format(zonename,location))
                                            self.zoneNames[ord(message[8])]= location
                                        #else:
                                        #    self.logger.debug("Updating zone name to match location in live event")
                                        #    #self.logger.debug "zones {0} matches location {1} ".format(zonename,location)
                                except Exception as ezone:
                                        self.logger.debug("Exception checking/updating zone names: {}".format(ezone.message))

                # these checks for triggers, still run other zone checks etc below as elif
                                if ord(message[7])==2:  ## this is _partitionstatus change, check trigger and then do the other if/elif's
                                    self.plugin.partitionstatusChange(ord(message[8]))
                                elif ord(message[7])==3:  ## this is Bell change, check trigger and then do the other if/elif's
                                    self.plugin.bellstatusChange(ord(message[8]))
                                elif ord(message[7]) == 44:
                                    self.plugin.newtroublestatusChange(ord(message[8]))
                                # zone status messages Paradox/Zone/ZoneName 0 for close, 1 for open
                                if ord(message[7]) == 0:
                                    #Zone state off
                                    if self.plugin.debug3:
                                        self.logger.debug("Zone OFF:"+str(location))
                                    self.plugin.zoneMotionFound(ord(message[8]), ord(message[7]))
                                   # self.logger.debug("Publishing ZONE event \"%s\" for \"%s\" =  %s" % (Topic_Publish_ZoneState, location, ZonesOff))
                                    #self.client.publish(Topic_Publish_ZoneState + "/" + location,ZonesOff, qos=1, retain=True)
                                elif ord(message[7]) == 1:
                                    #zone state on
                                    if self.plugin.debug3:
                                        self.logger.debug("Zone ON:"+str(location))
                                    self.plugin.zoneMotionFound(ord(message[8]), ord(message[7]))
                                    #self.logger.debug("Publishing ZONE event \"%s\" for \"%s\" =  %s" % ("", location, ZonesOn))
                                    #self.client.publish(Topic_Publish_ZoneState + "/" + location,ZonesOn, qos=1, retain=True)

                                elif ord(message[7])== 2 and (ord(message[8])==14):
                                    # 14 - Exit Delay Started
                                    # Is a Partition status event
                                    self.logger.debug("Exit Delay Started")

                                elif ord(message[7]) == 2 and (ord(message[8]) == 11 or ord(message[8]) == 3):   #Disarm
                                    #partition disarmed event
                                    self.logger.debug("Publishing DISARMED event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States['DISARMED']))
                                    #self.client.publish(Topic_Publish_ArmState ,ZonesOff, qos=1, retain=True)
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location+ "/Status" ,self.Alarm_Partition_States['DISARMED'], qos=1, retain=True)

                                elif ord(message[7]) == 6 and (ord(message[8]) == 4 ):   #SLEEP
                                    #partition sleep armed event
                                    #12 is sleep arm, 14 is full arm- is STAY 13?
                                    self.logger.debug("Publishing SLEEP event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States['SLEEP']))
                                    #self.client.publish(Topic_Publish_ArmState ,ZonesOn, qos=1, retain=True)
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location+ "/Status", self.Alarm_Partition_States['SLEEP'], qos=1, retain=True)

                                elif ord(message[7]) == 6 and (ord(message[8]) == 3 ):   #STAY
                                    #partition stayd armed event
                                    #12 is sleep arm, 14 is full arm- is STAY 13?
                                    self.logger.debug("Publishing STAY event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States['STAY']))
                                    #self.client.publish(Topic_Publish_ArmState ,ZonesOn, qos=1, retain=True)
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location+ "/Status", self.Alarm_Partition_States["STAY"], qos=1, retain=True)

                                elif ord(message[7]) == 2 and (ord(message[8]) == 12):   #arm
                                    #partition full armed event
                                    #12 is sleep arm, 14 is full arm - is STAY 13?
                                    self.logger.debug("Publishing ARMED event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States["ARMED"]))
                                    #self.client.publish(Topic_Publish_ArmState ,ZonesOn, qos=1, retain=True)
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location+ "/Status", self.Alarm_Partition_States["ARMED"], qos=1, retain=True)

                                elif ord(message[7]) == 2 and (ord(message[8]) == 9):   #Arming state on Swawk off
                                    #sqwak off messages - part of the arming sequence.
                                    self.logger.debug("Publishing ARMING event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States["ARMING"]))
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location+ "/Status", self.Alarm_Partition_States["ARMING"], qos=1, retain=True)
                                elif ord(message[7]) == 9: # and ord(message[8] == 1): # remote button pressed
                                    #remote button pressed
                                    self.logger.debug ("button pressed: " + str(ord(message[7]))) #+ " " +  str(ord(message[8]))
                                    if message[8]:
                                       #self.logger.debug "Message 8: %s" % str(ord(message[8]))
                                       self.logger.debug("Publishing PGM event \"%s Button%s\" =  \"%s\"" % ("",str(ord(message[8])), "ON"))
                                       #self.client.publish(Topic_Publish_Events + "/PGM" + str(ord(message[8])) ,"ON", qos=1, retain=True)
                                elif (ord(message[7]) == 36 or ord(message[7]) == 37) and (ord(message[8]) == 11):
                                    #zone triggered = 36
                                    #Smoke alarm = 37
                                    #2018-06-14 07:55:49,749 DEBUG Events 7-36 8-11- Reply: Event:Zone in alarm;SubEvent:Mid toilet Reed
                                    #2018-06-14 07:55:49,752 DEBUG Message 7: 36 Message 8: 11
                                    self.logger.debug("Publishing Triggered event \"%s\" =  \"%s\"" % ("", self.Alarm_Partition_States["TRIGGERED"]))
                                    #self.client.publish(Topic_Publish_ArmState + "/" + location + "/Status", self.Alarm_Partition_States["TRIGGERED"], qos=1, retain=True)
                                    #self.client.publish(Topic_Publish_ArmState + "/Alarm" ,"IN ALARM, Zone: " + location, qos=1, retain=True)
                                else:
                                    self.logger.debug("Events 7-{} 8-{}- Reply: {}".format(ord(message[7]),ord(message[8]),reply))


                            if Events_Payload_Numeric == 1:

                                reply = "E:" + str(ord(message[7])) + ";SE:" + str(ord(message[8]))
                                self.logger.debug("Publishing event E\"%s\" for :SE \"%s\" " % (str(ord(message[7])), str(ord(message[8])) ) )


                            #self.logger.debug("Message 7 is : {0} Message 8: {1}".format(ord(message[7]),ord(message[8])))

                            #self.client.publish(Topic_Publish_Events, reply, qos=0, retain=False)

                        except ValueError:
                            reply = "No register entry for Event: " + str(ord(message[7])) + ", Sub-Event: " + str(
                                ord(message[8]))

                    elif message[0] == '\x75' and message[1] == '\x49':
                        interrupt = 1
                    elif (message[0] == '\x52' or message[0] == 'x50') and message[2] =='\x80':
                        if Debug_Mode >= 2:
                            self.logger.debug("KEEP ALIVE REPLY FOUND********************{}*******".format(ord(message[3])) +  " ".join(hex(ord(i)) for i in message))
                        if ord(message[3]) == 0:
                            self.keepAliveStatus0(message, Debug_Mode)
                        elif ord(message[3]) == 1:
                            self.keepAliveStatus1(message, Debug_Mode)
                        elif Debug_Mode >= 2:
                            self.logger.debug("Other Keepalive Sequence reply: {}".format(ord(message[3])))
                    else:
                        reply = "Unknown event: " + " ".join(hex(ord(i)) for i in message)

        return interrupt

    def splitMessage(self, request=''):  # FIXME: Make msg a list to handle multiple 37byte replies

        if len(request) > 0:

            requests = request.split('\xaa')

            del requests[0]

            for i, val in enumerate(requests):
                requests[i] = '\xaa' + val
                # #self.logger.debug "Request seq " + str(i) + ": " + " ".join(hex(ord(i)) for i in requests[i])

            # #self.logger.debug "Request(s): ", requests

            replyAmount = len(requests)
            x = replyAmount

            headers = [] * replyAmount
            messages = [] * replyAmount

            # #self.logger.debug "Reply amount: ", x

            x -= 1

            # #self.logger.debug "Going into while with first element: " + requests[0]

            while x >= 0:
                # #self.logger.debug "Working on number " + str(x) + ": " + " ".join(hex(ord(i)) for i in requests[i])
                if len(requests[x]) > 16:
                    headers.append(requests[x][:16])
                    messages.append(requests[x][16:])

                elif len(requests[x]) == 16:
                    headers.append(requests[x][:16])
                    messages.append([])
                    # return headers, ''
                x -= 1

            return replyAmount, headers, messages

        else:
            return 0, [], []

    def sendData(self, request=''):

        if len(request) > 0:
            self.comms.send(request)
            time.sleep(0.25)

    def readDataRaw(self, request='', Debug_Mode=2):

        # self.testForEvents()                # First check for any pending events received
        tries = self.retries
        Error_Delay = 5
        while tries > 0:
            try:
                if Debug_Mode >= 2:
                    self.logger.debug(str(len(request)) + "->   " + " ".join(hex(ord(i)) for i in request))
                #if len(request) == 0: # heartbeart
                #    self.logger.debug("Publishing heartbeat event")
                #    #client.publish(Topic_Publish_Heartbeat,"ON")
                #self.logger.error("Socket Timeout ="+str(self.comms.getdefaulttimeout()))
                self.sendData(request)
                inc_data = self.comms.recv(1024)
                if Debug_Mode >= 2:
                    self.logger.debug( str(len(inc_data)) + "<-   " + " ".join(hex(ord(i)) for i in inc_data))
                tries = 0

            except socket.timeout as e:
                err = e.args[0]
                if err == 'timed out':
                    self.logger.debug("Timed out error, no retry -<-- could fix this" + repr(e))
                    #this seems to be where it goes normally while waiting for traffic.
                    tries = 0

                    #self.plugin.connected = False
                    return ''
                    # sleep(1)
                    # #self.logger.debug 'Receive timed out, ret'
                    # continue
                else:
                    self.logger.debug("Error reading data from IP module, retrying again... (" + str(tries) + "): " + repr(e))
                    tries -= 1
                    time.sleep(Error_Delay)
                    sys.exc_clear()
                    pass
            except socket.error as e:
                self.logger.debug("Unknown error on socket connection, retrying (%d) ... %s " % (tries, repr(e)))
                tries -= 1
                time.sleep(Error_Delay)
                if tries == 0:
                    self.logger.debug("Failure, disconnected.")
                    self.plugin.connected = False
                else:
                    self.logger.debug("After error, continuing %d attempts left" % tries)
                    time.sleep(5)
                    return ''
            else:
                if len(inc_data) == 0:
                    tries -= 1
                    self.logger.debug('Socket connection closed by remote host: %d' % tries)
                    time.sleep(Error_Delay)
                    if tries == 0:
                        self.logger.debug('Failure, disconnecting')
                        self.plugin.connected = False
                    return ''
                else:
                    #self.logger.error("Start:" + hex(ord(inc_data[0])))
                    if hex(ord(inc_data[0])) != hex(0xaa):
                        if len(inc_data) > 0:
                            self.logger.debug('Dangling data in the receive buffer: %s' % binascii.hexlify(inc_data))
                        inc_data = ''
                    return inc_data

    # def readDataRawControl(self, request='', Debug_Mode=2):
    #
    #     # self.testForEvents()                # First check for any pending events received
    #     tries = self.retries
    #     Error_Delay = 5
    #     while tries > 0:
    #         try:
    #             if Debug_Mode >= 2:
    #                 self.logger.debug(str(len(request)) + "->   " + " ".join(hex(ord(i)) for i in request))
    #             # if len(request) == 0: # heartbeart
    #             #    self.logger.debug("Publishing heartbeat event")
    #             #    #client.publish(Topic_Publish_Heartbeat,"ON")
    #             # self.logger.error("Socket Timeout ="+str(self.comms.getdefaulttimeout()))
    #             self.sendData(request)
    #             inc_data = self.comms.recv(1024)
    #             if Debug_Mode >= 2:
    #                 self.logger.debug(str(len(inc_data)) + "<-   " + " ".join(hex(ord(i)) for i in inc_data))
    #             tries = 0
    #
    #         except socket.timeout, e:
    #             err = e.args[0]
    #             if err == 'timed out':
    #                 self.logger.debug("Timed out error, no retry -<-- could fix this" + repr(e))
    #                 # this seems to be where it goes normally while waiting for traffic.
    #                 tries = 0
    #
    #                 # self.plugin.connected = False
    #                 return ''
    #                 # sleep(1)
    #                 # #self.logger.debug 'Receive timed out, ret'
    #                 # continue
    #             else:
    #                 self.logger.debug(
    #                     "Error reading data from IP module, retrying again... (" + str(tries) + "): " + repr(e))
    #                 tries -= 1
    #                 time.sleep(Error_Delay)
    #                 sys.exc_clear()
    #                 pass
    #         except socket.error, e:
    #             self.logger.debug("Unknown error on socket connection, retrying (%d) ... %s " % (tries, repr(e)))
    #             tries -= 1
    #             time.sleep(Error_Delay)
    #             if tries == 0:
    #                 self.logger.debug("Failure, disconnected.")
    #                 self.plugin.connected = False
    #             else:
    #                 self.logger.debug("After error, continuing %d attempts left" % tries)
    #                 time.sleep(5)
    #                 return ''
    #         else:
    #             if len(inc_data) == 0:
    #                 tries -= 1
    #                 self.logger.debug('Socket connection closed by remote host: %d' % tries)
    #                 time.sleep(Error_Delay)
    #                 if tries == 0:
    #                     self.logger.debug('Failure, disconnecting')
    #                     self.plugin.connected = False
    #                 return ''
    #             else:
    #                 self.logger.error("Start:"+hex(ord(inc_data[0])))
    #                 if hex(ord(inc_data[0])) != hex(0xaa):
    #                     if len(inc_data) > 0:
    #                         self.logger.error('Dangling data in the receive buffer: %s' % binascii.hexlify(inc_data))
    #                     inc_data = ''
    #
    #                 return inc_data


    def readDataStruct37(self, inputData='', Debug_Mode=0):  # Sends data, read input data and return the Header and Message

        rawdata = self.readDataRaw(inputData, Debug_Mode)

        # Extract the header and message
        if len(rawdata) > 16:
            header = rawdata[:16]
            message = rawdata[17:]

        return header, message

    def controlGenericOutput(self, mapping_dict, output, state, Debug_Mode=0):

        try:
            registers = mapping_dict
            header = registers["Header"]
            sending = True
            retries =0
            message = registers[output][state]
            assert isinstance(message, basestring), "Message to be sent is not a string: %r" % message
            message = message.ljust(36, '\x00')
            # #self.logger.debug " ".join(hex(ord(i)) for i in message)
            while sending == True and retries <= 10:
                self.logger.debug("Sending generic Output Control: Output: " + str(output) + ", State: " + state)
                reply = self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)
                if reply != '':
                    # self.logger.debug("Reply Obtained:  Need to check has actioned otherwise repeat...."+str(message))
                    data = reply[16:]
                    messagesent = registers[output][state]
                    self.logger.debug(str(len(reply)) + "Reply:" + " ".join(hex(ord(i)) for i in reply))
                    self.logger.debug("Data 0:" + str(hex(ord(data[0]))))
                    self.logger.debug("messagesent 2:" + str(hex(ord(messagesent[2]))))
                    self.logger.debug(
                        "Data 2:" + str(hex(ord(data[2]))))  ## is the command sent, if not returned then error.
                    # self.logger.error("Data 3:" + str(hex(ord(data[3]))))
                    commandtobesent = ord(messagesent[2])
                    replycommand = ord(data[2])
                    if commandtobesent != replycommand:
                        self.logger.debug(
                            u'Command returned, is not that sent ; resending/retrying command.  Retry ' + str(
                                retries))
                        sending = True
                        retries = retries + 1
                        time.sleep(2)
                    else:
                        sending = False
                        self.logger.info(u'Command successfully sent.')
                        return

                else:
                    self.logger.info('Error sending command.  Retry ' + str(retries))
                    sending = True
                    retries = retries + 1
                    time.sleep(2)

            self.logger.info(u'Command failed despite retries... aborting.')
            self.plugin.failedCommand(0, state)
        except:
            sending = False
            self.logger.exception(u"Error Sending Command.")

            return


        return

    def controlPGM(self, pgm, state="OFF", Debug_Mode=0):

        # #self.logger.debug state.upper()

        assert (isinstance(pgm, int) and pgm >= 0 and pgm <= 16), "Problem with PGM number: %r" % str(pgm)
        assert (isinstance(pgm, int) and pgm >= 0 and pgm <= 16), "Problem with PGM number: %r" % str(pgm)
        assert isinstance(state, basestring), "State given is not a string: %r" % str(state)
        assert (state.upper() == "ON" or state.upper() == "OFF" or state.upper() == "BEEP" or state.upper() == "ON_OVERRIDE" or state.upper() == "OFF_OVERRIDE"), "State is not given correctly: %r" % str(state)

        self.controlGenericOutput(self.registermap.getcontrolOutputRegister(), pgm, state.upper(), Debug_Mode)

        return

    def controlGenericAlarm(self, mapping_dict, partition, state, Debug_Mode):
        try:
            registers = mapping_dict
            header = registers["Header"]

            self.logger.debug("Sending generic Alarm Control: Partition: " + str(partition) + ", State: " + state)
            sending = True
            retries =0
            message = registers[partition][state]

            assert isinstance(message, basestring), "Message to be sent is not a string: %r" % message
            message = message.ljust(36, '\x00')

            # #self.logger.debug " ".join(hex(ord(i)) for i in message)

            while sending == True and retries <=3:
                self.logger.debug("Sending generic Alarm Control: Partition: " + str(partition) + ", State: " + state)
                reply = self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)
                time.sleep(0.5)
                if reply !='':
                    #self.logger.debug("Reply Obtained:  Need to check has actioned otherwise repeat...."+str(message))
                    data = reply[16:]
                    messagesent = registers[partition][state]
                    self.logger.debug(str(len(reply)) + "Reply:" + " ".join(hex(ord(i)) for i in reply))
                    self.logger.debug("Data 0:"+str(hex(ord(data[0]))))
                    self.logger.debug("messagesent 2:" + str(hex(ord(messagesent[2]))))
                    self.logger.debug("Data 2:" + str(hex(ord(data[2]))))  ## is the command sent, if not returned then error.
                    #self.logger.error("Data 3:" + str(hex(ord(data[3]))))
                    commandtobesent = ord(messagesent[2])
                    replycommand = ord(data[2])
                    if commandtobesent != replycommand:
                        self.logger.info(
                            u'Command returned, is not that sent ; resending/retrying command.  Retry ' + str(retries))
                        sending = True
                        retries = retries + 1
                        time.sleep(2)
                    else:
                        sending = False
                        self.logger.info(u'Command successfully sent.')
                        return

                else:
                    self.logger.info('Error sending command.  Retry ' + str(retries))
                    sending = True
                    retries = retries + 1
                    time.sleep(2)


            self.logger.info(u'Command failed despite retries... aborting.')
            self.plugin.failedCommand(partition, state)
        except:
            sending = False
            self.logger.exception(u"Error Sending Command.")

            return


        return

    def controlAlarm(self, partition=1, state="Disarm", Debug_Mode=0):

        assert (
            isinstance(partition,
                       int) and partition >= 0 and partition <= 16), "Problem with partition number: %r" % str(
            partition)
        assert isinstance(state, basestring), "State given is not a string: %r" % str(state)
        assert (state.upper() in self.registermap.getcontrolAlarmRegister()[
            partition]), "State is not given correctly: %r" % str(state)

        self.controlGenericAlarm(self.registermap.getcontrolAlarmRegister(), partition, state.upper(), Debug_Mode)

        return

    def disconnect(self, Debug_Mode=2):

        # header = "\xaa\x00\x00\x03\x51\xff\x00\x0e\x00\x01\xee\xee\xee\xee\xee\xee"
        header = "\xaa\x25\x00\x04\x08\x00\x00\x14\xee\xee\xee\xee\xee\xee\xee\xee"
        message = "\x70\x00\x05"

        self.readDataRaw(header + self.format37ByteMessage(message), Debug_Mode)

    def keepAliveStatus0(self, data, Debug_Mode,keepalivecount=keepalivecount):
        #Panel Status 0 - troubles, voltage, zone status
        paneldatetime = "{}-{}-{} {}:{}".format(ord(data[9])*100 + ord(data[10]),
                        "{0:02d}".format(ord(data[11])),
                        "{0:02d}".format(ord(data[12])),
                        "{0:02d}".format(ord(data[13])),
                        "{0:02d}".format(ord(data[14])))
        #self.logger.debug( "dateTime: {}".format(paneldatetime))
        self.plugin.paneldate = str(paneldatetime)

        vdc = round(ord(data[15])*(20.3-1.4)/255.0+1.4,1)
        self.plugin.batteryvdc = vdc
        #vdc = ord(data[15])
        if Debug_Mode > 1:
            self.logger.debug("VDC: {}".format(vdc) )
        dc = round(ord(data[16])*22.8/255.0,1)
        self.plugin.batterydc = dc
        if Debug_Mode > 1:
            self.logger.debug("DC: {}".format(dc))
        battery = round(ord(data[17])*22.8/255.0,1)
        self.plugin.battery = battery
        if Debug_Mode > 1:
            self.logger.debug("battery: {}".format(battery))

        #jsondata = json.dumps({"paneldate":paneldatetime,"vdc":vdc,"dc":dc,"battery":battery})
        #self.logger.debug("Publishing panel status json: '{}'".format(jsondata))
        bit = 0

        #self.logger.debug ("Length of Data:"+str(len(data)))
        zonebits = data[19:23]
        zonebits2 = data[24:36]
        #self.logger.debug( str(len(zonebits)) + "<-   " + " ".join(hex(ord(i)) for i in zonebits))
        #Tertuish Method
        for x in range(4):
            b = ord(zonebits[x])
            for y in range(8):
                bit = b & 1
                b = b / 2
                itemNo = x * 8 + y + 1
                zoneState = "ON" if bit else "OFF"
                if itemNo in self.zoneNames.keys():
                    location = self.zoneNames[itemNo]
                    if len(location) > 0:
                        if Debug_Mode > 1:
                            self.logger.debug("Publishing initial zone state (state: {}, zone number: {} Zone {})".format( zoneState,itemNo,location))


    def keepAliveStatus1(self, data, Debug_Mode,keepalivecount=keepalivecount):
        #Panel Status 1 - Partition Status
        # Get Partition 1 Status
        self.keepAlivePartitionStatus(data[17:21],1,50)

        # Get Partition 2 Status
        self.keepAlivePartitionStatus(data[21:25],2,0)

    def keepAlivePartitionStatus(self, data, partition, Debug_Mode=0):
        #Panel Status 1 - Partition Status
        partition1status1 = ord(data[0])
        ZonesOn = "ON"
        ZonesOff = "OFF"
        armstate = "DISARMED"
        for y in range(8):
            bit = partition1status1 & 1
            partition1status1 = partition1status1 / 2
            itemNo = y + 1
            zoneState = "ON" if bit else "OFF"
            if self.plugin.debug2:
                #self.logger.debug "Publishing paritions status 1 bits state (state: {}, bit: {})".format( zoneState, itemNo)
                self.logger.debug("Publishing paritions status 1 bits state (state: {}, bit: {})".format( zoneState, itemNo))
            if itemNo == 1:
                #alarm disarmed
                if self.plugin.debug2:
                    self.logger.debug("Publishing Partition Arm state (state: {}, bit: {})".format( zoneState, itemNo))
                if zoneState == ZonesOn:
                    armstate = "ARMED"

            elif itemNo == 2: # sleep
                if zoneState == ZonesOn:
                    armstate = "SLEEP"

            elif itemNo == 3: #away
                if zoneState == ZonesOn:
                    armstate = "STAY"

            ##client.publish(Topic_Publish_ZoneState + "/" + location, "ON" if bit else "OFF", qos=1, retain=True)
            ##client.publish(Topic_Publish_ZoneState + "/" + location, "ON" if bit else "OFF", qos=1, retain=True)
        partition1status2 = ord(data[1])
        for y in range(8):
            bit = partition1status2 & 1
            partition1status2 = partition1status2 / 2
            itemNo = y + 1
            zoneState = ZonesOn if bit else ZonesOff
            if self.plugin.debug2:
                #self.logger.debug "Publishing paritions status 2 bits state (state: {}, bit: {})".format( zoneState, itemNo)
                self.logger.debug("Publishing paritions status 2 bits state (state: {}, bit: {})".format( zoneState, itemNo))
            if itemNo == 1:
                if zoneState == ZonesOn:
                    armstate = "ARMING"


        partitionlocation =  ""
        if self.partitions:
            partitionlocation = "/" + self.partitions[partition].strip()
        #self.logger.debug("Publishing Partition \"{}\" Arm state (state: {})".format(partitionlocation, armstate))
            #self.client.publish(Topic_Publish_ArmState + partitionlocation + "/Status",self.Alarm_Partition_States[armstate],qos=1,retain=True)

        partition1status3 = ord(data[2])
        for y in range(8):
            bit = partition1status3 & 1
            partition1status3 = partition1status3 / 2
            itemNo = y + 1
            zoneState = ZonesOn if bit else ZonesOff
            if self.plugin.debug2:
                self.logger.debug( "Publishing paritions status 3 bits state (state: {}, bit: {})".format( zoneState, itemNo))
                #self.logger.debug("Publishing paritions status 3 bits state (state: {}, bit: {})".format( zoneState, itemNo))
        partition1status4 = ord(data[3])
        for y in range(8):
            bit = partition1status4 & 1
            partition1status4 = partition1status4 / 2
            itemNo = y + 1
            zoneState = ZonesOn if bit else ZonesOff
            if self.plugin.debug2:
                self.logger.debug("Publishing paritions status 4 bits state (state: {}, bit: {})".format( zoneState, itemNo))
                #self.logger.debug("Publishing paritions status 4 bits state (state: {}, bit: {})".format( zoneState, itemNo))
                #self.logger.debug "partition 1 status: {} {} {} {}".format(partition1status1,partition1status2,partition1status3,partition1status4)
        if self.plugin.debug2:
            self.logger.debug("partition {}:{} status: {} {} {} {}".format(partition,partitionlocation,partition1status1,partition1status2,partition1status3,partition1status4))
        #self.logger.debug ("Length of Data:"+str(len(data)))
        #self.logger.debug ( "Partition status 0 reply: <--" + " ".join(bin(ord(i)) for i in data))

    def keepAlive(self, Debug_Mode=0):

        header = "\xaa\x25\x00\x04\x08\x00\x00\x14\xee\xee\xee\xee\xee\xee\xee\xee"

        message = "\x50\x00\x80"

        message += bytes(bytearray([self.aliveSeq]))

        #message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                  #"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xd0\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
        message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        message = self.format37ByteMessage(message)

        #if Debug_Mode >= 2:
        #self.logger.debug "***** SEQUENCE {}".format(self.aliveSeq)


        self.sendData(header + message)

        self.aliveSeq += 1
        if self.aliveSeq > 6:
            self.aliveSeq = 0

    def walker(self, ):
        self.zoneTotal = Zone_Amount

        self.logger.debug("Reading (" + str(Zone_Amount) + ") zone names...")

        header = "\xaa\x25\x00\x04\x08\x00\x00\x14\xee\xee\xee\xee\xee\xee\xee\xee"

        for x in range(16, 65535, 32):
            message = "\xe2\x00"
            zone = x
            zone = list(struct.pack("H", zone))
            swop = zone[0]
            zone[0] = zone[1]
            zone[1] = swop

            temp = "".join(zone)
            # #self.logger.debug " ".join(hex(ord(i)) for i in temp)
            message += temp

            message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            # #self.logger.debug " ".join(hex(ord(i)) for i in message)
            reply = self.readDataRaw(header + self.format37ByteMessage(message))

            self.logger.debug(reply)
            # #self.logger.debug " ".join(hex(ord(i)) for i in reply)

            time.sleep(0.3)

        return



