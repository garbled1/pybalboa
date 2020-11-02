try:
    import balboa
except ImportError:
    import pybalboa as balboa

import asyncio
import sys


def usage():
    print("Usage: {0} <ip/host>".format(sys.argv[0]))


def test_crc():
    """ Test the CRC algo. """
    status_update = bytes.fromhex('7E1DFFAF13000064082D00000100000400000000000000000064000000067E')
    status_update_crc = 0x06

    conf_req = bytes.fromhex('7E050ABF04777E')
    conf_req_crc = 0x77

    spa = balboa.BalboaSpaWifi('gnet-37efed')

    result = spa.balboa_calc_cs(conf_req[1:], 4)
    print(f'Expected CRC={conf_req_crc:#04x} got {result:#04x}')
    if result != conf_req_crc:
        return 1

    result = spa.balboa_calc_cs(status_update[1:], 28)
    print(f'Expected CRC={status_update_crc:#04x} got {result:#04x}')
    print()
    if result != status_update_crc:
        return 1


async def connect_and_listen(spa_host):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    await spa.connect()

    for i in range(0, 4):
        print("Asking for module identification")
        await spa.send_mod_ident_req()
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_MOD_IDENT_RESP):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_MOD_IDENT_RESP):
            print("Got msg: {0}".format(msg.hex()))
            spa.parse_module_identification(msg)
            print("Mac Addr: " + spa.macaddr)
            print("iDigi Device Id:", spa.idigi_device_id)
            break
        else:
            print('Invalid message retrieved')
    print()

    for i in range(0, 4):
        print("Asking for device configuration")
        await spa.send_panel_req(0, 1)
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_DEVICE_CONFIG_RESP):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_DEVICE_CONFIG_RESP):
            print("Got msg: {0}".format(msg.hex()))
            spa.parse_device_configuration(msg)
            if spa.config_loaded:
                print('Pump Array: {0}'.format(str(spa.pump_array)))
                print('Light Array: {0}'.format(str(spa.light_array)))
                print('Aux Array: {0}'.format(str(spa.aux_array)))
                print('Circulation Pump: {0}'.format(spa.circ_pump))
                print('Blower: {0}'.format(spa.blower))
                print('Mister: {0}'.format(spa.mister))
            break
        else:
            print('Invalid message retrieved')
    print()

    if not spa.config_loaded:
        print('Config not loaded, something is wrong!')
        return 1

    for i in range(0, 4):
        print("Asking for system information")
        await spa.send_panel_req(2, 0)
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_SYS_INFO_RESP):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_SYS_INFO_RESP):
            print("Got msg: {0}".format(msg.hex()))
            spa.parse_system_information(msg)
            print('Model: {0}'.format(spa.model_name))
            print('Software Version: {0}'.format(spa.sw_vers))
            print('Configuration Signature: {0}'.format(spa.cfg_sig))
            print('Setup Mode: {0}'.format(str(spa.setup)))
            print('Software Version ID: {0}'.format(spa.ssid))
            print('Voltage: {0}'.format(spa.voltage))
            print('Heater Type: {0}'.format(spa.heater_type))
            print('DIP Switch: {0}'.format(spa.dip_switch))
            break
        else:
            print('Invalid message retrieved')
    print()

    for i in range(0, 4):
        print("Asking for setup parameters")
        await spa.send_panel_req(4, 0)
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_SETUP_PARAMS_RESP):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_SETUP_PARAMS_RESP):
            print("Got msg: {0}".format(msg.hex()))
            spa.parse_setup_parameters(msg)
            print("Min Temps: {0}".format(spa.tmin))
            print("Max Temps: {0}".format(spa.tmax))
            print("Nr of pumps: {0}".format(spa.nr_of_pumps))
            break
        else:
            print('Invalid message retrieved')
    print()

    for i in range(0, 4):
        print("Asking for filter cycle info")
        await spa.send_panel_req(1, 0)
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_FILTER_INFO_RESP):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_FILTER_INFO_RESP):
            print("Got msg: {0}".format(msg.hex()))
            spa.parse_filter_cycle_info(msg)
            print(f'Filter 1: {spa.filter1_hour}:{spa.filter1_minute:02d}')
            print(f'Filter 1 Duration: {spa.filter1_duration_hours}:'
                  f'{spa.filter1_duration_minutes:02d}')
            print(f'Filter 2: {spa.filter2_hour}:{spa.filter2_minute:02d} '
                  f'({"enabled" if spa.filter2_enabled else "disabled"})')
            print(f'Filter 2 Duration: {spa.filter2_duration_hours}:'
                f'{spa.filter2_duration_minutes:02d}')
            break
        else:
            print('Invalid message retrieved')
    print()
    
    for i in range(0, 4):
        print("Reading panel update")
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_STATUS_UPDATE):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            print("Got msg: {0}".format(msg.hex()))
            await spa.parse_status_update(msg)
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
            print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
            print("Set Temp: {0}".format(spa.get_settemp()))
            print("Heat Mode: {0}".format(spa.get_heatmode(True)))
            print("Heat State: {0}".format(spa.get_heatstate(True)))
            print("Temp Range: {0}".format(spa.get_temprange(True)))
            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Circulation Pump: {0}".format(spa.get_circ_pump(True)))
            print("Light Status: {0}".format(str(spa.light_status)))
            print("Mister Status: {0}".format(spa.get_mister(True)))
            print("Aux Status: {0}".format(str(spa.aux_status)))
            print("Blower Status: {0}".format(spa.get_blower(True)))
            print("Spa Time: {0:02d}:{1:02d} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))
            print("Filter Mode: {0}".format(spa.get_filtermode(True)))
            break
    print()

    print("Please add the above section to issue:")
    print("https://github.com/garbled1/pybalboa/issues/1")

    await spa.disconnect()
    return 0


async def mini_engine(spahost):
    """ Test a miniature engine of talking to the spa."""
    spa = balboa.BalboaSpaWifi(spahost)
    await spa.connect()

    asyncio.ensure_future(spa.listen())

    await spa.send_panel_req(0, 1)

    for i in range(0, 30):
        await asyncio.sleep(1)
        if spa.config_loaded:
            print("Config is loaded:")
            print('Pump Array: {0}'.format(str(spa.pump_array)))
            print('Light Array: {0}'.format(str(spa.light_array)))
            print('Aux Array: {0}'.format(str(spa.aux_array)))
            print('Circulation Pump: {0}'.format(spa.circ_pump))
            print('Blower: {0}'.format(spa.blower))
            print('Mister: {0}'.format(spa.mister))
            break
    print()
    await asyncio.sleep(5)

    lastupd = 0
    for i in range(0, 3):
        await asyncio.sleep(1)
        if spa.lastupd != lastupd:
            lastupd = spa.lastupd
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
            print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
            print("Set Temp: {0}".format(spa.get_settemp()))
            print("Heat Mode: {0}".format(spa.get_heatmode(True)))
            print("Heat State: {0}".format(spa.get_heatstate(True)))
            print("Temp Range: {0}".format(spa.get_temprange(True)))
            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Circulation Pump: {0}".format(spa.get_circ_pump(True)))
            print("Light Status: {0}".format(str(spa.light_status)))
            print("Mister Status: {0}".format(spa.get_mister(True)))
            print("Aux Status: {0}".format(str(spa.aux_status)))
            print("Blower Status: {0}".format(spa.get_blower(True)))
            print("Spa Time: {0:02d}:{1:02d} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))
            print("Filter Mode: {0}".format(spa.get_filtermode(True)))
            print()

    print("Trying to set temperatures")
    print("--------------------------")
    save_my_temp = spa.get_settemp()
    await temp_play(spa, spa.tmax[spa.temprange][spa.tempscale] if spa.settemp != spa.tmax[spa.temprange][spa.tempscale] else spa.tmax[spa.temprange][spa.tempscale] - 2)
    await temp_play(spa, save_my_temp)
    print()

    print("Trying to operate pump 0 (first pump)")
    print("-------------------------------------")
    await pump_play(spa, 0, spa.PUMP_LOW)
    await pump_play(spa, 0, spa.PUMP_OFF)
    await pump_play(spa, 0, spa.PUMP_HIGH)
    await pump_play(spa, 0, spa.PUMP_OFF)
    print()

    print("Play with heatmode")
    print("------------------")
    curHeatMode = spa.get_heatmode()
    await heatmode_play(spa, spa.HEATMODE_READY)
    await heatmode_play(spa, spa.HEATMODE_REST)
    await heatmode_play(spa, spa.HEATMODE_READY)
    print()

    await spa.disconnect()
    return

async def temp_play(spa, temp):
    print(f'Current Set Temp: {spa.get_settemp()}')
    print(f'  Set to {temp}')
    await spa.send_temp_change(temp)
    for i in range(1, 6):
        curSetTemp = spa.get_settemp()
        if (curSetTemp == temp):
            print(f'  Set Temp is now {curSetTemp}')
            return
        else:
            await asyncio.sleep(i)
    print(f'  Set Temp was not changed after {i} seconds')

async def pump_play(spa, pump, setting):
    print(f'Current Status: {spa.get_pump(pump, text=True)}')
    print(f'  Set to {balboa.text_pump[setting]}')
    await spa.change_pump(pump, setting)
    for i in range(1, 6):
        curPumpStatus = spa.get_pump(pump)
        if (curPumpStatus == setting):
            print(f'  Pump Status is now {spa.get_pump(pump, text=True)}')
            return
        else:
            await asyncio.sleep(i)
    print(
        f'  Pump Status was not changed to {balboa.text_pump[setting]} after {i} seconds')

async def heatmode_play(spa, to_heatmode):
    print(f'Heat Mode: {spa.get_heatmode(True)}')
    if to_heatmode == spa.HEATMODE_RNR:
        print("  Can't set heat mode to ready in rest")
        return
    print(f'  Set to {balboa.text_heatmode[to_heatmode]}')
    await spa.change_heatmode(to_heatmode)
    for i in range(1, 6):
        curHeatMode = spa.get_heatmode()
        if (curHeatMode == to_heatmode):
            print(f'  Heat Mode is now {spa.get_heatmode(True)}')
            return
        else:
            await asyncio.sleep(i)
    print(f'  Heat Mode was not changed after {i} seconds')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        exit(1)

    print("******* Testing CRC **********")
    test_crc()

    print("******** Testing basic commands **********")
    asyncio.run(connect_and_listen(sys.argv[1]))

    print("******** Testing engine ***********")
    asyncio.run(mini_engine(sys.argv[1]))

    exit(0)
