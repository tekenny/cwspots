#!/usr/bin/env python3
"""Download, validate, and atomically install the BigCTY database."""
import os
import tempfile
import urllib.request

from validate_cty import main as validate

SOURCE = "https://www.country-files.com/cty/cty.dat"
TARGET = "/opt/cwspots/cty.dat"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def refresh(target: str = TARGET) -> None:
    directory = os.path.dirname(target) or "."
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("cty.dat download is too large")

    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary.write(data)
        temporary_path = temporary.name
    try:
        validate(temporary_path)
        os.replace(temporary_path, target)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


if __name__ == "__main__":
    refresh()
