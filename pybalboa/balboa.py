import binascii
import numpy

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
    def __init__(self, hostname, port):
        self.initial_crc = numpy.uint8(0xb5)


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

    
