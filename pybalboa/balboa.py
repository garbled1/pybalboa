import asyncio
import numpy
import time
import logging
from socket import error as SocketError
import errno

BALBOA_DEFAULT_PORT = 4257

M_START = 0x7e
M_END = 0x7e

C_PUMP1 = 0x04
C_PUMP2 = 0x05
C_PUMP3 = 0x06
C_PUMP4 = 0x07
C_PUMP5 = 0x08
C_PUMP6 = 0x09
C_LIGHT1 = 0x11
C_LIGHT2 = 0x12
C_MISTER = 0x0e
C_AUX1 = 0x16
C_AUX2 = 0x17
C_BLOWER = 0x0c
C_TEMPRANGE = 0x50
C_HEATMODE = 0x51

MAX_PUMPS = 6

NROF_BMT = 14

(BMTR_STATUS_UPDATE,
 BMTR_FILTER_CONFIG,
 BMTS_CONFIG_REQ,
 BMTR_CONFIG_RESP,
 BMTS_FILTER_REQ,
 BMTS_CONTROL_REQ,
 BMTS_SET_TEMP,
 BMTS_SET_TIME,
 BMTS_SET_WIFI,
 BMTS_PANEL_REQ,
 BMTS_SET_TSCALE,
 BMTR_PANEL_RESP,
 BMTR_PANEL_NOCLUE1,
 BMTR_PANEL_NOCLUE2) = range(0, NROF_BMT)

mtypes = [
    [0xFF, 0xAF, 0x13],  # BMTR_STATUS_UPDATE
    [0x0A, 0xBF, 0x23],  # BMTR_FILTER_CONFIG
    [0x0A, 0xBF, 0x04],  # BMTS_CONFIG_REQ
    [0x0A, 0XBF, 0x94],  # BMTR_CONFIG_RESP
    [0x0A, 0xBF, 0x22],  # BMTS_FILTER_REQ
    [0x0A, 0xBF, 0x11],  # BMTS_CONTROL_REQ
    [0x0A, 0xBF, 0x20],  # BMTS_SET_TEMP
    [0x0A, 0xBF, 0x21],  # BMTS_SET_TIME
    [0x0A, 0xBF, 0x92],  # BMTS_SET_WIFI
    [0x0A, 0xBF, 0x22],  # BMTS_PANEL_REQ
    [0x0A, 0XBF, 0x27],  # BMTS_SET_TSCALE
    [0x0A, 0xBF, 0x2E],  # BMTR_PANEL_RESP
    [0x0A, 0xBF, 0x24],  # BMTR_PANEL_NOCLUE1
    [0x0A, 0XBF, 0x25],  # BMTR_PANEL_NOCLUE2
]

text_heatmode = ["Ready", "Ready in Rest", "Rest"]
text_tscale = ["Farenheit", "Celcius"]
text_timescale = ["12h", "24h"]
text_pump = ["Off", "Low", "High"]
text_temprange = ["Low", "High"]
text_blower = ["Off", "Low", "Medium", "High"]
text_switch = ["Off", "On"]
text_filter = ["Off", "Cycle 1", "Cycle 2", "Cycle 1 and 2"]

"""
The CRC is annoying.  Doing CRC's in python is even more annoying than it
should be.  I hate it.
 * Generated on Sun Apr  2 10:09:58 2017,
 * by pycrc v0.9, https://pycrc.org
 * using the configuration:
 *    Width         = 8
 *    Poly          = 0x07
 *    Xor_In        = 0x02
 *    ReflectIn     = False
 *    Xor_Out       = 0x02
 *    ReflectOut    = False
 *    Algorithm     = bit-by-bit

https://github.com/garbled1/gnhast/blob/master/balboacoll/collector.c
"""


class BalboaSpaWifi:
    def __init__(self, hostname, port=BALBOA_DEFAULT_PORT):
        # API Constants
        self.TSCALE_C = 1
        self.TSCALE_F = 0
        self.HEATMODE_READY = 0
        self.HEATMODE_RNR = 1  # Ready in Rest
        self.HEATMODE_REST = 2
        self.TIMESCALE_12H = 0
        self.TIMESCALE_24H = 1
        self.PUMP_OFF = 0
        self.PUMP_LOW = 1
        self.PUMP_HIGH = 2
        self.TEMPRANGE_LOW = 0
        self.TEMPRANGE_HIGH = 1
        self.tmin = [
            [50.0, 10.0],
            [80.0, 26.0],
        ]
        self.tmax = [
            [80.0, 26.0],
            [104.0, 40.0],
        ]
        self.BLOWER_OFF = 0
        self.BLOWER_LOW = 1
        self.BLOWER_MEDIUM = 2
        self.BLOWER_HIGH = 3
        self.FILTER_OFF = 0
        self.FILTER_1 = 1
        self.FILTER_2 = 2
        self.FILTER_1_2 = 3
        self.OFF = 0
        self.ON = 1

        # Internal states
        self.initial_crc = numpy.uint8(0xb5)
        self.host = hostname
        self.port = port
        self.reader = None
        self.writer = None
        self.connected = False
        self.config_loaded = False
        self.pump_array = [0, 0, 0, 0, 0, 0]
        self.light_array = [0, 0]
        self.circ_pump = 0
        self.blower = 0
        self.mister = 0
        self.aux_array = [0, 0]
        self.tempscale = self.TSCALE_F
        self.priming = 0
        self.timescale = 0
        self.curtemp = 0.0
        self.settemp = 0.0
        self.heatmode = 0
        self.heatstate = 0
        self.temprange = 0
        self.pump_status = [0, 0, 0, 0, 0, 0]
        self.circ_pump_status = 0
        self.light_status = [0, 0]
        self.mister_status = 0
        self.blower_status = 0
        self.aux_status = [0, 0]
        self.lastupd = 0
        self.sleep_time = 60
        self.macaddr = 'Unknown'
        self.time_hour = 0
        self.time_minute = 0
        self.filter_mode = 0
        self.prior_status = None
        self.new_data_cb = None
        self.log = logging.getLogger(__name__)

    def crc_update(self, crc, data, length):
        """ Update the crc value with new data
        crc = current crc value
        data = bytearray
        """

        for cur in range(length):
            for i in range(8):
                bit = bool(numpy.uint8(crc & 0x80))
                crc = numpy.uint8(numpy.uint8(crc << 1) |
                                  numpy.uint8(numpy.uint8(data[cur] >> (7 - i)) & 0x01))
                if (bit):
                    crc = numpy.uint8(crc ^ 0x07)
            crc &= 0xff
        return crc

    def crc_finalize(self, crc):
        """ Calculate the final CRC """
        for i in range(8):
            bit = bool(numpy.uint8(crc & 0x80))
            crc = numpy.uint8(numpy.uint8(crc << 1) | 0x00)
            if bit:
                crc ^= numpy.uint8(0x07)
        return numpy.uint8(crc ^ 0x02)

    def balboa_calc_cs(self, data, length):
        """ Calculate the checksum byte for a balboa message """

        crc = self.initial_crc
        crc = self.crc_update(crc, data, length)
        crc = self.crc_finalize(crc)
        return crc

    async def connect(self):
        """ Connect to the spa."""
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host,
                                                                     self.port)
        except (asyncio.TimeoutError, ConnectionRefusedError):
            self.log.error("Cannot connect to spa at {0}:{1}".format(self.host,
                                                                     self.port))
            return False
        self.connected = True
        return True

    async def disconnect(self):
        """ Stop talking to the spa."""
        self.log.info("Disconnect requested")
        self.connected = False
        self.writer.close()
        await self.writer.wait_closed()

    async def int_new_data_cb(self):
        """ Internal new data callback.
        Binds to self.new_data_cb()
        """

        if self.new_data_cb is None:
            return
        else:
            await self.new_data_cb()

    async def send_config_req(self):
        """ Ask the spa for it's config. """
        if not self.connected:
            return

        data = bytearray(7)
        data[0] = M_START
        data[1] = 5  # len of msg
        data[2] = mtypes[BMTS_CONFIG_REQ][0]
        data[3] = mtypes[BMTS_CONFIG_REQ][1]
        data[4] = mtypes[BMTS_CONFIG_REQ][2]
        data[5] = 0x77  # known value
        data[6] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def send_panel_req(self, ba, bb):
        """ Send a panel request, 2 bytes of data.
              0001020304 0506070809101112
        0,1 - 7E0B0ABF2E 0A0001500000BF7E
        2,0 - 7E1A0ABF24 64DC140042503230303047310451800C6B010A0200F97E
        4,0 - 7E0E0ABF25 120432635068290341197E
        """
        if not self.connected:
            return

        data = bytearray(10)
        data[0] = M_START
        data[1] = 8
        data[2] = mtypes[BMTS_PANEL_REQ][0]
        data[3] = mtypes[BMTS_PANEL_REQ][1]
        data[4] = mtypes[BMTS_PANEL_REQ][2]
        data[5] = numpy.uint8(ba)
        data[6] = 0
        data[7] = numpy.uint8(bb)
        data[8] = self.balboa_calc_cs(data[1:], 7)
        data[9] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def send_temp_change(self, newtemp):
        """ Change the set temp to newtemp. """
        if not self.connected:
            return

        # Check if the temp is valid for the heatmode
        if (newtemp < self.tmin[self.temprange][self.tempscale] or
                newtemp > self.tmax[self.temprange][self.tempscale]):
            self.log.error("Attempt to set temp outside of boundary of heatmode")
            return

        data = bytearray(8)
        data[0] = M_START
        data[1] = 6
        data[2] = mtypes[BMTS_SET_TEMP][0]
        data[3] = mtypes[BMTS_SET_TEMP][1]
        data[4] = mtypes[BMTS_SET_TEMP][2]

        if self.tempscale == self.TSCALE_C:
            newtemp *= 2.0
        val = int(round(newtemp))
        data[5] = val
        data[6] = self.balboa_calc_cs(data[1:], 5)
        data[7] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def change_light(self, light, newstate):
        """ Change light #light to newstate. """
        if not self.connected:
            return

        # we don't have 3 lights!
        if light > 1:
            return

        # we don't have THIS light
        if not self.light_array[light]:
            return

        # this is a toggle switch, not on/off
        if self.light_status[light] == newstate:
            return

        # Setup the basic things we know
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[5] = C_LIGHT1 if light == 0 else C_LIGHT2
        data[6] = 0x00  # who knows?
        data[7] = self.balboa_calc_cs(data[1:], 6)
        data[8] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def change_pump(self, pump, newstate):
        """ Change pump #pump to newstate. """
        if not self.connected:
            return

        # we don't have 7 pumps!
        if pump > MAX_PUMPS:
            return

        # we don't have THIS pump
        if not self.pump_array[pump]:
            return

        # this is a toggle switch, not on/off
        if self.pump_status[pump] == newstate:
            return

        # what we know:
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[6] = 0x00  # who knows?
        data[8] = M_END

        # calculate how many times to push the button
        for iter in range(0, 2):
            if newstate == ((self.pump_status[pump] + iter) % 3):
                break

        # now push the button until we hit desired state
        for pushes in range(0, iter):
            # 4 is 0, 5 is 2, presume 6 is 3?
            data[5] = C_PUMP1 + pump
            data[7] = self.balboa_calc_cs(data[1:], 6)
            self.writer.write(data)
            await self.writer.drain()
            await asyncio.sleep(0.5)

    async def change_heatmode(self, newmode):
        """ Change the spa's heatmode to newmode. """
        if not self.connected:
            return

        # check for sanity
        if newmode > 2:
            return

        # this is a toggle switch, not on/off
        if self.heatmode == newmode:
            return

        # what we know:
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[5] = C_HEATMODE
        data[6] = 0x00  # who knows?
        data[7] = self.balboa_calc_cs(data[1:], 6)
        data[8] = M_END

        # calculate how many times to push the button
        for iter in range(0, 3):
            if newmode == ((self.heatmode + iter) % 3):
                break
        for pushes in range(0, iter):
            self.writer.write(data)
            await self.writer.drain()
            await asyncio.sleep(0.5)

    async def change_temprange(self, newmode):
        """ Change the spa's temprange to newmode. """
        if not self.connected:
            return

        # check for sanity
        if newmode > 1:
            return

        # this is a toggle switch, not on/off
        if self.temprange == newmode:
            return

        # what we know:
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[5] = C_TEMPRANGE
        data[6] = 0x00  # who knows?
        data[7] = self.balboa_calc_cs(data[1:], 6)
        data[8] = M_END

    async def change_aux(self, aux, newstate):
        """ Change aux #aux to newstate. """
        if not self.connected:
            return

        # we don't have 3 auxs!
        if aux > 1:
            return

        # we don't have THIS aux
        if not self.aux_array[aux]:
            return

        # this is a toggle switch, not on/off
        if self.aux_status[aux] == newstate:
            return

        # Setup the basic things we know
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[5] = C_AUX1 if aux == 0 else C_AUX2
        data[6] = 0x00  # who knows?
        data[7] = self.balboa_calc_cs(data[1:], 6)
        data[8] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def change_mister(self, newmode):
        """ Change the spa's mister to newmode. """
        if not self.connected:
            return

        # check for sanity
        if newmode > 1:
            return

        # this is a toggle switch, not on/off
        if self.mister == newmode:
            return

        # what we know:
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[5] = C_MISTER
        data[6] = 0x00  # who knows?
        data[7] = self.balboa_calc_cs(data[1:], 6)
        data[8] = M_END

    async def change_blower(self, newstate):
        """ Change blower to newstate. """
        # this is a 4-mode switch
        if not self.connected:
            return

        # this is a toggle switch, not on/off
        if self.blower_status == newstate:
            return

        # what we know:
        data = bytearray(9)
        data[0] = M_START
        data[1] = 7
        data[2] = mtypes[BMTS_CONTROL_REQ][0]
        data[3] = mtypes[BMTS_CONTROL_REQ][1]
        data[4] = mtypes[BMTS_CONTROL_REQ][2]
        data[6] = 0x00  # who knows?
        data[8] = M_END

        # calculate how many times to push the button
        for iter in range(0, 4):
            if newstate == ((self.blower_status + iter) % 4):
                break

        # now push the button until we hit desired state
        for pushes in range(0, iter):
            data[5] = C_BLOWER
            data[7] = self.balboa_calc_cs(data[1:], 6)
            self.writer.write(data)
            await self.writer.drain()
            await asyncio.sleep(0.5)

    def find_balboa_mtype(self, data):
        """ Look at a message and try to figure out what type it was. """
        if len(data) < 5:
            return None
        for i in range(0, NROF_BMT):
            if (data[2] == mtypes[i][0] and
                data[3] == mtypes[i][1] and
                data[4] == mtypes[i][2]):
                return i
        return None

    def parse_config_resp(self, data):
        """ Parse a config response.

        SZ 02 03 04   05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
        1E 0A BF 94   02 14 80 00 15 27 37 EF ED 00 00 00 00 00 00 00 00 00
        23 24 25 26 27 28 29 CB
        15 27 FF FF 37 EF ED 42

        22,23,24 seems to be mac prefix,  27-29 suffix.  25/26 unk
        8-13 also full macaddr.
        05 - nrof pumps. Bitmask 2 bits per pump.
        06 - P6xxxxP5
        07 - L1xxxxL2

        I feel that the nrof pumps is untrustworthy here.
        """

        macaddr = f'{data[8]:x}:{data[9]:x}:{data[10]:x}'\
            f':{data[11]:x}:{data[12]:x}:{data[13]:x}'
        pump_array = [0, 0, 0, 0, 0, 0]
        pump_array[0] = int(numpy.uint8(data[5] & 0x03) != 0)
        pump_array[1] = int(numpy.uint8(data[5] & 0x0c) != 0)
        pump_array[2] = int(numpy.uint8(data[5] & 0x30) != 0)
        pump_array[3] = int(numpy.uint8(data[5] & 0xc0) != 0)
        pump_array[4] = int(numpy.uint8(data[6] & 0x03) != 0)
        pump_array[5] = int(numpy.uint8(data[6] & 0xc0) != 0)

        light_array = [0, 0]
        # not a typo
        light_array[1] = int(numpy.uint8(data[7] & 0x03) != 0)
        light_array[0] = int(numpy.uint8(data[7] & 0xc0) != 0)

        return (macaddr, pump_array, light_array)

    def parse_panel_config_resp(self, data):
        """ Parse a panel config response.
        SZ 02 03 04   05 06 07 08 09 10 CB
        0B 0A BF 2E   0A 00 01 50 00 00 BF

        05 - nrof pumps. Bitmask 2 bits per pump.
        06 - P6xxxxP5
        07 - L2xxxxL1 - Lights (notice the order!)
        08 - CxxxxxBL - circpump, blower
        09 - xxMIxxAA - mister, Aux2, Aux1

        """

        # pumps 0-5
        self.pump_array[0] = int(numpy.uint8(data[5] & 0x03) != 0)
        self.pump_array[1] = int(numpy.uint8(data[5] & 0x0c) != 0)
        self.pump_array[2] = int(numpy.uint8(data[5] & 0x30) != 0)
        self.pump_array[3] = int(numpy.uint8(data[5] & 0xc0) != 0)
        self.pump_array[4] = int(numpy.uint8(data[6] & 0x03) != 0)
        self.pump_array[5] = int(numpy.uint8(data[6] & 0xc0) != 0)

        # lights 0-1
        self.light_array[0] = int(numpy.uint8(data[7] & 0x03) != 0)
        self.light_array[1] = int(numpy.uint8(data[7] & 0xc0) != 0)

        self.circ_pump = int(numpy.uint8(data[8] & 0x80) != 0)
        self.blower = int(numpy.uint8(data[8] & 0x03) != 0)
        self.mister = int(numpy.uint8(data[9] & 0x30) != 0)

        self.aux_array[0] = int(numpy.uint8(data[9] & 0x01) != 0)
        self.aux_array[1] = int(numpy.uint8(data[9] & 0x02) != 0)

        self.config_loaded = True

    async def parse_status_update(self, data):
        """ Parse a status update from the spa.
        Normally the spa spams these at a very high rate of speed. However,
        once in a while it will decide to just stop.  If you send it a panel
        conf request, it will resume.

        00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
        MS ML MT MT MT XX F1 CT HH MM F2  X  X  X F3 F4 PP  X CP LF MB  X  X  X
        7E 1D FF AF 13  0  0 64  8 2D  0  0  1  0  0  4  0  0  0  0  0  0  0  0

        24 25 26 27 28 29 30
        X  ST X  X  X CB  ME
        0  64 0  0  0  6  7E

        20- mister/blower
        """

        # If we don't know the config, just ask for it and wait for that
        if not self.config_loaded:
            await self.send_panel_req(0, 1)
            return

        # Check if the spa had anything new to say.
        # This will cause our internal states to update once per minute due
        # to the hour/minute counter.  This is ok.
        have_new_data = False
        if self.prior_status is not None:
            for i in range(0, 31):
                if data[i] != self.prior_status[i]:
                    have_new_data = True
                    break
        else:
            have_new_data = True
            self.prior_status = bytearray(31)

        if not have_new_data:
            return

        if numpy.uint8(data[14] & 0x01):
            self.tempscale = self.TSCALE_C
        else:
            self.tempscale = self.TSCALE_F

        self.time_hour = data[8]
        self.time_minute = data[9]
        if numpy.uint8(data[14] & 0x02):
            self.timescale = self.TIMESCALE_12H
        else:
            self.timescale = self.TIMESCALE_24H

        temp = float(data[7])
        settemp = float(data[25])
        if self.tempscale == self.TSCALE_C:
            self.curtemp = temp / 2.0
            self.settemp = settemp / 2.0
        else:
            self.curtemp = temp
            self.settemp = settemp

        # flag 2 is heatmode
        self.heatmode = numpy.uint8(data[10] & 0x03)

        # flag 3 is filter mode
        self.filter_mode = numpy.uint8((data[14] & 0x0c) >> 2)

        # flag 4 heating, temp range
        self.heatstate = numpy.uint8((data[15] & 0x30) >> 4)
        self.temprange = numpy.uint8((data[15] & 0x04) >> 2)

        for i in range(0, 6):
            if not self.pump_array[i]:
                continue
            # 1-4 are in one byte, 5/6 are in another
            if i < 4:
                self.pump_status[i] = numpy.uint8((data[16] >> i) & 0x03)
            else:
                self.pump_status[i] = numpy.uint8((data[17] >> (i-4)) & 0x03)

        if self.circ_pump:
            if data[18] == 0x02:
                self.circ_pump_status = 1
            else:
                self.circ_pump_status = 0

        for i in range(0, 2):
            if not self.light_array[i]:
                continue
            self.light_status[i] = numpy.uint8(data[19] >> i & 0x03)

        if self.mister:
            self.mister_status = numpy.uint8(data[20] & 0x01)

        if self.blower:
            self.blower_status = numpy.uint8((data[18] & 0x0c) >> 2)

        for i in range(0, 2):
            if not self.aux_array[i]:
                continue
            if i == 0:
                self.aux_status[i] = numpy.uint8(data[20] & 0x08)
            else:
                self.aux_status[i] = numpy.uint8(data[20] & 0x10)

        self.lastupd = time.time()
        # populate prior_status
        for i in range(0, 31):
            self.prior_status[i] = data[i]
        await self.int_new_data_cb()

    async def read_one_message(self):
        """ Listen to the spa babble once."""
        if not self.connected:
            return None

        try:
            header = await self.reader.readexactly(2)
        except SocketError as err:
            if err.errno == errno.ECONNRESET:
                self.log.error('Connection reset by peer')
                self.connected = False
            else:
                self.log.error('Spa socket error: {0}'.format(str(err)))
            return None
        except Exception as e:
            self.log.error('Spa read failed: {0}'.format(str(e)))
            return None

        if header[0] == M_START:
            # header[1] is size, + checksum + M_END (we already read 2 tho!)
            rlen = header[1]
        else:
            return None

        # now get the rest of the data
        try:
            data = await self.reader.readexactly(rlen)
        except Exception as e:
            self.log.errpr('Spa read failed: {0}'.format(str(e)))
            return None

        full_data = header + data
        # don't count M_START, M_END or CHKSUM (remember that rlen is 2 short)
        crc = self.balboa_calc_cs(full_data[1:], rlen-1)
        if crc != full_data[-2]:
            self.log.error('Message had bad CRC, discarding')
            return None

        # self.log.debug(full_data.hex())
        return full_data

    async def check_connection_status(self):
        """ Set this up to periodically check the spa connection and fix. """
        while True:
            if not self.connected:
                self.log.error("Lost connection to spa, attempting reconnect.")
                await self.connect()
                await asyncio.sleep(10)
                continue
            if (self.lastupd + 5 * self.sleep_time) < time.time():
                self.log.error("Spa stopped responding, requesting panel config.")
                await self.send_panel_req(0, 1)
            await asyncio.sleep(self.sleep_time)

    async def listen(self):
        """ Listen to the spa babble forever. """

        while True:
            if not self.connected:
                # sleep and hope the checker fixes us
                await asyncio.sleep(5)
                continue
            data = await self.read_one_message()
            if data is None:
                await asyncio.sleep(1)
                continue
            mtype = self.find_balboa_mtype(data)

            if mtype is None:
                self.log.error("Spa sent an unknown message type.")
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_CONFIG_RESP:
                (self.macaddr, junk, morejunk) = self.parse_config_resp(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_STATUS_UPDATE:
                await self.parse_status_update(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_PANEL_RESP:
                self.parse_panel_config_resp(data)
                await asyncio.sleep(0.1)
                continue
            self.log.error("Unhandled mtype {0}".format(mtype))

    async def spa_configured(self):
        """Check if the spa has been configured.
        Use in conjunction with listen.  First listen, then send some config
        commands to set the spa up.
        """
        await self.send_config_req()
        await self.send_panel_req(0, 1)
        while True:
            if (self.connected
                    and self.config_loaded
                    and self.macaddr != 'Unknown'
                    and self.curtemp != 0.0):
                return
            await asyncio.sleep(1)

    async def listen_until_configured(self, maxiter=20):
        """ Listen to the spa babble until we are configured."""

        if not self.connected:
            return False
        for i in range(0, maxiter):
            if (self.config_loaded and self.macaddr != 'Unknown'
                    and self.curtemp != 0.0):
                return True
            data = await self.read_one_message()
            if data is None:
                await asyncio.sleep(1)
                continue
            mtype = self.find_balboa_mtype(data)

            if mtype is None:
                self.log.error("Spa sent an unknown message type.")
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_CONFIG_RESP:
                (self.macaddr, junk, morejunk) = self.parse_config_resp(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_STATUS_UPDATE:
                await self.parse_status_update(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_PANEL_RESP:
                self.parse_panel_config_resp(data)
                await asyncio.sleep(0.1)
                continue
            self.log.error("Unhandled mtype {0}".format(mtype))
        return False

    # Simple accessors
    def get_tempscale(self, text=False):
        """ What is our tempscale? """
        if text:
            return text_tscale[self.tempscale]
        return self.tempscale

    def get_timescale(self, text=False):
        """ What is our timescale? """
        if text:
            return text_timescale[self.timescale]
        return self.timescale

    def get_settemp(self):
        """ Ask for the set temp. """
        return self.settemp

    def get_curtemp(self):
        """ Ask for the current temp. """
        return self.curtemp

    def get_heatmode(self, text=False):
        """ Ask for the current heatmode. """
        if text:
            return text_heatmode[self.heatmode]
        return self.heatmode

    def get_heatstate(self, text=False):
        """ Ask for the current heat state. """
        if text:
            return text_switch[self.heatstate]
        return self.heatstate

    def get_temprange(self, text=False):
        """ Ask for the current temp range. """
        if text:
            return text_temprange[self.temprange]
        return self.temprange

    def have_pump(self, pump):
        """ Do we have a pump numbered pump? """
        if pump > MAX_PUMPS:
            return False
        return bool(self.pump_array[pump])

    def get_pump(self, pump, text=False):
        """ Ask for the pump status for pump #pump. """
        if not self.have_pump(pump):
            return None
        if text:
            return text_pump[self.pump_status[pump]]
        return self.pump_status[pump]

    def have_light(self, light):
        """ Do we have a light numbered light? """
        if light > 1:
            return False
        return bool(self.light_array[light])

    def get_light(self, light, text=False):
        """ Ask for the light status for light #light. """
        if not self.have_light(light):
            return None
        if text:
            return text_switch[self.light_status[light]]
        return self.light_status[light]

    def have_aux(self, aux):
        """ Do we have a aux numbered aux? """
        if aux > 1:
            return False
        return bool(self.aux_array[aux])

    def get_aux(self, aux, text=False):
        """ Ask for the aux status for aux #aux. """
        if not self.have_aux(aux):
            return None
        if text:
            return text_switch[self.aux_status[aux]]
        return self.aux_status[aux]

    def have_blower(self):
        """ Do we have a blower? """
        return bool(self.blower)

    def get_blower(self, text=False):
        """ Ask for blower status. """
        if not self.have_blower():
            return None
        if text:
            return text_blower[self.blower_status]
        return self.blower_status

    def have_mister(self):
        """ Do we have a mister? """
        return bool(self.mister)

    def get_mister(self, text=False):
        """ Ask for mister status. """
        if not self.have_mister():
            return None
        if text:
            return text_switch[self.mister_status]
        return self.mister_status

    def have_circ_pump(self):
        """ Do we have a circ_pump? """
        return bool(self.circ_pump)

    def get_circ_pump(self, text=False):
        """ Ask for circ_pump status. """
        if not self.have_circ_pump():
            return None
        if text:
            return text_switch[self.circ_pump_status]
        return self.circ_pump_status

    def get_macaddr(self):
        """ Return the macaddr of the spa wifi """
        return self.macaddr

    def get_filtermode(self, text=False):
        """ Return the filtermode. """
        if text:
            return text_filter[self.filter_mode]
        return self.filter_mode

    # Get lists of text values of various bits

    def get_heatmode_stringlist(self):
        """ Return a list of heatmode strings. """
        return text_heatmode

    def get_tscale_stringlist(self):
        """Return a list of temperature scale strings."""
        return text_tscale

    def get_timescale_stringlist(self):
        """Return a list of timescale strings."""
        return text_timescale

    def get_pump_stringlist(self):
        """Return a list of pump status strings."""
        return text_pump

    def get_temprange_stringlist(self):
        """Return a list of temperature range strings."""
        return text_temprange

    def get_blower_stringlist(self):
        """Return a list of blower status strings."""
        return text_blower

    def get_switch_stringlist(self):
        """Return a list of switch state strings."""
        return text_switch

    def get_filter_stringlist(self):
        """Return a list of filter state strings."""
        return text_filter

    # tell us about the config

    def get_nrof_pumps(self):
        """Return how many pumps we have."""
        pumps = 0
        for p in self.pump_array:
            if p:
                pumps += 1
        return pumps

    def get_nrof_lights(self):
        """Return how many lights we have."""
        lights = 0
        for l in self.light_array:
            if l:
                lights += 1
        return lights

    def get_nrof_aux(self):
        """Return how many aux devices we have."""
        aux = 0
        for l in self.aux_array:
            if l:
                aux += 1
        return aux

    def get_pump_list(self):
        """Return the actual pump list."""
        return self.pump_array

    def get_light_list(self):
        """Return the actual light list."""
        return self.light_array

    def get_aux_list(self):
        """Return the actual aux list."""
        return self.aux_array
