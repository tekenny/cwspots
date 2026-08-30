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


def _run_fetch(text, tmp_path, monkeypatch):
    """Run main() over *text* and return the JSON it wrote."""
    out_dir = tmp_path / "web"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "skcc_members.json"
    resp = MagicMock()
    resp.read.return_value = text.encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("fetch_skcc.urllib.request.urlopen", return_value=resp),          patch("fetch_skcc.urllib.request.Request", return_value=MagicMock()),          patch("fetch_skcc.OUT", str(out_file)):
        main()
    return json.loads(out_file.read_text(encoding="utf-8"))

class TestSilentKeysDoNotOverwriteMembers:
    """REGRESSION: whichever row came later won a reissued callsign.

    A /SK (silent key) and a current member reduce to the same base call, and
    the roster is written into a plain dict, so a reissued callsign could end
    up carrying the silent key's record instead of the live member's.
    """

    def _rows(self, *lines):
        header = "SKCCNR|CALL|NAME|SPC|DXENTITY"
        return "\n".join([header, *lines]) + "\n"

    def test_a_current_member_wins_over_a_later_silent_key(self, tmp_path, monkeypatch):
        text = self._rows("1|K1ABC|Live Op|NV|USA", "2|K1ABC/SK|Dead Op|NV|USA")
        members = _run_fetch(text, tmp_path, monkeypatch)
        assert members["K1ABC"]["name"] == "Live Op"

    def test_a_current_member_wins_over_an_earlier_silent_key(self, tmp_path, monkeypatch):
        text = self._rows("1|K1ABC/SK|Dead Op|NV|USA", "2|K1ABC|Live Op|NV|USA")
        members = _run_fetch(text, tmp_path, monkeypatch)
        assert members["K1ABC"]["name"] == "Live Op"

    def test_an_ex_member_also_yields_to_a_current_one(self, tmp_path, monkeypatch):
        text = self._rows("1|K1ABC/EX|Former Op|NV|USA", "2|K1ABC|Live Op|NV|USA")
        members = _run_fetch(text, tmp_path, monkeypatch)
        assert members["K1ABC"]["name"] == "Live Op"

    def test_a_silent_key_is_still_listed_when_nothing_else_claims_it(self, tmp_path, monkeypatch):
        text = self._rows("1|K9OLD/SK|Dead Op|NV|USA")
        members = _run_fetch(text, tmp_path, monkeypatch)
        assert members["K9OLD"]["name"] == "Dead Op"


class TestOutputEncoding:
    """REGRESSION: the cache was written in the locale encoding.

    NamedTemporaryFile("w") with no encoding uses cp1252 on Windows, and the
    roster carries accented operator names -- the dump raised
    UnicodeEncodeError part-way through, leaving a temp file behind and the
    cache unrefreshed.
    """

    def test_an_accented_name_survives(self, tmp_path, monkeypatch):
        text = "SKCCNR|CALL|NAME|SPC|DXENTITY\n1|F5ABC|José Müller|75|FRANCE\n"
        members = _run_fetch(text, tmp_path, monkeypatch)
        assert members["F5ABC"]["name"] == "José Müller"

    def test_the_file_is_utf8(self, tmp_path, monkeypatch):
        text = "SKCCNR|CALL|NAME|SPC|DXENTITY\n1|F5ABC|José|75|FRANCE\n"
        _run_fetch(text, tmp_path, monkeypatch)
        raw = (tmp_path / "web" / "skcc_members.json").read_bytes()
        assert "José".encode("utf-8") in raw
