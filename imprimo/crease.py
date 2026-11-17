"""Creasing (bigovanie): where the crease lines of one product are, and finding them in a PDF.

Positions are measured on the finished product (the trim, upright as designed):
vertical creases from the left edge, horizontal creases from the top edge, in mm.
The imposition then carries them to every copy on the sheet (rotated, on the back…).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pikepdf

from .spots import is_crease

MM = 72.0 / 25.4
PRESETS = ("off", "half", "z3", "c3", "custom", "pdf")
C_FOLD_INSET = 3.0       # mm – the inner panel of a roll (C) fold is this much narrower
EDGE_MIN = 1.0           # mm – a crease closer to the trim edge is ignored


def parse_positions(text: str) -> list[float]:
    """"99; 198" or "99,5 198" → [99.0, 198.0] / [99.5, 198.0] (mm). Semicolons or spaces
    separate values; a comma inside a number is a decimal comma."""
    out = []
    for tok in re.split(r"[;\s]+", text or ""):
        tok = tok.strip().rstrip(",").replace(",", ".")
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            raise ValueError(tok)
    return out


def format_positions(vals) -> str:
    return "; ".join(f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",") for v in vals)


def preset_positions(preset: str, length_mm: float) -> list[float]:
    """Crease positions in mm for a preset along a product side of `length_mm`."""
    L = length_mm
    if preset == "half":
        return [L / 2]
    if preset == "z3":
        return [L / 3, 2 * L / 3]
    if preset == "c3":                       # panels a, a, a − inset (the inner one narrower)
        a = (L + C_FOLD_INSET) / 3
        return [a, 2 * a]
    return []


@dataclass
class CreaseSpec:
    vertical: bool                   # True = vertical lines, positions from the left edge
    positions: list                  # mm, valid ones
    rejected: list = field(default_factory=list)   # mm outside the product


def crease_spec(s, W_pt: float, H_pt: float) -> CreaseSpec | None:
    """The creases of one product of W × H pt (upright) for the settings `s`, or None."""
    preset = getattr(s, "crease", "off")
    if preset in ("", "off", None):
        return None
    vertical = getattr(s, "crease_dir", "v") != "h"
    length = (W_pt if vertical else H_pt) / MM
    if preset in ("custom", "pdf"):
        try:
            vals = parse_positions(getattr(s, "crease_pos", ""))
        except ValueError:
            vals = []
    else:
        vals = preset_positions(preset, length)
    ok = [v for v in vals if EDGE_MIN <= v <= length - EDGE_MIN]
    bad = [v for v in vals if v not in ok]
    if not ok and not bad:
        return None
    return CreaseSpec(vertical, ok, bad)


def card_segments(spec: CreaseSpec, W: float, H: float) -> list:
    """Crease lines on the upright product (card coordinates, pt, y up)."""
    segs = []
    for v in spec.positions:
        p = v * MM
        if spec.vertical:
            segs.append(((p, 0.0), (p, H)))
        else:
            segs.append(((0.0, H - p), (W, H - p)))
    return segs


# --------------------------------------------------------------------------
# Finding crease lines in a PDF page (spot color “Crease” and its aliases)

@dataclass
class Detected:
    vertical: list = field(default_factory=list)     # mm from the left edge
    horizontal: list = field(default_factory=list)   # mm from the top edge
    other: int = 0                                  # slanted lines / curves in the crease color
    spot: str = ""                                  # the color name found

    @property
    def found(self):
        return bool(self.vertical or self.horizontal)

    @property
    def main_vertical(self):
        """Direction with more lines (vertical when equal)."""
        return len(self.vertical) >= len(self.horizontal)


def _mul(m1, m2):
    a, b, c, d, e, f = m1
    A, B, C, D, E, F = m2
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            e * A + f * C + E, e * B + f * D + F)


def _pt(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _cs_spot(cs, res, depth=0):
    """The crease color name if the color space `cs` is (or contains) a crease spot."""
    if depth > 4 or cs is None:
        return None
    try:
        if isinstance(cs, pikepdf.Name):
            nm = str(cs)
            if nm in ("/DeviceGray", "/DeviceRGB", "/DeviceCMYK", "/Pattern"):
                return None
            spaces = res.get("/ColorSpace") if res is not None else None
            if spaces is not None and nm in spaces:
                return _cs_spot(spaces[nm], res, depth + 1)
            return None
        if isinstance(cs, pikepdf.Array) and len(cs):
            fam = str(cs[0])
            if fam == "/Separation" and len(cs) > 1:
                nm = str(cs[1]).lstrip("/")
                return nm if is_crease(nm) else None
            if fam == "/DeviceN" and len(cs) > 1:
                for n in cs[1]:
                    nm = str(n).lstrip("/")
                    if is_crease(nm):
                        return nm
    except Exception:
        return None
    return None


def _walk(stream, res, ctm, segs, state, depth=0, seen=()):
    if depth > 10:
        return
    try:
        ops = pikepdf.parse_content_stream(stream)
    except Exception:
        return
    stack = []
    spot = state.get("spot")
    path, cur, start, curved = [], None, None, False
    xobjs = (res.get("/XObject") if res is not None else None) or {}
    for operands, op in ops:
        o = str(op)
        try:
            if o == "q":
                stack.append((ctm, spot))
            elif o == "Q":
                if stack:
                    ctm, spot = stack.pop()
            elif o == "cm" and len(operands) == 6:
                ctm = _mul(tuple(float(v) for v in operands), ctm)
            elif o == "CS" and operands:
                spot = _cs_spot(operands[0], res)
            elif o in ("RG", "G", "K"):
                spot = None
            elif o == "m" and len(operands) == 2:
                cur = start = (float(operands[0]), float(operands[1]))
            elif o == "l" and len(operands) == 2 and cur is not None:
                p = (float(operands[0]), float(operands[1]))
                path.append((_pt(ctm, *cur), _pt(ctm, *p)))
                cur = p
            elif o in ("c", "v", "y") and operands:
                curved = True
                cur = (float(operands[-2]), float(operands[-1]))
            elif o == "re" and len(operands) == 4:
                x, y, w, h = (float(v) for v in operands)
                pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
                path += [(_pt(ctm, *pts[k]), _pt(ctm, *pts[k + 1])) for k in range(4)]
                cur = start = (x, y)
            elif o == "h" and cur is not None and start is not None:
                if cur != start:
                    path.append((_pt(ctm, *cur), _pt(ctm, *start)))
                cur = start
            elif o in ("S", "s", "B", "B*", "b", "b*", "f", "F", "f*", "n"):
                if o in ("s", "b", "b*") and cur is not None and start is not None and cur != start:
                    path.append((_pt(ctm, *cur), _pt(ctm, *start)))
                if o in ("S", "s", "B", "B*", "b", "b*") and spot:
                    segs.extend(path)
                    state["found_spot"] = spot
                    if curved:
                        state["other"] = state.get("other", 0) + 1
                path, cur, start, curved = [], None, None, False
            elif o == "Do" and operands:
                x = xobjs.get(operands[0]) if hasattr(xobjs, "get") else None
                if x is None or str(x.get("/Subtype")) != "/Form":
                    continue
                key = x.objgen
                if key in seen:
                    continue
                m = x.get("/Matrix")
                sub = _mul(tuple(float(v) for v in m), ctm) if m is not None else ctm
                state["spot"] = spot
                _walk(x, x.get("/Resources") or res, sub, segs, state, depth + 1, seen + (key,))
        except Exception:
            continue


def detect(pdf: pikepdf.Pdf, info, tol_mm: float = 0.3) -> Detected:
    """Crease lines on the page described by `info` (core.PageInfo), measured on the
    upright product. Straight lines only; their position is rounded to 0.1 mm."""
    page = pdf.pages[info.pdf_page]
    segs, state = [], {}
    _walk(page.obj, page.obj.get("/Resources"), (1, 0, 0, 1, 0, 0), segs, state)
    out = Detected(other=state.get("other", 0), spot=state.get("found_spot", ""))
    W, H = info.vis_w, info.vis_h
    tol = tol_mm * MM
    v, h = [], []
    for p0, p1 in segs:
        (x0, y0), (x1, y1) = _pt(info.R, *p0), _pt(info.R, *p1)
        if abs(x1 - x0) <= tol and abs(y1 - y0) > 2 * MM:
            x = (x0 + x1) / 2
            if EDGE_MIN * MM <= x <= W - EDGE_MIN * MM:
                v.append(x / MM)
        elif abs(y1 - y0) <= tol and abs(x1 - x0) > 2 * MM:
            y = (y0 + y1) / 2
            if EDGE_MIN * MM <= y <= H - EDGE_MIN * MM:
                h.append((H - y) / MM)
        elif max(abs(x1 - x0), abs(y1 - y0)) > 2 * MM:
            out.other += 1                      # slanted line – not usable as a crease
    out.vertical = _cluster(v, tol_mm)
    out.horizontal = _cluster(h, tol_mm)
    return out


def detect_any(pdf: pikepdf.Pdf, infos, max_pages: int = 8) -> Detected:
    """First page (of the first few) with crease lines."""
    best = Detected()
    for info in infos[:max_pages]:
        d = detect(pdf, info)
        if d.found:
            return d
        best.other += d.other
    return best


def _cluster(vals, tol):
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [round(sum(g) / len(g), 1) for g in out]
