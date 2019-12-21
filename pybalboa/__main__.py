import balboa
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
    print('Expected CRC={0} got {1}'.format(hex(conf_req_crc), hex(result)))
    if result != conf_req_crc:
        return 1

    result = spa.balboa_calc_cs(status_update[1:], 28)
    print('Expected CRC={0} got {1}'.format(hex(status_update_crc), hex(result)))
    if result != status_update_crc:
        return 1


async def connect_and_listen(spa_host):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    await spa.connect()

    print("Asking for base config")
    await spa.send_config_req()
    msg = await spa.read_one_message()
    print("Got msg: {0}".format(msg.hex()))
    (mac, pump_array, light_array) = spa.parse_config_resp(msg)
    print("Mac Addr: " + mac)
    print("Pump Array: {0}".format(str(pump_array)))
    print("Light Array: {0}".format(str(light_array)))

    print("Asking for panel config")
    await spa.send_panel_req(0, 1)
    msg = await spa.read_one_message()
    print("Got msg: {0}".format(msg.hex()))
    spa.parse_panel_config_resp(msg)
    if spa.config_loaded:
        print('Pump Array: {0}'.format(str(spa.pump_array)))
        print('Light Array: {0}'.format(str(spa.light_array)))
        print('Aux Array: {0}'.format(str(spa.aux_array)))
        print('Circulation Pump: {0}'.format(spa.circ_pump))
        print('Blower: {0}'.format(spa.blower))
        print('Mister: {0}'.format(spa.mister))
    else:
        print('Config not loaded, something is wrong!')
        return 1

    print("Sending unknown commands")
    await spa.send_panel_req(2, 0)
    for i in range(0, 4):
        msg = await spa.read_one_message()
        print("Got msg: {0}".format(msg.hex()))
    await spa.send_panel_req(4, 0)
    for i in range(0, 4):
        msg = await spa.read_one_message()
        print("Got msg: {0}".format(msg.hex()))
    print("Please add this section to issue:")
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
            print("Spa Time: {0}:{1} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))
            print("Filter Mode: {0}".format(spa.get_filtermode(True)))
            print()

    print("Trying to set temperatures")
    save_my_temp = spa.get_settemp()
    print("Curent settemp: {0}".format(spa.get_settemp()))
    if spa.tempscale == spa.TSCALE_F:
        change_to = 100
    else:
        change_to = 24

    await spa.send_temp_change(change_to)
    await asyncio.sleep(2)

    if (spa.get_settemp() != change_to):
        print("Could not set temp to desired: {0}".format(spa.get_settemp()))
    else:
        print("New settemp: {0}".format(spa.get_settemp()))

    await spa.send_temp_change(save_my_temp)
    await asyncio.sleep(2)
    print("Current temp should be set back to {0} is: {1}".format(save_my_temp, spa.get_settemp()))

    await spa.disconnect()
    return


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
