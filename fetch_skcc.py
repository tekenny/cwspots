#!/usr/bin/env python3
"""Fetch SKCC member roster and cache locally as callsign-keyed JSON."""
import csv
import io
import json
import os
import sys
import urllib.request

SOURCE = "https://www.skccgroup.com/membership_data/skccdata.txt"
OUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "skcc_members.json")


def base_call(call):
    """Strip /SK (silent key) and /EX (ex-member) suffixes for lookup."""
    return call.split("/")[0].upper().strip()


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
        nr   = row.get("SKCCNR", "").strip()  # e.g. "12345S" (S=Senator, T=Tribune, C=Century)
        members[call] = {
            "nr":     nr,
            "name":   row.get("NAME",     "").strip(),
            "spc":    row.get("SPC",      "").strip(),
            "entity": row.get("DXENTITY", "").strip(),
        }

    with open(OUT, "w") as f:
        json.dump(members, f, separators=(",", ":"))

    print(f"Saved {len(members)} SKCC members to {OUT}")


if __name__ == "__main__":
    main()
