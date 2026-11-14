"""Sample PDFs for testing: business cards, A5 booklet, rotated page, no TrimBox,
PDF/X samples, layer samples (varnish) and crease samples (DL roll fold, invitation)."""
import os

import pikepdf
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples")
ASSETS = os.path.join(HERE, "..", "imprimo", "assets")
os.makedirs(OUT, exist_ok=True)


def boxes(path, bleed_mm):
    """Sets TrimBox (MediaBox minus bleed) and BleedBox (= MediaBox) on every page."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for pg in pdf.pages:
            x0, y0, x1, y1 = [float(v) for v in pg.mediabox]
            b = bleed_mm * mm
            pg.obj.TrimBox = pikepdf.Array([x0 + b, y0 + b, x1 - b, y1 - b])
            pg.obj.BleedBox = pikepdf.Array([x0, y0, x1, y1])
        pdf.save(path)


def card_page(c, w, h, b, color, title):
    c.setFillColor(color)
    c.rect(0, 0, w + 2*b, h + 2*b, stroke=0, fill=1)
    c.setStrokeColor(CMYKColor(0, 0, 0, 1))
    c.setLineWidth(0.3)
    c.rect(b + 4*mm, b + 4*mm, w - 8*mm, h - 8*mm)          # safe area
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(b + 7*mm, b + h - 14*mm, title)
    c.setFont("Helvetica", 8)
    c.drawString(b + 7*mm, b + 7*mm, "BOTTOM")
    c.drawString(b + 7*mm, b + h - 20*mm, "^ TOP")


def make_cards():
    p = os.path.join(OUT, "card_85x55_bleed3.pdf")
    w, h, b = 85*mm, 55*mm, 3*mm
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    card_page(c, w, h, b, CMYKColor(0, 0.6, 0.1, 0), "FRONT page 1")
    c.showPage()
    card_page(c, w, h, b, CMYKColor(0.6, 0, 0.1, 0), "BACK page 2")
    c.showPage()
    c.save()
    boxes(p, 3)


def make_booklet(n=10):
    p = os.path.join(OUT, f"booklet_A5_{n}p.pdf")
    w, h, b = 148*mm, 210*mm, 3*mm
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    for i in range(1, n + 1):
        hue = (i * 0.09) % 1
        c.setFillColor(CMYKColor(hue * 0.5, 0.15, 0.5 - hue * 0.4, 0))
        c.rect(0, 0, w + 2*b, h + 2*b, stroke=0, fill=1)
        # spine: odd pages on the left, even pages on the right
        c.setFillColor(CMYKColor(0, 0, 0, 0.8))
        if i % 2:
            c.rect(0, 0, b + 6*mm, h + 2*b, stroke=0, fill=1)
        else:
            c.rect(b + w - 6*mm, 0, 6*mm + b, h + 2*b, stroke=0, fill=1)
        c.setFillColor(CMYKColor(0, 0, 0, 1))
        c.setFont("Helvetica-Bold", 120)
        c.drawCentredString(b + w/2, b + h/2 - 40, str(i))
        c.setFont("Helvetica", 12)
        c.drawCentredString(b + w/2, b + h - 15*mm, "^ TOP")
        c.drawCentredString(b + w/2, b + 12*mm, "spine = dark strip")
        c.showPage()
    c.save()
    boxes(p, 3)


def make_rotated():
    p = os.path.join(OUT, "rotate90_page.pdf")
    w, h, b = 85*mm, 55*mm, 3*mm
    # drawn in portrait, shown in landscape thanks to /Rotate 90
    c = canvas.Canvas(p, pagesize=(h + 2*b, w + 2*b))
    c.setFillColor(CMYKColor(0, 0.2, 0.9, 0))
    c.rect(0, 0, h + 2*b, w + 2*b, stroke=0, fill=1)
    c.translate(h + 2*b, 0)
    c.rotate(90)                    # content rotated so it reads upright after /Rotate 90
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(b + 7*mm, b + h - 14*mm, "ROTATE 90")
    c.setFont("Helvetica", 8)
    c.drawString(b + 7*mm, b + h - 20*mm, "^ TOP")
    c.showPage()
    c.save()
    boxes(p, 3)
    with pikepdf.open(p, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(p)


def make_no_trimbox():
    p = os.path.join(OUT, "no_trimbox_A6.pdf")
    c = canvas.Canvas(p, pagesize=(105*mm, 148*mm))
    for i in range(1, 9):
        c.setFont("Helvetica-Bold", 60)
        c.drawCentredString(52.5*mm, 70*mm, str(i))
        c.showPage()
    c.save()


# --- PDF/X samples ----------------------------------------------------------
def mark_pdfx4(path, icc_path):
    """Tags a PDF as PDF/X-4 with an output intent (simulates an InDesign export)."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with open(icc_path, "rb") as f:
            prof = pdf.make_stream(f.read())
        prof.N = 4
        oi = pikepdf.Dictionary(Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX,
                                OutputConditionIdentifier="FOGRA39", RegistryName="http://www.color.org",
                                OutputCondition="Coated FOGRA39", DestOutputProfile=prof)
        pdf.Root.OutputIntents = pikepdf.Array([pdf.make_indirect(oi)])
        pdf.docinfo.GTS_PDFXVersion = "PDF/X-4"
        pdf.docinfo.Creator = "Adobe InDesign 20.4 (Macintosh)"
        pdf.docinfo.Producer = "Adobe PDF Library 18.0"
        pdf.save(path)


def make_pdfx_samples():
    from PIL import Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(ASSETS, "DejaVuSansCondensed.ttf")))
    w, h, b = 85*mm, 55*mm, 3*mm
    # 1) clean CMYK, embedded font, tagged PDF/X-4 + FOGRA39
    p = os.path.join(OUT, "pdfx4_fogra39_ok.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    c.setFillColor(CMYKColor(0.1, 0, 0.6, 0))
    c.rect(0, 0, w + 2*b, h + 2*b, stroke=0, fill=1)
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.setFont("DejaVu", 14)
    c.drawString(b + 7*mm, b + h - 14*mm, "PDF/X-4 OK – čšťž")
    c.showPage()
    c.save()
    boxes(p, 3)
    mark_pdfx4(p, os.path.join(ASSETS, "FOGRA39L_coated.icc"))
    # 2) problems: low-resolution RGB image, transparency, non-embedded Helvetica
    ip = os.path.join(OUT, "_tmp_rgb.png")
    Image.new("RGB", (120, 80), (220, 40, 40)).save(ip)
    p = os.path.join(OUT, "problem_rgb_transparency.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    c.setFillColorRGB(0.2, 0.5, 0.9)
    c.rect(0, 0, w + 2*b, h + 2*b, stroke=0, fill=1)
    c.drawImage(ip, b + 40*mm, b + 10*mm, 40*mm, 26.6*mm)
    c.setFillAlpha(0.5)
    c.setFillColorCMYK(0, 1, 0, 0)
    c.circle(b + 20*mm, b + 25*mm, 12*mm, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorCMYK(0, 0, 0, 1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(b + 6*mm, b + 6*mm, "RGB + alpha + Helvetica")
    c.showPage()
    c.save()
    boxes(p, 3)
    os.remove(ip)


# --- layer samples (varnish) ------------------------------------------------
def make_layer_samples():
    from reportlab.lib.colors import CMYKColorSep
    w, h, b = 85*mm, 55*mm, 3*mm
    # spot varnish with overprint – the right way
    p = os.path.join(OUT, "card_varnish_spot.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    for _ in range(2):
        c.setFillColor(CMYKColorSep(0, 1, 0, 0, spotName="Varnish", density=1))
        c.setFillOverprint(True)
        c.rect(b + 6*mm, b + h - 17*mm, 60*mm, 6*mm, stroke=0, fill=1)   # over the title
        c.circle(b + w - 14*mm, b + 14*mm, 8*mm, stroke=0, fill=1)
        c.showPage()
    c.save()
    boxes(p, 3)
    # plain black "varnish" without spot colour and overprint – wrong
    p = os.path.join(OUT, "card_varnish_wrong_black.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    c.rect(b + 6*mm, b + h - 17*mm, 60*mm, 6*mm, stroke=0, fill=1)
    c.showPage()
    c.save()
    boxes(p, 3)


def _crease_line(c, x, top, colour):
    c.setStrokeColor(colour)
    c.setStrokeOverprint(True)
    c.setLineWidth(0.25)
    c.line(x, 0, x, top)


def make_crease_samples():
    from reportlab.lib.colors import CMYKColorSep
    crease = CMYKColorSep(1, 0, 1, 0, spotName="Crease", density=1)
    b = 3*mm

    # DL roll (C) fold from A4 landscape: panels 100 / 100 / 97 mm, creases drawn in the
    # print PDF (the wrong-but-common way – preflight warns, Imprimo still reads them)
    w, h = 297*mm, 210*mm
    p = os.path.join(OUT, "dl_cfold_crease_in_print.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    for i, (x0, pw, col) in enumerate(((0, 100, (0.1, 0.3, 0.6, 0)), (100, 100, (0.5, 0.1, 0.1, 0)),
                                       (200, 97, (0.2, 0.6, 0.1, 0)))):
        c.setFillColor(CMYKColor(*col))
        c.rect(b + x0*mm - (b if i == 0 else 0), 0, pw*mm + (b if i in (0, 2) else 0), h + 2*b,
               stroke=0, fill=1)
        c.setFillColor(CMYKColor(0, 0, 0, 1))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(b + (x0 + 8)*mm, b + h - 20*mm, f"panel {i + 1} – {pw} mm")
    for x in (100, 200):
        _crease_line(c, b + x*mm, h + 2*b, crease)
    c.showPage()
    c.save()
    boxes(p, 3)

    # invitation A5 landscape folded in half: print PDF + a separate crease PDF (the right way)
    w, h = 210*mm, 148*mm
    p = os.path.join(OUT, "invite_A5.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    card_page(c, w, h, b, CMYKColor(0, 0.15, 0.4, 0), "INVITATION – front | inside")
    c.showPage()
    c.save()
    boxes(p, 3)
    p = os.path.join(OUT, "invite_A5_crease.pdf")
    c = canvas.Canvas(p, pagesize=(w + 2*b, h + 2*b))
    _crease_line(c, b + 105*mm, h + 2*b, crease)
    c.showPage()
    c.save()
    boxes(p, 3)
    # the same crease PDF with /Rotate 90 – the crease becomes horizontal, 105 mm from the top
    q = os.path.join(OUT, "invite_A5_crease_rot90.pdf")
    with pikepdf.open(p) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(q)


if __name__ == "__main__":
    make_cards()
    make_booklet(10)
    make_rotated()
    make_no_trimbox()
    make_pdfx_samples()
    make_layer_samples()
    make_crease_samples()
    print(sorted(os.listdir(OUT)))
