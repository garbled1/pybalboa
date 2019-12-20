import asyncio
import numpy
import time
import logging

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
C_TEMPRANGE = 0x60
C_HEATMODE = 0x51

MAX_PUMPS = 6

NROF_BMT = 14

TSCALE_C = 1
TSCALE_F = 2

TEMPRANGE_HIGH = 1
TEMPRANGE_LOW = 2

HEATMODE_READY = 1
HEATMODE_REST = 2
HEATMODE_READY_REST = 3

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
        self.tempscale = TSCALE_F
        self.curtemp = 0.0
        self.settemp = 0.0
        self.heatmode = 0
        self.heatstate = 0
        self.temprange = 0
        self.pump_status = [0, 0, 0, 0, 0, 0]
        self.circ_pump_status = 0
        self.light_status = [0, 0]
        self.mister_status = 0
        self.aux_status = [0, 0]
        self.lastupd = 0
        self.sleep_time = 60
        self.macaddr = 'Unknown'
        self.prev_status_data = []
        self.log = logging.getLogger(__name__)

        self.TSCALE_C = TSCALE_C
        self.TSCALE_F = TSCALE_F

    def crc_update(self, crc, data, length):
        """ Update the crc value with new data
        crc = current crc value
        data = bytearray
        """

        for cur in range(length):
            for i in range(8):
                bit = bool(numpy.uint8(crc & 0x80))
                crc = numpy.uint8(numpy.uint8(crc << 1) | numpy.uint8(numpy.uint8(data[cur] >> (7 - i)) & 0x01))
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
            return 1
        self.connected = True
        return 0

    async def disconnect(self):
        """ Stop talking to the spa."""
        self.log.info("Disconnect requested")
        self.connected = False
        self.writer.close()
        await self.writer.wait_closed()

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

        if numpy.uint8(data[14] & 0x01):
            self.tempscale = TSCALE_C
        else:
            self.tempscale = TSCALE_F

        temp = float(data[7])
        settemp = float(data[25])
        if self.tempscale == TSCALE_C:
            self.curtemp = (temp - 32.0) * 5.0 / 9.0
            self.settemp = (settemp - 32.0) * 5.0 / 9.0
        else:
            self.curtemp = temp
            self.settemp = settemp

        # flag 2 is heatmode
        self.heatmode = numpy.uint8(data[10] & 0x03)

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

        for i in range(0, 2):
            if not self.aux_array[i]:
                continue
            if i == 0:
                self.aux_status[i] = numpy.uint8(data[20] & 0x08)
            else:
                self.aux_status[i] = numpy.uint8(data[20] & 0x10)

        self.lastupd = time.time()

    async def read_one_message(self):
        """ Listen to the spa babble once."""
        if not self.connected:
            return None

        try:
            header = await self.reader.readexactly(2)
        except Exception as e:
            self.log.exception('Spa read failed: {0}'.format(str(e)))
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
            self.log.exception('Spa read failed: {0}'.format(str(e)))
            return None

        full_data = header + data
        # don't count M_START, M_END or CHKSUM (remember that rlen is 2 short)
        crc = self.balboa_calc_cs(full_data[1:], rlen-1)
        if crc != full_data[-2]:
            self.log.error('Message had bad CRC, discarding')
            return None

        self.log.warning(full_data.hex())
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

        while self.connected:
            data = await self.read_one_message()
            if data is None:
                await asyncio.sleep(1)
                continue
            mtype = self.find_balboa_mtype(data)

            if mtype is None:
                self.log.error("Spa sent an unknown message type.")
                continue
            if mtype == BMTR_CONFIG_RESP:
                (self.macaddr, junk, morejunk) = self.parse_config_resp(data)
                continue
            if mtype == BMTR_STATUS_UPDATE:
                await self.parse_status_update(data)
                continue
            if mtype == BMTR_PANEL_RESP:
                self.parse_panel_config_resp(data)
                continue
            print("Unhandled mtype {0}".format(mtype))
