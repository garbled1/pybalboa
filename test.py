import asyncio
import sys
import time

import pybalboa.balboa as balboa

spa_host = "10.0.0.103"
spa = balboa.BalboaSpaWifi(spa_host)


async def read_messages():
    if not spa.connected:
        await spa.connect()

    messages = {
        "device_config": "",
        "module": "",
        "sys_info": "",
        "setup_params": "",
        "filter_cycle": "",
        "panel_update": "",
    }

    for i in range(0, 10):
        await spa.send_panel_req(0, 1)
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_DEVICE_CONFIG_RESP:
            msg = await spa.read_one_message()
        if (
            msg is not None
            and spa.find_balboa_mtype(msg) == balboa.BMTR_DEVICE_CONFIG_RESP
        ):
            messages["device_config"] = msg.hex()
            spa.parse_device_configuration(msg)
            break

    if not spa.config_loaded:
        print("Config not loaded, something is wrong!")
        return 1

    for i in range(0, 10):
        await spa.send_mod_ident_req()
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_MOD_IDENT_RESP:
            msg = await spa.read_one_message()
        if msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_MOD_IDENT_RESP:
            messages["module"] = msg.hex()
            spa.parse_module_identification(msg)
            break

    for i in range(0, 10):
        await spa.send_panel_req(2, 0)
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_SYS_INFO_RESP:
            msg = await spa.read_one_message()
        if msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_SYS_INFO_RESP:
            messages["sys_info"] = msg.hex()
            spa.parse_system_information(msg)
            break

    for i in range(0, 10):
        await spa.send_panel_req(4, 0)
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_SETUP_PARAMS_RESP:
            msg = await spa.read_one_message()
        if (
            msg is not None
            and spa.find_balboa_mtype(msg) == balboa.BMTR_SETUP_PARAMS_RESP
        ):
            messages["setup_params"] = msg.hex()
            spa.parse_setup_parameters(msg)
            break

    for i in range(0, 10):
        await spa.send_panel_req(1, 0)
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_FILTER_INFO_RESP:
            msg = await spa.read_one_message()
        if (
            msg is not None
            and spa.find_balboa_mtype(msg) == balboa.BMTR_FILTER_INFO_RESP
        ):
            messages["filter_cycle"] = msg.hex()
            spa.parse_filter_cycle_info(msg)
            break

    for i in range(0, 10):
        msg = await spa.read_one_message()
        if msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_STATUS_UPDATE:
            msg = await spa.read_one_message()
        if msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE:
            messages["panel_update"] = msg.hex()
            await spa.parse_status_update(msg)
            break

    return messages


async def compare_messages(original_messages):
    messages = await read_messages()
    has_changes = False
    for msg_type in messages:
        msg = messages[msg_type]
        orig_msg = original_messages[msg_type]
        if msg == "":
            messages[msg_type] = orig_msg
        if msg_type == "panel_update":
            hour = int(msg[16:18], 16)
            orig_hour = int(orig_msg[16:18], 16)
            minute = int(msg[18:20], 16)
            orig_minute = int(orig_msg[18:20], 16)
            if (hour == orig_hour and minute == orig_minute + 1) or (
                hour == orig_hour + 1 and minute == ((orig_minute + 1) % 60)
            ):
                orig_msg = f"{orig_msg[0:16]}{msg[16:20]}{orig_msg[20:-4]}{msg[-4:]}"
                original_messages[msg_type] = orig_msg
        if msg != orig_msg:
            has_changes = True
            print(
                f"  {msg_type}: {original_messages[msg_type]} -> {messages[msg_type]}"
            )
    if not has_changes:
        print("  no changes detected")
    return messages


async def write_command(i):
    print(f"sending command: {i:02x}")
    data = bytearray(9)
    data[0] = 0x7E
    data[1] = 7
    data[2:5] = balboa.mtypes[balboa.BMTS_CONTROL_REQ]
    data[5] = i
    data[6] = 0x00
    data[7] = spa.balboa_calc_cs(data[1:], 6)
    data[8] = 0x7E
    spa.writer.write(data)
    await spa.writer.drain()
    await asyncio.sleep(3)


async def disconnect():
    if spa.connected:
        await spa.disconnect()


async def main():
    messages = await read_messages()
    if messages == 1:
        return
    print(messages["panel_update"])
    return
    repeat = 2

    # for i in range(0xc0, 0xd0):
    #   if spa.pump_status[0] == 0:
    #     await spa.change_pump(0, 1)
    #     messages = await read_messages()
    #   for r in range(0, repeat):
    #     await write_command(i)
    #     messages = await compare_messages(messages)

    print(spa.blower_status)
    await spa.change_blower(spa.BLOWER_HIGH)
    messages = await compare_messages(messages)
    print(spa.blower_status)
    await spa.change_light(0, spa.OFF)
    messages = await compare_messages(messages)
    print(spa.blower_status)


async def main2():
    try:
        await spa.connect()
        if spa.connected:
            if await spa.spa_configured():
                # await spa.change_filter_cycle(filter1_hour=0)
                # await spa.change_filter_cycle(
                #     filter1_hour=19,
                #     filter1_duration_hours=2,
                #     filter1_duration_minutes=0,
                #     filter2_enabled=True,
                #     filter2_hour=7,
                #     filter2_duration_hours=1,
                #     filter2_duration_minutes=0,
                # )
                # await spa.set_time(time.localtime())
                await asyncio.sleep(1)
            else:
                print("Spa did not finish loading.")
    except Exception as e:
        await spa.disconnect()


asyncio.run(main2())
asyncio.run(disconnect())
# print(spa.to_celsius(104))
# print(spa.to_celsius(103))
# print(spa.to_celsius(102))
# print(spa.to_celsius(101))
# print(spa.to_celsius(100))
# print(spa.to_celsius(99))

# async def foo(x, y, z=None):
#    print(f"{x}, {y}, {z}")

# values = [None]
# print(*[i for i in values if i])
# # asyncio.run(foo(*values))
