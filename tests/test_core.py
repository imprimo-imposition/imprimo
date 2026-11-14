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


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("OK", k)
