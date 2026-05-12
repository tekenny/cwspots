import pytest
from dxcc import DXCCLookup, DXCCEntity
from conftest import MINIMAL_CTY


@pytest.fixture
def dxcc(minimal_cty):
    return DXCCLookup(minimal_cty)


# ---------------------------------------------------------------------------
# DXCCLookup.lookup — prefix matching
# ---------------------------------------------------------------------------

class TestLookup:
    def test_us_callsign_w(self, dxcc):
        e = dxcc.lookup("W1AW")
        assert e is not None
        assert e.continent == "NA"
        assert "United States" in e.name

    def test_us_callsign_k(self, dxcc):
        e = dxcc.lookup("K1ABC")
        assert e is not None
        assert e.continent == "NA"

    def test_england_callsign(self, dxcc):
        e = dxcc.lookup("G3XYZ")
        assert e is not None
        assert e.continent == "EU"

    def test_japan_callsign(self, dxcc):
        e = dxcc.lookup("JA1ZZZ")
        assert e is not None
        assert e.continent == "AS"

    def test_australia_callsign(self, dxcc):
        e = dxcc.lookup("VK2DEF")
        assert e is not None
        assert e.continent == "OC"

    def test_brazil_callsign(self, dxcc):
        e = dxcc.lookup("PY1AB")
        assert e is not None
        assert e.continent == "SA"

    def test_south_africa_callsign(self, dxcc):
        e = dxcc.lookup("ZS6XYZ")
        assert e is not None
        assert e.continent == "AF"

    def test_unknown_callsign_returns_none(self, dxcc):
        assert dxcc.lookup("XXXUNKNOWN") is None

    def test_empty_callsign_returns_none(self, dxcc):
        assert dxcc.lookup("") is None

    def test_longest_prefix_wins(self, dxcc):
        # JA prefix is registered; JA1ZZZ should match JA
        e = dxcc.lookup("JA1ZZZ")
        assert e is not None
        assert e.continent == "AS"

    def test_callsign_with_slash_takes_longer_part(self, dxcc):
        # W1AW/JA1 — longer part is "JA1" but JA is in our fixture
        e = dxcc.lookup("W/JA1ABC")
        assert e is not None
        assert e.continent == "AS"

    def test_callsign_with_slash_portable(self, dxcc):
        # G3XYZ/P — longer is G3XYZ, G is in fixture
        e = dxcc.lookup("G3XYZ/P")
        assert e is not None
        assert e.continent == "EU"

    def test_lookup_case_insensitive(self, dxcc):
        e_upper = dxcc.lookup("W1AW")
        e_lower = dxcc.lookup("w1aw")
        assert e_upper is not None
        assert e_lower is not None
        assert e_upper.continent == e_lower.continent

    def test_returns_dxcc_entity(self, dxcc):
        e = dxcc.lookup("W1AW")
        assert isinstance(e, DXCCEntity)
        assert isinstance(e.continent, str)
        assert isinstance(e.cq_zone, int)
        assert isinstance(e.itu_zone, int)


# ---------------------------------------------------------------------------
# DXCCLookup.continent
# ---------------------------------------------------------------------------

class TestContinent:
    def test_known_callsign(self, dxcc):
        assert dxcc.continent("W1AW") == "NA"
        assert dxcc.continent("G3XYZ") == "EU"
        assert dxcc.continent("JA1ZZZ") == "AS"

    def test_unknown_returns_none(self, dxcc):
        assert dxcc.continent("XXXUNK") is None

    def test_empty_returns_none(self, dxcc):
        assert dxcc.continent("") is None


# ---------------------------------------------------------------------------
# DXCCLookup — coordinate parsing (lon negation from cty.dat convention)
# ---------------------------------------------------------------------------

class TestCoordinates:
    def test_lon_negation(self, dxcc):
        # cty.dat lists W lon as +87.90, which means West — should be stored as -87.90
        e = dxcc.lookup("W1AW")
        assert e is not None
        assert e.lon < 0  # West should be negative after negation

    def test_lat_reasonable(self, dxcc):
        e = dxcc.lookup("W1AW")
        assert e is not None
        assert -90 <= e.lat <= 90


# ---------------------------------------------------------------------------
# Integration test — real cty.dat
# ---------------------------------------------------------------------------

class TestIntegrationRealCtyDat:
    @pytest.fixture(autouse=True)
    def load_real(self):
        import os
        cty_path = os.path.join(os.path.dirname(__file__), "..", "cty.dat")
        if not os.path.exists(cty_path):
            pytest.skip("cty.dat not present")
        self.dxcc = DXCCLookup(cty_path)

    def test_k1abc_is_na(self):
        assert self.dxcc.continent("K1ABC") == "NA"

    def test_g3xyz_is_eu(self):
        assert self.dxcc.continent("G3XYZ") == "EU"

    def test_ja1zzz_is_as(self):
        assert self.dxcc.continent("JA1ZZZ") == "AS"

    def test_vk2def_is_oc(self):
        assert self.dxcc.continent("VK2DEF") == "OC"

    def test_py1ab_is_sa(self):
        assert self.dxcc.continent("PY1AB") == "SA"

    def test_zs6xyz_is_af(self):
        assert self.dxcc.continent("ZS6XYZ") == "AF"

    def test_many_prefixes_loaded(self):
        assert len(self.dxcc.prefixes) > 300
