#!/usr/bin/env python3
"""Fetch KiwiSDR station list from kiwisdr.com and cache locally."""
import json
import os
import sys
import urllib.request

SOURCE = "http://kiwisdr.com/tdoa/files/kiwi.gps.json"
OUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "kiwi_stations.json")


def main():
    try:
        with urllib.request.urlopen(SOURCE, timeout=30) as resp:
            raw = json.loads(resp.read())
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    stations = []
    for s in raw:
        h    = s.get("h", "").strip()
        p    = s.get("p", 8073)
        name = s.get("n", "").strip()
        if not h or not name:
            continue
        stations.append({
            "name":      name,
            "url":       f"http://{h}:{p}",
            "lat":       s.get("lat"),
            "lon":       s.get("lon"),
            "users":     s.get("u", 0),
            "users_max": s.get("um", 4),
        })

    stations.sort(key=lambda x: x["name"].lower())

    with open(OUT, "w") as f:
        json.dump(stations, f, separators=(",", ":"))

    print(f"Saved {len(stations)} stations to {OUT}")


if __name__ == "__main__":
    main()
