import asyncio
import logging
import re
import time
from typing import Callable, Awaitable

from spots import Spot, freq_to_band

logger = logging.getLogger(__name__)

RBN_HOST = "telnet.reversebeacon.net"
RBN_PORT = 7000

SPOT_RE = re.compile(
    r"^DX de\s+(?P<spotter>[A-Z0-9/\-#]+):\s+"
    r"(?P<freq>\d+\.\d+)\s+"
    r"(?P<dx>[A-Z0-9/]+)\s+"
    r"(?P<mode>\S+)\s+"
    r"(?P<snr>-?\d+)\s*dB\s+"
    r"(?P<wpm>\d+)\s*WPM\s+"
    r"(?P<type>\S+)\s+"
    r"(?P<time>\d{4}Z)",
    re.IGNORECASE,
)


class RBNClient:
    def __init__(self, callsign: str, on_spot: Callable[[Spot], Awaitable[None]],
                 host: str = RBN_HOST, port: int = RBN_PORT):
        self.callsign = callsign
        self.on_spot = on_spot
        self.host = host
        self.port = port
        self._reconnect_delay = 5
        self._max_delay = 300

    async def run(self) -> None:
        while True:
            try:
                await self._connect_and_read()
                self._reconnect_delay = 5
            except Exception as e:
                logger.warning(f"RBN connection error: {e}")
            logger.info(f"Reconnecting to RBN in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_delay)

    async def _connect_and_read(self) -> None:
        logger.info(f"Connecting to {self.host}:{self.port}...")
        reader, writer = await asyncio.open_connection(self.host, self.port)
        logger.info("Connected to RBN")
        try:
            await asyncio.wait_for(reader.readuntil(b":"), timeout=15)
            writer.write(f"{self.callsign}\r\n".encode())
            await writer.drain()
        except asyncio.TimeoutError:
            writer.write(f"{self.callsign}\r\n".encode())
            await writer.drain()
        logger.info(f"Logged in as {self.callsign}")
        while True:
            try:
                line_bytes = await asyncio.wait_for(reader.readline(), timeout=120)
            except asyncio.TimeoutError:
                logger.warning("No data from RBN for 120s, reconnecting")
                writer.close()
                return
            if not line_bytes:
                logger.info("RBN closed the connection")
                return
            line = line_bytes.decode("ascii", errors="replace").strip()
            if not line:
                continue
            spot = self._parse_line(line)
            if spot:
                await self.on_spot(spot)

    def _parse_line(self, line: str) -> Spot | None:
        match = SPOT_RE.match(line)
        if not match:
            return None
        try:
            freq = float(match.group("freq"))
            spotter_raw = match.group("spotter")
            spotter = spotter_raw.split("-")[0] if "-" in spotter_raw else spotter_raw
            return Spot(
                spotter=spotter,
                dx=match.group("dx").upper(),
                freq_khz=freq,
                mode=match.group("mode").upper(),
                snr_db=int(match.group("snr")),
                wpm=int(match.group("wpm")),
                spot_type=match.group("type").upper(),
                time_utc=match.group("time"),
                timestamp=time.time(),
                band_m=freq_to_band(freq),
            )
        except (ValueError, AttributeError):
            return None
