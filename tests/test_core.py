"""Quick tests of page order and export: python -m pytest tests  (or python tests/test_core.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from imprimo.core import Settings, Plan, build_plan, PageInfo, mm, raw_to_visual


def fake(n, w=148, h=210):
    t = (0, 0, mm(w), mm(h))
    return [PageInfo(i, t, t, t, 0, True, mm(w), mm(h), 0, raw_to_visual(t, 0)) for i in range(n)]


def order(plan, side):
    """Pages on a sheet side from left to right (1-based, 0 = blank)."""
    items = sorted(plan.sides[side].items, key=lambda it: (-it.trim[1], it.trim[0]))
    return [(it.page + 1 if it.page is not None else 0) for it in items]


def test_booklet_8():
    s = Settings(mode="booklet", sheet_w=297, sheet_h=420, duplex_flip="short", bleed=0)
    p = build_plan(fake(8), s)
    assert p.n_sheets == 2
    assert order(p, 0) == [8, 1] and order(p, 1) == [2, 7]
    assert order(p, 2) == [6, 3] and order(p, 3) == [4, 5]


def test_booklet_long_edge_rotates_back():
    s = Settings(mode="booklet", sheet_w=297, sheet_h=420, duplex_flip="long", bleed=0)
    p = build_plan(fake(4), s)
    assert order(p, 1) == [3, 2]                 # mirrored over the top edge
    a = p.sides[1].items[0].matrix
    assert abs(a[0] + 1) < 1e-9 and abs(a[3] + 1) < 1e-9   # rotated by 180°


def test_blanks_before_back():
    s = Settings(mode="booklet", sheet_w=297, sheet_h=420, duplex_flip="short",
                 blanks="before_back", bleed=0)
    p = build_plan(fake(6), s)
    assert order(p, 0) == [6, 1] and order(p, 1) == [2, 0]


def test_cutstack():
    s = Settings(mode="cutstack", cols=2, rows=2, sheet_w=320, sheet_h=450, bleed=0)
    p = build_plan(fake(8, 105, 148), s)
    assert order(p, 0) == [1, 3, 5, 7] and order(p, 1) == [2, 4, 6, 8]


def test_sequential_duplex():
    s = Settings(mode="sequential", cols=2, rows=1, sheet_w=320, sheet_h=450, duplex=True,
                 duplex_flip="long", rotation="0", bleed=0)
    p = build_plan(fake(4), s)
    assert order(p, 0) == [1, 3] and order(p, 1) == [4, 2]     # portrait: mirrored left↔right
    s.rotation = "90"
    p = build_plan(fake(4), s)
    assert p.sheet_w > p.sheet_h                                # landscape
    assert order(p, 0) == [1, 3] and order(p, 1) == [2, 4]     # turned over the top edge


SAMPLES = os.path.join(os.path.dirname(__file__), "samples")


def test_export_profiles():
    import tempfile
    import pikepdf
    from imprimo.core import impose_file
    from imprimo.pdfinfo import detect_profile
    src = os.path.join(SAMPLES, "pdfx4_fogra39_ok.pdf")
    if not os.path.exists(src):
        return
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.pdf")
        impose_file(src, out, Settings())                       # keep from source
        with pikepdf.open(out) as p:
            pr = detect_profile(p)
            assert pr.pdfx == "PDF/X-4" and pr.intents and pr.intents[0].icc is not None
            assert str(p.pdf_version) == "1.6"
        impose_file(src, out, Settings(pdf_standard="x1a2001", icc_profile="bundled"))
        with pikepdf.open(out) as p:
            pr = detect_profile(p)
            assert pr.pdfx == "PDF/X-1a:2001" and str(p.pdf_version) == "1.3"
            assert "/TrimBox" in p.pages[0].obj and str(p.docinfo.Trapped) == "/False"




def test_layers_export():
    import tempfile
    import pikepdf
    from imprimo.core import Layer, analyze, export_outputs
    from imprimo.pdfinfo import detect_profile
    base = os.path.join(SAMPLES, "card_85x55_bleed3.pdf")
    lay = os.path.join(SAMPLES, "card_varnish_spot.pdf")
    if not os.path.exists(lay):
        return
    s = Settings(duplex=True, pdf_standard="x4", icc_profile="bundled")
    with pikepdf.open(base) as src, pikepdf.open(lay) as lp, tempfile.TemporaryDirectory() as d:
        infos = analyze(src)
        plan = build_plan(infos, s)
        written = export_outputs(src, infos, detect_profile(src), plan, s,
                                 [(Layer(lay, kind="varnish", spot="Varnish"), lp, analyze(lp))],
                                 os.path.join(d, "card_imposed.pdf"), True, True, True, "card.pdf")
        names = [os.path.basename(p) for p in written]
        assert names == ["card_imposed.pdf", "card_imposed_varnish.pdf", "card_imposed_layers.pdf"]
        with pikepdf.open(written[-1]) as c:
            ocgs = [str(g.Name) for g in c.Root.OCProperties.OCGs]
            assert len(ocgs) == 2 and detect_profile(c).pdfx == "PDF/X-4"


# --------------------------------------------------------------------------
# Creasing and spot colours

SAMPLES = os.path.join(os.path.dirname(__file__), "samples")


def test_crease_presets():
    from imprimo.crease import parse_positions, preset_positions
    assert preset_positions("half", 210) == [105]
    assert [round(v, 1) for v in preset_positions("z3", 297)] == [99, 198]
    assert preset_positions("c3", 297) == [100, 200]          # panels 100 / 100 / 97
    assert parse_positions("99,5; 198  50") == [99.5, 198, 50]
    try:
        parse_positions("99; abc")
        assert False
    except ValueError:
        pass


def _xs(side):
    return [round(v / mm(1), 1) for v in side.creases_x]


def test_crease_marks_on_sheet():
    # 2 × 2 A5 on 320 × 450, margin (320 − 296) / 2 = 12 mm, crease in half = 74 mm
    s = Settings(sheet_w=320, sheet_h=450, bleed=0, crease="half", duplex=True)
    p = build_plan(fake(1), s)
    assert _xs(p.sides[0]) == [86, 234] and p.sides[0].creases_y == []
    assert _xs(p.sides[1]) == [86, 234]                       # symmetric → same on the back
    s.crease = "c3"
    p = build_plan(fake(1), s)
    assert _xs(p.sides[0]) == [62.3, 112.7, 210.3, 260.7]
    assert _xs(p.sides[1]) == [59.3, 109.7, 207.3, 257.7]     # mirrored on the back
    s.crease, s.crease_pos = "custom", "20; 500"              # 500 is outside the product
    p = build_plan(fake(1), s)
    assert _xs(p.sides[0]) == [32, 180]


def test_crease_follows_rotation():
    s = Settings(sheet_w=450, sheet_h=320, bleed=0, crease="half", rotation="90", cols=2, rows=2)
    p = build_plan(fake(1), s)
    assert p.sides[0].creases_x == [] and len(p.sides[0].creases_y) == 2


def test_crease_not_in_booklet():
    s = Settings(mode="booklet", sheet_w=297, sheet_h=420, bleed=0, crease="half")
    p = build_plan(fake(8), s)
    assert all(not sd.crease_segs for sd in p.sides)


def test_crease_detect():
    import pikepdf
    from imprimo.core import analyze
    from imprimo.crease import detect_any
    want = {"dl_cfold_crease_in_print.pdf": ([100, 200], []),
            "invite_A5_crease.pdf": ([105], []),
            "invite_A5_crease_rot90.pdf": ([], [105]),
            "invite_A5.pdf": ([], [])}
    for name, (v, h) in want.items():
        with pikepdf.open(os.path.join(SAMPLES, name)) as pdf:
            d = detect_any(pdf, analyze(pdf))
            assert (d.vertical, d.horizontal) == (v, h), (name, d)


def test_crease_pdf_mode_export():
    import pikepdf
    from imprimo.core import impose_file
    import tempfile
    s = Settings(crease="pdf", sheet_w=320, sheet_h=450)
    with tempfile.TemporaryDirectory() as d:
        plan = impose_file(os.path.join(SAMPLES, "dl_cfold_crease_in_print.pdf"),
                           os.path.join(d, "dl_imposed.pdf"), s)
        assert s.crease_dir == "v" and s.crease_pos == "100; 200"
        assert plan.sides[0].crease_segs


def test_spot_library():
    from imprimo.spots import SPOTS, ase_bytes, kind_of, read_ase
    sw = read_ase(ase_bytes())
    assert [n for n, *_ in sw] == [sp.name for sp in SPOTS]
    assert all(model == "CMYK" and ctype == 1 for _, model, _, ctype in sw)   # 1 = spot
    assert kind_of("Crease") == kind_of("/bigovanie") == kind_of("BIG") == "crease"
    assert kind_of("Výsek") == kind_of("Cut Contour") == "cut"
    assert kind_of("PANTONE 185 C") is None


def test_technical_spot_warning():
    import pikepdf
    from imprimo.preflight import evaluate, scan
    with pikepdf.open(os.path.join(SAMPLES, "dl_cfold_crease_in_print.pdf")) as pdf:
        F = scan(pdf)
    assert any(lvl == "warn" and "Crease" in txt for lvl, txt in evaluate(F, None, {1}))
    with pikepdf.open(os.path.join(SAMPLES, "card_varnish_spot.pdf")) as pdf:
        F = scan(pdf)
    assert not any("Varnish" in txt and lvl == "warn" for lvl, txt in evaluate(F, None, {1}))


# --------------------------------------------------------------------------
# Generated bleed

def test_bleed_patches():
    from imprimo.core import bleed_patches
    t = (0, 0, mm(85), mm(55))
    no_bleed = PageInfo(0, t, t, t, 0, True, mm(85), mm(55), 0, raw_to_visual(t, 0))
    assert len(bleed_patches(no_bleed, mm(3), "mirror")) == 8          # 4 sides + 4 corners
    assert len(bleed_patches(no_bleed, mm(3), "stretch")) == 8
    assert bleed_patches(no_bleed, mm(3), "off") == []
    lim = (-mm(3), -mm(3), mm(88), mm(58))
    full = PageInfo(0, t, lim, lim, 0, True, mm(85), mm(55), mm(3), raw_to_visual(t, 0))
    assert bleed_patches(full, mm(3), "mirror") == []                  # enough bleed already
    M, strip = bleed_patches(no_bleed, mm(3), "mirror")[1]             # left side
    assert M == (-1, 0, 0, 1, 0, 0) and abs(strip[0] + mm(3)) < 1e-6


def _pixel_outside_trim(method):
    """Colour 1.5 mm left of the first card's trim on the exported sheet."""
    import tempfile
    import pypdfium2 as pdfium
    from imprimo.core import impose_file
    s = Settings(bleed_fill=method, sheet_w=320, sheet_h=450, cols=2, rows=2,
                 gutter_x=10, gutter_y=10, bleed=3, crop_marks=False, slug=False)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "o.pdf")
        plan = impose_file(os.path.join(SAMPLES, "card_no_bleed.pdf"), out, s)
        x0, y0, x1, y1 = plan.sides[0].items[0].trim
        k = 2
        img = pdfium.PdfDocument(out)[0].render(scale=k).to_pil().convert("RGB")
        return img.getpixel((int((x0 - mm(1.5)) * k), int((plan.sheet_h - (y0 + y1) / 2) * k)))


def test_bleed_fill_export():
    assert _pixel_outside_trim("off") == (255, 255, 255)
    assert _pixel_outside_trim("mirror") != (255, 255, 255)
    assert _pixel_outside_trim("stretch") != (255, 255, 255)
    s = Settings(bleed_fill="mirror", bleed=3)
    import pikepdf
    from imprimo.core import analyze
    with pikepdf.open(os.path.join(SAMPLES, "card_no_bleed.pdf")) as pdf:
        p = build_plan(analyze(pdf), s)
    assert any("zrkadl" in w or "mirror" in w for w in p.warnings)


# --------------------------------------------------------------------------
# Job presets

def test_builtin_presets():
    from imprimo import presets
    from imprimo.core import SHEET_PRESETS
    from imprimo.i18n import STRINGS
    for p in presets.BUILTIN:
        s = p.to_settings()
        assert p.sheet_key in SHEET_PRESETS and p.builtin in STRINGS["sk"]
        build_plan(fake(8, 90, 50) if s.mode != "booklet" else fake(8), s)   # must plan
    by = {p.builtin: p.to_settings() for p in presets.BUILTIN}
    assert build_plan(fake(2, 90, 50), by["preset_cards"]).per_sheet == 21    # 3 mm bleed
    assert build_plan(fake(2, 85, 55), by["preset_cards"]).per_sheet == 21
    assert build_plan(fake(2, 90, 50), by["preset_cards2"]).per_sheet == 24   # 2 mm bleed
    assert not by["preset_cards_1s"].duplex and not by["preset_cards2_1s"].duplex
    assert build_plan(fake(1, 90, 50), by["preset_cards2_1s"]).per_sheet == 24
    dl = next(p for p in presets.BUILTIN if p.builtin == "preset_dl").to_settings()
    assert dl.crease == "c3" and dl.duplex


def test_preset_roundtrip_and_merge():
    from imprimo import presets
    s = Settings(mode="cutstack", bleed=2, page_range="1-4")
    p = presets.from_settings("Lístky", s, "A4 (210 × 297)")
    assert "page_range" not in p.settings
    back = presets.loads(presets.file_text([p]))[0]
    assert back.name == "Lístky" and back.sheet_key == "A4 (210 × 297)"
    assert presets.same(back.to_settings(), s)               # page_range is ignored
    s2 = Settings(mode="cutstack", bleed=3)
    assert not presets.same(back.to_settings(), s2)
    own, n = presets.merge([back], presets.loads(presets.file_text([p])))
    assert n == 0 and len(own) == 1                           # identical → skipped
    other = presets.from_settings("Lístky", s2, "A4 (210 × 297)")
    own, n = presets.merge(own, [other])
    assert n == 1 and [q.name for q in own] == ["Lístky", "Lístky (2)"]
    try:
        presets.loads('{"format": "something-else"}')
        assert False
    except ValueError:
        pass


# --------------------------------------------------------------------------
# Poster in pieces

def test_tile_names():
    from imprimo.core import tile_name
    assert [tile_name(0, 0), tile_name(1, 2), tile_name(25, 0), tile_name(26, 0)] == ["A1", "B3", "Z1", "AA1"]


def test_tile_plan():
    # A2 (420 × 594) at 100 % on A4, 10 mm margin and 10 mm overlap:
    # landscape area 277 × 190 → 2 × 4 = 8 pieces (portrait would be 3 × 3 = 9)
    s = Settings(mode="tile", sheet_w=210, sheet_h=297, margin=10, tile_overlap=10, bleed=3)
    p = build_plan(fake(1, 420, 594), s)
    assert (p.cols, p.rows, p.n_sheets) == (2, 4, 8)
    assert round(p.sheet_w / mm(1)) == 297
    a1, a2 = p.sides[0], p.sides[1]
    assert a1.tile == (0, 0, 4, 2) and a2.tile == (0, 1, 4, 2)
    # neighbouring pieces show the poster shifted by (area − overlap) = 267 mm
    shift = a1.items[0].matrix[4] - a2.items[0].matrix[4]
    assert abs(shift / mm(1) - 267) < 0.01
    assert a1.folds_x and not a2.folds_x                     # glue mark only where a piece follows
    s.tile_scale = 40                                        # 168 × 238 mm fits the 190 × 277 area
    assert build_plan(fake(1, 420, 594), s).n_sheets == 1
    s.tile_scale = 50                                        # exactly A4 – but the margin doesn't
    assert build_plan(fake(1, 420, 594), s).n_sheets > 1     # print, so it needs more pieces
    s.tile_scale, s.margin, s.tile_overlap = 100, 10, 300   # an overlap bigger than the piece
    try:
        build_plan(fake(1, 420, 594), s)
        assert False
    except Exception as e:
        assert "300" in str(e)


def test_poster_preset_sheet():
    from imprimo import presets
    s = next(p for p in presets.BUILTIN if p.builtin == "preset_poster").to_settings()
    assert (s.sheet_w, s.sheet_h, s.mode) == (210, 297, "tile")


# --------------------------------------------------------------------------
# Sample files (examples/)

def test_examples():
    import pikepdf
    from imprimo import presets
    from imprimo.core import analyze
    from imprimo.examples_dialog import LESSONS, examples_dir
    from imprimo.preflight import evaluate, scan
    d = examples_dir()
    keys = {p.builtin for p in presets.BUILTIN}
    for num, pdf, preset in LESSONS:
        assert preset is None or preset in keys
        with pikepdf.open(os.path.join(d, pdf)) as src:
            F = scan(src)
            bad = [txt for lvl, txt in evaluate(F, None, set(range(1, len(src.pages) + 1)))
                   if lvl in ("warn", "error")]
            if num == "08":
                assert len(bad) >= 4, bad                      # wrong on purpose
            else:
                assert not bad, (pdf, bad)                     # clean CMYK, embedded font
            if preset:
                s = next(p for p in presets.BUILTIN if p.builtin == preset).to_settings()
                build_plan(analyze(src), s)
    from imprimo.crease import detect_any
    for name, want in (("03_pozvanka_A5_bigy.pdf", [105.0]), ("04_DL_skladacka_bigy.pdf", [100.0, 200.0])):
        with pikepdf.open(os.path.join(d, name)) as src:
            assert detect_any(src, analyze(src)).vertical == want


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("OK", k)
