import asyncio
import binascii
import numpy
from enum import Enum

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
 BMTR_PANEL_NOCLUE2) = range(0, 14)

mtypes = [
    [ 0xFF, 0xAF, 0x13 ], # BMTR_STATUS_UPDATE
    [ 0x0A, 0xBF, 0x23 ], # BMTR_FILTER_CONFIG
    [ 0x0A, 0xBF, 0x04 ], # BMTS_CONFIG_REQ
    [ 0x0A, 0XBF, 0x94 ], # BMTR_CONFIG_RESP
    [ 0x0A, 0xBF, 0x22 ], # BMTS_FILTER_REQ
    [ 0x0A, 0xBF, 0x11 ], # BMTS_CONTROL_REQ
    [ 0x0A, 0xBF, 0x20 ], # BMTS_SET_TEMP
    [ 0x0A, 0xBF, 0x21 ], # BMTS_SET_TIME
    [ 0x0A, 0xBF, 0x92 ], # BMTS_SET_WIFI
    [ 0x0A, 0xBF, 0x22 ], # BMTS_PANEL_REQ
    [ 0x0A, 0XBF, 0x27 ], # BMTS_SET_TSCALE
    [ 0x0A, 0xBF, 0x2E ], # BMTR_PANEL_RESP
    [ 0x0A, 0xBF, 0x24 ], # BMTR_PANEL_NOCLUE1
    [ 0x0A, 0XBF, 0x25 ], # BMTR_PANEL_NOCLUE2
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
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        except (asyncio.TimeoutError, ConnectionRefusedError):
            print("Cannot connect to spa at {0}:{1}".format(self.host, self.port))
            return 1
        self.connected = True
        return 0

    async def send_config_req(self):
        """ Ask the spa for it's config. """
        if not self.connected:
            return

        data = bytearray(7)
        data[0] = M_START
        data[1] = 5 # len of msg
        data[2] = mtypes[BMTS_CONFIG_REQ][0]
        data[3] = mtypes[BMTS_CONFIG_REQ][1]
        data[4] = mtypes[BMTS_CONFIG_REQ][2]
        data[5] = 0x77 # known value
        data[6] = M_END

        self.writer.write(data)
        await self.writer.drain()

    async def read_one_message(self):
        """ Listen to the spa babble once."""
        if not self.connected:
            return None
        
        try:
            header = await self.reader.readexactly(2)
        except Exception as e:
            print('Spa read failed: {0}'.format(str(e)))
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
            print('Spa read failed: {0}'.format(str(e)))
                
        full_data = header + data
        # don't count M_START, M_END or CHECKSUM (remember that rlen is 2 short)
        crc = self.balboa_calc_cs(full_data[1:], rlen-1)
        if crc != full_data[-2]:
            print('Message had bad CRC, discarding')
            return None

        print('Message is :')
        print(full_data.hex())
        return full_data

    async def listen(self):
        """ Listen to the spa babble forever. """
        while self.connected:
            data = await self.read_one_message()
