"""Balboa spa control."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from datetime import datetime, time, timedelta
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Final

from .enums import (
    ControlType,
    HeatMode,
    MessageType,
    OffLowHighState,
    OffLowMediumHighState,
    OffOnState,
    ToggleItemCode,
    UnknownState,
)

if TYPE_CHECKING:
    from .client import SpaClient

_LOGGER = logging.getLogger(__name__)


CONTROL_TYPE_MAP = {
    ControlType.PUMP: ToggleItemCode.PUMP_1,
    ControlType.BLOWER: ToggleItemCode.BLOWER,
    ControlType.MISTER: ToggleItemCode.MISTER,
    ControlType.LIGHT: ToggleItemCode.LIGHT_1,
    ControlType.AUX: ToggleItemCode.AUX_1,
    ControlType.CIRCULATION_PUMP: ToggleItemCode.CIRCULATION_PUMP,
    ControlType.TEMPERATURE_RANGE: ToggleItemCode.TEMPERATURE_RANGE,
    ControlType.HEAT_MODE: ToggleItemCode.HEAT_MODE,
}
STATE_OPTIONS_MAP: dict[int, list[IntEnum]] = {
    2: list(OffOnState),
    3: list(OffLowHighState),
    4: list(OffLowMediumHighState),
}

EVENT_UPDATE = "update"

FAULT_LOG_ERROR_CODES: Final[dict[int, str]] = {
    15: "Sensors are out of sync",
    16: "The water flow is low",
    17: "The water flow has failed",
    18: "The settings have been reset",
    19: "Priming Mode",
    20: "The clock has failed",
    21: "The settings have been reset",
    22: "Program memory failure",
    26: "Sensors are out of sync -- Call for service",
    27: "The heater is dry",
    28: "The heater may be dry",
    29: "The water is too hot",
    30: "The heater is too hot",
    31: "Sensor A Fault",
    32: "Sensor B Fault",
    34: "A pump may be stuck on",
    35: "Hot fault",
    36: "The GFCI test failed",
    37: "Standby Mode (Hold Mode)",
}


class EventMixin:
    """Event mixin."""

    _listeners: dict[str, list[Callable]] = {}

    def on(  # pylint: disable=invalid-name
        self, event_name: str, callback: Callable
    ) -> Callable:
        """Register an event callback."""
        listeners: list = self._listeners.setdefault(event_name, [])
        listeners.append(callback)

        def unsubscribe() -> None:
            """Unsubscribe listeners."""
            if callback in listeners:
                listeners.remove(callback)

        return unsubscribe

    def emit(self, event_name: str, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Run all callbacks for an event."""
        for listener in self._listeners.get(event_name, []):
            listener(*args, **kwargs)


class SpaControl(EventMixin):
    """Spa control."""

    _options: list[IntEnum]

    def __init__(
        self,
        client: SpaClient,
        control_type: ControlType,
        states: int | list[IntEnum] = 1,
        index: int | None = None,
        custom_options: list[IntEnum] | None = None,
    ) -> None:
        """Initialize a spa control."""
        self._client = client
        self._control_type = control_type
        self._index = index

        self._name = f"{control_type.value}{'' if index is None else f' {index + 1}'}"
        self._code = CONTROL_TYPE_MAP[control_type]
        self._state_value = UnknownState.UNKNOWN.value
        self._state: IntEnum = UnknownState.UNKNOWN

        if isinstance(states, int):
            self._states = states
            self._options = STATE_OPTIONS_MAP[states]
        else:
            self._states = len(states)
            self._options = states
        self._custom_options = custom_options

    def __repr__(self) -> str:
        """Return repr(self)."""
        return f"{self.name}: {self.state.name}"

    @property
    def client(self) -> SpaClient:
        """Return the client."""
        return self._client

    @property
    def control_type(self) -> ControlType:
        """Return the control type."""
        return self._control_type

    @property
    def index(self) -> int | None:
        """Return the index."""
        return self._index

    @property
    def name(self) -> str:
        """Return the control name."""
        return self._name

    @property
    def options(self) -> list[IntEnum]:
        """Return the available control options."""
        return self._custom_options or [*self._options]

    @property
    def state(self) -> IntEnum:
        """Get the control's current state."""
        return self._state

    def update(self, state: int) -> None:
        """Update the control's current state."""
        if self._state_value != state:
            self._state_value = state
            self._state = next(
                (option for option in self._options if option == state),
                self._options[-1]
                if self.control_type == ControlType.PUMP and state >= self._states
                else UnknownState.UNKNOWN,
            )
            _LOGGER.debug(
                "%s -- %s is now %s (%s)",
                self._client.host,
                self.name,
                self.state.name,
                state,
            )
            self.emit(EVENT_UPDATE)

    async def set_state(self, state: int | IntEnum) -> bool:
        """Set control to state."""
        if state not in self.options:
            _LOGGER.error("Cannot set state to %s", state)
            return False
        if self._state == state:
            return True
        min_toggle = 1
        if self._state != UnknownState.UNKNOWN:
            min_toggle = max((state - self._state) % self._states, 1)
        for _ in range(min_toggle):
            await self._client.send_message(
                MessageType.TOGGLE_STATE, self._code + (self._index or 0)
            )
        return True


class HeatModeSpaControl(SpaControl):
    """Heat mode spa control."""

    def __init__(self, client: SpaClient) -> None:
        """Initialize a heat mode spa control."""
        super().__init__(
            client,
            ControlType.HEAT_MODE,
            list(HeatMode),
            custom_options=[*HeatMode][:2],
        )

    async def set_state(self, state: int | HeatMode) -> bool:
        """Set control to state."""
        if state not in self.options:
            _LOGGER.error("Cannot set state to %s", state)
            return False
        if self._state == state:
            return True
        i = 2 if self.state == HeatMode.READY_IN_REST and state == HeatMode.READY else 1
        for _ in range(i):
            await self._client.send_message(MessageType.TOGGLE_STATE, self._code)
        return True


@dataclass
class FaultLog:
    """Fault log."""

    count: int
    entry_number: int
    message_code: int
    days_ago: int
    time_hour: int
    time_minute: int
    flags: int
    target_temperature: int
    sensor_a_temperature: int
    sensor_b_temperature: int

    current_time: InitVar[datetime | None] = None
    fault_datetime: datetime = field(init=False)

    def __post_init__(self, current_time: datetime | None) -> None:
        """Compute the fault datetime on initialization."""
        self.fault_datetime = datetime.combine(
            (current_time or datetime.now()) - timedelta(days=self.days_ago),
            time(self.time_hour, self.time_minute),
        )

    def __str__(self) -> str:
        """Return str(self)."""
        return (
            f"Fault log {self.entry_number + 1}/{self.count}: {self.message} "
            f"occurred on {self.fault_datetime:%Y-%m-%d at %H:%M}"
        )

    @property
    def message(self) -> str:
        """Return the message for the error code."""
        return FAULT_LOG_ERROR_CODES.get(
            self.message_code, f"Unknown ({self.message_code})"
        )
