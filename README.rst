pybalboa
--------

Python Module to interface with a balboa spa

To test::
  python3 pybalboa <ip-of-spa-wifi>

To Use::
  See __main__.py for usage examples.
  At a minimum:

  import asyncio
  import pybalboa

  spa = balboa.BalboaSpaWifi(spa_host)
  await spa.connect()
  asyncio.ensure_future(spa.listen())
  await spa.disconnect()
  return
