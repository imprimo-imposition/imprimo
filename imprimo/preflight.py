"""Source PDF check (preflight): fonts, colour spaces, transparency, image
resolution, JPEG 2000, layers. Results are kept per page so they can be
evaluated for the selected pages only."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import pikepdf

from .i18n import t

PROCESS = {"Cyan", "Magenta", "Yellow", "Black", "All", "None"}
LOW_PPI = 250        # warn below this resolution
MIN_FONT_LIST = 6


def _mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


IDENT = (1, 0, 0, 1, 0, 0)


@dataclass
class Findings:
    fonts_missing: dict = field(default_factory=lambda: defaultdict(set))   # meno → strany
    rgb_device: set = field(default_factory=set)
    rgb_icc: set = field(default_factory=set)
    lab: set = field(default_factory=set)
    transparency: set = field(default_factory=set)
    jpx: set = field(default_factory=set)
    optional_content: set = field(default_factory=set)
    spots: dict = field(default_factory=lambda: defaultdict(set))           # meno → strany
    min_ppi: dict = field(default_factory=dict)                             # strana → ppi
    overprint: set = field(default_factory=set)
    scanned: set = field(default_factory=set)


def _key(obj):
    try:
        if obj.is_indirect:
            return obj.objgen
    except Exception:
        pass
    return id(obj)


def _name(v):
    try:
        return str(v).lstrip("/")
    except Exception:
        return ""


class _Scanner:
    def __init__(self, pdf, F: Findings):
        self.pdf = pdf
        self.F = F
        self.page = 0
        self.res_seen = set()
        self.cs_cache = {}

    # -- colour spaces
    def classify(self, cs, depth=0):
        tags = set()
        if cs is None or depth > 6:
            return tags
        try:
            if isinstance(cs, pikepdf.Name):
                n = _name(cs)
                if n == "DeviceRGB":
                    tags.add("rgb_device")
                return tags
            if isinstance(cs, pikepdf.Array) and len(cs):
                fam = _name(cs[0])
                if fam == "ICCBased":
                    n = int(cs[1].get("/N", 4))
                    if n == 3:
                        tags.add("rgb_icc")
                elif fam == "CalRGB":
                    tags.add("rgb_icc")
                elif fam == "Lab":
                    tags.add("lab")
                elif fam == "Indexed":
                    tags |= self.classify(cs[1], depth + 1)
                elif fam == "Separation":
                    nm = _name(cs[1])
                    if nm not in PROCESS:
                        tags.add("spot:" + nm)
                    tags |= {x for x in self.classify(cs[2], depth + 1) if x == "lab"}
                elif fam == "DeviceN":
                    for nm in cs[1]:
                        nm = _name(nm)
                        if nm not in PROCESS:
                            tags.add("spot:" + nm)
                elif fam == "Pattern" and len(cs) > 1:
                    tags |= self.classify(cs[1], depth + 1)
        except Exception:
            pass
        return tags

    def mark(self, tags):
        for tg in tags:
            if tg.startswith("spot:"):
                self.F.spots[tg[5:]].add(self.page)
            else:
                getattr(self.F, tg).add(self.page)

    # -- zdroje
    def scan_resources(self, res):
        if res is None:
            return
        k = (_key(res), self.page)
        if k in self.res_seen:
            return
        self.res_seen.add(k)
        F = self.F
        try:
            for nm, cs in (res.get("/ColorSpace") or {}).items():
                self.mark(self.classify(cs))
            for nm, sh in (res.get("/Shading") or {}).items():
                self.mark(self.classify(sh.get("/ColorSpace")))
            for nm, pat in (res.get("/Pattern") or {}).items():
                if int(pat.get("/PatternType", 0)) == 2 and "/Shading" in pat:
                    self.mark(self.classify(pat.Shading.get("/ColorSpace")))
                elif int(pat.get("/PatternType", 0)) == 1:
                    self.walk(pat, pat.get("/Resources"), None, 1)
            for nm, gs in (res.get("/ExtGState") or {}).items():
                if self.gs_transparent(gs):
                    F.transparency.add(self.page)
                if bool(gs.get("/OP", False)) or bool(gs.get("/op", False)):
                    F.overprint.add(self.page)
        except Exception:
            pass

    @staticmethod
    def gs_transparent(gs):
        try:
            for key in ("/CA", "/ca"):
                if key in gs and float(gs[key]) < 0.999:
                    return True
            sm = gs.get("/SMask")
            if sm is not None and not (isinstance(sm, pikepdf.Name) and _name(sm) == "None"):
                return True
            bm = gs.get("/BM")
            if bm is not None:
                names = [bm] if isinstance(bm, pikepdf.Name) else list(bm)
                if any(_name(b) not in ("Normal", "Compatible") for b in names):
                    return True
        except Exception:
            pass
        return False

    def check_font(self, font):
        try:
            sub = _name(font.get("/Subtype"))
            if sub == "Type3":
                return
            base = _name(font.get("/BaseFont", "?"))
            fd = None
            if sub == "Type0":
                desc = font.get("/DescendantFonts")
                if desc:
                    fd = desc[0].get("/FontDescriptor")
            else:
                fd = font.get("/FontDescriptor")
            embedded = fd is not None and any(k in fd for k in ("/FontFile", "/FontFile2", "/FontFile3"))
            if not embedded:
                self.F.fonts_missing[base.split("+")[-1]].add(self.page)
        except Exception:
            pass

    # -- content
    def image(self, img, ctm):
        F = self.F
        try:
            if "/SMask" in img or "/SMaskInData" in img and int(img.SMaskInData) > 0:
                F.transparency.add(self.page)
            flt = img.get("/Filter")
            flts = [flt] if isinstance(flt, pikepdf.Name) else list(flt or [])
            if any(_name(f) == "JPXDecode" for f in flts):
                F.jpx.add(self.page)
            if bool(img.get("/ImageMask", False)):
                return
            self.mark(self.classify(img.get("/ColorSpace")))
            if int(img.get("/BitsPerComponent", 8)) == 1 or ctm is None:
                return
            self.ppi(int(img.Width), int(img.Height), ctm)
        except Exception:
            pass

    def ppi(self, w, h, ctm):
        a, b, c, d, _, _ = ctm
        wpt, hpt = math.hypot(a, b), math.hypot(c, d)
        if wpt < 2 or hpt < 2 or w < 8 or h < 8:
            return
        v = min(w / (wpt / 72), h / (hpt / 72))
        cur = self.F.min_ppi.get(self.page)
        if cur is None or v < cur:
            self.F.min_ppi[self.page] = v

    def walk(self, stream, res, ctm, depth, stack=()):
        if depth > 12:
            return
        self.scan_resources(res)
        try:
            ops = pikepdf.parse_content_stream(stream)
        except Exception:
            return
        cur = ctm
        font = None
        saved = []
        xobjs = (res.get("/XObject") if res is not None else None) or {}
        for operands, op in ops:
            o = str(op)
            if o == "q":
                saved.append((cur, font))
            elif o == "Q":
                cur, font = saved.pop() if saved else (cur, font)
            elif o == "cm" and cur is not None and len(operands) == 6:
                try:
                    cur = _mul(tuple(float(v) for v in operands), cur)
                except Exception:
                    pass
            elif o == "Tf" and operands and res is not None:
                fonts = res.get("/Font")
                font = fonts[operands[0]] if fonts is not None and operands[0] in fonts else None
            elif o in ("Tj", "TJ", "'", '"'):
                if font is not None:      # a font that actually draws text
                    self.check_font(font)
            elif o in ("rg", "RG"):
                self.F.rgb_device.add(self.page)
            elif o in ("cs", "CS") and operands:
                if _name(operands[0]) == "DeviceRGB":
                    self.F.rgb_device.add(self.page)
            elif o == "BDC" and operands and _name(operands[0]) == "OC":
                self.F.optional_content.add(self.page)
            elif o == "INLINE IMAGE" and operands:
                self.inline(operands[0], cur)
            elif o == "Do" and operands:
                x = xobjs.get(operands[0]) if hasattr(xobjs, "get") else None
                if x is None:
                    continue
                sub = _name(x.get("/Subtype"))
                if sub == "Image":
                    self.image(x, cur)
                elif sub == "Form":
                    k = _key(x)
                    if k in stack:
                        continue
                    grp = x.get("/Group")
                    if grp is not None and _name(grp.get("/S")) == "Transparency":
                        self.F.transparency.add(self.page)
                    if "/OC" in x:
                        self.F.optional_content.add(self.page)
                    m = x.get("/Matrix")
                    sub_ctm = cur
                    if cur is not None and m is not None and len(m) == 6:
                        sub_ctm = _mul(tuple(float(v) for v in m), cur)
                    self.walk(x, x.get("/Resources") or res, sub_ctm, depth + 1, stack + (k,))

    def inline(self, im, ctm):
        try:
            d = im.obj if hasattr(im, "obj") else None
            w, h = int(im.width), int(im.height)
            if getattr(im, "image_mask", False):
                return
            cs = d.get("/CS") or d.get("/ColorSpace") if d is not None else None
            if cs is not None and _name(cs) in ("RGB", "DeviceRGB"):
                self.F.rgb_device.add(self.page)
            if ctm is not None and int(getattr(im, "bits_per_component", 8)) > 1:
                self.ppi(w, h, ctm)
        except Exception:
            pass


def _inherited(obj, key):
    for _ in range(64):
        if obj is None:
            return None
        if key in obj:
            return obj[key]
        obj = obj.get("/Parent")
    return None


def scan(pdf: pikepdf.Pdf, pages=None) -> Findings:
    F = Findings()
    sc = _Scanner(pdf, F)
    idx = range(len(pdf.pages)) if pages is None else pages
    for i in idx:
        pg = pdf.pages[i]
        sc.page = i + 1
        F.scanned.add(i + 1)
        try:
            sc.walk(pg, _inherited(pg.obj, "/Resources"), IDENT, 0)
        except Exception:
            continue
    return F


# --------------------------------------------------------------------------
# Evaluation against the target standard

def _pages(s, sel):
    pg = sorted(p for p in s if p in sel)
    if not pg:
        return ""
    txt = ", ".join(map(str, pg[:6])) + ("…" if len(pg) > 6 else "")
    return t("pf_pages", pages=txt)


def evaluate(F: Findings, family: str | None, selected_pages: set, src_intent_id=None,
             out_intent_id=None, encrypted=False):
    """family: None (no standard) | 'x1a' | 'x3' | 'x4'.
    Returns [(level, text)], level: 'ok' | 'warn' | 'error' | 'info'."""
    sel = set(selected_pages)
    out = []

    def hit(s):
        return any(p in sel for p in s)

    std = family is not None
    if encrypted:
        out.append(("error" if std else "warn", t("pf_encrypted")))

    # fonts
    missing = {n: pp for n, pp in F.fonts_missing.items() if hit(pp)}
    if missing:
        names = ", ".join(sorted(missing)[:MIN_FONT_LIST]) + ("…" if len(missing) > MIN_FONT_LIST else "")
        out.append(("error" if std else "warn", t("pf_fonts", fonts=names)))
    else:
        out.append(("ok", t("pf_fonts_ok")))

    # colours
    if hit(F.rgb_device):
        lvl = "error" if std else "warn"
        out.append((lvl, t("pf_rgb_device") + _pages(F.rgb_device, sel)))
    if hit(F.rgb_icc):
        lvl = "error" if family == "x1a" else "warn" if not std else "ok"
        out.append((lvl, t("pf_rgb_icc") + _pages(F.rgb_icc, sel)))
    if hit(F.lab):
        lvl = "error" if family == "x1a" else "warn"
        out.append((lvl, t("pf_lab") + _pages(F.lab, sel)))
    if not (hit(F.rgb_device) or hit(F.rgb_icc) or hit(F.lab)):
        out.append(("ok", t("pf_cmyk_ok")))

    spots = sorted(n for n, pp in F.spots.items() if hit(pp))
    if spots:
        out.append(("info", t("pf_spots", spots=", ".join(spots[:8]))))
    # technical colours (crease, die-cut…) belong in a layer of their own, not in the print
    from .spots import spot_for
    for n in spots:
        sp = spot_for(n)
        if sp is not None and sp.technical:
            out.append(("warn", t("pf_technical_spot", spot=n, use=t(f"spot_use_{sp.kind}"))
                        + _pages(F.spots[n], sel)))

    # transparency, JPEG 2000, layers
    if hit(F.transparency):
        lvl = "error" if family in ("x1a", "x3") else "ok" if family == "x4" else "info"
        out.append((lvl, t("pf_transp") + _pages(F.transparency, sel)))
    if hit(F.jpx) and family in ("x1a", "x3"):
        out.append(("error", t("pf_jpx") + _pages(F.jpx, sel)))
    if hit(F.optional_content) and family in ("x1a", "x3"):
        out.append(("error", t("pf_layers") + _pages(F.optional_content, sel)))

    # resolution
    low = {p: v for p, v in F.min_ppi.items() if p in sel and v < LOW_PPI}
    vals = [v for p, v in F.min_ppi.items() if p in sel]
    if low:
        worst = min(low, key=low.get)
        out.append(("warn", t("pf_ppi_low", ppi=round(low[worst]), page=worst, limit=LOW_PPI)))
    elif vals:
        out.append(("ok", t("pf_ppi_ok", ppi=round(min(vals)))))

    # output intent
    if src_intent_id and out_intent_id and src_intent_id != out_intent_id:
        out.append(("warn", t("pf_intent_diff", src=src_intent_id, out=out_intent_id)))
    return out


# --------------------------------------------------------------------------
# Layer checks (varnish, white, die-cut…)

def evaluate_layer(F: Findings, layer, layer_infos, base_infos, base_pages: set):
    """Checks a layer PDF against the print PDF. Returns [(level, text)]."""
    out = []
    n_layer = len(layer_infos)
    if layer.pages == "first":
        pages = {1} if n_layer else set()
    else:
        pages = {p for p in base_pages if p <= n_layer}
        missing = sorted(p for p in base_pages if p > n_layer)
        if missing:
            out.append(("warn", t("lc_pages", n=n_layer, m=len(base_pages))))
    if not n_layer:
        return [("error", t("err_no_pages"))]

    ref = base_infos[min(base_pages) - 1] if base_pages else base_infos[0]
    li = layer_infos[0]
    if abs(li.vis_w - ref.vis_w) > 1.5 or abs(li.vis_h - ref.vis_h) > 1.5:
        out.append(("warn", t("lc_size", lw=f"{li.vis_w / 72 * 25.4:.1f}", lh=f"{li.vis_h / 72 * 25.4:.1f}",
                              pw=f"{ref.vis_w / 72 * 25.4:.1f}", ph=f"{ref.vis_h / 72 * 25.4:.1f}")))

    spots = sorted({n for n, pp in F.spots.items() if pp & pages})
    want = (layer.spot or "").strip()
    if want:
        if any(s.lower() == want.lower() for s in spots):
            out.append(("ok", t("lc_spot_ok", spot=want)))
        elif spots:
            out.append(("warn", t("lc_spot_other", spot=want, found=", ".join(spots[:5]))))
        else:
            out.append(("warn", t("lc_spot_none", spot=want)))
    elif spots:
        out.append(("ok", t("lc_spots", found=", ".join(spots[:5]))))
    else:
        out.append(("warn", t("lc_no_spot")))

    process = (F.rgb_device | F.rgb_icc | F.lab) & pages
    if process:
        out.append(("info", t("lc_process")))

    if layer.overprint:
        out.append(("ok", t("lc_op_forced")))
    elif F.overprint & pages:
        out.append(("ok", t("lc_op_ok")))
    else:
        out.append(("warn", t("lc_op_none")))
    return out
