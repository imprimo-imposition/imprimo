"""Builds the icons for Windows (.ico), macOS (.icns) and Linux (PNG) from the 1024 px master.
Small sizes (16–32 px) get a simplified, bolder target so they stay legible.
Usage: python tools_make_icons.py"""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "imprimo", "assets", "icon")
MASTER = os.path.join(ICON_DIR, "imprimo-1024-master.png")


def small_icon(size, master):
    """Hand-hinted icon for small sizes."""
    ss = 8
    S = size * ss
    bg = master.resize((S, S), Image.LANCZOS)
    # clear the center – the symbol is redrawn
    clean = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = bg.getchannel("A")
    dark = master.crop((60, 60, 160, 964)).resize((S, S), Image.LANCZOS)
    clean.paste(dark, (0, 0), mask)
    d = ImageDraw.Draw(clean)
    c = S / 2
    white = (245, 245, 245, 255)
    through = size >= 32                      # from 32 px the arms cross the ring
    if through:
        w, r_out, arm = S * 0.066, S * 0.175, S * 0.30
    else:                                     # 16–24 px: ring + ticks outside
        w, r_out, arm = max(ss * 1.0, S * (0.115 if size <= 20 else 0.10)), S * (0.25 if size <= 20 else 0.23), S * (0.40 if size <= 20 else 0.38)
    r_in = r_out - w
    d.ellipse((c - r_out, c - r_out, c + r_out, c + r_out), fill=white)
    d.ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=(0, 0, 0, 0))
    # cut the hole back to the dark background
    hole = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hole).ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=255)
    clean.paste(dark, (0, 0), hole)
    d = ImageDraw.Draw(clean)
    for a, b in (((c - arm, c - w / 2), (c - (0 if through else r_out), c + w / 2)),
                 ((c + (0 if through else r_out), c - w / 2), (c + arm, c + w / 2)),
                 ((c - w / 2, c - arm), (c + w / 2, c - (0 if through else r_out))),
                 ((c - w / 2, c + (0 if through else r_out)), (c + w / 2, c + arm))):
        d.rectangle((a[0], a[1], b[0], b[1]), fill=white)
    if through:
        d.rectangle((c - arm, c - w / 2, c + arm, c + w / 2), fill=white)
        d.rectangle((c - w / 2, c - arm, c + w / 2, c + arm), fill=white)
    out = clean.resize((size, size), Image.LANCZOS)
    return out


def padded(master, scale):
    S = 1024
    inner = round(S * scale)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(master.resize((inner, inner), Image.LANCZOS), ((S - inner) // 2,) * 2)
    return out


def mac_master(master):
    """Apple grid: 824 × 824 px body centered on 1024, soft shadow."""
    S, body = 1024, 824
    icon = master.resize((body, body), Image.LANCZOS)
    off = (S - body) // 2
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    a = Image.new("L", (S, S), 0)
    a.paste(icon.getchannel("A").point(lambda v: v * 0.35), (off, off + 10))
    shadow.putalpha(a.filter(ImageFilter.GaussianBlur(14)))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(icon, (off, off))
    return out


def icon_at(size, base, master):
    if size <= 32:
        return small_icon(size, master)
    return base.resize((size, size), Image.LANCZOS)


def main():
    master = Image.open(MASTER).convert("RGBA")
    win = padded(master, 0.94)                     # Windows/Linux: small margin
    mac = mac_master(master)

    # Windows .ico
    ico_sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    imgs = [icon_at(s, win, master) for s in ico_sizes]
    imgs[-1].save(os.path.join(ICON_DIR, "imprimo.ico"), format="ICO",
                  sizes=[(s, s) for s in ico_sizes], append_images=imgs[:-1])

    # macOS .icns
    mac.save(os.path.join(ICON_DIR, "imprimo.icns"), format="ICNS")

    # Linux / application (window, splash screen)
    lin = os.path.join(ICON_DIR, "png")
    os.makedirs(lin, exist_ok=True)
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        icon_at(s, win, master).save(os.path.join(lin, f"imprimo-{s}.png"))
    win.save(os.path.join(ICON_DIR, "imprimo-1024.png"))
    mac.save(os.path.join(ICON_DIR, "imprimo-1024-mac.png"))
    print("hotovo:", ICON_DIR)


if __name__ == "__main__":
    main()
