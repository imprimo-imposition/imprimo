"""Job presets: named sets of Settings (“Business cards 85×55 – SRA3 double-sided”).

Built-in presets come with Imprimo; the user's own presets are kept in the app settings
and can be exported to / imported from a .json file (a teacher prepares them, students
import them).
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field

from .core import SHEET_PRESETS, Settings

FILE_FORMAT = "imprimo-presets"
FILE_VERSION = 1
NOT_SAVED = ("page_range",)          # belongs to the file, not to the job type
SRA3 = "SRA3 (320 × 450)"


@dataclass
class Preset:
    name: str
    sheet_key: str = SRA3
    settings: dict = field(default_factory=dict)    # Settings fields (only known ones are used)
    builtin: str = ""                               # i18n key of a built-in preset, "" = user's

    def to_settings(self) -> Settings:
        known = {f.name for f in dataclasses.fields(Settings)}
        return Settings(**{k: v for k, v in self.settings.items() if k in known})

    def to_dict(self) -> dict:
        return {"name": self.name, "sheet_key": self.sheet_key, "settings": self.settings}


def from_settings(name: str, s: Settings, sheet_key: str) -> Preset:
    d = dataclasses.asdict(s)
    for k in NOT_SAVED:
        d.pop(k, None)
    return Preset(name, sheet_key, d)


def _builtin(key, sheet_key=SRA3, **over) -> Preset:
    d = dataclasses.asdict(Settings())
    for k in NOT_SAVED:
        d.pop(k, None)
    if sheet_key in SHEET_PRESETS:                       # the sheet size belongs to its key
        d["sheet_w"], d["sheet_h"] = map(float, SHEET_PRESETS[sheet_key])
    d.update(over)
    return Preset(key, sheet_key, d, builtin=key)


# Defaults every new user gets – sensible starting points for school and print shop work.
BUILTIN = (
    # 3 mm bleed + 6 mm gaps: the safe standard – 21 cards 90×50 or 85×55 on SRA3
    _builtin("preset_cards", mode="repeat", duplex=True, bleed=3.0, gutter_x=6.0, gutter_y=6.0),
    # 2 mm bleed + 4 mm gaps: 24 cards 90×50 on SRA3 (common print-shop practice)
    _builtin("preset_cards2", mode="repeat", duplex=True, bleed=2.0, gutter_x=4.0, gutter_y=4.0),
    # the same, single-sided
    _builtin("preset_cards_1s", mode="repeat", duplex=False, bleed=3.0, gutter_x=6.0, gutter_y=6.0),
    _builtin("preset_cards2_1s", mode="repeat", duplex=False, bleed=2.0, gutter_x=4.0, gutter_y=4.0),
    _builtin("preset_invite", mode="repeat", duplex=True, gutter_x=6.0, gutter_y=6.0,
             crease="half", crease_dir="v"),
    _builtin("preset_dl", mode="repeat", duplex=True, gutter_x=6.0, gutter_y=6.0,
             crease="c3", crease_dir="v"),
    _builtin("preset_booklet", mode="booklet"),
    _builtin("preset_tickets", mode="cutstack", gutter_x=6.0, gutter_y=6.0),
    # a poster in A4 pieces for an office printer (10 mm unprintable margin)
    _builtin("preset_poster", "A4 (210 × 297)", mode="tile", margin=10.0, tile_overlap=10.0),
)


def same(a: Settings, b: Settings) -> bool:
    """True when two settings describe the same job (ignoring what NOT_SAVED lists)."""
    da, db = dataclasses.asdict(a), dataclasses.asdict(b)
    for k in NOT_SAVED:
        da.pop(k, None)
        db.pop(k, None)
    if da.get("crease") not in ("custom",):
        da.pop("crease_pos", None)                  # computed / detected, not chosen
        db.pop("crease_pos", None)
    return da == db


# --------------------------------------------------------------------------
# Storage (a JSON string in the app settings) and .json files

def loads(text: str) -> list[Preset]:
    """User presets from the stored JSON or a .json file (both formats are the same)."""
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return []
    if isinstance(data, dict):
        if data.get("format") != FILE_FORMAT:
            raise ValueError("not an Imprimo presets file")
        data = data.get("presets", [])
    out = []
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and d.get("name") and isinstance(d.get("settings"), dict):
            out.append(Preset(str(d["name"]), str(d.get("sheet_key") or SRA3), d["settings"]))
    return out


def dumps(presets: list[Preset]) -> str:
    return json.dumps([p.to_dict() for p in presets], ensure_ascii=False)


def file_text(presets: list[Preset]) -> str:
    return json.dumps({"format": FILE_FORMAT, "version": FILE_VERSION,
                       "presets": [p.to_dict() for p in presets]},
                      ensure_ascii=False, indent=2)


def unique_name(name: str, taken) -> str:
    taken = set(taken)
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def merge(own: list[Preset], new: list[Preset]) -> tuple[list[Preset], int]:
    """Imported presets added to the user's; an identical one (same name and settings) is
    skipped, a different one with a clashing name gets “(2)”. Returns (list, number added)."""
    out, added = list(own), 0
    for p in new:
        if any(q.name == p.name and q.sheet_key == p.sheet_key and q.settings == p.settings
               for q in out):
            continue
        p.name = unique_name(p.name, [q.name for q in out])
        out.append(p)
        added += 1
    return out, added
