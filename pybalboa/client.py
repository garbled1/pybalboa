"""Balboa spa client."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from random import uniform
from typing import Any

from .control import EVENT_UPDATE, EventMixin, FaultLog, HeatModeSpaControl, SpaControl
from .enums import (
    AccessibilityType,
    ControlType,
    HeatState,
    LowHighRange,
    MessageType,
    SettingsCode,
    TemperatureUnit,
    WiFiState,
)
from .exceptions import SpaConnectionError, SpaMessageError
from .utils import (
    byte_parser,
    calculate_checksum,
    cancel_task,
    default,
    read_one_message,
    to_celsius,
    utcnow,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 4257
MESSAGE_DELIMETER_BYTE = b"~"
MESSAGE_DELIMETER = MESSAGE_DELIMETER_BYTE[0]
MESSAGE_SEND = [0x0A, 0xBF]

ACCESSIBILITY_TYPE_MAP = {
    16: AccessibilityType.PUMP_LIGHT,
    32: AccessibilityType.NONE,
    48: AccessibilityType.NONE,
}


class SpaClient(EventMixin):
    """Spa client."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize a spa client."""
        self._host = host
        self._port = port

        self._device_configuration_loaded = False
        self._filter_cycle_loaded = False
        self._module_identification_loaded = False
        self._setup_parameters_loaded = False
        self._system_information_loaded = False
        self._configuration_loaded: asyncio.Event = asyncio.Event()

        self._last_log_mesage: bytes | None = None
        self._previous_status: bytes | None = None
        self._last_message_received: datetime | None = None
        self._last_message_sent: datetime | None = None

        self._disconnect = False
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connection_monitor: asyncio.Task | None = None
        self._listener: asyncio.Task | None = None

        self._controls: list[SpaControl] = [
            HeatModeSpaControl(self),
            SpaControl(self, ControlType.TEMPERATURE_RANGE, list(LowHighRange)),
        ]

        # module identification
        self._idigi_device_id: str
        self._mac_address: str

        # system information
        self._dip_switch: str
        self._configuration_signature: str
        self._current_setup: int
        self._heater_type: str
        self._model: str
        self._software_version: str
        self._voltage: int | None

        # setup parameters
        self._low_range: tuple[tuple[int, int], tuple[float, float]]
        self._high_range: tuple[tuple[int, int], tuple[float, float]]
        self._pump_count: int

        # filter cycle
        self._filter_cycle_1_start: time
        self._filter_cycle_1_duration: timedelta
        self._filter_cycle_2_enabled: bool
        self._filter_cycle_2_start: time
        self._filter_cycle_2_duration: timedelta

        # status update
        self._accessibility_type: AccessibilityType
        self._filter_cycle_1_running: bool
        self._filter_cycle_2_running: bool
        self._heat_state: HeatState
        self._is_24_hour: bool
        self._time_hour: int
        self._time_minute: int
        self._temperature_unit: TemperatureUnit
        self._temperature: float | None
        self._target_temperature: float
        self._temperature_range: int
        self._wifi_state: WiFiState

        # fault log
        self._fault: FaultLog

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    @property
    def available(self) -> bool:
        """Return True if the client is connected and available."""
        if self.connected and self.last_message_received is not None:
            return self.last_message_received >= utcnow() - timedelta(seconds=15)
        return False

    @property
    def connected(self) -> bool:
        """Return `True` if the client is connected."""
        if self._writer is None:
            return False
        return self._writer.transport.is_reading()  # type: ignore

    @property
    def last_message_received(self) -> datetime | None:
        """Return the last message received datetime."""
        return self._last_message_received

    @property
    def configuration_signature(self) -> str:
        """Return the configuration signature."""
        return self._configuration_signature

    @property
    def controls(self) -> list[SpaControl]:
        """Return the controls available."""
        return self._controls

    @property
    def current_setup(self) -> int:
        """Return the current setup."""
        return self._current_setup

    @property
    def dip_switch(self) -> str:
        """Return the dip switch settings."""
        return self._dip_switch

    @property
    def filter_cycle_1_start(self) -> time:
        """Return filter cycle 1 start time."""
        return self._filter_cycle_1_start

    @property
    def filter_cycle_1_duration(self) -> timedelta:
        """Return filter cycle 1 duration."""
        return self._filter_cycle_1_duration

    @property
    def filter_cycle_1_running(self) -> bool:
        """Return `True` if filter cycle 1 is running."""
        return self._filter_cycle_1_running

    @property
    def filter_cycle_2_enabled(self) -> bool:
        """Return `True` if filter cycle 2 is enabled."""
        return self._filter_cycle_2_enabled

    @property
    def filter_cycle_2_start(self) -> time:
        """Return filter cycle 2 start time."""
        return self._filter_cycle_2_start

    @property
    def filter_cycle_2_duration(self) -> timedelta:
        """Return filter cycle 2 duration."""
        return self._filter_cycle_2_duration

    @property
    def filter_cycle_2_running(self) -> bool:
        """Return `True` if filter cycle 2 is running."""
        return self._filter_cycle_2_running

    @property
    def heat_state(self) -> HeatState:
        """Return the heat state."""
        return self._heat_state

    @property
    def heater_type(self) -> str:
        """Return the heater type."""
        return self._heater_type

    @property
    def idigi_device_id(self) -> str:
        """Return the iDigi Device Id."""
        return self._idigi_device_id

    @property
    def mac_address(self) -> str:
        """Return the mac address."""
        return self._mac_address

    @property
    def model(self) -> str:
        """Return the model."""
        return self._model

    @property
    def pump_count(self) -> int:
        """Return the number of pumps."""
        return self._pump_count

    @property
    def software_version(self) -> str:
        """Return the software version."""
        return self._software_version

    @property
    def temperature_unit(self) -> TemperatureUnit:
        """Return the temperatre unit."""
        return self._temperature_unit

    @property
    def temperature(self) -> float | None:
        """Return the temperature."""
        return self._temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._target_temperature

    @property
    def temperature_minimum(self) -> float:
        """Return the temperature minimum."""
        valid_temps = (self._low_range, self._high_range)[self._temperature_range]
        return valid_temps[self._temperature_unit][0]

    @property
    def temperature_maximum(self) -> float:
        """Return the temperature maximum."""
        valid_temps = (self._low_range, self._high_range)[self._temperature_range]
        return valid_temps[self._temperature_unit][1]

    @property
    def time_hour(self) -> int:
        """Return the hour."""
        return self._time_hour

    @property
    def time_minute(self) -> int:
        """Return the minute."""
        return self._time_minute

    @property
    def is_24_hour(self) -> bool:
        """Return `True` if 24-hour time.."""
        return self._is_24_hour

    @property
    def voltage(self) -> int | None:
        """Return the voltage."""
        return self._voltage

    @property
    def aux(self) -> list[SpaControl]:
        """Return the aux controls."""
        return self.get_controls(ControlType.AUX)

    @property
    def blowers(self) -> list[SpaControl]:
        """Return the blower controls."""
        return self.get_controls(ControlType.BLOWER)

    @property
    def circulation_pump(self) -> SpaControl | None:
        """Return the circulation pump control."""
        return next(iter(self.get_controls(ControlType.CIRCULATION_PUMP)), None)

    @property
    def heat_mode(self) -> SpaControl:
        """Return the heat mode control."""
        return self.get_controls(ControlType.HEAT_MODE)[0]

    @property
    def lights(self) -> list[SpaControl]:
        """Return the light controls."""
        return self.get_controls(ControlType.LIGHT)

    @property
    def misters(self) -> list[SpaControl]:
        """Return the mister controls."""
        return self.get_controls(ControlType.MISTER)

    @property
    def pumps(self) -> list[SpaControl]:
        """Return the pump controls."""
        return self.get_controls(ControlType.PUMP)

    @property
    def temperature_range(self) -> SpaControl:
        """Return the temperature range controls."""
        return self.get_controls(ControlType.TEMPERATURE_RANGE)[0]

    def get_controls(self, control_type: ControlType) -> list[SpaControl]:
        """Get controls based on control type."""
        return [
            control for control in self.controls if control.control_type == control_type
        ]

    @property
    def configuration_loaded(self) -> bool:
        """Return `True` if the configuration is loaded."""
        return self._configuration_loaded.is_set()

    async def async_configuration_loaded(self, timeout: float = 15) -> bool:
        """Wait for configuration to complete."""
        if self.configuration_loaded:
            return True
        try:
            return await asyncio.wait_for(self._configuration_loaded.wait(), timeout)
        except asyncio.TimeoutError:
            return False

    def _check_configuration_loaded(self) -> None:
        """Return `True` if the spa is fully configured."""
        if all(
            (
                self._device_configuration_loaded,
                self._filter_cycle_loaded,
                self._module_identification_loaded,
                self._setup_parameters_loaded,
                self._system_information_loaded,
                self._previous_status,
            )
        ):
            assert self._previous_status
            self._parse_status_update(self._previous_status, True)
            self._configuration_loaded.set()

    async def connect(self) -> bool:
        """Connect to the spa."""
        self._disconnect = False
        return await self._connect()

    async def _connect(self) -> bool:
        """Connect to the spa."""
        if self.connected:
            _LOGGER.debug("%s -- already connected", self._host)
            return True
        if self._disconnect:
            _LOGGER.debug(
                "%s -- connect skipped due to previous disconnect request", self._host
            )
            return False

        _LOGGER.debug("%s -- establishing connection", self._host)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), 10
            )
        except (
            asyncio.TimeoutError,
            ConnectionRefusedError,
            TimeoutError,
            OSError,
        ) as err:
            msg = "Timed out" if isinstance(err, asyncio.TimeoutError) else err
            _LOGGER.error("%s ## cannot connect: %s", self._host, msg)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("%s ## error connecting: %s", self._host, ex)
        else:
            _LOGGER.debug("%s -- connected", self._host)
            self._listener = asyncio.ensure_future(self._start_listener())
            asyncio.ensure_future(self.request_all_configuration(True))
            await cancel_task(self._connection_monitor)

            async def _monitor() -> None:
                attempt = 0
                while not self._disconnect:
                    while self.connected:
                        await asyncio.sleep(1)
                    if not await self._connect():
                        await asyncio.sleep(min(1 * 2**attempt + uniform(0, 1), 60))
                        attempt += 1

            self._connection_monitor = asyncio.ensure_future(_monitor())
        return self.connected

    async def disconnect(self) -> None:
        """Disconnect from the spa."""
        _LOGGER.debug("%s -- disconnect requested", self._host)
        self._disconnect = True
        await cancel_task(self._connection_monitor)
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # pylint: disable=broad-except
                pass
        await cancel_task(self._listener)
        self._reader = self._writer = None
        _LOGGER.debug("%s -- disconnected", self._host)

    async def _start_listener(self) -> None:
        """Start the listener."""
        timeout = 15
        wait_time = timedelta(seconds=timeout)
        assert self._reader
        while self.connected:
            try:
                data = await read_one_message(self._reader, timeout)
            except SpaMessageError as err:
                _LOGGER.debug("%s ## %s", self._host, err)
                continue
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                if not (sent := self._last_message_sent) or sent + wait_time < utcnow():
                    self.emit(EVENT_UPDATE)
                    await self.send_device_present()
                continue
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error("%s ## %s", self._host, ex)
                continue
            self._process_message(data)
        self.emit(EVENT_UPDATE)
        _LOGGER.debug("%s -- stopped listening", self._host)

    def _process_message(self, data: bytes) -> None:
        """Process a message."""
        self._last_message_received = utcnow()
        message_type = self._log_message(data)
        data = data[4:-1]

        if message_type == MessageType.STATUS_UPDATE:
            self._parse_status_update(data)
        elif message_type == MessageType.MODULE_IDENTIFICATION:
            self._parse_module_identification(data)
        elif message_type == MessageType.FILTER_CYCLE:
            self._parse_filter_cycle(data)
        elif message_type == MessageType.FAULT_LOG:
            self._parse_fault_log(data)
        elif message_type == MessageType.DEVICE_CONFIGURATION:
            self._parse_device_configuration(data)
        elif message_type == MessageType.SETUP_PARAMETERS:
            self._parse_setup_parameters(data)
        elif message_type == MessageType.SYSTEM_INFORMATION:
            self._parse_system_information(data)

    def _parse_device_configuration(self, data: bytes) -> None:
        """Parse a device configuration message.

        Device configuration messages have a length of 6 bytes with the following information:

        Byte  | Data
        ---------------------------
        00    | P4P3P2P1 - Pumps 1-4
        01    | P6P7P8P5 - Pumps 5-8
        02    | L4L3L2L1 - Lights 1-4
        03    | CxxxB2B1 - circulation pump, blowers 1-2
        04    | xMMMAAAA - mister 1-3, aux 1-4
        05    | ?
        """
        if not self._device_configuration_loaded:

            def _add_controls(control_type: ControlType, on_states: list[int]) -> None:
                self._controls.extend(
                    SpaControl(
                        self,
                        control_type,
                        state + 1,
                        index if len(on_states) > 1 else None,
                    )
                    for index, state in enumerate(on_states)
                    if state > 0
                )

            pumps = [
                *byte_parser(data[0], count=4, bits=2),  # pumps 1-4
                data[1] & 0x03,  # pump 5
                data[1] >> 6 & 0x03,  # pump 6
                data[1] >> 4 & 0x03,  # pump 7
                data[1] >> 2 & 0x03,  # pump 8
            ]
            lights = byte_parser(data[2], count=4, bits=2)
            circulation_pump = data[3] >> 7  # only one
            blowers = byte_parser(data[3], count=2, bits=2)
            auxs = byte_parser(data[4], count=4)
            misters = byte_parser(data[4], offset=4, count=3)

            _add_controls(ControlType.PUMP, pumps)
            _add_controls(ControlType.LIGHT, lights)
            _add_controls(ControlType.CIRCULATION_PUMP, [circulation_pump])
            _add_controls(ControlType.BLOWER, blowers)
            _add_controls(ControlType.AUX, auxs)
            _add_controls(ControlType.MISTER, misters)

            self._device_configuration_loaded = True
            self._check_configuration_loaded()

    def _parse_fault_log(self, data: bytes) -> None:
        """Parse a fault log message.

        Fault log messages have a length of 10 bytes with the following information:

        Byte  | Data
        ---------------------------
        00    | fault count
        01    | entry number
        02    | message code
        03    | days ago
        04    | time hour
        05    | time minute
        06    | flags
        07    | target temperature
        08    | sensor A temperature
        09    | sensor B temperature
        """
        self._fault = FaultLog(*data)

    def _parse_filter_cycle(self, data: bytes) -> None:
        """Parse a filter cycle message.

        Filter cycle messages have a length of 8 bytes with the following information:

        Byte  | Data
        ---------------------------
        00    | filter cycle 1 start hour
        01    | filter cycle 1 start minute
        02    | filter cycle 1 duration hours
        03    | filter cycle 1 duration minutes
        04    | filter cycle 2 enabled and start hour
        05    | filter cycle 2 start minute
        06    | filter cycle 2 duration hours
        07    | filter cycle 2 duration minutes
        """
        start = (datetime.min + timedelta(hours=data[0], minutes=data[1])).time()
        self._filter_cycle_1_start = start
        self._filter_cycle_1_duration = timedelta(hours=data[2], minutes=data[3])
        self._filter_cycle_2_enabled = bool(data[4] >> 7)
        start = (datetime.min + timedelta(hours=data[4] & 0x7F, minutes=data[5])).time()
        self._filter_cycle_2_start = start
        self._filter_cycle_2_duration = timedelta(hours=data[6], minutes=data[7])
        self._filter_cycle_loaded = True
        self._check_configuration_loaded()

    def _parse_module_identification(self, data: bytes) -> None:
        """Parse a module identification message.

        Module identification messages have a length of 25 bytes with the following information:

        Byte  | Data
        ---------------------------
        00-02 | ? ? ?
        03-08 | mac address
        09-24 | iDigi device id (used to communicate with Balboa cloud API)
        """
        self._mac_address = ":".join(f"{x:02x}" for x in data[3:9])
        idigi_device_id = "-".join(data[i : i + 4].hex() for i in range(9, 25, 4))
        self._idigi_device_id = idigi_device_id.upper()
        self._module_identification_loaded = True
        self._check_configuration_loaded()

    def _parse_setup_parameters(self, data: bytes) -> None:
        """Parse a setup parameters message.

        Setup parameters messages have a length of 9 bytes with the following information:

        Byte  | Data
        ---------------------------
        00-01 | ? ?
        02    | low range minimum temperature in °F
        03    | low range maximum temperature in °F
        04    | high range minimum temperature in °F
        05    | high range maximum temperature in °F
        06    | ?
        07    | pump counter (add the number of "1"s from bit)
        08    | ?
        """
        if not self._setup_parameters_loaded:
            low, high = data[2], data[3]
            self._low_range = ((low, high), (to_celsius(low), to_celsius(high)))
            low, high = data[4], data[5]
            self._high_range = ((low, high), (to_celsius(low), to_celsius(high)))
            self._pump_count = sum(byte_parser(data[7]))
            self._setup_parameters_loaded = True
            self._check_configuration_loaded()

    def _parse_status_update(self, data: bytes, reprocess: bool = False) -> None:
        """Parse a status update message.

        Status update messages have a length of 24 bytes with the following information:

        Byte  | Data
        ---------------------------
        00-01 | ? ?
        02    | current temperature
        03    | current hour
        04    | current minute
        05    | heat mode
        06-08 | ? ? ?
        09    | temperature scale, time format, filter mode, accessibility type
        10    | temperature range, heating
        11    | pumps 1-4
        12    | pumps 5-8
        13    | circulation pump, blower state
        14    | lights 1-4
        15    | mister 1-3, aux 1-4
        16-19 | ? ? ? ?
        20    | target temperature
        21    | ?
        22    | wifi
        23    | ?
        """
        if data == self._previous_status and not reprocess:
            # No new information, so ignore it
            return

        self._previous_status = data
        self._time_hour = data[3]
        self._time_minute = data[4]
        self._is_24_hour = (flag := data[9]) & 0x02 != 0
        if flag & 0x01 == 0:
            self._temperature_unit = TemperatureUnit.FAHRENHEIT
            divisor = 1
        else:
            self._temperature_unit = TemperatureUnit.CELSIUS
            divisor = 2
        temperature = None if (temperature := data[2]) == 255 else temperature / divisor
        self._temperature = temperature
        self._target_temperature = data[20] / divisor
        self._filter_cycle_1_running = flag & 0x04 != 0
        self._filter_cycle_2_running = flag & 0x08 != 0
        self._accessibility_type = ACCESSIBILITY_TYPE_MAP.get(
            flag & 0x48, AccessibilityType.ALL
        )
        self._temperature_range = ((flag := data[10]) >> 2) & 0x01
        self._update_control_states(
            ControlType.TEMPERATURE_RANGE, [self._temperature_range]
        )
        self._heat_state = HeatState(flag >> 4 & 0x03)
        light_states = byte_parser(data[14], count=4, bits=2, fn=lambda _: _ >> 1)
        self._update_control_states(ControlType.LIGHT, light_states)
        heat_mode = data[5] & 0x03
        self._update_control_states(ControlType.HEAT_MODE, [heat_mode])
        pump_states = byte_parser(data[11], count=4, bits=2)
        pump_states.extend(byte_parser(data[12], count=4, bits=2))
        self._update_control_states(ControlType.PUMP, pump_states)
        circulation_pump = (data[13] & 0x03) >> 1
        self._update_control_states(ControlType.CIRCULATION_PUMP, [circulation_pump])
        blower_states = byte_parser(data[13], 1, 2, 2)
        self._update_control_states(ControlType.MISTER, blower_states)
        mister_states = byte_parser(data[15], count=3)
        self._update_control_states(ControlType.MISTER, mister_states)
        aux_states = byte_parser(data[15], offset=3, count=4)
        self._update_control_states(ControlType.AUX, aux_states)
        self._wifi_state = WiFiState(int((data[22] & 0xF0) / 16))

        if not self.configuration_loaded and not reprocess:
            self._check_configuration_loaded()

        self.emit(EVENT_UPDATE)

    def _update_control_states(
        self, control_type: ControlType, states: list[int]
    ) -> None:
        """Update the control states."""
        for index, state in enumerate(states):
            if control := next(
                (
                    control
                    for control in self.controls
                    if control.control_type == control_type
                    and (control.index == index or control.index is None)
                ),
                None,
            ):
                control.update(state)

    def _parse_system_information(self, data: bytes) -> None:
        """Parse a system information message.

        System information messages have a length of 21 bytes with the following information:

        Byte  | Data
        ---------------------------
        00-03 | software id (ssid) and version
        04-11 | model name
        12    | current setup
        13-16 | configuration signature
        17    | voltage
        18    | heater type
        19-20 | dip switch
        """
        self._software_version = f"M{data[0]}_{data[1]} V{data[2]}.{data[3]}"
        self._model = "".join(map(chr, data[4:12])).strip()
        self._current_setup = data[12]
        self._configuration_signature = data[13:17].hex()
        self._voltage = 240 if data[17] == 0x01 else None
        self._heater_type = "standard" if data[18] == 0x0A else "unknown"
        self._dip_switch = f"{data[19]:08b}{data[20]:08b}"
        self._system_information_loaded = True
        self._check_configuration_loaded()

    def _log_message(self, data: bytes) -> MessageType:
        """Log message and return message type."""
        message_type = MessageType(data[3])
        if self._last_log_mesage != data:
            self._last_log_mesage = data
            _LOGGER.debug("%s -> %s: %s", self._host, message_type.name, data.hex())
        return message_type

    async def request_all_configuration(self, wait: bool = False) -> None:
        """Request the full spa configuration."""
        if not self._module_identification_loaded or not wait:
            await self.request_module_identification()
        if not self._system_information_loaded or not wait:
            await self.request_system_information()
        if not self._setup_parameters_loaded or not wait:
            await self.request_setup_parameters()
        if not self._device_configuration_loaded or not wait:
            await self.request_device_configuration()
        if not self._filter_cycle_loaded or not wait:
            await self.request_filter_cycle()
        if wait and not await self.async_configuration_loaded(3):
            if self.connected:
                await self.request_all_configuration(wait)

    async def request_device_configuration(self) -> None:
        """Request the device configuration."""
        await self.send_message(
            MessageType.REQUEST, SettingsCode.DEVICE_CONFIGURATION, 0x00, 0x01
        )

    async def request_fault_log(self, entry: int = 0) -> None:
        """Request the filter cycle."""
        await self.send_message(
            MessageType.REQUEST, SettingsCode.FAULT_LOG, entry % 256, 0x00
        )

    async def request_filter_cycle(self) -> None:
        """Request the filter cycle."""
        await self.send_message(
            MessageType.REQUEST, SettingsCode.FILTER_CYCLE, 0x00, 0x00
        )

    async def request_module_identification(self) -> None:
        """Request the module identification."""
        await self.send_device_present()

    async def request_setup_parameters(self) -> None:
        """Request the system information."""
        await self.send_message(
            MessageType.REQUEST, SettingsCode.SETUP_PARAMETERS, 0x00, 0x00
        )

    async def request_system_information(self) -> None:
        """Request the system information."""
        await self.send_message(
            MessageType.REQUEST, SettingsCode.SYSTEM_INFORMATION, 0x00, 0x00
        )

    async def send_device_present(self) -> None:
        """Send a device present message."""
        await self.send_message(MessageType.DEVICE_PRESENT)

    async def send_message(
        self, message_type: MessageType | None, *message: int
    ) -> None:
        """Send a message to the spa with variable length."""
        if not self.connected:
            return
        if not message_type:
            message_type = MessageType.UNKNOWN
        prefix = [*MESSAGE_SEND, message_type.value] if message_type else []
        message_data = [*prefix, *message]
        message_length = len(message_data) + 2
        data = bytearray(message_length + 2)
        data[0] = MESSAGE_DELIMETER
        data[1] = message_length
        data[2:message_length] = message_data
        data[-2] = calculate_checksum(data[1:message_length])
        data[-1] = MESSAGE_DELIMETER

        _LOGGER.debug(
            "%s <- %s%s: %s",
            self._host,
            message_type.name,
            f"_{SettingsCode(data[5]).name}"
            if message_type == MessageType.REQUEST
            else "",
            data[1:-1].hex(),
        )
        try:
            assert self._writer
            self._writer.write(data)
            await self._writer.drain()
            self._last_message_sent = utcnow()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("%s ## error sending message: %s", self._host, ex)

    async def __aenter__(self) -> SpaClient:
        """Connect and start listening for messages."""
        if not await self._connect():
            raise SpaConnectionError()
        return self

    async def __aexit__(self, *exctype: Any) -> None:
        """Disconnect."""
        await self.disconnect()

    async def set_filter_cycle(
        self,
        filter_cycle_1_hour: int | None = None,
        filter_cycle_1_minute: int | None = None,
        filter_cycle_1_duration_hours: int | None = None,
        filter_cycle_1_duration_minutes: int | None = None,
        filter_cycle_2_enabled: bool | None = None,
        filter_cycle_2_hour: int | None = None,
        filter_cycle_2_minute: int | None = None,
        filter_cycle_2_duration_hours: int | None = None,
        filter_cycle_2_duration_minutes: int | None = None,
    ) -> None:
        """Set the filter cycle."""
        values = (
            filter_cycle_1_hour,
            filter_cycle_1_minute,
            filter_cycle_1_duration_hours,
            filter_cycle_1_duration_minutes,
            filter_cycle_2_enabled,
            filter_cycle_2_hour,
            filter_cycle_2_minute,
            filter_cycle_2_duration_hours,
            filter_cycle_2_duration_minutes,
        )
        if all(value is None for value in values):
            return

        message = [0] * 8
        message[0] = default(filter_cycle_1_hour, self.filter_cycle_1_start.hour)
        message[1] = default(filter_cycle_1_minute, self.filter_cycle_1_start.minute)
        old_duration = int(self.filter_cycle_1_duration.seconds / 60)
        message[2] = default(filter_cycle_1_duration_hours, int(old_duration / 60))
        message[3] = default(filter_cycle_1_duration_minutes, old_duration % 60)
        enabled = default(filter_cycle_2_enabled, self.filter_cycle_2_enabled) << 7
        message[4] = enabled | (
            default(filter_cycle_2_hour, self.filter_cycle_2_start.hour)
        )
        message[5] = default(filter_cycle_2_minute, self.filter_cycle_2_start.minute)
        old_duration = int(self.filter_cycle_2_duration.seconds / 60)
        message[6] = default(filter_cycle_2_duration_hours, int(old_duration / 60))
        message[7] = default(filter_cycle_2_duration_minutes, old_duration % 60)

        await self.send_message(MessageType.FILTER_CYCLE, *message)
        await self.request_filter_cycle()

    async def set_temperature(self, temperature: float) -> None:
        """Set the target temperature."""
        valid_temps = (self._low_range, self._high_range)[self._temperature_range]
        low, high = valid_temps[self._temperature_unit]
        if not low <= temperature <= high:
            err = f"temperature must be in {low}..{high}"
            _LOGGER.error("%s ## set temperature failed: %s", self._host, err)
            return
        if self._temperature_unit == TemperatureUnit.CELSIUS:
            temperature *= 2
        await self.send_message(MessageType.SET_TEMPERATURE, int(temperature))

    async def set_temperature_range(self, temperature_range: LowHighRange) -> None:
        """Set the temperature range."""
        if self._temperature_range == temperature_range:
            return
        await self.send_message(MessageType.TOGGLE_STATE, 0x50)

    async def set_temperature_unit(self, unit: TemperatureUnit) -> None:
        """Set the temperature unit."""
        await self.send_message(MessageType.SET_TEMPERATURE_UNIT, 0x01, unit.value)

    async def set_time(
        self, hour: int, minute: int, is_24_hour: bool | None = None
    ) -> None:
        """Set the time."""
        try:
            time(hour, minute)
        except ValueError as err:
            _LOGGER.error("%s ## set time failed: %s", self._host, err)
            return
        if is_24_hour is None:
            is_24_hour = self._is_24_hour
        await self.send_message(MessageType.SET_TIME, (is_24_hour << 7) | hour, minute)

    async def set_24_hour_time(self, is_24_hour: bool) -> None:
        """Set the 24-hour time."""
        await self.set_time(self._time_hour, self._time_minute, is_24_hour)
