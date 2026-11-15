"""Cover with a spine for perfect (V2) and sewn binding.

  spine width = leaves × caliper (thickness of one leaf),
  caliper     = grammage × bulk / 1000  (mm; bulk = volume of the paper, cm³/g)

`write_template` saves an empty cover PDF with guides for the designer;
`assemble` builds the opened cover (back | spine | front) from a designed PDF –
either the whole cover as one page, or front and back as separate pages. Pages
are placed as vector Form XObjects, their content is not changed.
"""
from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass, field

import pikepdf
from pikepdf import Array, Dictionary, Name

from .core import EPS, ImposeError, _n, _re, analyze, chain, mm, to_mm, translate
from .fonts import encode as font_encode, make_font
from .i18n import t

# (key, grammage g/m², bulk) – typical values; the real caliper depends on the paper
PAPERS = (
    ("offset", 80, 1.25),
    ("offset", 90, 1.2),
    ("offset", 100, 1.2),
    ("offset", 120, 1.15),
    ("bulky", 80, 1.5),
    ("bulky", 100, 1.5),
    ("silk", 115, 1.0),
    ("silk", 135, 1.0),
    ("gloss", 115, 0.9),
    ("gloss", 135, 0.9),
)
SIZE_TOL = mm(1.0)       # a page counts as the book size when it is within 1 mm
SPINE_TOL = 0.5          # mm – a designed spine this far from the computed one is fine


def caliper(grammage: float, bulk: float) -> float:
    """Thickness of one leaf in mm."""
    return grammage * bulk / 1000.0


def spine_width(pages: int, leaf_mm: float) -> float:
    """Spine in mm: one leaf = two pages."""
    return math.ceil(max(0, pages) / 2) * leaf_mm


def crease_positions(W_mm: float, spine_mm: float, hinge_mm: float = 0.0) -> list[float]:
    """Crease lines of the cover in mm from the left trim edge (outside view)."""
    out = [W_mm, W_mm + spine_mm]
    if hinge_mm > 0:
        out = [W_mm - hinge_mm] + out + [W_mm + spine_mm + hinge_mm]
    return [round(v, 2) for v in out]


def _num(v: float) -> str:
    from .i18n import get_language
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if get_language() == "sk" else s


def _boxes(page, W, H, b):
    page.obj.TrimBox = Array([b, b, b + W, b + H])
    page.obj.BleedBox = Array([0, 0, W + 2 * b, H + 2 * b])


# --------------------------------------------------------------------------
# Template

def write_template(path: str, W_mm: float, H_mm: float, spine_mm: float, bleed_mm: float = 3.0,
                   hinge_mm: float = 0.0, info: str = "") -> None:
    W, H, S, b = mm(W_mm), mm(H_mm), mm(spine_mm), mm(bleed_mm)
    CW = 2 * W + S                                  # opened cover, trimmed
    out = pikepdf.new()
    page = out.add_blank_page(page_size=(CW + 2 * b, H + 2 * b))
    _boxes(page, CW, H, b)
    font = make_font(out)

    # the guides are a layer that is visible on screen but never printed
    ocg = out.make_indirect(Dictionary(
        Type=Name.OCG, Name=pikepdf.String(t("cover_tpl_layer")),
        Usage=Dictionary(Print=Dictionary(PrintState=Name.OFF),
                         View=Dictionary(ViewState=Name.ON))))
    out.Root.OCProperties = Dictionary(
        OCGs=Array([ocg]),
        D=Dictionary(Order=Array([ocg]), ON=Array([ocg]),
                     AS=Array([Dictionary(Event=Name.Print, OCGs=Array([ocg]),
                                          Category=Array([Name.Print]))])))

    x_back, x_spine, x_front = b, b + W, b + W + S
    safe = mm(5)
    ops = ["/OC /G BDC q"]
    # bleed and trim
    ops.append(f"0.5 w 0 1 0 0 K {_re((0.25, 0.25, CW + 2 * b - 0.25, H + 2 * b - 0.25))} S")
    ops.append(f"0.75 w 1 0 0 0 K {_re((b, b, b + CW, b + H))} S")
    # safe area of the back and the front
    ops.append("[1 2] 0 d 0.4 w 0 0 0 0.45 K")
    for x in (x_back, x_front):
        ops.append(f"{_re((x + safe, b + safe, x + W - safe, b + H - safe))} S")
    # spine (and hinge) folds
    ops.append("[4 2] 0 d 0.75 w 0 1 1 0 K")
    for x in (x_spine, x_front):
        ops.append(f"{_n(x)} 0 m {_n(x)} {_n(H + 2 * b)} l S")
    if hinge_mm > 0:
        h = mm(hinge_mm)
        ops.append("[1 1.5] 0 d")
        for x in (x_spine - h, x_front + h):
            ops.append(f"{_n(x)} 0 m {_n(x)} {_n(H + 2 * b)} l S")
    ops.append("[] 0 d")

    def text(x, y, size, s, centre=True, rot=False):
        s = font_encode(s).decode("latin-1")
        w = size * 0.5 * len(s)
        if rot:                                     # bottom to top, centred on (x, y)
            return (f"BT /F1 {_n(size)} Tf 0 1 -1 0 {_n(x + size * 0.35)} {_n(y - w / 2)} Tm "
                    f"({s}) Tj ET")
        return f"BT /F1 {_n(size)} Tf {_n(x - w / 2 if centre else x)} {_n(y)} Td ({s}) Tj ET"

    ops.append("0 0 0 0.55 k")
    ops.append(text(x_back + W / 2, b + H / 2, 14, t("cover_tpl_back")))
    ops.append(text(x_front + W / 2, b + H / 2, 14, t("cover_tpl_front")))
    size = max(4.0, min(9.0, S * 0.6))
    ops.append(text(x_spine + S / 2, b + H / 2, size,
                    t("cover_tpl_spine", s=_num(spine_mm)), rot=True))
    if info:
        ops.append(text(x_back + safe, b + safe + 2, 6, info, centre=False))
    ops.append("Q EMC")

    page.obj.Resources = Dictionary(Font=Dictionary(F1=font),
                                    Properties=Dictionary(G=ocg))
    page.obj.Contents = out.make_stream("\n".join(ops).encode("latin-1"))
    out.docinfo["/Title"] = pikepdf.String(t("cover_tpl_title"))
    out.save(path)


# --------------------------------------------------------------------------
# Assembling the cover from a designed PDF

@dataclass
class CoverResult:
    path: str
    spine_mm: float                 # spine width used (from the PDF when it has a whole cover)
    two_sided: bool                 # the inside of the cover is printed too
    blank_spine: bool               # front and back were separate pages – the spine is white
    warnings: list = field(default_factory=list)


def assemble(src_path: str, out_path: str, W_mm: float, H_mm: float, spine_mm: float) -> CoverResult:
    """Opened cover from `src_path`:
      • 1 or 2 pages of the whole cover (outside, inside) – used as they are,
      • 2 pages of the book size: front, back,
      • 4 pages of the book size: front, inside front, inside back, back."""
    W, H, S = mm(W_mm), mm(H_mm), mm(spine_mm)
    warnings = []
    with pikepdf.open(src_path) as src:
        infos = analyze(src, 0.0, split_spreads=False)
        if not infos:
            raise ImposeError(t("err_no_pages"))
        p0 = infos[0]
        if abs(p0.vis_h - H) > SIZE_TOL:
            raise ImposeError(t("cover_err_size", w=f"{to_mm(p0.vis_w):.1f}", h=f"{to_mm(p0.vis_h):.1f}",
                                bw=_num(W_mm), bh=_num(H_mm)))
        whole = p0.vis_w > 1.5 * W
        if whole:
            if len(infos) > 2:
                raise ImposeError(t("cover_err_pages_whole", n=len(infos)))
            S = p0.vis_w - 2 * W
            if S < -EPS:
                raise ImposeError(t("cover_err_size", w=f"{to_mm(p0.vis_w):.1f}",
                                    h=f"{to_mm(p0.vis_h):.1f}", bw=_num(W_mm), bh=_num(H_mm)))
            if abs(to_mm(S) - spine_mm) > SPINE_TOL:
                warnings.append(t("cover_warn_spine", pdf=_num(to_mm(S)), calc=_num(spine_mm)))
        else:
            if abs(p0.vis_w - W) > SIZE_TOL:
                raise ImposeError(t("cover_err_size", w=f"{to_mm(p0.vis_w):.1f}",
                                    h=f"{to_mm(p0.vis_h):.1f}", bw=_num(W_mm), bh=_num(H_mm)))
            if len(infos) not in (2, 4):
                raise ImposeError(t("cover_err_pages", n=len(infos)))
        for i in infos[1:]:
            if abs(i.vis_w - p0.vis_w) > SIZE_TOL or abs(i.vis_h - p0.vis_h) > SIZE_TOL:
                raise ImposeError(t("cover_err_mixed"))

        b = max(0.0, min(i.bleed_avail for i in infos))
        b = min(b, mm(5))
        CW = 2 * W + S
        out = pikepdf.new()
        forms = {}

        def form(i):
            info = infos[i]
            if i not in forms:
                fx = src.pages[info.pdf_page].as_form_xobject(handle_transformations=False)
                fo = out.copy_foreign(fx)
                fo.BBox = Array([float(v) for v in info.media])
                fo.Matrix = Array([1, 0, 0, 1, 0, 0])
                forms[i] = fo
            return forms[i]

        def place(i, x, clip):
            info = infos[i]
            m = chain(info.R, translate(x, b))
            return (f"q {_re(clip)} W n {' '.join(_n(v) for v in m)} cm "
                    f"{_re(info.limit)} W n /P{i} Do Q")

        full = (0, 0, CW + 2 * b, H + 2 * b)
        left = (0, 0, b + W, H + 2 * b)                       # no bleed into the spine
        right = (b + W + S, 0, CW + 2 * b, H + 2 * b)
        if whole:
            sides = [[(0, b, full)]] + ([[(1, b, full)]] if len(infos) == 2 else [])
        elif len(infos) == 2:                                  # front, back
            sides = [[(1, b, left), (0, b + W + S, right)]]
        else:                                                  # front, in. front, in. back, back
            sides = [[(3, b, left), (0, b + W + S, right)],
                     [(1, b, left), (2, b + W + S, right)]]

        for side in sides:
            page = out.add_blank_page(page_size=(CW + 2 * b, H + 2 * b))
            _boxes(page, CW, H, b)
            xo = Dictionary()
            ops = []
            for i, x, clip in side:
                xo[f"/P{i}"] = form(i)
                ops.append(place(i, x, clip))
            page.obj.Resources = Dictionary(XObject=xo)
            page.obj.Contents = out.make_stream("\n".join(ops).encode("latin-1"))

        if "/OutputIntents" in src.Root:                       # keep the print condition
            out.Root.OutputIntents = out.copy_foreign(src.Root.OutputIntents)
        if b < mm(3) - EPS:
            warnings.append(t("cover_warn_bleed", b=_num(to_mm(b))))
        out.save(out_path)

    return CoverResult(out_path, round(to_mm(S), 2), len(sides) == 2, not whole, warnings)


def _free_name(path: str) -> str:
    stem, ext = os.path.splitext(path)
    n, out = 2, path
    while os.path.exists(out):
        out, n = f"{stem}-{n}{ext}", n + 1
    return out


def prepare(src_path: str, W_mm: float, H_mm: float, spine_mm: float) -> CoverResult:
    """A cover ready for imposing, in one step: a PDF with the whole opened cover is used
    as it is; front and back as separate pages are joined into “<name>_cover.pdf”
    next to the source (a new name, nothing is overwritten)."""
    with pikepdf.open(src_path) as src:
        infos = analyze(src, 0.0, split_spreads=False)
    whole = bool(infos) and infos[0].vis_w > 1.5 * mm(W_mm)
    if not whole:
        out = _free_name(os.path.splitext(src_path)[0] + t("cover_file_sfx") + ".pdf")
        return assemble(src_path, out, W_mm, H_mm, spine_mm)
    tmp = _free_name(os.path.join(tempfile.gettempdir(), "imprimo_cover_check.pdf"))
    try:                                # validate (sizes, pages, spine) without keeping a copy
        res = assemble(src_path, tmp, W_mm, H_mm, spine_mm)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    res.path = src_path
    return res
