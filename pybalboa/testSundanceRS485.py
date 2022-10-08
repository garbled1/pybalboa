try:
    import balboa
except ImportError:
    import pybalboa as balboa
    
try:
    import sundanceRS485
except ImportError:
    import sundanceRS485 as SundanceRS485

import asyncio
import sys


async def ReadR(spa, lastupd):
        await asyncio.sleep(1)
        if spa.lastupd != lastupd:
            lastupd = spa.lastupd
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
            print("Current Temp2: {0}".format(spa.temp2))
            print("Set Temp: {0}".format(spa.get_settemp()))          
            print("Heat State: {0} {1}".format(spa.get_heatstate(True),spa.heatState2))
            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Circulation Pump: {0}  Auto:  {1}  Man: {2}  Unkfield: {3}".format(spa.get_circ_pump(True), spa.autoCirc, spa.manualCirc, spa.unknownCirc))

            print("Display Text: {}".format(spa.get_displayText()))
            print("Heat Mode: {}".format(spa.get_heatMode()))
            
            print("UnknownField3: {}".format(spa.UnknownField3))
            print("UnknownField9: {}".format(spa.UnknownField9))
 
            print("Light Status: M{0} Br{1} R{2} G{3} B{4} T{4}".format(spa.lightMode,spa.lightBrightnes,spa.lightR,spa.lightG, spa.lightB, spa.lightCycleTime))
 
            print("Spa Time: {0:04d} {1:02d} {2:02d} {3:02d}:{4:02d} {5}".format(
                spa.year,
                spa.month,
                spa.day,
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))

            print()
        return lastupd

async def newFormatTest():
    """ Test a miniature engine of talking to the spa."""
    spa = sundanceRS485.SundanceRS485("192.168.50.53", 8899)
    await spa.connect()

    asyncio.ensure_future(spa.listen())
    lastupd = 0
    for i in range(0, 9999999999):
        lastupd = await ReadR(spa, lastupd)     
        #if i == 10:
        #    await spa.send_CCmessage(241)
        #if i == 20:
        #    await spa.send_CCmessage(241)
        #if i == 30:
        #    await spa.send_CCmessage(241)
        #if i == 40:
        #    await spa.send_CCmessage(241)        
        #if i == 10:
        #    await spa.send_CCmessage(242)    
        #if i == 20:
        #    await spa.send_CCmessage(242)    
        #if i == 30:
        #    await spa.send_CCmessage(242)    
        #if i == 40:
        #    await spa.send_CCmessage(242)  
        #if i == 50:
        #    await spa.send_CCmessage(242)  
    return

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
    for i in range(0, 9999999999):
         lastupd = await ReadR(spa, lastupd)     
        

if __name__ == "__main__":
    
    asyncio.run(newFormatTest())

    
