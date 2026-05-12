import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rbn_client import RBNClient, SPOT_RE
from spots import Spot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(on_spot=None):
    if on_spot is None:
        on_spot = AsyncMock()
    return RBNClient(callsign="W1AW", on_spot=on_spot, host="localhost", port=9999)


VALID_LINE = "DX de W1AW-1:      14025.0  K1ABC        CW     10 dB  25 WPM  CQ      1234Z"
VALID_LINE_NEG_SNR = "DX de W1AW-1:      7025.0   K1ABC        CW     -3 dB  18 WPM  CQ      0000Z"
VALID_LINE_NO_SUFFIX = "DX de VK2DEF:      21200.0  JA1ZZZ       CW      8 dB  20 WPM  CQ      0001Z"
VALID_LINE_SLASH_DX = "DX de W1AW:        14025.0  G3XYZ/P      CW     15 dB  22 WPM  CQ      1200Z"


# ---------------------------------------------------------------------------
# _parse_line
# ---------------------------------------------------------------------------

class TestParseLine:
    def test_valid_line_returns_spot(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert isinstance(spot, Spot)

    def test_spotter_suffix_stripped(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.spotter == "W1AW"
        assert "-" not in spot.spotter

    def test_spotter_without_suffix_preserved(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE_NO_SUFFIX)
        assert spot is not None
        assert spot.spotter == "VK2DEF"

    def test_freq_parsed_correctly(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.freq_khz == pytest.approx(14025.0)

    def test_dx_uppercased(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.dx == "K1ABC"

    def test_mode_uppercased(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.mode == "CW"

    def test_snr_positive(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.snr_db == 10

    def test_snr_negative(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE_NEG_SNR)
        assert spot is not None
        assert spot.snr_db == -3

    def test_wpm_parsed(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.wpm == 25

    def test_time_utc_parsed(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.time_utc == "1234Z"

    def test_spot_type_uppercased(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.spot_type == "CQ"

    def test_band_assigned(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE)
        assert spot is not None
        assert spot.band_m == 20

    def test_dx_with_slash_preserved(self):
        client = make_client()
        spot = client._parse_line(VALID_LINE_SLASH_DX)
        assert spot is not None
        assert spot.dx == "G3XYZ/P"

    def test_garbage_line_returns_none(self):
        client = make_client()
        assert client._parse_line("") is None
        assert client._parse_line("not a spot at all") is None
        assert client._parse_line("DX de incomplete") is None

    def test_timestamp_is_recent(self):
        client = make_client()
        before = time.time()
        spot = client._parse_line(VALID_LINE)
        after = time.time()
        assert spot is not None
        assert before <= spot.timestamp <= after

    def test_40m_band(self):
        line = "DX de W1AW:         7025.0  K1ABC        CW     10 dB  25 WPM  CQ      1234Z"
        client = make_client()
        spot = client._parse_line(line)
        assert spot is not None
        assert spot.band_m == 40

    def test_out_of_band_freq(self):
        line = "DX de W1AW:         5000.0  K1ABC        CW     10 dB  25 WPM  CQ      1234Z"
        client = make_client()
        spot = client._parse_line(line)
        assert spot is not None
        assert spot.band_m == 0


# ---------------------------------------------------------------------------
# SPOT_RE regex
# ---------------------------------------------------------------------------

class TestSpotRegex:
    def test_matches_valid_line(self):
        assert SPOT_RE.match(VALID_LINE) is not None

    def test_no_match_garbage(self):
        assert SPOT_RE.match("random text") is None

    def test_captures_all_groups(self):
        m = SPOT_RE.match(VALID_LINE)
        assert m is not None
        assert m.group("spotter") is not None
        assert m.group("freq") is not None
        assert m.group("dx") is not None
        assert m.group("mode") is not None
        assert m.group("snr") is not None
        assert m.group("wpm") is not None
        assert m.group("type") is not None
        assert m.group("time") is not None


# ---------------------------------------------------------------------------
# Async: _connect_and_read — mocked TCP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestConnectAndRead:
    async def _run_with_lines(self, lines: list[bytes], on_spot=None):
        if on_spot is None:
            on_spot = AsyncMock()
        client = make_client(on_spot=on_spot)

        reader = AsyncMock()
        writer = AsyncMock()
        writer.close = MagicMock()

        reader.readuntil = AsyncMock(return_value=b"login:")
        reader.readline = AsyncMock(side_effect=lines + [b""])

        with patch("rbn_client.asyncio.open_connection", return_value=(reader, writer)):
            await client._connect_and_read()

        return on_spot

    async def test_valid_line_triggers_callback(self):
        line = (VALID_LINE + "\r\n").encode("ascii")
        on_spot = await self._run_with_lines([line])
        on_spot.assert_called_once()
        arg = on_spot.call_args[0][0]
        assert isinstance(arg, Spot)

    async def test_garbage_line_does_not_trigger_callback(self):
        line = b"not a spot\r\n"
        on_spot = await self._run_with_lines([line])
        on_spot.assert_not_called()

    async def test_multiple_valid_lines_trigger_multiple_callbacks(self):
        line = (VALID_LINE + "\r\n").encode("ascii")
        on_spot = await self._run_with_lines([line, line, line])
        assert on_spot.call_count == 3

    async def test_empty_line_skipped(self):
        on_spot = await self._run_with_lines([b"\r\n", b"   \r\n"])
        on_spot.assert_not_called()

    async def test_login_callsign_sent(self):
        writer = AsyncMock()
        writer.close = MagicMock()
        reader = AsyncMock()
        reader.readuntil = AsyncMock(return_value=b"login:")
        reader.readline = AsyncMock(return_value=b"")

        on_spot = AsyncMock()
        client = RBNClient(callsign="TEST", on_spot=on_spot, host="h", port=1)

        with patch("rbn_client.asyncio.open_connection", return_value=(reader, writer)):
            await client._connect_and_read()

        write_calls = [call[0][0] for call in writer.write.call_args_list]
        assert any(b"TEST" in c for c in write_calls)
