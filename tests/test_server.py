import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from server import spot_matches, enrich
from conftest import make_spot


# ---------------------------------------------------------------------------
# spot_matches — wpm filter
# ---------------------------------------------------------------------------

class TestSpotMatchesWpm:
    def test_within_range(self):
        s = make_spot(wpm=25)
        assert spot_matches(s, {"wpm_min": 20, "wpm_max": 30}) is True

    def test_at_min_boundary(self):
        s = make_spot(wpm=20)
        assert spot_matches(s, {"wpm_min": 20, "wpm_max": 30}) is True

    def test_at_max_boundary(self):
        s = make_spot(wpm=30)
        assert spot_matches(s, {"wpm_min": 20, "wpm_max": 30}) is True

    def test_below_min(self):
        s = make_spot(wpm=10)
        assert spot_matches(s, {"wpm_min": 20, "wpm_max": 30}) is False

    def test_above_max(self):
        s = make_spot(wpm=35)
        assert spot_matches(s, {"wpm_min": 20, "wpm_max": 30}) is False

    def test_bad_wpm_values_default_to_0_99(self):
        s = make_spot(wpm=25)
        assert spot_matches(s, {"wpm_min": "bad", "wpm_max": "bad"}) is True

    def test_no_wpm_filter(self):
        s = make_spot(wpm=99)
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# spot_matches — band filter
# ---------------------------------------------------------------------------

class TestSpotMatchesBands:
    def test_band_in_list(self):
        s = make_spot(band_m=20)
        assert spot_matches(s, {"bands": [20, 40]}) is True

    def test_band_not_in_list(self):
        s = make_spot(band_m=10)
        assert spot_matches(s, {"bands": [20, 40]}) is False

    def test_empty_bands_passes_all(self):
        s = make_spot(band_m=10)
        assert spot_matches(s, {"bands": []}) is True

    def test_bad_band_value_defaults_to_empty(self):
        s = make_spot(band_m=20)
        assert spot_matches(s, {"bands": ["bad"]}) is True

    def test_no_bands_key_passes_all(self):
        s = make_spot(band_m=6)
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# spot_matches — dx continent filter
# ---------------------------------------------------------------------------

class TestSpotMatchesDxContinent:
    def test_matching_continent(self):
        s = make_spot(dx_continent="EU")
        assert spot_matches(s, {"continents_dx": ["EU", "AS"]}) is True

    def test_non_matching_continent(self):
        s = make_spot(dx_continent="NA")
        assert spot_matches(s, {"continents_dx": ["EU", "AS"]}) is False

    def test_empty_list_passes_all(self):
        s = make_spot(dx_continent="NA")
        assert spot_matches(s, {"continents_dx": []}) is True

    def test_missing_key_passes_all(self):
        s = make_spot(dx_continent="OC")
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# spot_matches — spotter continent filter
# ---------------------------------------------------------------------------

class TestSpotMatchesSpotterContinent:
    def test_matching(self):
        s = make_spot(spotter_continent="NA")
        assert spot_matches(s, {"continents_spotter": ["NA"]}) is True

    def test_non_matching(self):
        s = make_spot(spotter_continent="EU")
        assert spot_matches(s, {"continents_spotter": ["NA"]}) is False

    def test_empty_passes(self):
        s = make_spot(spotter_continent="AF")
        assert spot_matches(s, {"continents_spotter": []}) is True


# ---------------------------------------------------------------------------
# spot_matches — SNR filter
# ---------------------------------------------------------------------------

class TestSpotMatchesSnr:
    def test_above_min(self):
        s = make_spot(snr_db=10)
        assert spot_matches(s, {"snr_min": 5}) is True

    def test_at_min(self):
        s = make_spot(snr_db=5)
        assert spot_matches(s, {"snr_min": 5}) is True

    def test_below_min(self):
        s = make_spot(snr_db=3)
        assert spot_matches(s, {"snr_min": 5}) is False

    def test_negative_snr(self):
        s = make_spot(snr_db=-5)
        assert spot_matches(s, {"snr_min": -10}) is True
        assert spot_matches(s, {"snr_min": 0}) is False

    def test_bad_snr_min_defaults(self):
        s = make_spot(snr_db=-50)
        assert spot_matches(s, {"snr_min": "bad"}) is True

    def test_no_snr_filter(self):
        s = make_spot(snr_db=-99)
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# spot_matches — mode filter
# ---------------------------------------------------------------------------

class TestSpotMatchesModes:
    def test_matching_mode(self):
        s = make_spot(mode="CW")
        assert spot_matches(s, {"modes": ["CW"]}) is True

    def test_non_matching_mode(self):
        s = make_spot(mode="FT8")
        assert spot_matches(s, {"modes": ["CW"]}) is False

    def test_empty_modes_passes(self):
        s = make_spot(mode="FT8")
        assert spot_matches(s, {"modes": []}) is True

    def test_no_modes_key(self):
        s = make_spot(mode="CW")
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# spot_matches — beacon filter
# ---------------------------------------------------------------------------

class TestSpotMatchesBeacon:
    def _beacon_spot(self):
        return make_spot(dx="K1ABC/B")

    def _non_beacon_spot(self):
        return make_spot(dx="K1ABC")

    def test_both_accepts_beacon(self):
        assert spot_matches(self._beacon_spot(), {"beacon": "both"}) is True

    def test_both_accepts_non_beacon(self):
        assert spot_matches(self._non_beacon_spot(), {"beacon": "both"}) is True

    def test_beacons_only_accepts_beacon(self):
        assert spot_matches(self._beacon_spot(), {"beacon": "beacons"}) is True

    def test_beacons_only_rejects_non_beacon(self):
        assert spot_matches(self._non_beacon_spot(), {"beacon": "beacons"}) is False

    def test_non_beacons_only_accepts_non_beacon(self):
        assert spot_matches(self._non_beacon_spot(), {"beacon": "non-beacons"}) is True

    def test_non_beacons_only_rejects_beacon(self):
        assert spot_matches(self._beacon_spot(), {"beacon": "non-beacons"}) is False

    def test_default_no_beacon_key(self):
        assert spot_matches(self._beacon_spot(), {}) is True
        assert spot_matches(self._non_beacon_spot(), {}) is True


# ---------------------------------------------------------------------------
# spot_matches — combined filters
# ---------------------------------------------------------------------------

class TestSpotMatchesCombined:
    def test_all_pass(self):
        s = make_spot(wpm=25, band_m=20, dx_continent="EU",
                      spotter_continent="NA", snr_db=10, mode="CW", dx="G3XYZ")
        filters = {
            "wpm_min": 20, "wpm_max": 30,
            "bands": [20],
            "continents_dx": ["EU"],
            "continents_spotter": ["NA"],
            "snr_min": 5,
            "modes": ["CW"],
            "beacon": "non-beacons",
        }
        assert spot_matches(s, filters) is True

    def test_one_fails_all_fail(self):
        s = make_spot(wpm=25, band_m=20, dx_continent="EU",
                      spotter_continent="NA", snr_db=10, mode="CW")
        filters = {
            "wpm_min": 20, "wpm_max": 30,
            "bands": [40],  # wrong band
        }
        assert spot_matches(s, filters) is False

    def test_empty_filters_pass_everything(self):
        s = make_spot(wpm=1, band_m=0, snr_db=-99)
        assert spot_matches(s, {}) is True


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

class TestEnrich:
    def _make_dxcc(self):
        mock = MagicMock()
        mock.continent.side_effect = lambda call: {"W1AW": "NA", "K1ABC": "NA"}.get(call)
        entity = MagicMock()
        entity.name = "United States"
        entity.lat = 43.0
        entity.lon = -87.9
        mock.lookup.return_value = entity
        return mock

    def test_enriches_continents(self):
        mock_dxcc = self._make_dxcc()
        s = make_spot(spotter="W1AW", dx="K1ABC",
                      spotter_continent=None, dx_continent=None, dx_entity=None)
        with patch("server.dxcc", mock_dxcc):
            result = enrich(s)
        assert result.spotter_continent == "NA"
        assert result.dx_continent == "NA"

    def test_enriches_entity_name(self):
        mock_dxcc = self._make_dxcc()
        s = make_spot(dx_entity=None)
        with patch("server.dxcc", mock_dxcc):
            result = enrich(s)
        assert result.dx_entity == "United States"

    def test_enriches_spotter_lat_lon(self):
        mock_dxcc = self._make_dxcc()
        s = make_spot(spotter_lat=None, spotter_lon=None)
        with patch("server.dxcc", mock_dxcc):
            result = enrich(s)
        assert result.spotter_lat == 43.0
        assert result.spotter_lon == -87.9

    def test_unknown_dx_entity_is_none(self):
        mock_dxcc = MagicMock()
        mock_dxcc.continent.return_value = None
        mock_dxcc.lookup.return_value = None
        s = make_spot(dx_entity=None, dx_continent=None)
        with patch("server.dxcc", mock_dxcc):
            result = enrich(s)
        assert result.dx_entity is None

    def test_unknown_spotter_lat_lon_unchanged(self):
        mock_dxcc = MagicMock()
        mock_dxcc.continent.return_value = None
        mock_dxcc.lookup.return_value = None
        s = make_spot(spotter_lat=None, spotter_lon=None)
        with patch("server.dxcc", mock_dxcc):
            result = enrich(s)
        assert result.spotter_lat is None
        assert result.spotter_lon is None


# ---------------------------------------------------------------------------
# on_spot — async broadcast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOnSpot:
    def _make_ws(self, filters=None):
        ws = AsyncMock()
        ws.filters = filters or {}
        ws.send = AsyncMock()
        return ws

    async def test_spot_broadcast_to_matching_client(self):
        import server
        ws = self._make_ws()
        old_clients = server.clients.copy()
        server.clients.clear()
        server.clients.add(ws)
        try:
            s = make_spot()
            mock_dxcc = MagicMock()
            mock_dxcc.continent.return_value = "NA"
            entity = MagicMock()
            entity.name = "United States"
            entity.lat = 43.0
            entity.lon = -87.9
            mock_dxcc.lookup.return_value = entity
            with patch("server.dxcc", mock_dxcc):
                await server.on_spot(s)
            ws.send.assert_called_once()
            payload = json.loads(ws.send.call_args[0][0])
            assert payload["type"] == "spot"
        finally:
            server.clients.clear()
            server.clients.update(old_clients)

    async def test_spot_not_sent_to_non_matching_client(self):
        import server
        ws = self._make_ws(filters={"bands": [40]})
        old_clients = server.clients.copy()
        server.clients.clear()
        server.clients.add(ws)
        try:
            s = make_spot(band_m=20)
            mock_dxcc = MagicMock()
            mock_dxcc.continent.return_value = "NA"
            entity = MagicMock()
            entity.name = "US"
            entity.lat = 43.0
            entity.lon = -87.9
            mock_dxcc.lookup.return_value = entity
            with patch("server.dxcc", mock_dxcc):
                await server.on_spot(s)
            ws.send.assert_not_called()
        finally:
            server.clients.clear()
            server.clients.update(old_clients)

    async def test_dead_client_removed(self):
        import server
        ws = self._make_ws()
        ws.send.side_effect = websockets.ConnectionClosed(None, None)
        old_clients = server.clients.copy()
        server.clients.clear()
        server.clients.add(ws)
        try:
            s = make_spot()
            mock_dxcc = MagicMock()
            mock_dxcc.continent.return_value = "NA"
            entity = MagicMock()
            entity.name = "US"
            entity.lat = 43.0
            entity.lon = -87.9
            mock_dxcc.lookup.return_value = entity
            with patch("server.dxcc", mock_dxcc):
                await server.on_spot(s)
            assert ws not in server.clients
        finally:
            server.clients.clear()
            server.clients.update(old_clients)

    async def test_no_clients_no_broadcast(self):
        import server
        old_clients = server.clients.copy()
        server.clients.clear()
        try:
            s = make_spot()
            mock_dxcc = MagicMock()
            mock_dxcc.continent.return_value = "NA"
            mock_dxcc.lookup.return_value = None
            with patch("server.dxcc", mock_dxcc):
                await server.on_spot(s)  # should not raise
        finally:
            server.clients.clear()
            server.clients.update(old_clients)
