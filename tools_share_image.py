"""Social media images (1200 × 630): docs/img/share.png (website preview) and
promo/imprimo-kofi.png (Ko-fi / support banner, promo/ is not in git).
Uses the website hero screenshot docs/mac/hero_sk_dark.webp – retake that first.
macOS only (Helvetica Neue, Menlo).  Run from the repository root:
    .venv/bin/python tools_share_image.py
"""
import os, math
from PIL import Image, ImageDraw, ImageFont
HN = "/System/Library/Fonts/HelveticaNeue.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"
S = 3                                     # draw 3× larger, then scale down = smooth edges
W, H = 1200 * S, 630 * S
INK, MUTED = (21, 23, 28), (150, 158, 172)
C, M, Y, K = (0, 148, 200), (207, 0, 114), (240, 189, 0), (240, 242, 245)
WHITE = (255, 255, 255)

def font(size, idx=0, path=HN):
    return ImageFont.truetype(path, size * S, index=idx)

def heart(d, cx, cy, size, fill):
    """Classic heart curve (x = 16 sin³t, y = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t)."""
    k = size / 34.0
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * k, cy - y * k - size * 0.05))
    d.polygon(pts, fill=fill)

def card(out, kofi):
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    shot = Image.open("docs/mac/hero_sk_dark.webp").convert("RGBA")
    sw = 700 * S
    shot = shot.resize((sw, round(shot.height * sw / shot.width)), Image.LANCZOS)
    sx, sy = 615 * S, 110 * S
    im.paste(shot, (sx, sy), shot)
    bx0, by0, _x, _y = shot.getchannel("A").point(lambda a: 255 if a > 230 else 0).getbbox()
    wx, wy = sx + bx0, sy + by0
    mk, lw = (110, 116, 128), 2 * S
    d.line([(wx - 10 * S, wy + 18 * S), (wx - 36 * S, wy + 18 * S)], fill=mk, width=lw)
    d.line([(wx + 18 * S, wy - 10 * S), (wx + 18 * S, wy - 36 * S)], fill=mk, width=lw)
    tx, ty, r = wx - 30 * S, wy - 30 * S, 9 * S
    d.ellipse([tx - r, ty - r, tx + r, ty + r], outline=mk, width=lw)
    d.line([(tx - 16 * S, ty), (tx + 16 * S, ty)], fill=mk, width=lw)
    d.line([(tx, ty - 16 * S), (tx, ty + 16 * S)], fill=mk, width=lw)

    icon = Image.open("imprimo/assets/icon/png/imprimo-512.png").convert("RGBA").resize((88 * S, 88 * S), Image.LANCZOS)
    im.paste(icon, (64 * S, 70 * S), icon)
    d.text((64 * S, 182 * S), "Imprimo", font=font(92, 1), fill=K)
    d.text((66 * S, 292 * S), "Vyraďovanie PDF pre tlač", font=font(36, 0), fill=K)
    d.text((66 * S, 340 * S), "PDF imposition for print", font=font(28, 7), fill=MUTED)
    d.text((66 * S, 404 * S), "vizitky · brožúry · bigy · plagáty", font=font(19, 0, MONO), fill=MUTED)
    d.text((66 * S, 432 * S), "Windows · macOS · Linux · GPL-3.0", font=font(19, 0, MONO), fill=MUTED)
    if kofi:
        f = font(26, 1)
        txt = "Podporte projekt · Support Imprimo"
        x0, top, hgt = 64 * S, 490 * S, 60 * S
        pad, hs, gap = 28 * S, 22 * S, 14 * S       # padding, heart size, heart–text gap
        tw = d.textlength(txt, font=f)
        x1 = x0 + pad + hs + gap + tw + pad
        d.rounded_rectangle([x0, top, x1, top + hgt], radius=hgt // 2, fill=M)
        cy = top + hgt / 2
        heart(d, x0 + pad + hs / 2, cy, hs, WHITE)
        d.text((x0 + pad + hs + gap, cy), txt, font=f, fill=WHITE, anchor="lm")   # vertically centred
    else:
        d.text((66 * S, 500 * S), "imprimo-imposition.github.io/imprimo", font=font(22, 0, MONO), fill=K)
    for i, col in enumerate((C, M, Y, K)):
        d.rectangle([i * W / 4, H - 10 * S, (i + 1) * W / 4, H], fill=col)
    im.resize((1200, 630), Image.LANCZOS).save(out, optimize=True)
    print(out)

os.makedirs("promo", exist_ok=True)
card("promo/imprimo-kofi.png", True)
card("docs/img/share.png", False)
