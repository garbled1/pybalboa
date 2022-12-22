"""Main entry."""
import asyncio
import logging
import sys
from enum import IntEnum

try:
    from . import SpaClient, SpaConnectionError, SpaControl
except ImportError:
    from pybalboa import SpaClient, SpaConnectionError, SpaControl


def usage() -> None:
    """Print uage instructions."""
    print(f"Usage: {sys.argv[0]} <ip/host> <flag>")
    print("\tip/host:\tip address of spa (required)")
    print("\t-d, --debug:\tenable debug logs (optional)")


async def connect_and_listen(host: str) -> None:
    """Connect to the spa and try some commands."""
    print("******** Testing spa connection and configuration **********")
    try:
        async with SpaClient(host) as spa:
            if not await spa.async_configuration_loaded():
                print("Config not loaded, something is wrong!")
                return

            print()
            print("Module identification")
            print("---------------------")
            print(f"MAC address: {spa.mac_address}")
            print(f"iDigi Device Id: {spa.idigi_device_id}")
            print()

            print("Device configuration")
            print("--------------------")
            print(spa.circulation_pump)
            print(f"Pumps: {[pump.name for pump in spa.pumps]}")
            print(f"Lights: {[light.name for light in spa.lights]}")
            print(f"Aux: {[aux.name for aux in spa.aux]}")
            print(f"Blower: {[blower.name for blower in spa.blowers]}")
            print(f"Mister: {[mister.name for mister in spa.misters]}")
            print()

            print("System information")
            print("------------------")
            print(f"Model: {spa.model}")
            print(f"Software version: {spa.software_version}")
            print(f"Configuration signature: {spa.configuration_signature}")
            print(f"Current setup: {spa.current_setup}")
            print(f"Voltage: {spa.voltage}")
            print(f"Heater type: {spa.heater_type}")
            print(f"DIP switch: {spa.dip_switch}")
            print()

            print("Setup parameters")
            print("----------------")
            print(f"Min temps: {spa._low_range}")  # pylint: disable=protected-access
            print(f"Max temps: {spa._high_range}")  # pylint: disable=protected-access
            print(f"# of pumps: {spa._pump_count}")  # pylint: disable=protected-access
            print()

            print("Filter cycle")
            print("------------")
            print(f"Filter cycle 1 start: {spa.filter_cycle_1_start}")
            print(f"Filter cycle 1 duration: {spa.filter_cycle_1_duration}")
            print(
                f"Filter cycle 2 start: {spa.filter_cycle_2_start} ({'en' if spa.filter_cycle_2_enabled else 'dis'}abled)"
            )
            print(f"Filter cycle 2 duration: {spa.filter_cycle_2_duration}")
            print()

            print("Status update")
            print("-------------")
            print(f"Temperature unit: {spa.temperature_unit.name}")
            print(f"Temperature: {spa.temperature}")
            print(f"Target temperature: {spa.target_temperature}")
            print(f"Temperature range: {spa.temperature_range.state.name}")
            print(f"Heat mode: {spa.heat_mode.state.name}")
            print(f"Heat state: {spa.heat_state.name}")
            print(f"Pump status: {spa.pumps}")
            print(spa.circulation_pump)
            print(f"Light status: {spa.lights}")
            print(f"Mister status: {spa.misters}")
            print(f"Aux status: {spa.aux}")
            print(f"Blower status: {spa.blowers}")
            print(
                f"Spa time: {spa.time_hour:02d}:{spa.time_minute:02d} {'24hr' if spa.is_24_hour else '12hr'}"
            )
            print(f"Filter cycle 1 running: {spa.filter_cycle_1_running}")
            print(f"Filter cycle 2 running: {spa.filter_cycle_2_running}")
            print()

            await test_controls(spa)
    except SpaConnectionError:
        print(f"Failed to connect to spa at {host}")
    else:
        print()
        print("Please add the above output to issue:")
        print("https://github.com/garbled1/pybalboa/issues/1")
        print()


async def test_controls(spa: SpaClient) -> None:
    """Test spa controls."""
    print("******** Testing spa controls **********")
    print()
    print("Temperature control")
    print("-------------------")
    target_temperature = spa.target_temperature
    await adjust_temperature(
        spa,
        spa.temperature_maximum
        if spa.target_temperature != spa.temperature_maximum
        else spa.temperature_minimum,
    )
    await adjust_temperature(spa, target_temperature)
    print()

    for control in spa.controls:
        print(f"{control.name} control")
        print("-" * (len(control.name) + 8))
        state = control.state
        for option in control.options:
            if option not in (state, control.state):
                await adjust_control(control, option)
        if control.state != state:
            await adjust_control(control, state)
        print()


async def adjust_temperature(spa: SpaClient, temperature: float) -> None:
    """Adjust target temperature settings."""
    print(f"Current target temperature: {spa.target_temperature}")
    print(f"  Set to {temperature}")
    await spa.set_temperature(temperature)

    async def _temperature_check() -> None:
        while spa.target_temperature != temperature:
            await asyncio.sleep(0.1)

    wait = 10
    try:
        await asyncio.wait_for(_temperature_check(), wait)
        print(f"  Set temperature is now {spa.target_temperature}")
    except asyncio.TimeoutError:
        print(
            f"  Set temperature was not changed after {wait} seconds; is {spa.target_temperature}"
        )


async def adjust_control(control: SpaControl, state: IntEnum) -> None:
    """Adjust control state."""
    print(f"Current state: {control.state.name}")
    print(f"  Set to {state.name}")
    if not await control.set_state(state):
        return

    async def _state_check() -> None:
        while control.state != state:
            await asyncio.sleep(0.1)

    wait = 10
    try:
        await asyncio.wait_for(_state_check(), wait)
        print(f"  State is now {control.state.name}")
    except asyncio.TimeoutError:
        print(f"  State was not changed after {wait} seconds; is {control.state.name}")


if __name__ == "__main__":
    if (args := len(sys.argv)) < 2:
        usage()
        sys.exit(1)

    if args > 2 and sys.argv[2] in ("-d", "--debug"):
        logging.basicConfig(level=logging.DEBUG)

    asyncio.run(connect_and_listen(sys.argv[1]))

    sys.exit(0)
