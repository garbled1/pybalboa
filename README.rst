pybalboa
--------

Python Module to interface with a balboa spa

Requires Python 3 with asyncio.

To Install::

  pip install pybalboa

To test::

  python3 pybalboa <ip-of-spa-wifi> <debug-flag>

To Use
``````

See ``__main__.py`` for usage examples.

Minimal example::

  import asyncio
  import pybalboa

  async with pybalboa.SpaClient(spa_host) as spa:
    # read/run spa commands
  return


Related
```````
- https://github.com/ccutrer/balboa_worldwide_app/wiki - invaluable wiki for Balboa module protocol
