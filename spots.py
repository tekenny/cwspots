import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Spot:
    spotter: str
    dx: str
    freq_khz: float
    mode: str
    snr_db: int
    wpm: int
    spot_type: str
    time_utc: str
    timestamp: float
    band_m: int
    spotter_continent: Optional[str] = None
    dx_continent: Optional[str] = None
    dx_entity: Optional[str] = None
    spotter_lat: Optional[float] = None
    spotter_lon: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def freq_to_band(freq_khz: float) -> int:
    f = freq_khz
    bands = [
        (1800, 2000, 160), (3500, 4000, 80), (5330, 5410, 60),
        (7000, 7300, 40), (10100, 10150, 30), (14000, 14350, 20),
        (18068, 18168, 17), (21000, 21450, 15), (24890, 24990, 12),
        (28000, 29700, 10), (50000, 54000, 6), (144000, 148000, 2),
    ]
    for low, high, band in bands:
        if low <= f <= high:
            return band
    return 0


class SpotBuffer:
    def __init__(self, window_seconds: int = 600):
        self.window = window_seconds
        self.spots: deque[Spot] = deque(maxlen=5000)

    def add(self, spot: Spot) -> None:
        self.spots.append(spot)
        self._evict_old()

    def _evict_old(self) -> None:
        cutoff = time.time() - self.window
        while self.spots and self.spots[0].timestamp < cutoff:
            self.spots.popleft()

    def recent(self, since: float = 0) -> list[Spot]:
        self._evict_old()
        return [s for s in self.spots if s.timestamp >= since]
