#!/usr/bin/env python3
"""Fetch SKCC member roster and cache locally as callsign-keyed JSON."""
import csv
import io
import json
import os
import sys
import tempfile
import urllib.request

SOURCE = "https://www.skccgroup.com/membership_data/skccdata.txt"
OUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "skcc_members.json")


def base_call(call):
    """Strip /SK (silent key) and /EX (ex-member) suffixes for lookup."""
    return call.split("/")[0].upper().strip()


def _is_current(call_raw):
    """True when a roster row is a current member rather than /SK or /EX.

    Both forms reduce to the same base call, and the roster is written into a
    plain dict, so whichever row came later in the file won a callsign that had
    been reissued -- sometimes the silent key, overwriting the live member.
    """
    suffix = call_raw.upper().rpartition("/")[2]
    return suffix not in {"SK", "EX"}


def main():
    try:
        req = urllib.request.Request(SOURCE, headers={"User-Agent": "cwspots/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    members = {}
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        call_raw = row.get("CALL", "").strip()
        if not call_raw:
            continue
        call = base_call(call_raw)
        # A current member always wins the callsign; a /SK or /EX row only
        # fills one nothing else has claimed.
        if not _is_current(call_raw) and call in members:
            continue
        nr   = row.get("SKCCNR", "").strip()  # e.g. "12345S" (S=Senator, T=Tribune, C=Century)
        entry = {
            "nr":     nr,
            "name":   row.get("NAME",     "").strip(),
            "spc":    row.get("SPC",      "").strip(),
            "entity": row.get("DXENTITY", "").strip(),
        }
        if _is_current(call_raw) or call not in members:
            members[call] = entry

    directory = os.path.dirname(OUT)
    # encoding is explicit: without it this uses the locale encoding, which on
    # Windows is cp1252 -- and the roster carries accented operator names, so
    # the dump raised UnicodeEncodeError part-way through and left a temp file
    # behind with the cache unrefreshed. ensure_ascii=False keeps the file small
    # and readable now that it is genuinely UTF-8.
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                     encoding="utf-8") as f:
        json.dump(members, f, separators=(",", ":"), ensure_ascii=False)
        temp_path = f.name
    os.replace(temp_path, OUT)

    print(f"Saved {len(members)} SKCC members to {OUT}")


if __name__ == "__main__":
    main()
