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


# Segments that say something about the operation rather than where it is:
# portable, maritime/aeronautical mobile, low power, lighthouse, and the bare
# digit that changes call area within one country (W1AW/4 is still the USA).
_NON_ENTITY_SUFFIXES = frozenset({
    "P", "M", "MM", "AM", "A", "B", "QRP", "QRPP", "LH", "J", "R",
})


def _is_non_entity_segment(segment: str) -> bool:
    return segment in _NON_ENTITY_SUFFIXES or segment.isdigit()


class DXCCLookup:
    def __init__(self, cty_file: str = "cty.dat"):
        self.prefixes: dict[str, DXCCEntity] = {}
        # Exact callsign overrides, kept apart from the prefix table.
        #
        # BigCTY marks these with a leading '=' and they mean "this exact call,
        # not anything starting with it". The marker used to be stripped and the
        # call filed as a prefix among the other 6,600, so all 525 of them
        # became prefixes: =4U1UN turned into a five-character prefix that also
        # claimed 4U1UNX, and any exact override could shadow a real prefix.
        self.exact: dict[str, DXCCEntity] = {}
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
                is_exact = prefix.startswith("=")
                prefix = re.sub(r"\(.*?\)|\[.*?\]|<.*?>|\{.*?\}|~.*?~", "", prefix)
                prefix = prefix.lstrip("=").strip()
                if not prefix:
                    continue
                if is_exact:
                    self.exact[prefix.upper()] = entity
                else:
                    self.prefixes[prefix.upper()] = entity

    def _by_prefix(self, segment: str) -> Optional[DXCCEntity]:
        """Longest-prefix match for one callsign segment."""
        for length in range(min(len(segment), 6), 0, -1):
            entity = self.prefixes.get(segment[:length])
            if entity is not None:
                return entity
        return None

    def lookup(self, callsign: str) -> Optional[DXCCEntity]:
        """The DXCC entity a callsign belongs to, or None.

        An exact override wins outright; otherwise the entity comes from the
        callsign's *location* segment.

        For a slashed call that used to be ``max(parts, key=len)`` -- the
        longest segment -- which is right for a suffix (K1ABC/QRP -> K1ABC) and
        backwards for a prefix. VE3/K1ABC was reported as the United States
        when the VE3 is the whole point: the operator is in Canada. The
        location indicator is the *shorter* segment, because it is a prefix
        rather than a full callsign, so that is what decides now. Ties go to
        the first, which is where a prefix is conventionally written and gives
        VP2M/AA7V -> Montserrat.
        """
        if not callsign:
            return None
        cs = callsign.upper().strip()

        exact = self.exact.get(cs)
        if exact is not None:
            return exact

        if "/" not in cs:
            return self._by_prefix(cs)

        segments = [s for s in cs.split("/") if s]
        if not segments:
            return None

        # Drop the segments that describe the operation rather than the place.
        located = [s for s in segments if not _is_non_entity_segment(s)]
        if not located:
            located = segments

        # Shortest first, ties in written order: a location indicator is a
        # prefix, and a prefix is shorter than the callsign it qualifies.
        for segment in sorted(located, key=len):
            entity = self._by_prefix(segment)
            if entity is not None:
                return entity
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
