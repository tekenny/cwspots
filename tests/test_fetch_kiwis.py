import json
from unittest.mock import MagicMock, patch

import pytest

from fetch_kiwis import SOURCE, main


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