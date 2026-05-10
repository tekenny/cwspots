import asyncio
import logging
import os

from rbn_client import RBNClient
from dxcc import DXCCLookup
from spots import Spot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

dxcc = DXCCLookup("cty.dat")

async def print_spot(spot: Spot):
    spot.spotter_continent = dxcc.continent(spot.spotter)
    spot.dx_continent = dxcc.continent(spot.dx)
    entity = dxcc.lookup(spot.dx)
    spot.dx_entity = entity.name if entity else None
    print(f"{spot.time_utc}  {spot.freq_khz:>9.1f} kHz  "
          f"{spot.dx:<12} {spot.wpm:>3} wpm  {spot.snr_db:>3} dB  "
          f"{spot.dx_continent or '??':<2} ({spot.dx_entity or 'unknown':<25})  "
          f"via {spot.spotter}({spot.spotter_continent or '??'})")

async def main():
    callsign = os.environ.get("RBN_CALLSIGN", "YOURCALL")
    if callsign == "YOURCALL":
        print("Set your callsign: export RBN_CALLSIGN=YOURCALL")
        return
    client = RBNClient(callsign=callsign, on_spot=print_spot)
    await client.run()

asyncio.run(main())
