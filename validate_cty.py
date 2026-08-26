#!/usr/bin/env python3
"""Validate a downloaded BigCTY file before replacing the live database."""
import sys

from dxcc import DXCCLookup

MIN_PREFIXES = 100


def main(path: str) -> None:
    lookup = DXCCLookup(path)
    if len(lookup.prefixes) < MIN_PREFIXES:
        raise ValueError(f"only {len(lookup.prefixes)} DXCC prefixes found")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_cty.py PATH")
    try:
        main(sys.argv[1])
    except (OSError, ValueError) as error:
        print(f"invalid cty.dat: {error}", file=sys.stderr)
        raise SystemExit(1)
