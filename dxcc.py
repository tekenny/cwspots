import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DXCCEntity:
    name: str
    continent: str
    cq_zone: int
    itu_zone: int
    lat: float = 0.0
    lon: float = 0.0  # standard convention: + = East, - = West


class DXCCLookup:
    def __init__(self, cty_file: str = "cty.dat"):
        self.prefixes: dict[str, DXCCEntity] = {}
        self._load(cty_file)

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        records = content.split(";")
        for record in records:
            record = record.strip()
            if not record:
                continue
            lines = record.split("\n")
            header_parts = [p.strip() for p in lines[0].split(":")]
            if len(header_parts) < 8:
                continue
            try:
                entity = DXCCEntity(
                    name=header_parts[0],
                    cq_zone=int(header_parts[1]),
                    itu_zone=int(header_parts[2]),
                    continent=header_parts[3].upper(),
                    lat=float(header_parts[4]),
                    lon=-float(header_parts[5]),  # cty.dat: + = West; negate for standard
                )
            except (ValueError, IndexError):
                continue
            prefix_text = " ".join(lines[1:]).replace("\n", " ")
            for raw_prefix in prefix_text.split(","):
                prefix = raw_prefix.strip()
                if not prefix:
                    continue
                prefix = re.sub(r"\(.*?\)|\[.*?\]|<.*?>|\{.*?\}|~.*?~", "", prefix)
                prefix = prefix.lstrip("=").strip()
                if prefix:
                    self.prefixes[prefix.upper()] = entity

    def lookup(self, callsign: str) -> Optional[DXCCEntity]:
        if not callsign:
            return None
        cs = callsign.upper().strip()
        if "/" in cs:
            parts = cs.split("/")
            cs = max(parts, key=len)
        for length in range(min(len(cs), 6), 0, -1):
            candidate = cs[:length]
            if candidate in self.prefixes:
                return self.prefixes[candidate]
        return None

    def continent(self, callsign: str) -> Optional[str]:
        entity = self.lookup(callsign)
        return entity.continent if entity else None


if __name__ == "__main__":
    dx = DXCCLookup("cty.dat")
    for call in ["K1ABC", "G3XYZ", "JA1ZZZ", "VK2DEF", "PY1AB", "ZS6XYZ"]:
        entity = dx.lookup(call)
        if entity:
            print(f"{call:12} -> {entity.continent}  {entity.name}")
        else:
            print(f"{call:12} -> NOT FOUND")
