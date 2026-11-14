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


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("OK", k)
