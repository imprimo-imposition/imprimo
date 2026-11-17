"""Imprimo spot color library: technical spot colors for finishing (crease, die-cut, …).

The same names are used by the designer (Illustrator, InDesign, Affinity – imported from the
.ase file), by Imprimo (detection, layers) and by the printer / finishing machines.
The CMYK values are only the alternate color for the screen; each spot color becomes its
own separation.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class Spot:
    name: str               # exact name to use in the design programs
    kind: str               # crease | cut | perf | fold | white | varnish | foil
    cmyk: tuple             # alternate color, 0..100
    aliases: tuple = ()     # other names Imprimo recognizes (any case, spaces / - / _ ignored)
    technical: bool = True  # a line for finishing – must not be printed


SPOTS = (
    Spot("Crease", "crease", (100, 0, 100, 0),
         ("creasing", "creaseline", "score", "scoring", "big", "bigy", "bigovanie", "biga",
          "ryha", "ryhovanie", "rilovanie")),
    Spot("CutContour", "cut", (0, 100, 0, 0),
         ("cut", "cutline", "cutting", "dieline", "diecut", "die", "thrucut", "kisscut",
          "vysek", "kontura", "konturovyrez")),
    Spot("Perforation", "perf", (100, 0, 0, 0),
         ("perf", "perfcutcontour", "perfcut", "perforacia", "perforovanie")),
    Spot("Fold", "fold", (100, 100, 0, 0),
         ("folding", "foldline", "sklad", "skladanie", "falc", "falz")),
    Spot("White", "white", (0, 0, 0, 25),
         ("whiteink", "biela", "bielapodtlac", "podtlac"), technical=False),
    Spot("Varnish", "varnish", (0, 0, 100, 0),
         ("spotvarnish", "uv", "uvlak", "lak", "parcialnylak", "selektivnylak"), technical=False),
    Spot("Foil", "foil", (0, 30, 80, 20),
         ("hotfoil", "foiling", "folia", "razba", "zlato", "striebro"), technical=False),
)

BY_KIND = {s.kind: s for s in SPOTS}


def _norm(name: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFKD", str(name))
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    return re.sub(r"[\s_\-./#]+", "", n)


_LOOKUP = {}
for _s in SPOTS:
    for _n in (_s.name,) + _s.aliases:
        _LOOKUP.setdefault(_norm(_n), _s)


def spot_for(name: str) -> Spot | None:
    """The library spot a color name stands for (case, accents, spaces ignored), or None."""
    if not name:
        return None
    return _LOOKUP.get(_norm(name.lstrip("/")))


def kind_of(name: str) -> str | None:
    sp = spot_for(name)
    return sp.kind if sp else None


def is_crease(name: str) -> bool:
    return kind_of(name) == "crease"


# --------------------------------------------------------------------------
# Adobe Swatch Exchange (.ase) – imported by Illustrator, InDesign, Photoshop,
# Affinity, CorelDRAW and Scribus

ASE_SPOT = 1


def _ase_name(name: str) -> bytes:
    s = name + "\0"
    return struct.pack(">H", len(s)) + s.encode("utf-16-be")


def ase_bytes(spots=SPOTS, group: str | None = None) -> bytes:
    blocks = []
    if group:
        blocks.append(struct.pack(">H", 0xC001) + _block(_ase_name(group)))
    for sp in spots:
        body = (_ase_name(sp.name) + b"CMYK"
                + struct.pack(">4f", *(v / 100.0 for v in sp.cmyk))
                + struct.pack(">H", ASE_SPOT))
        blocks.append(struct.pack(">H", 0x0001) + _block(body))
    if group:
        blocks.append(struct.pack(">H", 0xC002) + _block(b""))
    return b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks)) + b"".join(blocks)


def _block(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def write_ase(path: str, spots=SPOTS):
    with open(path, "wb") as f:
        f.write(ase_bytes(spots))


def read_ase(data: bytes) -> list[tuple]:
    """[(name, model, values, type)] – used by the tests to check the writer."""
    assert data[:4] == b"ASEF"
    n = struct.unpack(">I", data[8:12])[0]
    pos, out = 12, []
    for _ in range(n):
        btype, length = struct.unpack(">HI", data[pos:pos + 6])
        body = data[pos + 6:pos + 6 + length]
        pos += 6 + length
        if btype != 0x0001:
            continue
        nl = struct.unpack(">H", body[:2])[0]
        name = body[2:2 + nl * 2].decode("utf-16-be").rstrip("\0")
        p = 2 + nl * 2
        model = body[p:p + 4].decode("ascii").strip()
        cnt = {"CMYK": 4, "RGB": 3, "LAB": 3, "Gray": 1}[model]
        vals = struct.unpack(f">{cnt}f", body[p + 4:p + 4 + 4 * cnt])
        ctype = struct.unpack(">H", body[p + 4 + 4 * cnt:p + 6 + 4 * cnt])[0]
        out.append((name, model, vals, ctype))
    return out
