import asyncio
import json
import logging
import os
import time
from aiohttp import web
import websockets
from websockets.server import serve

from rbn_client import RBNClient
from dxcc import DXCCLookup
from spots import Spot, SpotBuffer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# --- Config ---
CALLSIGN   = os.environ.get("RBN_CALLSIGN", "YOURCALL")
HTTP_PORT  = int(os.environ.get("PORT", 8080))
WS_PORT    = int(os.environ.get("WS_PORT", 8081))
WEB_DIR    = os.path.join(os.path.dirname(__file__), "web")

# --- Shared state ---
dxcc       = DXCCLookup("cty.dat")
buffer     = SpotBuffer(window_seconds=600)
clients: set[websockets.WebSocketServerProtocol] = set()


def enrich(spot: Spot) -> Spot:
    spot.spotter_continent = dxcc.continent(spot.spotter)
    spot.dx_continent      = dxcc.continent(spot.dx)
    entity                 = dxcc.lookup(spot.dx)
    spot.dx_entity         = entity.name if entity else None
    spotter_entity         = dxcc.lookup(spot.spotter)
    if spotter_entity:
        spot.spotter_lat = spotter_entity.lat
        spot.spotter_lon = spotter_entity.lon
    return spot


def spot_matches(spot: Spot, filters: dict) -> bool:
    """Return True if spot passes all client filters."""
    try:
        wpm_min = int(filters.get("wpm_min", 0))
        wpm_max = int(filters.get("wpm_max", 99))
    except (TypeError, ValueError):
        wpm_min, wpm_max = 0, 99
    if not (wpm_min <= spot.wpm <= wpm_max):
        return False
    try:
        bands = [int(b) for b in filters.get("bands", [])]
    except (TypeError, ValueError):
        bands = []
    if bands and spot.band_m not in bands:
        return False
    continents_dx = filters.get("continents_dx", [])
    if continents_dx and spot.dx_continent not in continents_dx:
        return False
    continents_spotter = filters.get("continents_spotter", [])
    if continents_spotter and spot.spotter_continent not in continents_spotter:
        return False
    try:
        snr_min = int(filters.get("snr_min", -99))
    except (TypeError, ValueError):
        snr_min = -99
    if spot.snr_db < snr_min:
        return False
    modes = filters.get("modes", [])
    if modes and spot.mode not in modes:
        return False
    beacon_filter = filters.get("beacon", "both")
    if beacon_filter != "both":
        is_beacon = spot.dx.endswith("/B")
        if beacon_filter == "beacons" and not is_beacon:
            return False
        if beacon_filter == "non-beacons" and is_beacon:
            return False
    return True


async def on_spot(spot: Spot) -> None:
    spot = enrich(spot)
    buffer.add(spot)

    if not clients:
        return

    msg = json.dumps({"type": "spot", "data": spot.to_dict()})
    dead = set()
    for ws in clients:
        try:
            filters = getattr(ws, "filters", {})
            if spot_matches(spot, filters):
                await ws.send(msg)
        except websockets.ConnectionClosed:
            dead.add(ws)
    clients.difference_update(dead)


async def ws_handler(ws: websockets.WebSocketServerProtocol) -> None:
    ws.filters = {}
    clients.add(ws)
    remote = ws.remote_address
    logger.info(f"WS client connected: {remote}  total={len(clients)}")

    # Send recent buffered spots immediately on connect
    recent = buffer.recent(since=time.time() - 600)
    for spot in recent:
        if spot_matches(spot, ws.filters):
            await ws.send(json.dumps({"type": "spot", "data": spot.to_dict()}))

    try:
        async for message in ws:
            try:
                msg = json.loads(message)
                if msg.get("type") == "filter":
                    ws.filters = msg.get("filters", {})
                    logger.info(f"Client {remote} set filters: {ws.filters}")
                    # Resend buffer with new filters applied
                    recent = buffer.recent(since=time.time() - 600)
                    for spot in recent:
                        if spot_matches(spot, ws.filters):
                            await ws.send(json.dumps({"type": "spot", "data": spot.to_dict()}))
            except json.JSONDecodeError:
                pass
    except websockets.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        logger.info(f"WS client disconnected: {remote}  total={len(clients)}")



async def index_handler(request):
    return web.FileResponse(os.path.join(WEB_DIR, "index.html"))

async def main():
    if CALLSIGN == "YOURCALL":
        logger.error("Set RBN_CALLSIGN environment variable before starting")
        return

    logger.info(f"Starting CW Spotter  callsign={CALLSIGN}  "
                f"http=:{HTTP_PORT}  ws=:{WS_PORT}")

    # HTTP server for static files
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_static("/", WEB_DIR, show_index=False)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    logger.info(f"HTTP server running on port {HTTP_PORT}")

    # WebSocket server
    ws_server = await serve(ws_handler, "0.0.0.0", WS_PORT)
    logger.info(f"WebSocket server running on port {WS_PORT}")

    # RBN client
    rbn = RBNClient(callsign=CALLSIGN, on_spot=on_spot)
    await asyncio.gather(
        rbn.run(),
        ws_server.wait_closed(),
    )


if __name__ == "__main__":
    asyncio.run(main())
