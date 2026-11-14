"""Imposition core: sheet geometry and writing the output PDF.

Source pages are placed as vector Form XObjects, so nothing is lost – fonts,
CMYK, spot colours and gradients stay exactly as they were. All internal
calculations are in points (pt), settings are in mm.

Coordinate systems:
  raw    – original page coordinates in the PDF (without /Rotate)
  visual – the page as the reader sees it, lower-left corner of the TrimBox at (0, 0)
  card   – a cell on the sheet before rotation, W × H (size of the first page)
  sheet  – the press sheet
"""
from __future__ import annotations

import datetime
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import reduce

import pikepdf
from pikepdf import Array, Dictionary, Name

from . import APP_NAME, __version__
from .crease import card_segments, crease_spec
from .fonts import encode as font_encode, make_font
from .i18n import t
from .pdfinfo import BUNDLED_ICC, STANDARDS, SourceProfile, icc_from_file, icc_info

MM = 72.0 / 25.4
EPS = 0.01


def mm(v: float) -> float:
    return v * MM


def to_mm(pt: float) -> float:
    return pt / MM


# Sheets in portrait orientation (width × height in mm)
SHEET_PRESETS = {
    "SRA3 (320 × 450)": (320, 450),
    "A3+ (330 × 487)": (330, 487),
    "A3 (297 × 420)": (297, 420),
    "SRA4 (225 × 320)": (225, 320),
    "A4 (210 × 297)": (210, 297),
    "B3 (353 × 500)": (353, 500),
    "SRA2 (450 × 640)": (450, 640),
    "B2 (500 × 707)": (500, 707),
}

MODES = ("repeat", "sequential", "cutstack", "booklet")


class ImposeError(Exception):
    """An error to be shown to the user."""


@dataclass
class Settings:
    mode: str = "repeat"
    fit_sheet: bool = False          # sheet sized to the content
    sheet_w: float = 320.0           # mm
    sheet_h: float = 450.0
    orientation: str = "auto"        # auto | portrait | landscape
    margin: float = 10.0             # min. distance from the sheet edge to the trim
    cols: int = 0                    # 0 = automatic
    rows: int = 0
    gutter_x: float = 0.0
    gutter_y: float = 0.0
    rotation: str = "auto"           # auto | 0 | 90
    bleed: float = 3.0
    bleed_fill: str = "off"          # missing bleed: off | mirror (mirrored edges) | stretch (edge stretched)
    assume_bleed: float = 0.0        # PDF without TrimBox: trim this much from the edges
    duplex: bool = False
    duplex_flip: str = "long"        # long | short (printer duplex setting)
    back_orientation: str = "book"   # book | calendar
    crop_marks: bool = True
    mark_offset: float = 3.0
    mark_length: float = 5.0
    mark_weight: float = 0.25        # pt
    reg_marks: bool = False
    slug: bool = True
    creep: float = 0.0               # total shift of the innermost sheet
    blanks: str = "end"              # end | before_back
    page_range: str = ""
    split_spreads: bool = True       # PDF exported as spreads: split them into pages
    export_print: bool = True
    export_layers: bool = True
    export_combined: bool = False
    pdf_standard: str = "keep"       # keep | none | x1a2001 | x1a2003 | x32002 | x32003 | x4
    icc_profile: str = "keep"        # keep | bundled | cesta k .icc
    crease: str = "off"              # off | half | z3 | c3 | custom | pdf (see crease.py)
    crease_dir: str = "v"            # v = vertical lines (from the left) | h = horizontal (from the top)
    crease_pos: str = ""             # custom / pdf: positions in mm on the product, "99; 198"
    crease_marks: bool = True        # crease marks at the sheet edge (manual creaser with a stop)


# --------------------------------------------------------------------------
# Affine matrices in PDF order (a b c d e f); compose(m1, m2) = m1 first, then m2

def compose(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


def chain(*ms):
    return reduce(compose, ms, (1, 0, 0, 1, 0, 0))


def translate(tx, ty):
    return (1, 0, 0, 1, tx, ty)


def apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def map_rect(m, r):
    pts = [apply(m, x, y) for x in (r[0], r[2]) for y in (r[1], r[3])]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def raw_to_visual(trim, rot):
    """Page with /Rotate (clockwise) → upright, trim at (0,0)."""
    x0, y0, x1, y1 = trim
    w, h = x1 - x0, y1 - y0
    r = {0: (1, 0, 0, 1, 0, 0),
         90: (0, -1, 1, 0, 0, w),
         180: (-1, 0, 0, -1, w, h),
         270: (0, 1, -1, 0, h, 0)}[rot]
    return compose(translate(-x0, -y0), r)


def card_rotation(rot, W, H):
    """Counter-clockwise rotation of a W × H cell; the result has its lower-left corner at (0,0)."""
    return {0: (1, 0, 0, 1, 0, 0),
            90: (0, 1, -1, 0, H, 0),
            180: (-1, 0, 0, -1, W, H),
            270: (0, -1, 1, 0, 0, W)}[rot]


# --------------------------------------------------------------------------
# Source PDF analysis

def _rect(arr):
    x0, y0, x1, y1 = (float(v) for v in arr)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _intersect(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def _inherited(obj, key):
    seen = 0
    while obj is not None and seen < 64:
        if key in obj:
            return obj[key]
        obj = obj.get("/Parent")
        seen += 1
    return None


@dataclass
class PageInfo:
    index: int
    trim: tuple          # raw coordinates
    limit: tuple         # raw: BleedBox ∩ MediaBox – nothing is drawn beyond it
    media: tuple
    rotate: int
    has_trim: bool
    vis_w: float         # trim size in upright position (pt)
    vis_h: float
    bleed_avail: float   # smallest available bleed of the four sides (pt)
    R: tuple = field(repr=False, default=(1, 0, 0, 1, 0, 0))
    pdf_page: int = -1   # page index in the PDF (one PDF page = two pages for a split spread)
    half: str = ""       # "" | "left" | "right" for halves of a split spread

    def __post_init__(self):
        if self.pdf_page < 0:
            self.pdf_page = self.index


SPREAD_TOL = 3.0     # pt


def spread_pages(infos: list[PageInfo]) -> list[int]:
    """Indexes of pages that are spreads (two pages side by side) in a PDF that also
    contains single pages – typical for an export "as spreads" from InDesign or Affinity
    (cover alone, then spreads, back cover alone)."""
    upright = [p for p in infos if p.rotate == 0]
    if len(upright) < 2:
        return []
    single_w = min(p.vis_w for p in upright)
    h = next(p.vis_h for p in upright if abs(p.vis_w - single_w) <= SPREAD_TOL)
    out = [p.index for p in upright
           if abs(p.vis_w - 2 * single_w) <= SPREAD_TOL and abs(p.vis_h - h) <= SPREAD_TOL]
    has_single = any(abs(p.vis_w - single_w) <= SPREAD_TOL for p in upright)
    return out if out and has_single else []


def _split(p: PageInfo) -> list[PageInfo]:
    x0, y0, x1, y1 = p.trim
    mid = (x0 + x1) / 2
    lx0, ly0, lx1, ly1 = p.limit
    out = []
    for half, trim, limit in (("left", (x0, y0, mid, y1), (lx0, ly0, mid, ly1)),
                              ("right", (mid, y0, x1, y1), (mid, ly0, lx1, ly1))):
        # bleed only on the three outer sides – the spine side continues on the other half
        sides = [trim[1] - limit[1], limit[3] - trim[3]]
        sides.append(trim[0] - limit[0] if half == "left" else limit[2] - trim[2])
        out.append(PageInfo(0, trim, limit, p.media, 0, p.has_trim, mid - x0, y1 - y0,
                            max(0.0, min(sides)), raw_to_visual(trim, 0),
                            pdf_page=p.pdf_page, half=half))
    return out


def analyze(pdf: pikepdf.Pdf, assume_bleed_mm: float = 0.0,
            split_spreads: bool = True) -> list[PageInfo]:
    """Page geometry. With split_spreads, spread pages become two logical pages."""
    infos = _analyze_pages(pdf, assume_bleed_mm)
    if not split_spreads:
        return infos
    spreads = set(spread_pages(infos))
    if not spreads:
        return infos
    out = []
    for p in infos:
        out.extend(_split(p) if p.index in spreads else [p])
    for i, p in enumerate(out):
        p.index = i
    return out


def _analyze_pages(pdf: pikepdf.Pdf, assume_bleed_mm: float = 0.0) -> list[PageInfo]:
    infos = []
    for i, pg in enumerate(pdf.pages):
        media = _rect(pg.mediabox)
        crop = _intersect(_rect(pg.cropbox), media)
        has_trim = "/TrimBox" in pg.obj
        if has_trim:
            trim = _intersect(_rect(pg.obj.TrimBox), media)
        else:
            inset = mm(assume_bleed_mm)
            trim = (crop[0] + inset, crop[1] + inset, crop[2] - inset, crop[3] - inset)
            if trim[2] - trim[0] < 1 or trim[3] - trim[1] < 1:
                raise ImposeError(t("err_inset", page=i + 1, mm=f"{assume_bleed_mm:g}"))
        if "/BleedBox" in pg.obj:
            limit = _intersect(_rect(pg.obj.BleedBox), media)
        else:
            limit = crop
        limit = (min(limit[0], trim[0]), min(limit[1], trim[1]),
                 max(limit[2], trim[2]), max(limit[3], trim[3]))
        rot_obj = _inherited(pg.obj, "/Rotate")
        rot = int(rot_obj) % 360 if rot_obj is not None else 0
        if rot not in (0, 90, 180, 270):
            rot = 0
        w, h = trim[2] - trim[0], trim[3] - trim[1]
        vis_w, vis_h = (h, w) if rot in (90, 270) else (w, h)
        avail = max(0.0, min(trim[0] - limit[0], trim[1] - limit[1],
                             limit[2] - trim[2], limit[3] - trim[3]))
        infos.append(PageInfo(i, trim, limit, media, rot, has_trim, vis_w, vis_h,
                              avail, raw_to_visual(trim, rot)))
    return infos


def parse_range(text: str, n: int) -> list[int]:
    """'1-4, 7, 10-' → zero-based indexes. Empty string = all pages."""
    text = (text or "").strip()
    if not text:
        return list(range(n))
    out = []
    for part in re.split(r"[,;\s]+", text):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else n
            step = 1 if b >= a else -1
            seq = range(a, b + step, step)
        elif part.isdigit():
            seq = [int(part)]
        else:
            raise ImposeError(t("err_range", part=part))
        for p in seq:
            if not 1 <= p <= n:
                raise ImposeError(t("err_page_missing", p=p, n=n))
            out.append(p - 1)
    return out


# --------------------------------------------------------------------------
# Imposition plan

@dataclass
class Cell:
    x: float            # lower-left corner of the trim on the sheet (after rotation)
    y: float
    rot: int
    W: float            # cell size before rotation (page trim)
    H: float
    dx: float = 0.0     # content shift (creep)

    @property
    def size(self):
        return (self.H, self.W) if self.rot in (90, 270) else (self.W, self.H)

    @property
    def rect(self):
        cw, ch = self.size
        return (self.x, self.y, self.x + cw, self.y + ch)

    @property
    def matrix(self):
        return compose(card_rotation(self.rot, self.W, self.H),
                       translate(self.x + self.dx, self.y))


@dataclass
class Item:
    page: int | None    # source page index or None (blank)
    matrix: tuple       # card → sheet
    clip: tuple         # clipping path on the sheet (trim + allowed bleed)
    trim: tuple         # trim on the sheet
    W: float
    H: float


@dataclass
class Side:
    sheet_no: int
    is_back: bool
    items: list
    block: tuple
    cuts_x: list
    cuts_y: list
    folds_x: list
    folds_y: list
    crease_segs: list = field(default_factory=list)   # crease lines on this side (sheet coords)

    @property
    def creases_x(self):
        return _uniq([a[0] for a, b in self.crease_segs if abs(a[0] - b[0]) < EPS])

    @property
    def creases_y(self):
        return _uniq([a[1] for a, b in self.crease_segs if abs(a[1] - b[1]) < EPS])


@dataclass
class Plan:
    sheet_w: float
    sheet_h: float
    sides: list
    n_sheets: int
    per_sheet: int
    page_w: float
    page_h: float
    cols: int = 0
    rows: int = 0
    rot: int = 0
    blanks: int = 0
    warnings: list = field(default_factory=list)
    cap: tuple | None = None        # what fits (columns, rows); None = sheet sized to content
    gutter: tuple = (0.0, 0.0)
    margin: float = 0.0

    @property
    def utilization(self):
        return self.per_sheet * self.page_w * self.page_h / (self.sheet_w * self.sheet_h)

    def summary(self, s: Settings) -> str:
        if s.mode == "booklet":
            core = t("sum_booklet", n=self.n_sheets * 4)
        else:
            core = f"{self.cols}x{self.rows}={self.per_sheet}"
            if self.rot:
                core += f" rot {self.rot}"
        return (f"{core} | {to_mm(self.page_w):.0f}x{to_mm(self.page_h):.0f} mm"
                f" | {t('sum_sheet')} {to_mm(self.sheet_w):.0f}x{to_mm(self.sheet_h):.0f} mm")


def _side_bleeds(rect, rects, bleed):
    """Bleed on each side of a cell; if a neighbour is closer than 2× bleed,
    the gap is split in half so neighbouring bleeds don't overlap."""
    x0, y0, x1, y1 = rect
    L = B = R = T = bleed
    for o in rects:
        if o is rect:
            continue
        ox0, oy0, ox1, oy1 = o
        if min(y1, oy1) - max(y0, oy0) > EPS:
            g = ox0 - x1
            if -EPS <= g < 2 * bleed:
                R = min(R, max(g, 0) / 2)
            g = x0 - ox1
            if -EPS <= g < 2 * bleed:
                L = min(L, max(g, 0) / 2)
        if min(x1, ox1) - max(x0, ox0) > EPS:
            g = oy0 - y1
            if -EPS <= g < 2 * bleed:
                T = min(T, max(g, 0) / 2)
            g = y0 - oy1
            if -EPS <= g < 2 * bleed:
                B = min(B, max(g, 0) / 2)
    return L, B, R, T


# --------------------------------------------------------------------------
# Generated bleed: mirrored or stretched copies of the page around its trim.
# The page itself is not changed – extra clipped copies are drawn under it.

STRETCH_BAND = 0.5       # mm of the page edge stretched over the missing bleed


def bleed_patches(info: PageInfo, bleed: float, method: str):
    """[(M, strip)] for the sides where the page has less bleed than `bleed` (pt).
    Both in upright page coordinates (trim = 0..vis_w × 0..vis_h, y up): M maps the
    page onto itself (mirror / stretch), strip is the area the copy fills."""
    if method not in ("mirror", "stretch") or bleed <= EPS:
        return []
    w, h, b = info.vis_w, info.vis_h, bleed
    lx0, ly0, lx1, ly1 = map_rect(info.R, info.limit)
    short = {"l": -lx0 < b - EPS, "r": lx1 - w < b - EPS,
             "b": -ly0 < b - EPS, "t": ly1 - h < b - EPS}
    if not any(short.values()):
        return []
    if method == "mirror":
        fx = {"l": (-1, 0), "r": (-1, 2 * w), "": (1, 0)}       # x' = a·x + e
        fy = {"b": (-1, 0), "t": (-1, 2 * h), "": (1, 0)}
    else:
        e = min(mm(STRETCH_BAND), w / 4, h / 4)
        k = b / e
        fx = {"l": (k, -b), "r": (k, w - (w - e) * k), "": (1, 0)}
        fy = {"b": (k, -b), "t": (k, h - (h - e) * k), "": (1, 0)}
    o = 0.5          # pt – strips reach slightly under the page, so no hairline gap shows
    xs = {"l": (-b, o), "r": (w - o, w + b), "": (0, w)}
    ys = {"b": (-b, o), "t": (h - o, h + b), "": (0, h)}
    out = []
    for sx in ("l", "", "r"):
        for sy in ("b", "", "t"):
            if not (sx or sy):
                continue
            # a side strip when that side is short; a corner when either side is short
            if not ((sx and short[sx]) or (sy and short[sy])):
                continue
            ax, ex = fx[sx]
            ay, ey = fy[sy]
            out.append(((ax, 0, 0, ay, ex, ey), (xs[sx][0], ys[sy][0], xs[sx][1], ys[sy][1])))
    return out


def _uniq(vals, exclude=()):
    out = []
    for v in sorted(vals):
        if any(abs(v - e) < EPS for e in exclude):
            continue
        if not out or abs(v - out[-1]) > EPS:
            out.append(v)
    return out


FLIP_BOOK = "book"


def _sheet_sides(sheet_no, entries, SW, SH, s: Settings, bleed, duplex,
                 back_flip, folds_x=(), folds_y=()):
    """entries: [(Cell, front_page, back_page)] → [front Side, (back Side)]."""
    rects = [c.rect for c, _, _ in entries]
    block = (min(r[0] for r in rects), min(r[1] for r in rects),
             max(r[2] for r in rects), max(r[3] for r in rects))
    cuts_x = _uniq([v for r in rects for v in (r[0], r[2])], folds_x)
    cuts_y = _uniq([v for r in rects for v in (r[1], r[3])], folds_y)

    front, back = [], []
    portrait = SW <= SH
    mirror_x = (s.duplex_flip == "long") == portrait
    M = (-1, 0, 0, 1, SW, 0) if mirror_x else (1, 0, 0, -1, 0, SH)

    creases = []                     # front side, sheet coordinates
    for (cell, fp, bp), rect in zip(entries, rects):
        L, B, R, T = _side_bleeds(rect, rects, bleed)
        clip = (rect[0] - L, rect[1] - B, rect[2] + R, rect[3] + T)
        P = cell.matrix
        front.append(Item(fp, P, clip, rect, cell.W, cell.H))
        spec = crease_spec(s, cell.W, cell.H) if s.mode != "booklet" and fp is not None else None
        if spec is not None:
            for a, b in card_segments(spec, cell.W, cell.H):
                creases.append((apply(P, *a), apply(P, *b)))
        if duplex:
            if back_flip == FLIP_BOOK:
                F = (-1, 0, 0, 1, cell.W, 0)
            else:
                F = (1, 0, 0, -1, 0, cell.H)
            back.append(Item(bp, chain(F, P, M), map_rect(M, clip),
                             map_rect(M, rect), cell.W, cell.H))

    sides = [Side(sheet_no, False, front, block, cuts_x, cuts_y,
                  list(folds_x), list(folds_y), creases)]
    if duplex:
        mx = lambda v: SW - v
        my = lambda v: SH - v
        if mirror_x:
            bx = (_uniq([mx(v) for v in cuts_x]), cuts_y,
                  [mx(v) for v in folds_x], list(folds_y))
        else:
            bx = (cuts_x, _uniq([my(v) for v in cuts_y]),
                  list(folds_x), [my(v) for v in folds_y])
        back_creases = [(apply(M, *a), apply(M, *b)) for a, b in creases]
        sides.append(Side(sheet_no, True, back, map_rect(M, block), *bx, back_creases))
    return sides


def _sheet_candidates(s: Settings):
    a, b = sorted((mm(s.sheet_w), mm(s.sheet_h)))
    if s.orientation == "portrait":
        return [(a, b)]
    if s.orientation == "landscape":
        return [(b, a)]
    return [(a, b), (b, a)] if abs(a - b) > EPS else [(a, b)]


def build_plan(infos: list[PageInfo], s: Settings) -> Plan:
    if not infos:
        raise ImposeError(t("err_no_pages"))
    pages = parse_range(s.page_range, len(infos))
    if not pages:
        raise ImposeError(t("err_none_selected"))
    ref = infos[pages[0]]
    W, H = ref.vis_w, ref.vis_h
    warnings = []

    odd = sorted({p + 1 for p in pages
                  if abs(infos[p].vis_w - W) > mm(0.5) or abs(infos[p].vis_h - H) > mm(0.5)})
    if odd:
        lst = ", ".join(map(str, odd[:8])) + ("…" if len(odd) > 8 else "")
        warnings.append(t("warn_size", pages=lst))
    if not ref.has_trim and s.assume_bleed <= 0 and s.bleed > 0:
        warnings.append(t("warn_no_trim"))
    bleed = mm(max(0.0, s.bleed))
    avail = min(infos[p].bleed_avail for p in pages)
    if bleed > avail + EPS:
        if s.bleed_fill in ("mirror", "stretch"):
            warnings.append(t(f"info_bleed_fill_{s.bleed_fill}", avail=f"{to_mm(avail):.1f}",
                              want=f"{s.bleed:g}"))
        elif ref.has_trim or s.assume_bleed > 0:
            warnings.append(t("warn_bleed_short", avail=f"{to_mm(avail):.1f}", want=f"{s.bleed:g}"))

    if s.mode == "booklet":
        plan = _plan_booklet(pages, W, H, s, bleed)
    elif s.mode in ("repeat", "sequential", "cutstack"):
        plan = _plan_grid(pages, W, H, s, bleed)
    else:
        raise ImposeError(t("err_mode", mode=s.mode))
    plan.warnings = warnings + plan.warnings
    if s.reg_marks and plan.sides:
        skipped = max(_reg_targets(sd, s, plan.sheet_w, plan.sheet_h, bleed)[1] for sd in plan.sides)
        if skipped:
            plan.warnings.append(t("warn_reg_marks", n=skipped))
    return plan


def _plan_grid(pages, W, H, s: Settings, bleed) -> Plan:
    gx, gy = mm(max(0, s.gutter_x)), mm(max(0, s.gutter_y))
    m = mm(max(0, s.margin))
    rots = {"auto": [0, 90], "0": [0], "90": [90]}.get(str(s.rotation), [0])

    def dims(rot):
        return (H, W) if rot == 90 else (W, H)

    best = None
    cap = None
    if s.fit_sheet:
        cols, rows = max(1, s.cols), max(1, s.rows)
        rot = rots[0]
        cw, ch = dims(rot)
        SW = cols * cw + (cols - 1) * gx + 2 * m
        SH = rows * ch + (rows - 1) * gy + 2 * m
        best = (cols * rows, SW, SH, rot, cols, rows)
    else:
        cands = []                      # (SW, SH, rot, column capacity, row capacity)
        for rot in rots:
            for SW, SH in _sheet_candidates(s):
                cw, ch = dims(rot)
                fc = max(0, int((SW - 2 * m + gx + EPS) // (cw + gx)))
                fr = max(0, int((SH - 2 * m + gy + EPS) // (ch + gy)))
                cands.append((SW, SH, rot, fc, fr))
        for SW, SH, rot, fc, fr in cands:
            cols = s.cols if s.cols > 0 else fc
            rows = s.rows if s.rows > 0 else fr
            if cols > fc or rows > fr or cols < 1 or rows < 1:
                continue
            # with the same piece count prefer the larger capacity,
            # so a manual choice doesn't needlessly rotate the sheet
            if best is None or (cols * rows, fc * fr) > (best[0], cap[0] * cap[1]):
                best = (cols * rows, SW, SH, rot, cols, rows)
                cap = (fc, fr)
        if best is None:
            SW, SH, rot, fc, fr = max(cands, key=lambda c: c[3] * c[4])
            pw, ph = (to_mm(v) for v in dims(rot))
            if fc * fr == 0:
                raise ImposeError(t("err_grid_none", pw=f"{to_mm(W):.1f}", ph=f"{to_mm(H):.1f}",
                                    sw=f"{s.sheet_w:g}", sh=f"{s.sheet_h:g}", m=f"{s.margin:g}"))
            raise ImposeError(t("err_grid_cap", mc=fc, mr=fr,
                                sw=f"{to_mm(SW):.0f}", sh=f"{to_mm(SH):.0f}"))

    N, SW, SH, rot, cols, rows = best
    cw, ch = dims(rot)
    block_w = cols * cw + (cols - 1) * gx
    block_h = rows * ch + (rows - 1) * gy
    x0 = (SW - block_w) / 2
    ytop = (SH + block_h) / 2
    cells = [Cell(x0 + c * (cw + gx), ytop - (r + 1) * ch - r * gy, rot, W, H)
             for r in range(rows) for c in range(cols)]

    if s.duplex:
        items = [(pages[i], pages[i + 1] if i + 1 < len(pages) else None)
                 for i in range(0, len(pages), 2)]
    else:
        items = [(p, None) for p in pages]

    sheets = []
    if s.mode == "repeat":
        sheets = [[it] * N for it in items]
    elif s.mode == "sequential":
        for k in range(0, len(items), N):
            chunk = items[k:k + N]
            sheets.append(chunk + [(None, None)] * (N - len(chunk)))
    else:  # cutstack
        S = math.ceil(len(items) / N)
        for sh in range(S):
            row = []
            for c in range(N):
                i = c * S + sh
                row.append(items[i] if i < len(items) else (None, None))
            sheets.append(row)

    sides = []
    for k, sheet in enumerate(sheets):
        entries = [(cell, fp, bp) for cell, (fp, bp) in zip(cells, sheet)]
        sides += _sheet_sides(k + 1, entries, SW, SH, s, bleed, s.duplex, s.back_orientation)

    plan = Plan(SW, SH, sides, len(sheets), N, W, H, cols, rows, rot)
    plan.cap = cap
    plan.gutter = (gx, gy)
    plan.margin = m
    if s.mode == "cutstack" and len(items) % N:
        plan.warnings.append(t("warn_cutstack", n=len(items), N=N * len(sheets)))
    if s.duplex and len(pages) % 2:
        plan.warnings.append(t("warn_duplex_odd"))
    return plan


def _plan_booklet(pages, W, H, s: Settings, bleed) -> Plan:
    P0 = len(pages)
    P = max(4, math.ceil(P0 / 4) * 4)
    blanks = P - P0
    if s.blanks == "before_back" and P0 > 1:
        padded = pages[:-1] + [None] * blanks + [pages[-1]]
    else:
        padded = pages + [None] * blanks
    S = P // 4
    m = mm(max(0, s.margin))
    bw, bh = 2 * W, H

    if s.fit_sheet:
        SW, SH = bw + 2 * m, bh + 2 * m
    else:
        fit = [(sw, sh) for sw, sh in _sheet_candidates(s)
               if bw <= sw - 2 * m + EPS and bh <= sh - 2 * m + EPS]
        if not fit:
            raise ImposeError(t("err_booklet", bw=f"{to_mm(bw):.1f}", bh=f"{to_mm(bh):.1f}",
                                sw=f"{s.sheet_w:g}", sh=f"{s.sheet_h:g}", m=f"{s.margin:g}"))
        SW, SH = fit[0]

    x0, y0 = (SW - bw) / 2, (SH - bh) / 2
    crp = mm(max(0.0, s.creep))
    sides = []
    for k in range(S):
        d = crp * k / (S - 1) if S > 1 else 0.0
        left = Cell(x0, y0, 0, W, H, dx=+d)
        right = Cell(x0 + W, y0, 0, W, H, dx=-d)
        entries = [(left, padded[P - 1 - 2 * k], padded[P - 2 - 2 * k]),
                   (right, padded[2 * k], padded[2 * k + 1])]
        sides += _sheet_sides(k + 1, entries, SW, SH, s, bleed, True, FLIP_BOOK,
                              folds_x=[x0 + W])
    plan = Plan(SW, SH, sides, S, 2, W, H, 2, 1, 0, blanks)
    if blanks:
        key = "warn_blanks_before" if s.blanks == "before_back" else "warn_blanks_end"
        plan.warnings.append(t(key, n=blanks))
    if crp > bleed + EPS:
        plan.warnings.append(t("warn_creep"))
    return plan


# --------------------------------------------------------------------------
# Writing the PDF

def _n(v: float) -> str:
    t = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if t in ("", "-0") else t


def _re(r):
    return f"{_n(r[0])} {_n(r[1])} {_n(r[2] - r[0])} {_n(r[3] - r[1])} re"


def _ascii(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("×", "x").replace("–", "-").replace("„", '"').replace("“", '"')
    t = t.encode("latin-1", "replace").decode("latin-1")
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _circle(cx, cy, r):
    k = 0.5523 * r
    return (f"{_n(cx + r)} {_n(cy)} m "
            f"{_n(cx + r)} {_n(cy + k)} {_n(cx + k)} {_n(cy + r)} {_n(cx)} {_n(cy + r)} c "
            f"{_n(cx - k)} {_n(cy + r)} {_n(cx - r)} {_n(cy + k)} {_n(cx - r)} {_n(cy)} c "
            f"{_n(cx - r)} {_n(cy - k)} {_n(cx - k)} {_n(cy - r)} {_n(cx)} {_n(cy - r)} c "
            f"{_n(cx + k)} {_n(cy - r)} {_n(cx + r)} {_n(cy - k)} {_n(cx + r)} {_n(cy)} c S")


REG_ARM = mm(3.5)          # half the length of a target's arm
REG_MIN_ARM = mm(1.5)      # anything smaller is useless
REG_PAD = mm(0.5)          # clearance from the sheet edge and the bleed


def _reg_targets(side: Side, s: Settings, SW, SH, bleed):
    """Registration targets in the middle of each sheet margin.
    Returns ([(x, y, radius, arm)], number skipped). In a narrow margin the target
    shrinks and is centred in the free space between the sheet edge and the bleed."""
    bx0, by0, bx1, by1 = side.block
    off = max(mm(s.mark_offset), bleed)
    L = mm(s.mark_length) if s.crop_marks else 0.0

    def mid(vals, lo, hi, center):
        pts = sorted(set([lo, hi] + list(vals)))
        gaps = [(a + b) / 2 for a, b in zip(pts, pts[1:]) if b - a > mm(12)]
        return min(gaps, key=lambda v: abs(v - center)) if gaps else (lo + hi) / 2

    cx = mid(side.cuts_x + side.folds_x, bx0, bx1, SW / 2)
    cy = mid(side.cuts_y + side.folds_y, by0, by1, SH / 2)
    # (free strip from the sheet edge to the bleed, edge of the block, direction)
    sides = [((cx, None), by0 - bleed, -1, by0),         # bottom
             ((cx, None), SH - (by1 + bleed), +1, by1),  # top
             ((None, cy), bx0 - bleed, -1, bx0),         # left
             ((None, cy), SW - (bx1 + bleed), +1, bx1)]  # right
    out, skipped = [], 0
    for (fx, fy), free, sign, edge in sides:
        free -= 2 * REG_PAD
        arm = min(REG_ARM, free / 2)
        if arm < REG_MIN_ARM:
            skipped += 1
            continue
        # ideally beyond the crop marks, but always fully inside the free strip
        want = off + max(L, mm(4)) / 2
        lo = bleed + REG_PAD + arm
        hi = bleed + REG_PAD + free - arm
        dist = min(max(want, lo), hi)
        pos = edge + sign * dist
        x, y = (fx, pos) if fx is not None else (pos, fy)
        out.append((x, y, arm * 0.57, arm))
    return out, skipped


def _marks(side: Side, s: Settings, SW, SH, bleed):
    ops = []
    bx0, by0, bx1, by1 = side.block
    off = max(mm(s.mark_offset), bleed)
    L = mm(s.mark_length)

    def vseg(x, ya, yb):
        ya, yb = max(0, ya), min(SH, yb)
        if yb - ya > 0.5:
            ops.append(f"{_n(x)} {_n(ya)} m {_n(x)} {_n(yb)} l S")

    def hseg(y, xa, xb):
        xa, xb = max(0, xa), min(SW, xb)
        if xb - xa > 0.5:
            ops.append(f"{_n(xa)} {_n(y)} m {_n(xb)} {_n(y)} l S")

    if s.crop_marks:
        for x in side.cuts_x:
            vseg(x, by0 - off - L, by0 - off)
            vseg(x, by1 + off, by1 + off + L)
        for y in side.cuts_y:
            hseg(y, bx0 - off - L, bx0 - off)
            hseg(y, bx1 + off, bx1 + off + L)
        if side.folds_x or side.folds_y:
            ops.append("[2 2] 0 d")
            for x in side.folds_x:
                vseg(x, by0 - off - L, by0 - off)
                vseg(x, by1 + off, by1 + off + L)
            for y in side.folds_y:
                hseg(y, bx0 - off - L, bx0 - off)
                hseg(y, bx1 + off, bx1 + off + L)
            ops.append("[] 0 d")

    if s.crease_marks and side.crease_segs:
        # dash-dot, so a crease mark is never mistaken for a cut or a fold mark
        ops.append("[4 1.5 0.8 1.5] 0 d")
        for x in side.creases_x:
            vseg(x, by0 - off - L, by0 - off)
            vseg(x, by1 + off, by1 + off + L)
        for y in side.creases_y:
            hseg(y, bx0 - off - L, bx0 - off)
            hseg(y, bx1 + off, bx1 + off + L)
        ops.append("[] 0 d")

    if s.reg_marks:
        for tx, ty, r, arm in _reg_targets(side, s, SW, SH, bleed)[0]:
            ops.append(_circle(tx, ty, r))
            ops.append(f"{_n(tx - arm)} {_n(ty)} m {_n(tx + arm)} {_n(ty)} l S")
            ops.append(f"{_n(tx)} {_n(ty - arm)} m {_n(tx)} {_n(ty + arm)} l S")
    return ops


CREASE_LABEL = "B"       # next to each crease mark (B = big, crease)


def _crease_labels(side: Side, s: Settings, SW, SH, bleed):
    """A small letter at the outer end of each crease mark."""
    size = 5.0
    bx0, by0, bx1, by1 = side.block
    off = max(mm(s.mark_offset), bleed)
    L = mm(s.mark_length)
    txt = font_encode(t("crease_mark_letter")).decode("latin-1")
    out = []

    def put(x, y):
        if 0 <= x <= SW - size and 0 <= y <= SH - size:
            out.append(f"BT /F1 {_n(size)} Tf {_n(x)} {_n(y)} Td ({txt}) Tj ET")

    for x in side.creases_x:
        put(x + 1.2, by1 + off + L - size)              # top end
        put(x + 1.2, by0 - off - L)                     # bottom end
    for y in side.creases_y:
        put(bx0 - off - L, y + 1.2)                     # left end
        put(bx1 + off + L - size * 0.7, y + 1.2)        # right end
    return out


def crease_summary(s: Settings, W: float, H: float) -> str:
    """“Big: 99 / 198 mm zľava” – for the info line and the panel."""
    spec = crease_spec(s, W, H)
    if spec is None or not spec.positions:
        return ""
    from .i18n import get_language
    pos = " / ".join(f"{v:.1f}".rstrip("0").rstrip(".") for v in spec.positions)
    if get_language() == "sk":
        pos = pos.replace(".", ",")
    return t("crease_from_left" if spec.vertical else "crease_from_top", pos=pos)


def _slug(side: Side, plan: Plan, s: Settings, SW, SH, bleed, filename, stamp, label=None):
    size = 6.0
    bx0, by0, bx1, by1 = side.block
    off = max(mm(s.mark_offset), bleed)
    reach = off + (mm(s.mark_length) if s.crop_marks else 0) + mm(1)
    total = plan.n_sheets
    extra_label = label
    label = t("slug_back") if side.is_back else t("slug_front")
    if extra_label:
        label = f"{label} | {extra_label}"
    crease = crease_summary(s, plan.page_w, plan.page_h) if side.crease_segs else ""
    text = (f"{filename} | {t('slug_sheet')} {side.sheet_no}/{total} {label} | "
            f"{plan.summary(s)}" + (f" | {crease}" if crease else "") + f" | {stamp}")
    y = by0 - reach - size
    if y < mm(2):
        y_top = by1 + reach
        y = y_top if y_top + size < SH - mm(2) else max(mm(1), y)
    x = max(mm(4), bx0)
    return f"BT /F1 {_n(size)} Tf {_n(x)} {_n(y)} Td ({font_encode(text).decode('latin-1')}) Tj ET"


# --------------------------------------------------------------------------
# Layers (varnish, white, die-cut, foil…) – extra PDFs imposed with the same plan

LAYER_KINDS = {
    # kind: (file suffix, default position)
    "varnish": ("varnish", "above"),
    "white": ("white", "below"),
    "diecut": ("diecut", "above"),
    "foil": ("foil", "above"),
    "crease": ("crease", "above"),   # crease lines: read for the crease marks, never printed
    "custom": ("layer", "above"),
}


@dataclass
class Layer:
    path: str
    name: str = ""
    kind: str = "varnish"
    spot: str = ""                  # "" = read from the PDF; otherwise the name the printer expects
    position: str = "above"         # above | below the print
    overprint: bool = True          # force overprint for the whole layer
    pages: str = "same"             # same (page n ↔ n) | first (page 1 for all)
    visible: bool = True            # preview only

    @property
    def suffix(self):
        if self.kind != "custom":
            return LAYER_KINDS[self.kind][0]
        s = unicodedata.normalize("NFKD", self.name or "layer")
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
        return s or "layer"


@dataclass
class Source:
    """One PDF drawn onto the sheets."""
    pdf: pikepdf.Pdf
    infos: list
    page_map: object = None         # base page index → index in this PDF (or None)
    ocg: str | None = None          # optional-content group name (layered output)
    overprint: bool = False
    alpha: float | None = None      # preview: semi-transparent layer
    key: str = "P"                  # prefix for XObject names

    def page_for(self, i):
        return i if self.page_map is None else self.page_map(i)


def layer_source(layer: Layer, pdf: pikepdf.Pdf, infos, key, ocg=None, alpha=None) -> Source:
    n = len(infos)
    if layer.pages == "first":
        pm = lambda i: 0 if n else None
    else:
        pm = lambda i: i if i < n else None
    return Source(pdf, infos, pm, ocg=ocg, overprint=layer.overprint, alpha=alpha, key=key)


def render(src: pikepdf.Pdf, infos: list[PageInfo], plan: Plan, s: Settings,
           side_indices=None, guides=False, filename="", extra=None) -> pikepdf.Pdf:
    """Print only (plus optional extra sources, e.g. layers in the preview)."""
    sources = [Source(src, infos)] + list(extra or [])
    return render_sources(sources, plan, s, side_indices, guides, filename)


def render_sources(sources: list[Source], plan: Plan, s: Settings, side_indices=None,
                   guides=False, filename="", label=None, layered=False) -> pikepdf.Pdf:
    """Draw the given sources in order onto the sheets of `plan`.
    layered=True wraps each source with an `ocg` name into its own PDF layer."""
    out = pikepdf.new()
    SW, SH = plan.sheet_w, plan.sheet_h
    bleed = mm(max(0.0, s.bleed))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    forms = {}

    def form_for(si, src, i):
        pp = src.infos[i].pdf_page
        k = (si, pp)
        if k not in forms:
            fx = src.pdf.pages[pp].as_form_xobject(handle_transformations=False)
            fo = out.copy_foreign(fx)
            fo.BBox = Array([float(v) for v in src.infos[i].media])
            fo.Matrix = Array([1, 0, 0, 1, 0, 0])
            forms[k] = fo
        return forms[k]

    fn = out.make_indirect(Dictionary(FunctionType=2, Domain=[0, 1], C0=[0, 0, 0, 0],
                                      C1=[1, 1, 1, 1], N=1))
    cs_reg = out.make_indirect(Array([Name.Separation, Name("/All"), Name.DeviceCMYK, fn]))
    has_creases = s.crease_marks and any(sd.crease_segs for sd in plan.sides)
    font = make_font(out) if (s.slug or has_creases) else None

    gstates = Dictionary()
    if any(src.overprint for src in sources):
        gstates.GSop = out.make_indirect(Dictionary(Type=Name.ExtGState, OP=True, op=True, OPM=1))
    for src in sources:
        if src.alpha is not None:
            key = f"/GSa{int(src.alpha * 100)}"
            if key not in gstates:
                gstates[key] = out.make_indirect(Dictionary(Type=Name.ExtGState, CA=src.alpha, ca=src.alpha))

    ocgs = {}
    if layered:
        for src in sources:
            if src.ocg and src.ocg not in ocgs:
                ocgs[src.ocg] = out.make_indirect(Dictionary(Type=Name.OCG, Name=pikepdf.String(src.ocg)))
        if ocgs:
            arr = Array(list(ocgs.values()))
            out.Root.OCProperties = Dictionary(
                OCGs=arr,
                D=Dictionary(Name=pikepdf.String(APP_NAME), BaseState=Name.ON,
                             Order=Array(list(ocgs.values())), ON=Array(list(ocgs.values()))))
    props = Dictionary({f"/OC{i}": g for i, g in enumerate(ocgs.values())})
    oc_key = {name: f"/OC{i}" for i, name in enumerate(ocgs)}

    indices = range(len(plan.sides)) if side_indices is None else side_indices
    for si in indices:
        side = plan.sides[si]
        xobjs = Dictionary()
        ops = []
        for n, src in enumerate(sources):
            body = []
            for it in side.items:
                if it.page is None:
                    continue
                pi = src.page_for(it.page)
                if pi is None or pi >= len(src.infos):
                    continue
                info = src.infos[pi]
                C = translate((it.W - info.vis_w) / 2, (it.H - info.vis_h) / 2)
                m = chain(info.R, C, it.matrix)
                name = f"/{src.key}{n}_{info.pdf_page}"
                xobjs[name] = form_for(n, src, pi)
                gs = ""
                if src.overprint:
                    gs += "/GSop gs "
                if src.alpha is not None:
                    gs += f"/GSa{int(src.alpha * 100)} gs "
                v2s = chain(C, it.matrix)                      # upright page → sheet
                for M, strip in bleed_patches(info, bleed, s.bleed_fill):
                    pm = chain(info.R, M)
                    body.append(f"q {_re(it.clip)} W n {gs}{' '.join(_n(v) for v in v2s)} cm "
                                f"{_re(strip)} W n {' '.join(_n(v) for v in pm)} cm "
                                f"{_re(info.limit)} W n {name} Do Q")
                body.append(f"q {_re(it.clip)} W n {gs}"
                            f"{' '.join(_n(v) for v in m)} cm "
                            f"{_re(info.limit)} W n {name} Do Q")
            if not body:
                continue
            if layered and src.ocg in oc_key:
                ops.append(f"/OC {oc_key[src.ocg]} BDC")
                ops += body
                ops.append("EMC")
            else:
                ops += body

        mark_ops = _marks(side, s, SW, SH, bleed)
        if mark_ops:
            ops.append(f"q /CSReg CS 1 SCN {_n(s.mark_weight)} w 0 J")
            ops += mark_ops
            ops.append("Q")
        if font is not None and s.crease_marks and side.crease_segs:
            lbl = _crease_labels(side, s, SW, SH, bleed)
            if lbl:
                ops.append("q /CSReg cs 1 scn")
                ops += lbl
                ops.append("Q")
        if s.slug:
            ops.append("q /CSReg cs 1 scn " + _slug(side, plan, s, SW, SH, bleed, filename, stamp, label) + " Q")
        if guides:
            ops.append("q 0.5 w 0 0.62 1 RG")
            ops += [f"{_re(it.trim)} S" for it in side.items]
            ops.append("[3 2] 0 d 1 0 0.6 RG")
            ops += [f"{_re(it.clip)} S" for it in side.items]
            if side.crease_segs:
                ops.append("0.8 w [6 2 1.5 2] 0 d 0 0.62 0.25 RG")
                ops += [f"{_n(a[0])} {_n(a[1])} m {_n(b[0])} {_n(b[1])} l S"
                        for a, b in side.crease_segs]
            ops.append("Q")

        page = out.add_blank_page(page_size=(SW, SH))
        res = Dictionary(XObject=xobjs, ColorSpace=Dictionary(CSReg=cs_reg),
                         Font=Dictionary(F1=font) if font else Dictionary())
        if len(gstates):
            res.ExtGState = gstates
        if len(props):
            res.Properties = props
        page.obj.Resources = res
        page.obj.Contents = out.make_stream("\n".join(ops).encode("latin-1"))

    return out


# --------------------------------------------------------------------------
# Export: PDF/X standard, output intent, metadata

@dataclass
class ExportPlan:
    label: str | None = None          # e.g. "PDF/X-4"; None = no standard
    gts_version: str | None = None
    gts_conformance: str | None = None
    pdf_version: str | None = None
    family: str | None = None         # x1a | x3 | x4 | None
    intent: str | None = None         # "copy" | "icc" | None
    icc_bytes: bytes | None = None
    icc_desc: str = ""
    intent_id: str | None = None      # output condition identifier (e.g. FOGRA39)
    warnings: list = field(default_factory=list)


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def resolve_export(s: Settings, prof: SourceProfile) -> ExportPlan:
    ex = ExportPlan()
    std = s.pdf_standard
    if std == "keep":
        if prof.pdfx:
            key = prof.standard_key
            if key:
                ex.label, ex.gts_version, ex.gts_conformance, ex.pdf_version, ex.family = STANDARDS[key]
            else:   # unknown PDF/X (X-5, X-6…) – take the values from the source
                ex.label = prof.pdfx
                ex.gts_version, ex.gts_conformance = prof.pdfx_version_key, prof.pdfx_conformance
                ex.pdf_version, ex.family = max(prof.pdf_version, "1.6"), "x4"
    elif std in STANDARDS:
        ex.label, ex.gts_version, ex.gts_conformance, ex.pdf_version, ex.family = STANDARDS[std]

    src_oi = prof.pdfx_intent
    choice = s.icc_profile or "keep"
    if choice == "keep" and src_oi is not None:
        ex.intent = "copy"
        ex.intent_id = src_oi.identifier or (src_oi.icc.condition_id if src_oi.icc else None)
        ex.icc_desc = src_oi.label()
        if ex.label and src_oi.icc is None and ex.family == "x4":
            ex.warnings.append(t("ex_no_icc_in_src"))
        return ex
    if choice == "keep" and not ex.label:
        return ex                     # no standard and no output intent in the source
    data = None
    if choice not in ("keep", "bundled"):
        data = _read(choice)
        if data is None or icc_info(data) is None:
            ex.warnings.append(t("ex_icc_missing", path=choice))
            data = None
    if data is None:
        if choice == "keep":
            ex.warnings.append(t("ex_icc_fallback"))
        data = _read(BUNDLED_ICC)
    info = icc_info(data) if data else None
    if info is None:
        return ex
    ex.intent, ex.icc_bytes, ex.icc_desc = "icc", data, info.desc
    ex.intent_id = info.condition_id
    return ex


def _pdf_date(dt):
    off = dt.utcoffset() or datetime.timedelta(0)
    mins = int(off.total_seconds() // 60)
    sign = "+" if mins >= 0 else "-"
    mins = abs(mins)
    return dt.strftime("D:%Y%m%d%H%M%S") + f"{sign}{mins // 60:02d}'{mins % 60:02d}'"


def _xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def finalize(out: pikepdf.Pdf, src: pikepdf.Pdf, prof: SourceProfile, s: Settings,
             filename: str = "") -> dict:
    """Adds the standard, output intent and metadata to the imposed PDF.
    Returns keyword arguments for Pdf.save()."""
    import uuid

    ex = resolve_export(s, prof)
    for pg in out.pages:
        mb = Array([float(v) for v in pg.mediabox])
        pg.obj.TrimBox = mb
        pg.obj.BleedBox = Array([float(v) for v in pg.mediabox])

    # output intent
    if ex.intent == "copy":
        arr = Array()
        for oi in src.Root.get("/OutputIntents", []):
            try:
                o = oi if oi.is_indirect else src.make_indirect(oi)
                arr.append(out.copy_foreign(o))
            except Exception:
                pass
        if len(arr):
            out.Root.OutputIntents = arr
    elif ex.intent == "icc":
        info = icc_info(ex.icc_bytes)
        prof_stream = out.make_stream(ex.icc_bytes)
        prof_stream.N = info.channels
        registered = ex.intent_id and ex.intent_id != "Custom"
        oi = Dictionary(Type=Name.OutputIntent, S=Name.GTS_PDFX,
                        OutputConditionIdentifier=pikepdf.String(ex.intent_id if registered else "Custom"),
                        OutputCondition=pikepdf.String(info.desc),
                        Info=pikepdf.String(info.desc),
                        RegistryName=pikepdf.String("http://www.color.org"),
                        DestOutputProfile=prof_stream)
        out.Root.OutputIntents = Array([out.make_indirect(oi)])

    # layers (not allowed in PDF/X-1a and X-3)
    if ex.family in ("x1a", "x3"):
        if "/OCProperties" in out.Root:          # layers are not allowed there
            del out.Root["/OCProperties"]
    elif "/OCProperties" in src.Root:
        try:
            theirs = out.copy_foreign(src.Root.OCProperties)
            if "/OCProperties" not in out.Root:
                out.Root.OCProperties = theirs
            else:                                 # merge with Imprimo's layers
                mine = out.Root.OCProperties
                for g in theirs.get("/OCGs", []):
                    mine.OCGs.append(g)
                    mine.D.ON.append(g)
        except Exception:
            pass

    # Info + XMP (dates must match)
    now = datetime.datetime.now().astimezone().replace(microsecond=0)
    pdate, xdate = _pdf_date(now), now.isoformat()
    tool = f"{APP_NAME} {__version__}"
    title = os.path.splitext(filename)[0] if filename else APP_NAME
    info = out.docinfo
    info.Title = pikepdf.String(title)
    info.Creator = pikepdf.String(tool)
    info.Producer = pikepdf.String(f"{tool} (pikepdf {pikepdf.__version__})")
    info.CreationDate = pikepdf.String(pdate)
    info.ModDate = pikepdf.String(pdate)
    info.Trapped = Name("/False")
    if ex.gts_version:
        info.GTS_PDFXVersion = pikepdf.String(ex.gts_version)
    if ex.gts_conformance:
        info.GTS_PDFXConformance = pikepdf.String(ex.gts_conformance)

    attrs = [f'xmp:CreateDate="{xdate}"', f'xmp:ModifyDate="{xdate}"',
             f'xmp:MetadataDate="{xdate}"', f'xmp:CreatorTool="{_xml(tool)}"',
             f'pdf:Producer="{_xml(info.Producer)}"', 'pdf:Trapped="False"',
             f'xmpMM:DocumentID="uuid:{uuid.uuid4()}"', f'xmpMM:InstanceID="uuid:{uuid.uuid4()}"',
             'xmpMM:RenditionClass="default"', 'xmpMM:VersionID="1"']
    if ex.family == "x4" and ex.gts_version:
        attrs.append(f'pdfxid:GTS_PDFXVersion="{_xml(ex.gts_version)}"')
    elif ex.gts_version:
        attrs.append(f'pdfx:GTS_PDFXVersion="{_xml(ex.gts_version)}"')
        if ex.gts_conformance:
            attrs.append(f'pdfx:GTS_PDFXConformance="{_xml(ex.gts_conformance)}"')
    xmp = ('<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
           '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
           ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
           '  <rdf:Description rdf:about=""\n'
           '    xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
           '    xmlns:xmp="http://ns.adobe.com/xap/1.0/"\n'
           '    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"\n'
           '    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"\n'
           '    xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/"\n'
           '    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/"\n    '
           + "\n    ".join(attrs) + '>\n'
           '   <dc:format>application/pdf</dc:format>\n'
           f'   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{_xml(title)}</rdf:li></rdf:Alt></dc:title>\n'
           '  </rdf:Description>\n'
           ' </rdf:RDF>\n'
           '</x:xmpmeta>\n' + "\n".join([" " * 100] * 20) + '\n<?xpacket end="w"?>')
    meta = out.make_stream(xmp.encode("utf-8"))
    meta.Type = Name.Metadata
    meta.Subtype = Name.XML
    out.Root.Metadata = meta

    kw = dict(compress_streams=True)
    if ex.pdf_version:
        kw["force_version"] = ex.pdf_version
        kw["object_stream_mode"] = (pikepdf.ObjectStreamMode.disable if ex.pdf_version < "1.5"
                                    else pikepdf.ObjectStreamMode.generate)
    else:
        kw["min_version"] = prof.pdf_version
        kw["object_stream_mode"] = pikepdf.ObjectStreamMode.generate
    return kw


def output_paths(base_path: str, layers: list[Layer]):
    """Names of all outputs derived from the chosen print file name."""
    stem, ext = os.path.splitext(base_path)
    ext = ext or ".pdf"
    used, layer_paths = set(), []
    for ly in layers:
        sfx, n = ly.suffix, 2
        while sfx in used:
            sfx, n = f"{ly.suffix}-{n}", n + 1
        used.add(sfx)
        layer_paths.append(f"{stem}_{sfx}{ext}")
    return {"print": stem + ext, "layers": layer_paths, "combined": f"{stem}_layers{ext}"}


def layer_display_name(ly: Layer) -> str:
    return ly.name or t(f"layer_{ly.kind}")


def export_outputs(src, infos, prof, plan, s: Settings, layers: list, base_path: str,
                   want_print=True, want_layers=True, want_combined=False, filename=""):
    """Write the selected outputs. `layers` = [(Layer, pikepdf.Pdf, infos)].
    Returns the list of written paths."""
    paths = output_paths(base_path, [ly for ly, _, _ in layers])
    written = []

    def save(out, path):
        out.save(path, **finalize(out, src, prof, s, filename))
        written.append(path)

    if want_print:
        save(render_sources([Source(src, infos, ocg=None)], plan, s, filename=filename), paths["print"])
    if want_layers:
        for (ly, lpdf, linfos), path in zip(layers, paths["layers"]):
            srcs = [layer_source(ly, lpdf, linfos, key="L")]
            save(render_sources(srcs, plan, s, filename=filename, label=layer_display_name(ly)), path)
    layered = resolve_export(s, prof).family not in ("x1a", "x3")   # X-1a/X-3: no layers
    if want_combined and layers:
        below = [(ly, p, i) for ly, p, i in layers if ly.position == "below"]
        above = [(ly, p, i) for ly, p, i in layers if ly.position != "below"]
        srcs = [layer_source(ly, p, i, key=f"B{k}", ocg=layer_display_name(ly)) for k, (ly, p, i) in enumerate(below)]
        srcs.append(Source(src, infos, ocg=t("layer_print")))
        srcs += [layer_source(ly, p, i, key=f"A{k}", ocg=layer_display_name(ly)) for k, (ly, p, i) in enumerate(above)]
        save(render_sources(srcs, plan, s, filename=filename, layered=layered), paths["combined"])
    return written


def detect_creases(pdf: pikepdf.Pdf, infos):
    from .crease import detect_any
    return detect_any(pdf, infos)


def apply_detected_creases(s: Settings, det) -> bool:
    """Fill crease_dir / crease_pos from detected lines; False when nothing was found."""
    from .crease import format_positions
    if not det.found:
        s.crease_pos = ""
        return False
    s.crease_dir = "v" if det.main_vertical else "h"
    s.crease_pos = format_positions(det.vertical if det.main_vertical else det.horizontal)
    return True


def impose_file(in_path: str, out_path: str, s: Settings) -> Plan:
    from .pdfinfo import detect_profile
    with pikepdf.open(in_path) as src:
        infos = analyze(src, s.assume_bleed, s.split_spreads)
        if s.crease == "pdf":
            apply_detected_creases(s, detect_creases(src, infos))
        plan = build_plan(infos, s)
        prof = detect_profile(src)
        name = os.path.basename(in_path)
        out = render(src, infos, plan, s, filename=name)
        out.save(out_path, **finalize(out, src, prof, s, name))
    return plan
