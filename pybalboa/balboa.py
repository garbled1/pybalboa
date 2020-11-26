import asyncio
import errno
import logging
import time
import warnings
from socket import error as SocketError

BALBOA_DEFAULT_PORT = 4257

M_STARTEND = 0x7e

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
 BMTR_FILTER_INFO_RESP,
 BMTS_CONFIG_REQ,
 BMTR_MOD_IDENT_RESP,
 BMTS_FILTER_REQ,
 BMTS_CONTROL_REQ,
 BMTS_SET_TEMP,
 BMTS_SET_TIME,
 BMTS_SET_WIFI,
 BMTS_PANEL_REQ,
 BMTS_SET_TSCALE,
 BMTR_DEVICE_CONFIG_RESP,
 BMTR_SYS_INFO_RESP,
 BMTR_SETUP_PARAMS_RESP) = range(0, NROF_BMT)

mtypes = [
    [0xFF, 0xAF, 0x13],  # BMTR_STATUS_UPDATE
    [0x0A, 0xBF, 0x23],  # BMTR_FILTER_INFO_RESP
    [0x0A, 0xBF, 0x04],  # BMTS_CONFIG_REQ
    [0x0A, 0XBF, 0x94],  # BMTR_MOD_IDENT_RESP
    [0x0A, 0xBF, 0x22],  # BMTS_FILTER_REQ
    [0x0A, 0xBF, 0x11],  # BMTS_CONTROL_REQ
    [0x0A, 0xBF, 0x20],  # BMTS_SET_TEMP
    [0x0A, 0xBF, 0x21],  # BMTS_SET_TIME
    [0x0A, 0xBF, 0x92],  # BMTS_SET_WIFI
    [0x0A, 0xBF, 0x22],  # BMTS_PANEL_REQ
    [0x0A, 0XBF, 0x27],  # BMTS_SET_TSCALE
    [0x0A, 0xBF, 0x2E],  # BMTR_DEVICE_CONFIG_RESP
    [0x0A, 0xBF, 0x24],  # BMTR_SYS_INFO_RESP
    [0x0A, 0XBF, 0x25],  # BMTR_SETUP_PARAMS_RESP
]

text_heatmode = ["Ready", "Rest", "Ready in Rest"]
text_heatstate = ["Idle", "Heating", "Heat Waiting"]
text_tscale = ["Fahrenheit", "Celcius"]
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
        self.HEATMODE_REST = 1
        self.HEATMODE_RNR = 2
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
        self.HEATSTATE_IDLE = 0
        self.HEATSTATE_HEATING = 1
        self.HEATSTATE_HEAT_WAITING = 2
        self.VOLTAGE_240 = 240
        self.VOLTAGE_UNKNOWN = 0
        self.HEATERTYPE_STANDARD = "Standard"
        self.HEATERTYPE_UNKNOWN = "Unknown"

        # Internal states
        self.host = hostname
        self.port = port
        self.reader = None
        self.writer = None
        self.connected = False
        self.config_loaded = False
        self.pump_array = [0, 0, 0, 0, 0, 0]
        self.nr_of_pumps = 0
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
        self.wifistate = 0
        self.lastupd = 0
        self.sleep_time = 60
        self.macaddr = 'Unknown'
        self.idigi_device_id = 'Unknown'
        self.time_hour = 0
        self.time_minute = 0
        self.filter_mode = 0
        self.prior_status = None
        self.new_data_cb = None
        self.model_name = 'Unknown'
        self.sw_vers = 'Unknown'
        self.cfg_sig = 'Unknown'
        self.setup = 0
        self.ssid = 'Unknown'
        self.voltage = 0
        self.heater_type = 'Unknown'
        self.dip_switch = '0000000000000000'
        self.filter1_hour = 0
        self.filter1_minute = 0
        self.filter1_duration_hours = 0
        self.filter1_duration_minutes = 0
        self.filter2_enabled = 0
        self.filter2_hour = 0
        self.filter2_minute = 0
        self.filter2_duration_hours = 0
        self.filter2_duration_minutes = 0
        self.log = logging.getLogger(__name__)

    def to_celsius(self, fahrenheit):
        return .5 * round(((fahrenheit-32) / 1.8) / .5)

    def balboa_calc_cs(self, data, length):
        """ Calculate the checksum byte for a balboa message """
        crc = 0xb5
        for cur in range(length):
            for i in range(8):
                bit = crc & 0x80
                crc = ((crc << 1) & 0xff) | ((data[cur] >> (7 - i)) & 0x01)
                if (bit):
                    crc = crc ^ 0x07
            crc &= 0xff
        for i in range(8):
            bit = crc & 0x80
            crc = (crc << 1) & 0xff
            if bit:
                crc ^= 0x07
        return crc ^ 0x02

    async def connect(self):
        """ Connect to the spa."""
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host,
                                                                     self.port)
        except (asyncio.TimeoutError, ConnectionRefusedError):
            self.log.error("Cannot connect to spa at {0}:{1}".format(self.host,
                                                                     self.port))
            return False
        except Exception as e:
            self.log.error(
                f'Error connecting to spa at {self.host}:{self.port}: {e}')
            return False
        self.connected = True
        return True

    async def disconnect(self):
        """ Stop talking to the spa."""
        self.log.info("Disconnect requested")
        self.connected = False
        if not self.writer._loop.is_closed():
            self.writer.close()
            await self.writer.wait_closed()
        await self.int_new_data_cb()

    async def int_new_data_cb(self):
        """ Internal new data callback.
        Binds to self.new_data_cb()
        """

        if self.new_data_cb is None:
            return
        else:
            await self.new_data_cb()

    async def send_config_req(self):
        """ send_config_req() has been deprecated in favor of send_mod_ident_req() """
        warnings.warn(
            "send_config_req() has been deprecated in favor of send_mod_ident_req()", DeprecationWarning)
        return await self.send_mod_ident_req()

    async def send_mod_ident_req(self):
        """ Ask for the module identification. """
        await self.send_message(*mtypes[BMTS_CONFIG_REQ])

    async def send_panel_req(self, ba, bb):
        """ Send a panel request, 2 bytes of data.
              0001020304 0506070809101112
        0,1 - 7E0B0ABF2E 0A0001500000BF7E
        2,0 - 7E1A0ABF24 64DC140042503230303047310451800C6B010A0200F97E
        4,0 - 7E0E0ABF25 120432635068290341197E
        """
        await self.send_message(*mtypes[BMTS_PANEL_REQ], ba, 0, bb)

    async def send_temp_change(self, newtemp):
        """ Change the set temp to newtemp. """
        # Check if the new temperature is valid for the current heat mode
        if (newtemp < self.tmin[self.temprange][self.tempscale] or
                newtemp > self.tmax[self.temprange][self.tempscale]):
            self.log.error(
                "Attempt to set temperature outside of heat mode boundary")
            return

        if self.tempscale == self.TSCALE_C:
            newtemp *= 2.0

        await self.send_message(*mtypes[BMTS_SET_TEMP], int(round(newtemp)))

    async def change_light(self, light, newstate):
        """ Change light #light to newstate. """
        # sanity check
        if (light > 1
                or not self.light_array[light]
                or self.light_status[light] == newstate):
            return

        await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_LIGHT1 if light == 0 else C_LIGHT2, 0x00)

    async def change_pump(self, pump, newstate):
        """ Change pump #pump to newstate. """
        # sanity check
        if (pump > MAX_PUMPS
                or newstate > self.pump_array[pump]
                or self.pump_status[pump] == newstate):
            return

        # toggle until we hit the desired state
        for i in range(0, (newstate-self.pump_status[pump]) % (self.pump_array[pump]+1)):
            await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_PUMP1 + pump, 0x00)
            await asyncio.sleep(1.0)

    async def change_heatmode(self, newmode):
        """Change the spa's heat mode.

        A spa cannot be put into Ready in Rest (RNR). It can be in RNR, but you cannot
        force it into RNR. It's a tri-state, but a binary switch.

        :param newmode: The new heat mode.
        """
        # sanity check
        if (newmode > 2
                or self.heatmode == newmode
                or newmode == self.HEATMODE_RNR):  # also can't change mode to Ready in Rest
            return

        # if currently in ready in rest and changing to ready, the first toggle
        # will set the heat mode to rest, so we need to toggle an additional time
        if (newmode == self.HEATMODE_READY and self.heatmode == self.HEATMODE_RNR):
            await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_HEATMODE, 0x00)
            await asyncio.sleep(0.5)

        await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_HEATMODE, 0x00)

    async def change_temperature_unit(self, temperature_unit):
        """Change the spa's temperature unit.

        :param temperature_unit: The new temperature unit.
        """
        # sanity check
        if (temperature_unit > 1
                or self.tempscale == temperature_unit):
            return

        await self.send_message(*mtypes[BMTS_SET_TSCALE], 0x01, temperature_unit)

    async def change_temprange(self, newmode):
        """ Change the spa's temprange to newmode. """
        # sanity check
        if (newmode > 1 or self.temprange == newmode):
            return

        await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_TEMPRANGE, 0x00)

    async def change_aux(self, aux, newstate):
        """ Change aux #aux to newstate. """
        # sanity check
        if (aux > 1
                or not self.aux_array[aux]
                or self.aux_status[aux] == newstate):
            return

        await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_AUX1 if aux == 0 else C_AUX2, 0x00)

    async def change_mister(self, newmode):
        """ Change the spa's mister to newmode. """
        # sanity check
        if (newmode > 1
                or self.mister == newmode):
            return

        await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_MISTER, 0x00)

    async def change_blower(self, newstate):
        """ Change blower to newstate. """
        # sanity check
        if (not self.have_blower()
                or self.blower_status == newstate
                or newstate > 3):
            return

        # toggle until we hit the desired state
        for i in range(0, ((newstate-self.blower_status) % 4)):
            await self.send_message(*mtypes[BMTS_CONTROL_REQ], C_BLOWER, 0x00)
            await asyncio.sleep(0.5)

    async def set_time(self, new_time, timescale=None):
        """ Set time on spa to new_time with optional timescale. """
        # sanity check
        if (not isinstance(new_time, time.struct_time)):
            return

        await self.send_message(*mtypes[BMTS_SET_TIME],
                                ((self.timescale if timescale is None else timescale)
                                 << 7) + new_time.tm_hour,
                                new_time.tm_min)

    async def send_message(self, *bytes):
        """ Sends a message to the spa with variable length bytes. """
        # if not connected, we can't send a message
        if not self.connected:
            return

        message_length = len(bytes)+2
        data = bytearray(message_length+2)
        data[0] = M_STARTEND
        data[1] = message_length
        data[2:message_length] = bytes
        data[-2] = self.balboa_calc_cs(data[1:message_length],
                                       message_length-1)
        data[-1] = M_STARTEND

        self.log.debug(f'Sending message: {data.hex()}')
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            self.log.error(f'Error sending message: {e}')

    def find_balboa_mtype(self, data):
        """ Look at a message and try to figure out what type it was. """
        if len(data) < 5:
            return None
        for i in range(0, NROF_BMT):
            if (data[2] == mtypes[i][0]
                    and data[3] == mtypes[i][1]
                    and data[4] == mtypes[i][2]):
                return i
        return None

    def parse_noclue1(self, data):
        """ parse_noclue1(data) has been deprecated in favor of parse_system_information(data) """
        warnings.warn(
            "parse_noclue1(data) has been deprecated in favor of parse_system_information(data)", DeprecationWarning)
        return self.parse_system_information(data)

    def parse_system_information(self, data):
        """ Parse a system information response.

        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
        ML 02 03 04 I0 I1 V0 V1 T1 T2 T3 T4 T5 T6 T7 T8 SU S0 S1 S2 S3 HV HT D0 D1 26
        1a 0a bf 24 64 dc 14 00 42 50 32 30 30 30 47 31 04 51 80 0c 6b 01 0a 02 00 f9
        Bullfrog Stil7 / BWGWIFI1:
        1A 0A BF 24 64 DC 24 00 42 46 42 50 32 30 53 20 03 5C D4 CC D7 01 0A 00 00 DE

        SSID = "M100_220 V20.0" so "M[I0]_[I1] V[V0].[V1]"
        V0.V1 = Software Vers (ex 20.0)
        T1-T8 = model name in ascii
        SU = Setup
        S0-S3 = "Configuration Signature"
        HV = Heat Voltage, 01 = 240V, other unknown
        HT = Heater Type, 0A = Standard, other unknown
        D0D1 = dip switch setting of spa

        Examples:
        7e1a0abf24 64dc 1400 4250323030304731 04 51800c6b 01 0a 0200 f9 7e <-- mine
        7e1a0abf24 64c9 1300 4d51425035303120 01 0403daed 01 06 0400 35 7e
        7e1a0abf24 64e1 2400 4d53343045202020 01 c3479636 03 0a 4400 19 7e
        7e1a0abf24 64e1 1400 4250323130304731 11 ebce9fd8 03 0a 1600 d7 7e
        7e1a0abf24 64dc 2400 4246425032305320 03 5cd4ccd7 01 0a 0000 de 7e

        """

        self.sw_vers = f'{data[7]}.{data[8]}'
        self.ssid = f'M{data[5]}_{data[6]} V{self.sw_vers}'
        self.model_name = "".join(map(chr, data[9:17])).strip()
        self.setup = data[17]
        self.cfg_sig = f"{data[18]:x}{data[19]:x}{data[20]:x}{data[21]:x}"
        self.voltage = self.VOLTAGE_240 if data[22] == 0x01 else self.VOLTAGE_UNKNOWN
        self.heater_type = self.HEATERTYPE_STANDARD if data[23] == 0x0A else self.HEATERTYPE_UNKNOWN
        self.dip_switch = f'{data[24]:08b}{data[25]:08b}'

    def parse_setup_parameters(self, data):
        """ Parse a setup parameters response.

        01 02 03 04 05 06 07 08 09 10 11 12 13 14
        ML AD PF PT 05 06 LL LH HL HH 11 12 13 CB
        Bullfrog Stil7 / BWGWIFI1:
        0E 0A BF 25 04 03 32 63 50 68 E9 01 45 4F

        05-06 - unknown
        07 = LL (low low) low range temperature's minimum
        08 - LH (low high) low range temperature's maximum
        09 - HL (high low) high range temperature's minimum
        10 - HH (high high) high range temperature's maximum
        11 - unknown
        12 - number of pumps
        13 - unknown
        """

        # store low range min and max temperatures as [°F, °C]
        self.tmin[0] = [data[7], self.to_celsius(data[7])]
        self.tmax[0] = [data[8], self.to_celsius(data[8])]

        # store high range min and max temperatures as [°F, °C]
        self.tmin[1] = [data[9], self.to_celsius(data[9])]
        self.tmax[1] = [data[10], self.to_celsius(data[10])]

        self.nr_of_pumps = (data[12] & 1)\
            + (data[12] >> 1 & 1)\
            + (data[12] >> 2 & 1)\
            + (data[12] >> 3 & 1)\
            + (data[12] >> 4 & 1)\
            + (data[12] >> 5 & 1)

    def parse_config_resp(self, data):
        """ parse_config_resp(data) has been deprecated in favor of parse_module_identification(data) """
        warnings.warn(
            "parse_config_resp(data) has been deprecated in favor of parse_module_identification(data)", DeprecationWarning)
        self.parse_module_identification(data)
        return (self.macaddr, self.pump_array, self.light_array)

    def parse_module_identification(self, data):
        """ Parse a module identification response.

        ML 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 CB
        1E 0A BF 94 02 14 80 00 15 27 37 EF ED 00 00 00 00 00 00 00 00 00 15 27 FF FF 37 EF ED 42
        Bullfrog Stil7 / BWGWIFI1:
        1E 0A BF 94 02 14 80 00 15 27 ## ## ## 00 00 00 00 00 00 00 00 00 15 27 FF FF ## ## ## ##

        05-07 - unknown
        08-13 - mac address
        14-29 - iDigi device id (used to communicate with Balboa cloud API)
        """

        self.macaddr = f'{data[8]:02x}:{data[9]:02x}:{data[10]:02x}'\
            f':{data[11]:02x}:{data[12]:02x}:{data[13]:02x}'
        self.idigi_device_id = f'{data[14:18].hex()}-{data[18:22].hex()}-{data[22:26].hex()}-{data[26:30].hex()}'.upper()

    def parse_panel_config_resp(self, data):
        """ parse_panel_config_resp(data) has been deprecated in favor of parse_device_configuration(data) """
        warnings.warn(
            "parse_panel_config_resp(data) has been deprecated in favor of parse_device_configuration(data)", DeprecationWarning)
        return self.parse_device_configuration(data)

    def parse_device_configuration(self, data):
        """ Parse a panel config response.
        ML 02 03 04 05 06 07 08 09 10 CB
        0B 0A BF 2E 0A 00 01 50 00 00 BF
        Bullfrog Stil7 / BWGWIFI1:
        0B 0A BF 2E 02 00 05 D0 00 00 A3

        *** each bit pair appears to indicate the number of settings per "device"
        *** so if you have the byte "0A" in byte 05 (pumps 1-4), this translates to 00001010 in binary
        *** pump 1 is then "10" (the right most bit pair) which equals 2 to indicate 2 settings (low/high) in addition to "off" 
        *** pump 2 is also "10" to indicate 2 settings, while pump 3 and 4 are "00" so only "off" (or not available) exists
        05 - P4P3P2P1 - Pumps 1-4
        06 - P6xxxxP5 - Pumps 5-6
        07 - xxxxL2L1 - Lights 1-2
        08 - CxxxxxBL - circpump, blower
        09 - xxMIxxAA - mister, Aux2, Aux1

        """

        # pumps 0-5
        self.pump_array[0] = int((data[5] & 0x03))
        self.pump_array[1] = int((data[5] & 0x0c) >> 2)
        self.pump_array[2] = int((data[5] & 0x30) >> 4)
        self.pump_array[3] = int((data[5] & 0xc0) >> 6)
        self.pump_array[4] = int((data[6] & 0x03))
        self.pump_array[5] = int((data[6] & 0xc0) >> 6)

        # lights 0-1
        self.light_array[0] = int((data[7] & 0x03))
        self.light_array[1] = int((data[7] >> 2) & 0x03)

        self.circ_pump = int((data[8] & 0x80) != 0)
        self.blower = int((data[8] & 0x03) != 0)
        self.mister = int((data[9] & 0x30) != 0)

        self.aux_array[0] = int((data[9] & 0x01) != 0)
        self.aux_array[1] = int((data[9] & 0x02) != 0)

        self.config_loaded = True

    def parse_filter_cycle_info(self, data):
        """ Parse a filter cycle info response.
        01 02 03 04 05 06 07 08 09 10 11 12 13
        ML AD PF PT 1H 1M 1D 1E 2H 2M 2D 2E CB
        Bullfrog Stil7 / BWGWIFI1:
        0D 0A BF 23 13 00 02 00 88 00 01 00 9F

        1H - filter cycle 1's start hour
        1M - filter cycle 1's start minute
        1D - filter cycle 1's duration hours
        1E - filter cycle 1's duration minutes
        2H - filter cycle 2's start hour
        2M - filter cycle 2's start minute
        2D - filter cycle 2's duration hours
        2E - filter cycle 2's duration minutes
        """
        self.filter1_hour = data[5]
        self.filter1_minute = data[6]
        self.filter1_duration_hours = data[7]
        self.filter1_duration_minutes = data[8]
        self.filter2_enabled = data[9] >> 7
        self.filter2_hour = data[9] ^ (self.filter2_enabled << 7)
        self.filter2_minute = data[10]
        self.filter2_duration_hours = data[11]
        self.filter2_duration_minutes = data[12]

    async def parse_status_update(self, data):
        """ Parse a status update from the spa.
        Normally the spa spams these at a very high rate of speed. However,
        once in a while it will decide to just stop.  If you send it a panel
        conf request, it will resume.

        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        ML MT MT MT HM F1 CT HH MM F2  X  X  X F3 F4 PP  X CP LF MB  X  X  X  X ST  X  X  X CB
        1D FF AF 13  0  0 64  8 2D  0  0  1  0  0  4  0  0  0  0  0  0  0  0  0 64  0  0  0  6
        1D FF AF 13 00 01 FF 09 0A 01 26 01 00 02 00 00 00 00 00 00 00 00 02 00 5B 00 00 12 7E

        20 - mister/blower
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

        if data[14] & 0x01:
            self.tempscale = self.TSCALE_C
        else:
            self.tempscale = self.TSCALE_F

        self.time_hour = data[8]
        self.time_minute = data[9]
        if data[14] & 0x02 == 0:
            self.timescale = self.TIMESCALE_12H
        else:
            self.timescale = self.TIMESCALE_24H

        temp = float(data[7])
        settemp = float(data[25])
        self.curtemp = temp / (2 if self.tempscale ==
                               self.TSCALE_C else 1) if temp != 255 else None
        self.settemp = settemp / (2 if self.tempscale == self.TSCALE_C else 1)

        # flag 2 is heatmode
        self.heatmode = data[10] & 0x03

        # flag 3 is filter mode
        self.filter_mode = (data[14] & 0x0c) >> 2

        # flag 4 heating, temp range
        self.heatstate = (data[15] & 0x30) >> 4
        self.temprange = (data[15] & 0x04) >> 2

        for i in range(0, 6):
            if not self.pump_array[i]:
                continue
            # 1-4 are in one byte, 5/6 are in another
            if i < 4:
                self.pump_status[i] = (data[16] >> i*2) & 0x03
            else:
                self.pump_status[i] = (data[17] >> ((i - 4)*2)) & 0x03

        if self.circ_pump:
            if data[18] == 0x02:
                self.circ_pump_status = 1
            else:
                self.circ_pump_status = 0

        for i in range(0, 2):
            if not self.light_array[i]:
                continue
            self.light_status[i] = ((data[19] >> i*2) & 0x03) >> 1

        if self.mister:
            self.mister_status = data[20] & 0x01

        if self.blower:
            self.blower_status = (data[18] & 0x0c) >> 2

        for i in range(0, 2):
            if not self.aux_array[i]:
                continue
            if i == 0:
                self.aux_status[i] = data[20] & 0x08
            else:
                self.aux_status[i] = data[20] & 0x10

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
            elif err.errno == errno.EHOSTUNREACH:
                self.log.error('Spa unreachable')
            elif err.errno == errno.EPIPE:
                self.log.error('Broken pipe')
            else:
                self.log.error('Spa socket error: {0}'.format(str(err)))
            self.connected = False
            await self.int_new_data_cb()
            return None
        except Exception as e:
            self.log.error('Spa read failed: {0}'.format(str(e)))
            return None

        if header[0] == M_STARTEND:
            # header[1] is size, + checksum + M_STARTEND (we already read 2 tho!)
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
        # don't count M_STARTENDs or CHKSUM (remember that rlen is 2 short)
        crc = self.balboa_calc_cs(full_data[1:], rlen-1)
        if crc != full_data[-2]:
            self.log.error('Message had bad CRC, discarding')
            return None

        # self.log.error('got update: {}'.format(full_data.hex()))
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
                self.log.error(
                    "Spa stopped responding, requesting panel config.")
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
                self.log.error(f"Spa sent an unknown message: {data.hex()}")
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_MOD_IDENT_RESP:
                self.parse_module_identification(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_STATUS_UPDATE:
                await self.parse_status_update(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_DEVICE_CONFIG_RESP:
                self.parse_device_configuration(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_SYS_INFO_RESP:
                self.parse_system_information(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_SETUP_PARAMS_RESP:
                self.parse_setup_parameters(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_FILTER_INFO_RESP:
                self.parse_filter_cycle_info(data)
                await asyncio.sleep(0.1)
                continue
            self.log.error("Unhandled mtype {0}".format(mtype))

    async def spa_configured(self):
        """Check if the spa has been configured.
        Use in conjunction with listen.  First listen, then send some config
        commands to set the spa up.
        """
        await self.send_mod_ident_req()  # request module identification
        await self.send_panel_req(0, 1)  # request device configuration
        await self.send_panel_req(2, 0)  # request system information
        await self.send_panel_req(4, 0)  # request setup parameters
        await self.send_panel_req(1, 0)  # request filter cycle info
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
                self.log.error(f"Spa sent an unknown message: {data.hex()}")
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_MOD_IDENT_RESP:
                self.parse_module_identification(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_STATUS_UPDATE:
                await self.parse_status_update(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_DEVICE_CONFIG_RESP:
                self.parse_device_configuration(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_SYS_INFO_RESP:
                self.parse_system_information(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_SETUP_PARAMS_RESP:
                self.parse_setup_parameters(data)
                await asyncio.sleep(0.1)
                continue
            if mtype == BMTR_FILTER_INFO_RESP:
                self.parse_filter_cycle_info(data)
                await asyncio.sleep(0.1)
                continue
            self.log.error("Unhandled mtype {0}".format(mtype))
        return False

    # Simple accessors
    def get_model_name(self):
        return self.model_name

    def get_sw_vers(self):
        return self.sw_vers

    def get_cfg_sig(self):
        return self.cfg_sig

    def get_setup(self):
        return self.setup

    def get_ssid(self):
        return self.ssid

    def get_voltage(self):
        return self.voltage

    def get_heater_type(self):
        return self.heater_type

    def get_dip_switch(self):
        return self.dip_switch

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
            return text_heatstate[self.heatstate]
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

    def get_idigi_device_id(self):
        """ Return the idigi device id of the spa wifi """
        return self.idigi_device_id

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
