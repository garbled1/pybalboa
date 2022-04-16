import pybalboa as balboa
import sundance780

import asyncio
import sys


async def ReadR(spa, lastupd):
        await asyncio.sleep(1)
        if spa.lastupd != lastupd:
            lastupd = spa.lastupd
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
 
            print("Set Temp: {0}".format(spa.get_settemp()))

            print("Heat State: {0}".format(spa.get_heatstate(True)))

            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Circulation Pump: {0}".format(spa.get_circ_pump(True)))
            print("Light Status: {0}".format(str(spa.light_status)))

            print("Aux Status: {0}".format(str(spa.aux_status)))

            print("Spa Time: {0:02d}:{1:02d} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))

            print()
        return lastupd

async def newFormatTest():
    """ Test a miniature engine of talking to the spa."""
    spa = sundance780.SundanceRS485("192.168.50.53", 8899)
    await spa.connect()

    asyncio.ensure_future(spa.listen())


    print('Pump Array: {0}'.format(str(spa.pump_array)))
    print('Light Array: {0}'.format(str(spa.light_array)))
    print('Aux Array: {0}'.format(str(spa.aux_array)))
    print('Circulation Pump: {0}'.format(spa.circ_pump))
    print('Blower: {0}'.format(spa.blower))
    print('Mister: {0}'.format(spa.mister))
    print("Min Temps: {0}".format(spa.tmin))
    print("Max Temps: {0}".format(spa.tmax))
    print("Nr of pumps: {0}".format(spa.nr_of_pumps))
    print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
    print("Heat Mode: {0}".format(spa.get_heatmode(True)))
    print("Temp Range: {0}".format(spa.get_temprange(True)))
    print("Blower Status: {0}".format(spa.get_blower(True)))
    print("Mister Status: {0}".format(spa.get_mister(True)))  
    print("Filter Mode: {0}".format(spa.get_filtermode(True)))               
    lastupd = 0
   
    for i in range(0, 10):
         lastupd = await ReadR(spa, lastupd)
    await spa.change_pump(1, spa.PUMP_LOW)
    for i in range(0, 10):
         lastupd = await ReadR(spa, lastupd)
    await spa.change_pump(1, spa.PUMP_OFF)
    for i in range(0, 10):
         lastupd = await ReadR(spa, lastupd)
    await spa.send_temp_change(103)
    for i in range(0, 10):
         lastupd = await ReadR(spa, lastupd)
    await spa.send_temp_change(97)
    for i in range(0, 30):
         lastupd = await ReadR(spa, lastupd)        
        

if __name__ == "__main__":
    
    asyncio.run(newFormatTest())

    
