"""Embedded font for the info line (PDF/X requires embedded fonts).

A subset of DejaVu Sans Condensed with WinAnsi encoding (cp1252) is used:
it covers á, é, í, ó, ú, ý, ä, ô, š, ž; other accented characters are
written without the accent."""
from __future__ import annotations

import io
import os
import unicodedata

from pikepdf import Array, Dictionary, Name

FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "DejaVuSansCondensed.ttf")
FONT_NAME = "IMPRMO+DejaVuSansCondensed"
_cache = None


def _build():
    import logging
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    from fontTools import subset
    from fontTools.ttLib import TTFont

    chars = []
    for code in range(32, 256):
        try:
            chars.append(ord(bytes([code]).decode("cp1252")))
        except UnicodeDecodeError:
            pass
    font = TTFont(FONT_PATH)
    opts = subset.Options()
    opts.layout_features = []
    opts.hinting = False
    opts.notdef_outline = True
    opts.name_IDs = ["*"]
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "kern"]
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=chars)
    sub.subset(font)

    upm = font["head"].unitsPerEm
    k = 1000.0 / upm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    widths = []
    for code in range(32, 256):
        try:
            u = ord(bytes([code]).decode("cp1252"))
            g = cmap.get(u)
            widths.append(round(hmtx[g][0] * k) if g else 0)
        except UnicodeDecodeError:
            widths.append(0)
    head, os2, post = font["head"], font["OS/2"], font["post"]
    bbox = [round(head.xMin * k), round(head.yMin * k), round(head.xMax * k), round(head.yMax * k)]
    buf = io.BytesIO()
    font.save(buf)
    return {
        "data": buf.getvalue(),
        "widths": widths,
        "bbox": bbox,
        "ascent": round(os2.sTypoAscender * k),
        "descent": round(os2.sTypoDescender * k),
        "cap": round(getattr(os2, "sCapHeight", 700) * k) or 700,
        "italic": float(post.italicAngle),
    }


def font_data():
    global _cache
    if _cache is None:
        _cache = _build()
    return _cache


def make_font(pdf):
    """Creates the font dictionary (indirect objects) in `pdf` and returns it."""
    d = font_data()
    ff = pdf.make_stream(d["data"])
    ff.Length1 = len(d["data"])
    desc = pdf.make_indirect(Dictionary(
        Type=Name.FontDescriptor, FontName=Name("/" + FONT_NAME), Flags=32,
        FontBBox=Array(d["bbox"]), ItalicAngle=d["italic"], Ascent=d["ascent"],
        Descent=d["descent"], CapHeight=d["cap"], StemV=80, FontFile2=ff))
    return pdf.make_indirect(Dictionary(
        Type=Name.Font, Subtype=Name.TrueType, BaseFont=Name("/" + FONT_NAME),
        FirstChar=32, LastChar=255, Widths=Array(d["widths"]),
        Encoding=Name.WinAnsiEncoding, FontDescriptor=desc))


def encode(text: str) -> bytes:
    """Text → cp1252 bytes for a PDF string (escaped)."""
    out = bytearray()
    for ch in text:
        if ch in "×":
            ch = "x"
        try:
            b = ch.encode("cp1252")
        except UnicodeEncodeError:
            base = "".join(c for c in unicodedata.normalize("NFKD", ch)
                           if not unicodedata.combining(c))
            b = base.encode("cp1252", "replace")
        for byte in b:
            if byte in (0x28, 0x29, 0x5C):
                out += b"\\"
            out.append(byte)
    return bytes(out)
