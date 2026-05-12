import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fetch_skcc import base_call, main


SAMPLE_CSV = """\
CALL|SKCCNR|NAME|SPC|DXENTITY
W1AW|12345|HIRAM|CT|United States
G3XYZ/EX|67890|JOHN|-|England
JA1ZZZ/SK|11111|TARO|-|Japan
VK2DEF|22222|BRUCE|NSW|Australia
"""


# ---------------------------------------------------------------------------
# base_call
# ---------------------------------------------------------------------------

class TestBaseCall:
    def test_clean_callsign_unchanged(self):
        assert base_call("W1AW") == "W1AW"

    def test_lowercase_uppercased(self):
        assert base_call("w1aw") == "W1AW"

    def test_sk_suffix_stripped(self):
        assert base_call("G3XYZ/SK") == "G3XYZ"

    def test_ex_suffix_stripped(self):
        assert base_call("JA1ZZZ/EX") == "JA1ZZZ"

    def test_portable_suffix_stripped(self):
        # /P is not specifically handled — base_call splits on first /
        assert base_call("VK2DEF/P") == "VK2DEF"

    def test_strips_whitespace(self):
        assert base_call("  W1AW  ") == "W1AW"

    def test_empty_string(self):
        assert base_call("") == ""


# ---------------------------------------------------------------------------
# main — CSV parsing with mocked HTTP
# ---------------------------------------------------------------------------

class TestFetchSkccMain:
    def _mock_response(self, text: str):
        resp = MagicMock()
        resp.read.return_value = text.encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_parses_members_correctly(self, tmp_path):
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(SAMPLE_CSV)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        assert "W1AW" in data
        assert data["W1AW"]["nr"] == "12345"
        assert data["W1AW"]["name"] == "HIRAM"

    def test_ex_callsign_stored_under_base(self, tmp_path):
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(SAMPLE_CSV)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        assert "G3XYZ" in data
        assert "G3XYZ/EX" not in data

    def test_sk_callsign_stored_under_base(self, tmp_path):
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(SAMPLE_CSV)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        assert "JA1ZZZ" in data
        assert "JA1ZZZ/SK" not in data

    def test_all_members_saved(self, tmp_path):
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(SAMPLE_CSV)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        assert len(data) == 4

    def test_member_fields(self, tmp_path):
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(SAMPLE_CSV)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        vk = data["VK2DEF"]
        assert vk["nr"] == "22222"
        assert vk["name"] == "BRUCE"
        assert vk["spc"] == "NSW"
        assert vk["entity"] == "Australia"

    def test_fetch_failure_exits(self):
        with patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.urllib.request.urlopen", side_effect=Exception("network error")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_empty_call_row_skipped(self, tmp_path):
        csv_with_empty = "CALL|SKCCNR|NAME|SPC|DXENTITY\n|99999|NOBODY|-|Unknown\nW1AW|12345|HIRAM|CT|US\n"
        out_file = tmp_path / "skcc_members.json"
        resp = self._mock_response(csv_with_empty)

        with patch("fetch_skcc.urllib.request.urlopen", return_value=resp), \
             patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()), \
             patch("fetch_skcc.OUT", str(out_file)):
            main()

        data = json.loads(out_file.read_text())
        assert "" not in data
        assert "W1AW" in data
