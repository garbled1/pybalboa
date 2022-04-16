import asyncio
import errno
import logging
import time
import warnings
import queue
import socket
from socket import error as SocketError
import balboa
from balboa import *



CLIENT_CLEAR_TO_SEND = 0x00
CHANNEL_ASSIGNMENT_REQ = 0x01
CHANNEL_ASSIGNMENT_RESPONCE = 0x02
CHANNEL_ASSIGNMENT_ACK = 0x03
EXISTING_CLIENT_REQ = 0x04
EXISTING_CLIENT_RESPONCE = 0x05
CLEAR_TO_SEND = 0x06
NOTHING_TO_SEND =  0x07

STATUS_UPDATE = 0xC4
LIGHTS_UPDATE = 0xCA
CC_REQ = 0xCC

DETECT_CHANNEL_STATE_START = 0
DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND = 5

class SundanceRS485(balboa.BalboaSpaWifi):
    def __init__(self, hostname, port=899):
        super().__init__(hostname, port)
        logging.basicConfig()
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.queue = queue.Queue()
        self.channel = None
        self.config_loaded = True
        self.pump_array = [1, 1, 1, 0, 0, 0]
        self.nr_of_pumps = 3
        self.circ_pump = 1
        self.aux_array = [1, 1]
        self.tempscale = self.TSCALE_F
        self.timescale = self.TIMESCALE_24H
        self.temprange = 1
        self.discoveredChannels = []
        self.activeChannels = []
        self.detectChannelState = DETECT_CHANNEL_STATE_START
        self.target_pump_status  = [-1, -1, -1, -1, -1, -1]
        self.targetTemp = -1
        self.checkCounter = 0

 
    async def connect(self):
        """ Connect to the spa."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
        except (asyncio.TimeoutError, ConnectionRefusedError):
            self.log.error(
                "Cannot connect to spa at {0}:{1}".format(self.host, self.port)
            )
            return False
        except Exception as e:
            self.log.error(f"Error connecting to spa at {self.host}:{self.port}: {e}")
            return False
        self.connected = True
        sock = self.writer.transport.get_extra_info('socket')
        print(str(sock))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return True

    async def send_temp_change(self, newtemp):
        """ Change the set temp to newtemp. """
        # Check if the new temperature is valid for the current heat mode
        if (
            newtemp < self.tmin[self.temprange][self.tempscale]
            or newtemp > self.tmax[self.temprange][self.tempscale]
        ):
            self.log.error("Attempt to set temperature outside of heat mode boundary")
            return
  
        self.targetTemp = newtemp


    async def change_light(self, light, newstate):
        """ Change light #light to newstate. """
        # sanity check
        if (
            light > 1
            or not self.light_array[light]
            or self.light_status[light] == newstate
        ):
            return

        if light == 0:
            await self.send_CCmessage(241) #Lights Brightness Button
        else: 
            await self.send_CCmessage(242) #Lights Color Button

    async def change_pump(self, pump, newstate):
        """ Change pump #pump to newstate. """
        # sanity check
        print("{} {}".format(self.pump_status[pump] , newstate))
        if (
            pump > MAX_PUMPS
            or newstate > self.pump_array[pump]
            or self.pump_status[pump] == newstate
        ):
            return
        
        self.target_pump_status[pump] = newstate
        

    async def send_CCmessage(self, val):
        """ Sends a message to the spa with variable length bytes. """    
        # if not connected, we can't send a message
        if not self.connected:
            self.log.info("Tried to send CC message while not connected")
            return

        # if we dont have a channel number yet, we cant form a message
        if self.channel is None:
            self.log.info("Tried to send CC message without having been assigned a channel")
            return
            
        # Exampl: 7E 07 10 BF CC 65 85 A6 7E 
        message_length = 7
        data = bytearray(9)
        data[0] = M_STARTEND
        data[1] = message_length
        data[2] = self.channel
        data[3] = 0xBF
        data[4] = CC_REQ
        data[5] = val
        data[6] = 0
        data[7] = self.balboa_calc_cs(data[1:message_length], message_length - 1)
        data[8] = M_STARTEND

        self.log.debug(f"queueing message: {data.hex()}")
        self.queue.put(data)

    async def send_message(self, *bytes):
        """ Sends a message to the spa with variable length bytes. """
        self.log.info("Not supported with New Format messaging")
        return 
        
    def xormsg(self, data):
        lst = []
        for i in range(0,len(data)-1,2):
                c = data[i]^data[i+1]^1
                lst.append(c)
        return lst

    async def parse_C4status_update(self, data):
        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        7E 26 FF AF C4 AE A7 AA AB A4 A1 C9 5D A5 A1 C2 A1 9C BD CE BB E2 B9 BB AD B4 B5 A7 B7 DF B1 B2 9B D3 8D 8E 8F 88 F9 7E
        """
        
        #print ("".join(map("{:02X} ".format, bytes(data))))

        
        #"Decrypt" the message
        data = self.xormsg(data[5:len(data)-2])

        #print ("x{}".format(data))


        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        [9, 0, 5, 148, 5, 99, 32, 124, 96, 23, 0, 33, 110, 39, 96, 0]
        """

        # Check if the spa had anything new to say.
        # This will cause our internal states to update once per minute due
        # to the hour/minute counter.  This is ok.
        have_new_data = False
        if self.prior_status is not None:
            for i in range(0, len(data)):
                if data[i] != self.prior_status[i]:
                    have_new_data = True
                    break
        else:
            have_new_data = True
            self.prior_status = bytearray(len(data))



        self.time_hour = data[0]^6
        self.time_minute = data[11]

        circ = (data[1]>> 6) & 1
        clearray1 = (data[1] >> 5) & 1 # MIGHT BE SWAPPED WITH CIRC PUMP?
        clearray2 = (data[1] >> 7) & 1  #Ozone maybe?

        temp = float(data[14])
        if(clearray1 == 1): #Unclear why this is ncessary
            temp = temp + 32   
        
        self.curtemp = (
            temp / (2 if self.tempscale == self.TSCALE_C else 1)
            if temp != 255
            else None
        )
        
        #Not doing anything with temp 2 yet..
        t2 = data[5]   #Might need ot xor bit 2? 
        
        settemp = float(data[8])
        self.settemp = settemp / (2 if self.tempscale == self.TSCALE_C else 1)
              
        self.heatstate = (data[2] >> 5) & 1

        self.pump_status[0] = (data[2] >> 4) & 1
        self.pump_status[1] = (data[1] >> 2) & 1
        self.pump_status[2] = circ
        self.circ_pump_status = circ

        self.aux_status[0] = clearray1
        self.aux_status[1] = clearray2

        #FIND OUT IF OUR LAST COMMAND WORKED...
        sendCmd = False
        if(self.settemp  != self.targetTemp and self.targetTemp > 0 and self.checkCounter > 2):
            if self.targetTemp < self.settemp:
                await self.send_CCmessage(226) #Temp Down Key
            else:
                await self.send_CCmessage(225) #Temp Up Key
            self.checkCounter = 0
        elif self.settemp  == self.targetTemp:
            self.targetTemp = 0
        else: 
            sendCmd = True
            

        for i in range(0,len(self.target_pump_status)):
            if self.pump_status[i] != self.target_pump_status[i] and self.target_pump_status[i] >= 0:
                if self.checkCounter > 2:
                    if i == 0:
                        await self.send_CCmessage(228) #Pump 1 Button
                    elif i == 1: 
                        await self.send_CCmessage(229) #Pump 2 Button
                    else:
                        await self.send_CCmessage(239) #Clear Ray / Circulating Pump
                    self.checkCounter = 0
            elif self.pump_status[i] == self.target_pump_status[i]:
                self.target_pump_status[i] = -1
            else:
                sendCmd = True
                
        if sendCmd:
            self.checkCounter += 1

        if not have_new_data:
             return
        self.log.info("x{}".format(data))
        
        
        self.lastupd = time.time()
        # populate prior_status
        for i in range(0, len(data)):
            self.prior_status[i] = data[i]
        await self.int_new_data_cb()

    async def parse_CA_light_status_update(self, data):
        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        7E 22 FF AF CA 8A 36 CA CB C4 C5 C6 FB C0 C1 C2 3C DC DD DE DF D8 D9 DA DB D4 D5 D6 D7 D0 D1 D2 D3 EC E5 7E 
        """
        #"Decrypt" the message
        data = self.xormsg(data)
        
        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        TODO Example after decryption
        """      
        #TODO: The rest...

    async def setMyChan(self, chan):
        self.channel = chan
        self.log.info("Got assigned channel = {}".format(self.channel))
        message_length = 7
        self.NTS = bytearray(9)
        self.NTS[0] = M_STARTEND
        self.NTS[1] = message_length
        self.NTS[2] = self.channel
        self.NTS[3] = 0xBF
        self.NTS[4] = CC_REQ
        self.NTS[5] = 0 #Dummy
        self.NTS[6] = 0
        self.NTS[7] = self.balboa_calc_cs(self.NTS[1:message_length], message_length - 1)
        self.NTS[8] = M_STARTEND

    async def listen(self):
        """ Listen to the spa babble forever. """
        while True:
            if not self.connected:
                # sleep and hope the checker fixes us
                await asyncio.sleep(5)
                continue

            data = await self.read_one_message()
            if data is None:
                await asyncio.sleep(0.1)
                continue

            channel = data[2]
            mid = data[3]
            mtype = data[4]

            if mtype == STATUS_UPDATE:
                await self.parse_C4status_update(data)
            elif mtype == LIGHTS_UPDATE:
                await self.parse_CA_light_status_update(data)
            elif mtype == CLIENT_CLEAR_TO_SEND:
                if self.channel is None and self.detectChannelState == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND:
                    message_length = 8
                    data = bytearray(10)
                    data[0] = M_STARTEND
                    data[1] = message_length
                    data[2] = 0xFE
                    data[3] = 0xBF
                    data[4] = CHANNEL_ASSIGNMENT_REQ #type
                    data[5] = 0x02
                    data[6] = 0xF1 #random Magic
                    data[7] = 0x73
                    data[8] = self.balboa_calc_cs(data[1:message_length], message_length - 1)
                    data[9] = M_STARTEND
                    self.writer.write(data)
                    await self.writer.drain()                        
            elif mtype == CHANNEL_ASSIGNMENT_RESPONCE:
                #TODO check for magic numbers to be repeated back
                await setMyChan(data[5])
                message_length = 5
                data = bytearray(7)
                data[0] = M_STARTEND
                data[1] = message_length
                data[2] = self.channel
                data[3] = 0xBF
                data[4] = CHANNEL_ASSIGNMENT_ACK #type
                data[5] = self.balboa_calc_cs(data[1:message_length], message_length - 1)
                data[6] = M_STARTEND
                self.writer.write(data) 
                await self.writer.drain()                   
            elif mtype == EXISTING_CLIENT_REQ:                      
                print("Existing Client")
                message_length = 8
                data = bytearray(9)
                data[0] = M_STARTEND
                data[1] = message_length
                data[2] = self.channel
                data[3] = 0xBF
                data[4] = EXISTING_CLIENT_RESPONCE #type
                data[5] = 0x04 #Dont know!
                data[6] = 0x08 #Dont know!
                data[7] = 0x00 #Dont know!
                data[8] = self.balboa_calc_cs(data[1:message_length], message_length - 1)
                data[9] = M_STARTEND
                self.writer.write(data)
                await self.writer.drain()
            elif mtype == CLEAR_TO_SEND:               
                if not channel in  self.discoveredChannels:
                    self.discoveredChannels.append(data[2])
                    print("Discovered Channels:" + str(self.discoveredChannels))
                elif channel == self.channel:
                    if self.queue.empty():
                        #self.writer.write(self.NTS)
                        await self.writer.drain()
                    else:
                        msg = self.queue.get()
                        self.writer.write(msg)
                        await self.writer.drain()
                        print("sent")
            else:
                if mtype == CC_REQ:
                    if not channel in  self.activeChannels:
                        self.activeChannels.append(data[2])
                        print("Active Channels:" + str(self.activeChannels))
                    elif  self.detectChannelState < DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND:
                        self.detectChannelState += 1
                        print(self.detectChannelState)
                        if self.detectChannelState == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND:
                            self.discoveredChannels.sort()
                            print("Discovered Channels:" + str(self.discoveredChannels))
                            for chan in self.discoveredChannels:
                                if not chan in self.activeChannels:
                                    await self.setMyChan( chan)
                                    break
                elif (mtype > NOTHING_TO_SEND) :
                    self.log.warn("Unknown Message {:02X} {:02X} {:02X} x".format(channel, mid, mtype) + "".join(map("{:02X} ".format, bytes(data))))


                
    async def spa_configured(self):
            return True
        
   
    async def listen_until_configured(self, maxiter=20):
        """ Listen to the spa babble until we are configured."""
        return True
      
   