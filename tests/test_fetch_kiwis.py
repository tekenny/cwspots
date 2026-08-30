import json
from unittest.mock import MagicMock, patch

import pytest

from fetch_kiwis import SOURCE, main, valid_station


class TestFetchKiwisMain:
    def test_source_uses_https(self):
        assert SOURCE.startswith("https://")

    def _response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        return response

    def test_filters_defaults_and_sorts_stations(self, tmp_path, capsys):
        output = tmp_path / "kiwi_stations.json"
        payload = [
            {"h": "z.example", "n": "Zulu", "lat": 1, "lon": 2},
            {"h": "", "n": "Missing host"},
            {"h": "no-name.example", "n": ""},
            {"h": "a.example", "n": " alpha ", "p": 9000, "u": 2, "um": 10},
        ]
        with patch("fetch_kiwis.urllib.request.urlopen", return_value=self._response(payload)), \
                patch("fetch_kiwis.OUT", str(output)):
            main()

        stations = json.loads(output.read_text())
        assert [station["name"] for station in stations] == ["alpha", "Zulu"]
        assert stations[0] == {
            "name": "alpha", "url": "http://a.example:9000",
            "lat": None, "lon": None, "users": 2, "users_max": 10,
        }
        assert stations[1]["url"] == "http://z.example:8073"
        assert "Saved 2 stations" in capsys.readouterr().out

    def test_fetch_failure_exits(self, capsys):
        with patch("fetch_kiwis.urllib.request.urlopen", side_effect=OSError("offline")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        assert "fetch failed: offline" in capsys.readouterr().err

def _build(payload, tmp_path=None):
    """Run main() over *payload* and return the station list it wrote."""
    import tempfile, pathlib
    out = pathlib.Path(tempfile.mkdtemp()) / "kiwi_stations.json"
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch("fetch_kiwis.urllib.request.urlopen", return_value=response),          patch("fetch_kiwis.OUT", str(out)):
        main()
    return json.loads(out.read_text(encoding="utf-8"))

class TestHostValidationRejectsUserinfo:
    """REGRESSION: '@' passed the character filter.

    The host goes straight into f"http://{h}:{p}", so "user@evil.example"
    makes that a URL pointing at evil.example with the intended host demoted to
    userinfo -- a link in the station picker that goes somewhere else. The
    filter already covered the characters that end the authority component; it
    just did not cover the one that starts it.
    """

    @pytest.mark.parametrize("host", [
        "user@evil.example",
        "kiwi.example.com@evil.example",
        "a" + chr(92) + "b",   # backslash: a UNC-style path, not a hostname
    ])
    def test_a_host_that_could_redirect_is_rejected(self, host):
        assert valid_station({"h": host, "n": "Site"}) is False

    def test_an_ordinary_host_is_still_accepted(self):
        assert valid_station({"h": "kiwi.example.com", "n": "Site"}) is True

    def test_the_url_uses_the_validated_port(self):
        # The URL used to be built from the raw value rather than the int the
        # validator checked, so "8073" and 8073.0 reached it verbatim.
        stations = _build([{"h": "kiwi.example.com", "n": "Site", "p": "8073"}])
        assert stations[0]["url"] == "http://kiwi.example.com:8073"


class TestOutputEncoding:
    """REGRESSION: the cache was written in the locale encoding.

    NamedTemporaryFile("w") with no encoding uses cp1252 on Windows, and
    KiwiSDR site names carry accented characters -- the dump raised
    UnicodeEncodeError part-way through, leaving a temp file behind and the
    cache unrefreshed.
    """

    def test_an_accented_site_name_survives(self):
        stations = _build([{"h": "kiwi.example.com", "n": "Genève SDR"}])
        assert stations[0]["name"] == "Genève SDR"
