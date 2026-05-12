import time
from unittest.mock import patch

import pytest
from spots import Spot, SpotBuffer, freq_to_band
from conftest import make_spot


# ---------------------------------------------------------------------------
# freq_to_band
# ---------------------------------------------------------------------------

class TestFreqToBand:
    def test_160m(self):
        assert freq_to_band(1800) == 160
        assert freq_to_band(1900) == 160
        assert freq_to_band(2000) == 160

    def test_80m(self):
        assert freq_to_band(3500) == 80
        assert freq_to_band(3750) == 80
        assert freq_to_band(4000) == 80

    def test_60m(self):
        assert freq_to_band(5330) == 60
        assert freq_to_band(5405) == 60
        assert freq_to_band(5410) == 60

    def test_40m(self):
        assert freq_to_band(7000) == 40
        assert freq_to_band(7200) == 40
        assert freq_to_band(7300) == 40

    def test_30m(self):
        assert freq_to_band(10100) == 30
        assert freq_to_band(10125) == 30
        assert freq_to_band(10150) == 30

    def test_20m(self):
        assert freq_to_band(14000) == 20
        assert freq_to_band(14025) == 20
        assert freq_to_band(14350) == 20

    def test_17m(self):
        assert freq_to_band(18068) == 17
        assert freq_to_band(18100) == 17
        assert freq_to_band(18168) == 17

    def test_15m(self):
        assert freq_to_band(21000) == 15
        assert freq_to_band(21225) == 15
        assert freq_to_band(21450) == 15

    def test_12m(self):
        assert freq_to_band(24890) == 12
        assert freq_to_band(24940) == 12
        assert freq_to_band(24990) == 12

    def test_10m(self):
        assert freq_to_band(28000) == 10
        assert freq_to_band(28500) == 10
        assert freq_to_band(29700) == 10

    def test_6m(self):
        assert freq_to_band(50000) == 6
        assert freq_to_band(52000) == 6
        assert freq_to_band(54000) == 6

    def test_2m(self):
        assert freq_to_band(144000) == 2
        assert freq_to_band(146000) == 2
        assert freq_to_band(148000) == 2

    def test_out_of_band_returns_zero(self):
        assert freq_to_band(0) == 0
        assert freq_to_band(5000) == 0       # between 160 and 80
        assert freq_to_band(10200) == 0      # between 30 and 20
        assert freq_to_band(999999) == 0

    def test_just_below_band_edge(self):
        assert freq_to_band(13999.9) == 0
        assert freq_to_band(28000) == 10     # exactly at edge is in-band

    def test_just_above_band_edge(self):
        assert freq_to_band(14350.1) == 0


# ---------------------------------------------------------------------------
# SpotBuffer
# ---------------------------------------------------------------------------

class TestSpotBuffer:
    def _spot_at(self, ts: float) -> Spot:
        return make_spot(timestamp=ts)

    def test_add_and_recent_returns_all_within_window(self):
        buf = SpotBuffer(window_seconds=600)
        now = 1000000.0
        with patch("spots.time") as mock_time:
            mock_time.time.return_value = now
            s = self._spot_at(now)
            buf.add(s)
            result = buf.recent()
        assert s in result

    def test_evicts_spots_older_than_window(self):
        buf = SpotBuffer(window_seconds=600)
        old_ts = 1000000.0
        new_ts = old_ts + 601

        old = self._spot_at(old_ts)
        with patch("spots.time") as mock_time:
            mock_time.time.return_value = old_ts
            buf.add(old)

        with patch("spots.time") as mock_time:
            mock_time.time.return_value = new_ts
            result = buf.recent()

        assert old not in result

    def test_since_filters_by_timestamp(self):
        buf = SpotBuffer(window_seconds=600)
        now = 1000000.0
        early = self._spot_at(now - 100)
        late = self._spot_at(now)

        with patch("spots.time") as mock_time:
            mock_time.time.return_value = now
            buf.add(early)
            buf.add(late)
            result = buf.recent(since=now - 50)

        assert early not in result
        assert late in result

    def test_maxlen_cap(self):
        buf = SpotBuffer(window_seconds=99999)
        now = 1000000.0
        with patch("spots.time") as mock_time:
            mock_time.time.return_value = now
            for i in range(5100):
                buf.add(self._spot_at(now))
        assert len(buf.spots) <= 5000

    def test_empty_buffer_recent_returns_empty(self):
        buf = SpotBuffer()
        with patch("spots.time") as mock_time:
            mock_time.time.return_value = 1000000.0
            assert buf.recent() == []

    def test_multiple_adds_and_evictions(self):
        buf = SpotBuffer(window_seconds=100)
        base = 1000000.0

        spots = [self._spot_at(base + i * 10) for i in range(15)]

        with patch("spots.time") as mock_time:
            for s in spots:
                mock_time.time.return_value = s.timestamp
                buf.add(s)

            # Now at base + 140; window=100 so only spots with ts >= base+40 survive
            mock_time.time.return_value = base + 140
            result = buf.recent()

        expected_survivors = [s for s in spots if s.timestamp >= base + 40]
        assert set(id(s) for s in result) == set(id(s) for s in expected_survivors)


# ---------------------------------------------------------------------------
# Spot.to_dict
# ---------------------------------------------------------------------------

class TestSpotToDict:
    def test_to_dict_contains_all_fields(self):
        s = make_spot()
        d = s.to_dict()
        for field in ("spotter", "dx", "freq_khz", "mode", "snr_db", "wpm",
                      "spot_type", "time_utc", "timestamp", "band_m",
                      "spotter_continent", "dx_continent", "dx_entity",
                      "spotter_lat", "spotter_lon"):
            assert field in d

    def test_to_dict_values_match(self):
        s = make_spot(freq_khz=14025.5, wpm=18, snr_db=-3)
        d = s.to_dict()
        assert d["freq_khz"] == 14025.5
        assert d["wpm"] == 18
        assert d["snr_db"] == -3

    def test_to_dict_optional_fields_none(self):
        s = Spot(spotter="W1AW", dx="K1ABC", freq_khz=14000.0, mode="CW",
                 snr_db=5, wpm=20, spot_type="CQ", time_utc="0000Z",
                 timestamp=0.0, band_m=20)
        d = s.to_dict()
        assert d["spotter_continent"] is None
        assert d["dx_continent"] is None
        assert d["dx_entity"] is None
