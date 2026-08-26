#!/usr/bin/env python3
"""Fetch KiwiSDR station list from kiwisdr.com and cache locally."""
import json
import math
import os
import sys
import tempfile
import urllib.request

SOURCE = "https://kiwisdr.com/tdoa/files/kiwi.gps.json"
OUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "kiwi_stations.json")
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def valid_station(record):
    if not isinstance(record, dict):
        return False
    host = record.get("h")
    name = record.get("n")
    port = record.get("p", 8073)
    if not isinstance(host, str) or not host.strip() or any(c in host for c in " /?#"):
        return False
    if not isinstance(name, str) or not name.strip():
        return False
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False
    if not 1 <= port <= 65535:
        return False
    for key, low, high in (("lat", -90, 90), ("lon", -180, 180)):
        value = record.get(key)
        if value is not None and (not isinstance(value, (int, float)) or
                                  not math.isfinite(value) or not low <= value <= high):
            return False
    for key in ("u", "um"):
        value = record.get(key, 0 if key == "u" else 4)
        if not isinstance(value, int) or value < 0:
            return False
    return True


def main():
    try:
        with urllib.request.urlopen(SOURCE, timeout=30) as resp:
            payload = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise ValueError("station list is too large")
            raw = json.loads(payload)
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, list):
        print("fetch failed: station list is not an array", file=sys.stderr)
        sys.exit(1)

    stations = []
    for s in raw:
        if not valid_station(s):
            continue
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

    directory = os.path.dirname(OUT)
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as f:
        json.dump(stations, f, separators=(",", ":"))
        temp_path = f.name
    os.replace(temp_path, OUT)

    print(f"Saved {len(stations)} stations to {OUT}")


if __name__ == "__main__":
    main()
