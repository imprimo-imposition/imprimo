"""Builds the sample PDFs in this folder – lessons for trying Imprimo (see CITAJ-MA.md / README.md).

    pip install reportlab pillow
    python examples/make_examples.py

All colours are CMYK (or spot colours), text uses the bundled DejaVu font (embedded),
so the samples pass the preflight – except lesson 08, which is wrong on purpose.
"""
import io
import os

import pikepdf
from reportlab.lib.colors import CMYKColor, CMYKColorSep
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "imprimo", "assets", "DejaVuSansCondensed.ttf")
pdfmetrics.registerFont(TTFont("DejaVu", FONT))

K = CMYKColor(0, 0, 0, 1)
WHITE = CMYKColor(0, 0, 0, 0)
GREY = CMYKColor(0, 0, 0, 0.45)
BLUE = CMYKColor(0.85, 0.35, 0, 0)
TEAL = CMYKColor(0.75, 0, 0.35, 0)
ORANGE = CMYKColor(0, 0.55, 0.9, 0)
PINK = CMYKColor(0, 0.75, 0.1, 0)
SAND = CMYKColor(0.03, 0.08, 0.22, 0)
LIGHT = CMYKColor(0.06, 0.02, 0, 0)
CREASE = CMYKColorSep(1, 0, 1, 0, spotName="Crease", density=1)
VARNISH = CMYKColorSep(0, 0, 1, 0, spotName="Varnish", density=1)


class Doc:
    """A PDF with pages of trim w × h mm and `bleed` mm around; drawing coordinates are
    in mm from the lower-left corner of the trim (negative = in the bleed)."""

    def __init__(self, name, w, h, bleed=3.0, title=""):
        self.path = os.path.join(HERE, name)
        self.w, self.h, self.b = w, h, bleed
        self.c = canvas.Canvas(self.path, pagesize=((w + 2 * bleed) * mm, (h + 2 * bleed) * mm))
        self.c.setTitle(title or name)
        self.c.setAuthor("Imprimo – vzorové súbory")
        self.c.translate(bleed * mm, bleed * mm)

    def fill(self, colour, x=None, y=None, w=None, h=None):
        """A filled rectangle; without coordinates the whole page including the bleed."""
        if x is None:
            x, y, w, h = -self.b, -self.b, self.w + 2 * self.b, self.h + 2 * self.b
        self.c.setFillColor(colour)
        self.c.rect(x * mm, y * mm, w * mm, h * mm, stroke=0, fill=1)

    def text(self, x, y, s, size=10, colour=K, align="left"):
        self.c.setFillColor(colour)
        self.c.setFont("DejaVu", size)
        draw = {"left": self.c.drawString, "center": self.c.drawCentredString,
                "right": self.c.drawRightString}[align]
        draw(x * mm, y * mm, s)

    def lesson(self, s, colour=GREY, y=None):
        """Small grey line saying which lesson / page this is."""
        self.text(4, 3 if y is None else y, s, 6, colour)

    def line(self, x0, y0, x1, y1, colour, width=0.25, overprint=False):
        self.c.setStrokeColor(colour)
        self.c.setStrokeOverprint(overprint)
        self.c.setLineWidth(width)
        self.c.line(x0 * mm, y0 * mm, x1 * mm, y1 * mm)
        self.c.setStrokeOverprint(False)

    def page(self):
        self.c.showPage()
        self.c.translate(self.b * mm, self.b * mm)

    def save(self, trim_is_media=False):
        self.c.save()
        with pikepdf.open(self.path, allow_overwriting_input=True) as pdf:
            for pg in pdf.pages:
                x0, y0, x1, y1 = [float(v) for v in pg.mediabox]
                b = self.b * mm
                pg.obj.TrimBox = pikepdf.Array([x0 + b, y0 + b, x1 - b, y1 - b])
                pg.obj.BleedBox = pikepdf.Array([x0, y0, x1, y1])
            pdf.save(self.path)
        print("  ", os.path.basename(self.path))


def stripes(d, colours, angle_from=0.0):
    """Diagonal colour stripes over the whole page including the bleed."""
    n = len(colours)
    W, H, b = d.w + 2 * d.b, d.h + 2 * d.b, d.b
    step = (W + H) / n
    for i, col in enumerate(colours):
        p = d.c.beginPath()
        x0 = -b - H + i * step + angle_from
        p.moveTo(x0 * mm, -b * mm)
        p.lineTo((x0 + step) * mm, -b * mm)
        p.lineTo((x0 + step + H) * mm, (H - b) * mm)
        p.lineTo((x0 + H) * mm, (H - b) * mm)
        p.close()
        d.c.setFillColor(col)
        d.c.drawPath(p, stroke=0, fill=1)


def ramp(n, a, b):
    """n CMYK colours between a and b (tuples)."""
    return [CMYKColor(*[a[k] + (b[k] - a[k]) * i / max(1, n - 1) for k in range(4)])
            for i in range(n)]


# --------------------------------------------------------------------------
# 01 – business cards, double-sided

def lesson_01():
    d = Doc("01_vizitky_90x50_obojstranne.pdf", 90, 50, 3, "Vizitka 90×50 – líc a rub")
    d.fill(BLUE)                                             # front: colour up to the bleed
    d.fill(TEAL, 62, -3, 31, 56)
    d.text(7, 30, "Jana Nováková", 15, WHITE)
    d.text(7, 24, "grafička tlačových médií", 8, WHITE)
    d.c.setFillColor(WHITE)
    d.c.circle(76 * mm, 25 * mm, 7 * mm, stroke=0, fill=1)
    d.text(76, 23.3, "JN", 9, BLUE, "center")
    d.lesson("Imprimo · vzor 01 · LÍC (strana 1)", WHITE)
    d.page()
    d.fill(LIGHT)                                            # back
    d.fill(BLUE, -3, -3, 96, 9)
    d.text(7, 36, "+421 900 000 000", 8)
    d.text(7, 31, "jana@priklad.sk", 8)
    d.text(7, 26, "Košická 20, Prešov", 8)
    d.lesson("Imprimo · vzor 01 · RUB (strana 2)", WHITE, 1.8)
    d.save()


# 02 – a card without bleed

def lesson_02():
    d = Doc("02_vizitka_bez_spadavky.pdf", 90, 50, 0, "Vizitka bez spadávky")
    stripes(d, ramp(18, (0.1, 0.8, 0.2, 0), (0.85, 0.1, 0.5, 0)))
    d.fill(WHITE, 6, 14, 52, 22)
    d.text(9, 28, "Bez spadávky", 13)
    d.text(9, 22, "farba končí presne na oreze", 7, GREY)
    d.text(9, 17.5, "→ Spadávka: Doplniť zrkadlením", 7, GREY)
    d.lesson("Imprimo · vzor 02", WHITE)
    d.save()


# 03 – invitation A5 folded in half + crease PDF

def lesson_03():
    w, h = 210, 148
    d = Doc("03_pozvanka_A5_na_polovicu.pdf", w, h, 3, "Pozvánka A5 na polovicu")
    d.fill(SAND)                                             # outside: back | front
    d.fill(PINK, 105, -3, 108, 154)
    d.text(157.5, 84, "Pozvánka", 30, WHITE, "center")
    d.text(157.5, 70, "na stužkovú slávnosť", 11, WHITE, "center")
    d.text(52.5, 20, "zadná strana", 9, GREY, "center")
    d.lesson("Imprimo · vzor 03 · VONKAJŠOK (strana 1) – vľavo zadná, vpravo predná strana")
    d.page()
    d.fill(WHITE)                                            # inside
    d.fill(SAND, -3, -3, 216, 18)
    d.text(52.5, 90, "Milí hostia,", 14, K, "center")
    d.text(52.5, 80, "srdečne vás pozývame…", 9, GREY, "center")
    d.text(157.5, 90, "Sobota 14. 2. o 18:00", 12, K, "center")
    d.text(157.5, 80, "Hotel Dukla, Prešov", 9, GREY, "center")
    d.lesson("Imprimo · vzor 03 · VNÚTRO (strana 2)")
    d.save()

    c = Doc("03_pozvanka_A5_bigy.pdf", w, h, 3, "Pozvánka – čiara bigu (farba Crease)")
    c.line(105, -3, 105, h + 3, CREASE, overprint=True)
    c.save()


# 04 – DL roll (C) fold from A4 + crease PDF

def lesson_04():
    w, h = 297, 210
    panels = (100, 100, 97)                                  # the narrow one folds in
    d = Doc("04_DL_skladacka_zavinovacia.pdf", w, h, 3, "DL zavinovacia skladačka")
    cols = (LIGHT, SAND, CMYKColor(0.12, 0, 0.08, 0))
    x = 0
    for i, (pw, col) in enumerate(zip(panels, cols)):        # inside (page 1): 100 | 100 | 97
        left = -3 if i == 0 else 0
        d.fill(col, x + left, -3, pw - left + (3 if i == 2 else 0), h + 6)
        d.text(x + pw / 2, 150, f"vnútro – diel {i + 1}", 12, K, "center")
        d.text(x + pw / 2, 140, f"{pw} mm", 18, BLUE, "center")
        x += pw
    d.text(250, 120, "tento diel je o 3 mm užší,", 7, GREY, "center")
    d.text(250, 115, "aby sa pri zložení nekrčil", 7, GREY, "center")
    d.lesson("Imprimo · vzor 04 · VNÚTRO (strana 1) – diely 100 / 100 / 97 mm")
    d.page()
    x = 0
    names = ("záložka (otvorí sa prvá)", "zadná strana", "predná strana")
    for i, pw in enumerate(reversed(panels)):                # outside (page 2): 97 | 100 | 100
        col = (SAND, LIGHT, BLUE)[i]
        left = -3 if i == 0 else 0
        d.fill(col, x + left, -3, pw - left + (3 if i == 2 else 0), h + 6)
        d.text(x + pw / 2, 150, names[i], 11, WHITE if i == 2 else K, "center")
        d.text(x + pw / 2, 140, f"{pw} mm", 18, WHITE if i == 2 else BLUE, "center")
        x += pw
    d.text(247, 90, "SKLADAČKA", 20, WHITE, "center")
    d.lesson("Imprimo · vzor 04 · VONKAJŠOK (strana 2) – diely 97 / 100 / 100 mm")
    d.save()

    c = Doc("04_DL_skladacka_bigy.pdf", w, h, 3, "DL skladačka – čiary bigov (farba Crease)")
    for xx in (100, 200):
        c.line(xx, -3, xx, h + 3, CREASE, overprint=True)
    c.save()


# 05 – saddle-stitch booklet A5, 12 pages

def lesson_05():
    w, h, n = 148, 210, 12
    d = Doc("05_brozura_A5_12_stran.pdf", w, h, 3, "Brožúra A5, 12 strán")
    for p in range(1, n + 1):
        cover = p in (1, n)
        right = p % 2 == 1                                   # odd pages are on the right
        d.fill(BLUE if cover else WHITE)
        col = WHITE if cover else K
        if cover and p == 1:
            d.text(w / 2, 130, "Brožúra A5", 26, WHITE, "center")
            d.text(w / 2, 118, "vzor 05 · väzba V1 (zošitová)", 9, WHITE, "center")
        elif cover:
            d.text(w / 2, 110, "zadná strana obálky", 11, WHITE, "center")
        else:
            d.text(w / 2, 150, f"strana {p}", 16, K, "center")
            for k in range(14):                              # some body text lines
                d.fill(CMYKColor(0, 0, 0, 0.12), 18, 120 - k * 6, w - 36, 2.2)
        d.text(w / 2, 70, str(p), 72, col if cover else ORANGE, "center")
        # a bar 4 mm from the outer edge – shows creep: inner pages move towards the spine
        bx = w - 6 if right else 4
        d.fill(ORANGE if not cover else WHITE, bx, 20, 2, h - 40)
        d.text(w / 2, 8, "← chrbát" if right else "chrbát →", 7, GREY if not cover else WHITE,
               "left" if right else "right")
        d.lesson(f"Imprimo · vzor 05 · strana {p} z {n}", GREY if not cover else WHITE, 3)
        if p < n:
            d.page()
    d.save()


# 06 – tickets for cut & stack, numbered 001–028 (14 per SRA3 → 2 full sheets)

def lesson_06():
    w, h, n = 140, 50, 28
    d = Doc("06_vstupenky_cut_and_stack.pdf", w, h, 3, "Vstupenky 001–028")
    for p in range(1, n + 1):
        d.fill(CMYKColor(0, 0.1, 0.35, 0))
        d.fill(ORANGE, 100, -3, 43, 56)
        d.text(8, 30, "Stužková slávnosť 2027", 13)
        d.text(8, 22, "vstupenka · sobota 14. 2. · 18:00", 8, GREY)
        d.text(120, 26, f"Č. {p:03d}", 13, WHITE, "center")
        d.text(120, 18, "odtrhnúť", 6, WHITE, "center")
        d.line(100, 3, 100, 47, CMYKColor(0, 0, 0, 0.5), 0.3)
        d.lesson(f"Imprimo · vzor 06 · lístok {p} z {n}")
        if p < n:
            d.page()
    d.save()


# 07 – card with spot varnish (layer)

def lesson_07():
    d = Doc("07_vizitka_s_lakom.pdf", 90, 50, 3, "Vizitka – tlač")
    d.fill(CMYKColor(0.9, 0.7, 0.2, 0.3))
    d.text(45, 28, "LAK", 26, WHITE, "center")
    d.text(45, 18, "lesklý parciálny lak na nápise a kruhoch", 6.5, WHITE, "center")
    for cx in (12, 78):
        d.c.setFillColor(ORANGE)
        d.c.circle(cx * mm, 25 * mm, 5 * mm, stroke=0, fill=1)
    d.lesson("Imprimo · vzor 07 · tlač", WHITE)
    d.save()

    v = Doc("07_vizitka_lak.pdf", 90, 50, 3, "Vizitka – vrstva laku (farba Varnish)")
    v.c.setFillColor(VARNISH)
    v.c.setFillOverprint(True)
    v.c.setFont("DejaVu", 26)
    v.c.drawCentredString(45 * mm, 28 * mm, "LAK")
    for cx in (12, 78):
        v.c.circle(cx * mm, 25 * mm, 5 * mm, stroke=0, fill=1)
    v.save()


# 08 – a PDF with mistakes, for the preflight

def lesson_08():
    from PIL import Image
    w, h = 148, 105
    d = Doc("08_chybne_pdf_na_preflight.pdf", w, h, 0, "Chybné PDF – nájdi chyby")
    c = d.c
    c.setFillColorRGB(0.95, 0.3, 0.2)                        # mistake 1: RGB colour
    c.rect(0, 0, w * mm, h * mm, stroke=0, fill=1)           # mistake 2: no bleed
    img = Image.new("RGB", (60, 40))                         # mistake 3: low resolution
    for x in range(60):
        for y in range(40):
            img.putpixel((x, y), (40 + x * 3, 90 + y * 3, 200 - x * 2))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(buf), 84 * mm, 20 * mm, 56 * mm, 37 * mm)   # 60 px over 56 mm ≈ 27 ppi
    c.setFillColor(K)
    c.setFont("Helvetica", 16)                               # mistake 4: font not embedded
    c.drawString(8 * mm, 80 * mm, "Toto PDF má chyby")
    c.setFont("Helvetica", 8)
    c.drawString(8 * mm, 72 * mm, "Otvor ho v Imprime a pozri preflight.")
    d.line(74, 0, 74, h, CREASE, overprint=True)             # mistake 5: crease line in the print
    d.save()


# 09 – poster A2, printed in pieces on A4 / A3

def lesson_09():
    w, h = 420, 594
    d = Doc("09_plagat_A2.pdf", w, h, 3, "Plagát A2 – tlač po dieloch")
    d.fill(CMYKColor(0.02, 0.04, 0.12, 0))
    c = d.c
    # thin diagonal lines across the whole poster: after gluing they must continue without a step
    c.setStrokeColor(CMYKColor(0, 0, 0, 0.25))
    c.setLineWidth(0.5)
    for k in range(-12, 13):
        x = w / 2 + k * 40
        c.line((x - h) * mm, -3 * mm, (x + 3) * mm, (h + 3) * mm)
    for r, col in ((170, PINK), (130, ORANGE), (90, TEAL), (50, BLUE)):   # target circles
        c.setFillColor(col)
        c.circle(w / 2 * mm, 300 * mm, r * mm, stroke=0, fill=1)
    d.text(w / 2, 520, "PLAGÁT", 96, K, "center")
    d.text(w / 2, 490, "A2 · 420 × 594 mm · vzor 09", 22, GREY, "center")
    d.text(w / 2, 292, "A2", 60, WHITE, "center")
    for y, s in ((90, "Vytlač po dieloch na A4 alebo A3 a zlep –"),
                 (72, "šikmé čiary a kruhy musia nadväzovať bez schodíka.")):
        d.text(w / 2, y, s, 20, K, "center")
    d.lesson("Imprimo · vzor 09 · plagát po dieloch")
    d.save()


# 10 – gang run: business cards of three people on one sheet

def lesson_10():
    people = (("jana", "Jana Nováková", "grafička", BLUE),
              ("peter", "Peter Horváth", "tlačiar", ORANGE),
              ("eva", "Eva Kováčová", "knihárka", TEAL))
    for key, name, job, col in people:
        d = Doc(f"10_vizitky_{key}.pdf", 90, 50, 3, f"Vizitka – {name}")
        d.fill(col)
        d.text(7, 30, name, 15, WHITE)
        d.text(7, 24, job, 8, WHITE)
        d.c.setFillColor(WHITE)
        d.c.circle(76 * mm, 25 * mm, 7 * mm, stroke=0, fill=1)
        d.text(76, 23.3, "".join(w[0] for w in name.split()), 9, col, "center")
        d.lesson(f"Imprimo · vzor 10 · {key} · LÍC", WHITE)
        d.page()
        d.fill(LIGHT)
        d.fill(col, -3, -3, 96, 9)
        d.text(7, 36, "SOŠ služieb, Košická 20, Prešov", 8)
        d.text(7, 31, f"{key}@priklad.sk", 8)
        d.lesson(f"Imprimo · vzor 10 · {key} · RUB", WHITE, 1.8)
        d.save()


# 11 – a small book for perfect binding (V2): signatures, collation marks, cover with spine

BOOK_PAGES = 48
BOOK_SPINE = 2.4          # 48 pages = 24 leaves × 0.1 mm (uncoated 80 g/m², bulk 1.25)


def lesson_11():
    w, h, n = 105, 148, BOOK_PAGES
    d = Doc("11_zbornik_A6_48_stran.pdf", w, h, 3, "Malý zborník A6, 48 strán")
    for p in range(1, n + 1):
        right = p % 2 == 1                                   # odd pages are on the right
        d.fill(WHITE)
        if p == 1:
            d.text(w / 2, 100, "Malý zborník", 18, BLUE, "center")
            d.text(w / 2, 92, "vzor 11 · väzba V2 (lepená)", 7, GREY, "center")
        else:
            chapter = (p - 1) // 8 + 1
            if (p - 1) % 8 == 0:                             # a new chapter every 8 pages
                d.fill(TEAL, 0, h - 34, w, 34)
                d.text(w / 2, h - 22, f"Kapitola {chapter}", 13, WHITE, "center")
            else:
                d.text(w / 2, h - 16, f"Kapitola {chapter}", 7, GREY, "center")
            for k in range(10):                              # some body text lines
                d.fill(CMYKColor(0, 0, 0, 0.12), 14, 95 - k * 5, w - 28, 1.8)
        d.text(w / 2, 22, str(p), 30, ORANGE, "center")
        # the head of the page – after folding all heads must point the same way
        band = p > 1 and (p - 1) % 8 == 0
        d.text(w / 2, h - 7, "▲ hlava", 5, WHITE if band else GREY, "center")
        d.text(w - 4 if not right else 4, 8, "chrbát →" if not right else "← chrbát", 5, GREY,
               "right" if not right else "left")
        d.lesson(f"Imprimo · vzor 11 · strana {p} z {n}", GREY, 3)
        if p < n:
            d.page()
    d.save()

    # the opened cover: back | spine | front, spine for 48 pages on uncoated 80 g/m²
    S = BOOK_SPINE
    d = Doc("11_zbornik_A6_obalka.pdf", 2 * w + S, h, 3, "Malý zborník – obálka")
    d.fill(TEAL)
    d.fill(BLUE, w, -3, S, h + 6)                            # the spine
    d.text(w + S + w / 2, 100, "Malý zborník", 18, WHITE, "center")
    d.text(w + S + w / 2, 92, "vzor 11 · obálka", 7, WHITE, "center")
    d.text(w / 2, 74, "zadná strana obálky", 9, WHITE, "center")
    d.text(w / 2, 66, f"chrbát {S:g} mm = 24 listov × 0,1 mm".replace(".", ","), 6, WHITE, "center")
    d.c.saveState()                                          # spine title, top to bottom (ISO 6357)
    d.c.translate((w + S / 2 - 0.6) * mm, (h / 2) * mm)
    d.c.rotate(-90)
    d.c.setFillColor(WHITE)
    d.c.setFont("DejaVu", 4.5)
    d.c.drawCentredString(0, 0, "MALÝ ZBORNÍK · vzor 11")
    d.c.restoreState()
    d.lesson("Imprimo · vzor 11 · obálka (vonkajšia strana)", WHITE, 3)
    d.save()


# Lessons whose PDFs were redesigned by hand (Affinity, Illustrator… – see ZADANIE.md):
# the script no longer overwrites them. Add a lesson number when its new PDFs arrive.
DESIGNED = {"01"}


if __name__ == "__main__":
    import sys
    force = "--all" in sys.argv          # rebuild even the designed ones (old generated look)
    print("Imprimo – vzorové súbory:")
    for f in (lesson_01, lesson_02, lesson_03, lesson_04, lesson_05, lesson_06, lesson_07,
              lesson_08, lesson_09, lesson_10, lesson_11):
        num = f.__name__[-2:]
        if num in DESIGNED and not force:
            print(f"   {num}: navrhnuté ručne – preskočené (--all ich prepíše)")
            continue
        f()
