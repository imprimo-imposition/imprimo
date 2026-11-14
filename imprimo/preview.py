"""Fast preview: every source page is rendered once by pdfium into a bitmap and
cached; sheets are then composed from those bitmaps with QPainter transforms.
Only the marks (crop marks, targets, info line, guides) are rendered as a small
PDF per sheet. Changing settings therefore never decodes the images again.

Pages with large JPEG images are rendered from a preview proxy: a one-page copy
whose JPEGs are downscaled (fast DCT scaling in Pillow). pdfium can need seconds
per page for full-resolution CMYK photos; the proxy takes a fraction of that.
Exported PDFs always use the original."""
from __future__ import annotations

import io
import math
import zlib
from collections import OrderedDict

import pikepdf
import pypdfium2 as pdfium
from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QTransform

from .core import bleed_patches, chain, compose, map_rect, translate

LEVELS = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)   # pixels per point
MAX_SIDE = 8000                                           # longest bitmap side in px
BUDGET = 700 * 2 ** 20                                    # cache size in bytes
# (highest bitmap level, longest image side in px) of the preview proxies
PROXY_STEPS = ((2.0, 1200), (99.0, 2400))


def _downscale_jpegs(pdf: pikepdf.Pdf, cap: int) -> bool:
    """Replaces JPEG images larger than `cap` px with downscaled Flate images
    in the same colour space. Returns True if anything was changed."""
    from PIL import Image, ImageChops
    changed = False
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream) or obj.get("/Subtype") != "/Image":
            continue
        flt = obj.get("/Filter")
        if flt != "/DCTDecode" and not (isinstance(flt, pikepdf.Array) and len(flt) == 1
                                        and flt[0] == "/DCTDecode"):
            continue
        w, h = int(obj.get("/Width", 0)), int(obj.get("/Height", 0))
        if max(w, h) <= cap or int(obj.get("/BitsPerComponent", 8)) != 8:
            continue
        try:
            raw = obj.read_raw_bytes()
            im = Image.open(io.BytesIO(raw))
            if im.mode not in ("L", "RGB", "CMYK"):
                continue
            f = max(w, h) / cap
            im.draft(im.mode, (max(1, int(w / f)), max(1, int(h / f))))
            im.load()
            if max(im.size) > cap * 1.05:
                im.thumbnail((cap, cap))
            if im.mode == "CMYK" and b"Adobe" in raw[:4096]:
                im = ImageChops.invert(im)       # Adobe CMYK JPEGs store inverted values
            obj.write(zlib.compress(im.tobytes(), 1), filter=pikepdf.Name.FlateDecode)
            obj.Width, obj.Height = im.size
            for key in ("/DecodeParms", "/SMaskInData"):
                if key in obj:
                    del obj[key]
            changed = True
        except Exception:
            continue
    return changed


class PageRasters:
    """Cache of page bitmaps (raw page orientation, whole MediaBox, transparent background)."""

    def __init__(self):
        self.docs = {}
        self.pikes = {}
        self.proxies = {}               # (path, page, cap) -> pdfium doc, or None = use original
        self.cache = OrderedDict()      # (path, page, level) -> QImage
        self.media = {}                 # (path, page) -> (x0, y0, x1, y1)
        self.size = 0

    def clear(self):
        self.cache.clear()
        self.media.clear()
        self.size = 0
        for d in list(self.docs.values()) + [p for p in self.proxies.values() if p]:
            try:
                d.close()
            except Exception:
                pass
        for p in self.pikes.values():
            try:
                p.close()
            except Exception:
                pass
        self.docs.clear()
        self.proxies.clear()
        self.pikes.clear()

    def _doc(self, path):
        d = self.docs.get(path)
        if d is None:
            d = self.docs[path] = pdfium.PdfDocument(path)
        return d

    def _proxy(self, path, idx, cap):
        """One-page pdfium document with downscaled JPEGs, or None if not needed."""
        key = (path, idx, cap)
        if key not in self.proxies:
            doc = None
            try:
                src = self.pikes.get(path)
                if src is None:
                    src = self.pikes[path] = pikepdf.open(path)
                one = pikepdf.new()
                one.pages.append(src.pages[idx])
                if _downscale_jpegs(one, cap):
                    buf = io.BytesIO()
                    one.save(buf)
                    doc = pdfium.PdfDocument(buf.getvalue())
                one.close()
            except Exception:
                doc = None
            self.proxies[key] = doc
        return self.proxies[key]

    def level_for(self, ppt, media):
        w, h = media[2] - media[0], media[3] - media[1]
        cap = MAX_SIDE / max(w, h, 1)
        for lv in LEVELS:
            if lv >= ppt * 0.95:
                return min(lv, cap)
        return min(LEVELS[-1], cap)

    def best(self, path, idx, level):
        """The cached bitmap closest to `level` from below (or the smallest above)."""
        below = above = None
        for (p, i, lv), img in self.cache.items():
            if p != path or i != idx:
                continue
            if lv <= level + 1e-6:
                if below is None or lv > below[1]:
                    below = (img, lv)
            elif above is None or lv < above[1]:
                above = (img, lv)
        hit = below or above
        if hit:
            self.cache.move_to_end((path, idx, hit[1]))
        return hit or (None, 0.0)

    def render(self, path, idx, level):
        key = (path, idx, level)
        if key in self.cache:
            return self.cache[key]
        cap = next(c for lv, c in PROXY_STEPS if level <= lv)
        proxy = self._proxy(path, idx, cap)
        page = proxy[0] if proxy is not None else self._doc(path)[idx]
        try:
            page.set_rotation(0)                  # raw orientation – rotation is in our matrix
            mb = page.get_mediabox()
            page.set_cropbox(*mb)
            bm = page.render(scale=level, fill_color=(255, 255, 255, 0), rev_byteorder=True,
                             may_draw_forms=False)
            img = QImage(bm.buffer, bm.width, bm.height, bm.stride,
                         QImage.Format_RGBA8888).copy()
        finally:
            page.close()
        self.media[(path, idx)] = tuple(mb)
        self.cache[key] = img
        self.size += img.sizeInBytes()
        while self.size > BUDGET and len(self.cache) > 1:
            _, old = self.cache.popitem(last=False)
            self.size -= old.sizeInBytes()
        return img


class PreviewSource:
    """One PDF drawn in the preview: the print or a layer."""

    def __init__(self, path, infos, page_for=None, opacity=1.0, fill=("off", 0.0)):
        self.path = path
        self.infos = infos
        self.page_for = page_for or (lambda i: i)
        self.opacity = opacity
        self.fill = fill              # generated bleed: (method, bleed in pt)


def sheet_to_widget(ox, oy, s, sheet_h):
    """PDF sheet coordinates (y up) → widget coordinates (y down)."""
    return (s, 0.0, 0.0, -s, ox, oy + sheet_h * s)


def paint_side(p: QPainter, side, sources, s2w, dpr, rasters: PageRasters, wanted: set,
               sync=True):
    """Draws the pages of one sheet side. Missing sharper bitmaps are added to `wanted`."""
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    for src in sources:
        for it in side.items:
            if it.page is None:
                continue
            pi = src.page_for(it.page)
            if pi is None or pi >= len(src.infos):
                continue
            info = src.infos[pi]
            C = translate((it.W - info.vis_w) / 2, (it.H - info.vis_h) / 2)
            r2s = chain(info.R, C, it.matrix)
            r2w = compose(r2s, s2w)
            ppt = math.hypot(r2w[0], r2w[1]) * dpr
            level = rasters.level_for(ppt, info.media)
            pp = info.pdf_page
            img, lv = rasters.best(src.path, pp, level)
            if img is None:
                if not sync:
                    wanted.add((src.path, pp, level))
                    continue
                img, lv = rasters.render(src.path, pp, level), level
            elif lv + 1e-6 < level:
                wanted.add((src.path, pp, level))
            media = rasters.media.get((src.path, pp), info.media)
            i2r = (1.0 / lv, 0.0, 0.0, -1.0 / lv, media[0], media[3])
            ca = map_rect(s2w, it.clip)
            # generated bleed first (mirrored / stretched copies), the page on top
            v2w = compose(chain(C, it.matrix), s2w)
            for M, strip in bleed_patches(info, src.fill[1], src.fill[0]):
                pw = compose(chain(info.R, M), v2w)
                _draw(p, img, i2r, pw, src.opacity, ca, map_rect(v2w, strip), map_rect(pw, info.limit))
            _draw(p, img, i2r, r2w, src.opacity, ca, map_rect(r2w, info.limit))
    p.restore()


def _draw(p, img, i2r, r2w, opacity, *rects):
    """Draws a page bitmap with the raw → widget transform, clipped to all `rects`."""
    x0 = max(r[0] for r in rects)
    y0 = max(r[1] for r in rects)
    x1 = min(r[2] for r in rects)
    y1 = min(r[3] for r in rects)
    if x1 <= x0 or y1 <= y0:
        return
    p.save()
    p.setClipRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    p.setOpacity(opacity)
    p.setTransform(QTransform(*compose(i2r, r2w)))
    p.drawImage(0, 0, img)
    p.restore()


def paint_numbers(p: QPainter, side, s2w, infos, blank_text="", half_text=None):
    """Page number badges in the middle of every page. Each badge is turned like the
    page content, so an upside-down number shows that the page is upside down."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    font = QFont()
    font.setBold(True)
    for it in side.items:
        k = 0.30 * min(it.W, it.H) / 100.0           # badge = 100 units across
        # text space (y down, origin = page centre) → card → sheet → widget
        t2w = chain((k, 0, 0, -k, it.W / 2, it.H / 2), it.matrix, s2w)
        p.setTransform(QTransform(*t2w))
        p.setPen(QPen(QColor(255, 255, 255, 230), 3))
        if it.page is None:
            p.setBrush(QBrush(QColor(120, 120, 120, 170)))
            p.drawRoundedRect(QRectF(-75, -22, 150, 44), 22, 22)
            font.setPixelSize(22)
            p.setFont(font)
            p.drawText(QRectF(-75, -22, 150, 44), Qt.AlignCenter, blank_text)
            continue
        p.setBrush(QBrush(QColor(0, 102, 204, 200)))
        p.drawEllipse(QRectF(-50, -50, 100, 100))
        num = str(it.page + 1)
        font.setPixelSize(52 if len(num) < 3 else 38)
        p.setFont(font)
        p.drawText(QRectF(-50, -54, 100, 100), Qt.AlignCenter, num)
        # underline: tells 6 from 9 and shows where the bottom of the page is
        p.setPen(QPen(QColor(255, 255, 255, 230), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(-14 * len(num), 26, 14 * len(num), 26)
        info = infos[it.page] if it.page < len(infos) else None
        if info is not None and info.half and half_text:
            font.setPixelSize(15)
            p.setFont(font)
            r = QRectF(-90, 54, 180, 26)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, 150)))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(QColor(255, 255, 255))
            p.drawText(r, Qt.AlignCenter, half_text(info))
    p.restore()


def render_overlay(pdf_bytes, page_index, scale, crop=(0, 0, 0, 0)):
    """Renders marks/guides of one sheet side with a transparent background."""
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[page_index]
        bm = page.render(scale=scale, crop=crop, fill_color=(255, 255, 255, 0), rev_byteorder=True)
        img = QImage(bm.buffer, bm.width, bm.height, bm.stride, QImage.Format_RGBA8888).copy()
        page.close()
        return img
    finally:
        doc.close()
