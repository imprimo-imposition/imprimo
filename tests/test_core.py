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


def _used_ocgs(pdf):
    """objgen of every OCG that page content reaches through /Properties."""
    import pikepdf
    found, seen = set(), set()

    def walk(res):
        if not isinstance(res, pikepdf.Dictionary):
            return
        for g in res.get("/Properties", {}).values():
            if g.get("/Type") == "/OCG":
                found.add(g.objgen)
        for x in res.get("/XObject", {}).values():
            if x.objgen not in seen:
                seen.add(x.objgen)
                walk(x.get("/Resources"))

    for pg in pdf.pages:
        walk(pg.obj.get("/Resources"))
    return found


def test_source_layers_direct_ocproperties():
    """Illustrator/Affinity write /OCProperties as a direct object; its layers must survive."""
    import tempfile
    import pikepdf
    from pikepdf import Array, Dictionary, Name
    from imprimo.core import impose_file
    with tempfile.TemporaryDirectory() as d:
        src = pikepdf.new()
        g1 = src.make_indirect(Dictionary(Type=Name.OCG, Name=pikepdf.String("Art")))
        g2 = src.make_indirect(Dictionary(Type=Name.OCG, Name=pikepdf.String("Text")))
        content = (b"/OC /MC0 BDC 0 0 0 1 k 0 0 100 100 re f EMC "
                   b"/OC /MC1 BDC 0 1 0 0 k 10 10 50 50 re f EMC")
        page = Dictionary(Type=Name.Page, MediaBox=Array([0, 0, mm(85), mm(55)]),
                          Resources=Dictionary(Properties=Dictionary(MC0=g1, MC1=g2)),
                          Contents=src.make_stream(content))
        src.pages.append(pikepdf.Page(page))
        src.Root.OCProperties = Dictionary(          # direct, not an indirect reference
            OCGs=Array([g1, g2]), D=Dictionary(Order=Array([g1, g2]), ON=Array([g1, g2])))
        assert not src.Root.OCProperties.is_indirect
        sp, op = os.path.join(d, "layers.pdf"), os.path.join(d, "layers_imposed.pdf")
        src.save(sp)
        impose_file(sp, op, Settings(pdf_standard="x4", icc_profile="bundled"))
        with pikepdf.open(op) as p:
            assert "/OCProperties" in p.Root
            listed = {g.objgen for g in p.Root.OCProperties.OCGs}
            used = _used_ocgs(p)
            assert len(used) == 2 and used <= listed
            assert {str(g.Name) for g in p.Root.OCProperties.OCGs} == {"Art", "Text"}
        impose_file(sp, op, Settings(pdf_standard="x1a2001", icc_profile="bundled"))
        with pikepdf.open(op) as p:
            assert "/OCProperties" not in p.Root       # no layers in PDF/X-1a


# --------------------------------------------------------------------------
# Creasing and spot colors

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
    """Color 1.5 mm left of the first card's trim on the exported sheet."""
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
        if s.mode == "gang":
            from imprimo.core import GangJob
            build_plan(fake(2, 90, 50), s, [GangJob("a", [0, 1], 100)])
        else:
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
    assert abs(p.utilization - 0.5) < 0.01                    # 420×594 over 8 × A4 = 50 %
    assert round(p.sheet_w / mm(1)) == 297
    a1, a2 = p.sides[0], p.sides[1]
    assert a1.tile == (0, 0, 4, 2) and a2.tile == (0, 1, 4, 2)
    # neighboring pieces show the poster shifted by (area − overlap) = 267 mm
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
# Gang run

def test_gang_allocate():
    from imprimo.core import gang_allocate
    assert gang_allocate([100, 100, 100], 24) == [8, 8, 8]
    assert gang_allocate([500, 100, 100], 24) == [16, 4, 4]
    assert gang_allocate([10, 10, 10, 10], 24) == [6, 6, 6, 6]   # spare slots spread evenly
    assert gang_allocate([1000, 1], 21) == [20, 1]


def test_gang_plan():
    from imprimo.core import GangJob
    s = Settings(mode="gang", duplex=True, bleed=2, gutter_x=4, gutter_y=4)
    jobs = [GangJob("jana", [0, 1], 100), GangJob("peter", [2, 3], 250), GangJob("eva", [4], 50)]
    p = build_plan(fake(5, 90, 50), s, jobs)
    assert p.per_sheet == 24 and p.n_sheets == 17                 # 255 / 15 → 17
    assert [k for _n, _q, k, _m in p.gang] == [6, 15, 3]
    assert [it.page for it in p.sides[0].items] == [0] * 6 + [2] * 15 + [4] * 3
    assert [it.page for it in p.sides[1].items][:7] == [1] * 6 + [3]
    assert any("C" in w for w in p.warnings)                       # eva has no back
    try:
        build_plan(fake(30, 90, 50), s, [GangJob(str(i), [i], 10) for i in range(25)])
        assert False
    except Exception as e:
        assert "25" in str(e)


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
                if s.mode == "gang":
                    from imprimo.core import GangJob
                    build_plan(analyze(src), s, [GangJob(pdf, [0, 1], 100)])
                else:
                    build_plan(analyze(src), s)
    # exact trim sizes (mm) as in examples/ZADANIE.md – catches apps that round the page,
    # e.g. Affinity exporting 90 × 50.038 mm (examples/affinity-page-size.md); 08 is free
    sizes = {"01": (90, 50), "02": (90, 50), "03": (210, 148), "04": (297, 210),
             "05": (148, 210), "06": (140, 50), "07": (90, 50), "09": (420, 594),
             "10": (90, 50), "11": (105, 148)}
    for name in sorted(os.listdir(d)):
        want = sizes.get(name[:2])
        if not name.endswith(".pdf") or want is None or name == "11_zbornik_A6_obalka.pdf":
            continue
        with pikepdf.open(os.path.join(d, name)) as src:
            for i in analyze(src):
                got = (i.vis_w / mm(1), i.vis_h / mm(1))
                assert all(abs(g - w) < 0.005 for g, w in zip(got, want)), \
                    (name, i.index + 1, [round(g, 3) for g in got], want)
    # lesson 11: 6 signatures of 8 pages on SRA3, the cover fits the computed 2.4 mm spine
    import shutil, tempfile
    from imprimo.cover import caliper, prepare, spine_width
    with pikepdf.open(os.path.join(d, "11_zbornik_A6_48_stran.pdf")) as src:
        s = next(p for p in presets.BUILTIN if p.builtin == "preset_signatures").to_settings()
        assert build_plan(analyze(src), s).signatures == [8] * 6
    spine = round(spine_width(48, caliper(80, 1.25)), 1)
    tmp = os.path.join(tempfile.mkdtemp(), "c.pdf")
    shutil.copy(os.path.join(d, "11_zbornik_A6_obalka.pdf"), tmp)
    r = prepare(tmp, 105, 148, spine)
    assert spine == 2.4 and r.path == tmp and not r.warnings
    from imprimo.crease import detect_any
    for name, want in (("03_pozvanka_A5_bigy.pdf", [105.0]), ("04_DL_skladacka_bigy.pdf", [100.0, 200.0])):
        with pikepdf.open(os.path.join(d, name)) as src:
            assert detect_any(src, analyze(src)).vertical == want


def test_signature_schemes():
    from imprimo.signatures import scheme, split
    for n in (4, 8, 16, 32):
        sc = scheme(n)
        pages = sorted([p.front for p in sc.panels] + [p.back for p in sc.panels])
        assert pages == list(range(1, n + 1))
        for b in sc.spine_cols:                 # across a spine fold: n + 1
            for r in range(sc.rows):
                assert sc.at(b - 1, r).front + sc.at(b, r).front == n + 1
        assert max(f for _, _, f in sc.fold_order) == len(sc.folds)
    # the usual schemes F8-7 and F16-7 (top row upside down)
    sc = scheme(8)
    assert [sc.at(c, 1).front for c in range(2)] == [5, 4] and [sc.at(c, 0).front for c in range(2)] == [8, 1]
    assert all(sc.at(c, 1).rot == 180 and sc.at(c, 0).rot == 0 for c in range(2))
    sc = scheme(16)
    assert [sc.at(c, 0).front for c in range(4)] == [4, 13, 16, 1]
    assert [sc.at(c, 1).front for c in range(4)] == [5, 12, 9, 8]
    assert sc.spine_cols == [1, 3]
    assert split(104, 16) == [16] * 6 + [8] and split(12, 32) == [8, 4] and split(4, 16) == [4]


def test_signatures_plan():
    # A5 on SRA3: only 4-page signatures fit; spine milled 3 mm, no crop marks there
    s = Settings(mode="signatures", sheet_w=320, sheet_h=450, bleed=3, milling=3)
    p = build_plan(fake(12), s)
    assert p.signatures == [4, 4, 4] and p.n_sheets == 3 and len(p.sides) == 6
    assert order(p, 0) == [4, 1] and sorted(order(p, 1)) == [2, 3] and order(p, 2) == [8, 5]
    a, b = sorted(p.sides[0].items, key=lambda it: it.trim[0])
    assert abs((b.trim[0] - a.trim[2]) - mm(6)) < 0.01          # 2 × milling
    spine = p.sides[0].spine_x[0]
    assert all(abs(x - spine) > mm(3) for x in p.sides[0].cuts_x)
    assert p.sides[0].collation and p.sides[1].collation is None
    assert abs((p.sides[0].collation[0] + p.sides[0].collation[2]) / 2 - spine) < 0.01
    # collation marks step down from one signature to the next
    assert p.sides[2].collation[3] < p.sides[0].collation[3]
    # sewn: pages meet at the fold
    s.binding, s.sig_pages = "sewn", 4
    a, b = sorted(build_plan(fake(12), s).sides[0].items, key=lambda it: it.trim[0])
    assert abs(b.trim[0] - a.trim[2]) < 0.01
    # B2: 16-page signatures, the rest in a smaller one; a forced size that does not fit = error
    s = Settings(mode="signatures", sheet_w=500, sheet_h=700)
    p = build_plan(fake(20), s)
    assert p.signatures == [16, 4] and p.pages == 20
    s = Settings(mode="signatures", sheet_w=320, sheet_h=450, sig_pages=16)
    try:
        build_plan(fake(32), s)
        assert False, "16 pages A5 must not fit on SRA3"
    except Exception as e:
        assert "16" in str(e)


def test_signatures_render_dummy():
    import pikepdf
    from imprimo.core import render_sources
    s = Settings(mode="signatures", sheet_w=500, sheet_h=700)
    p = build_plan(fake(16), s)
    nos = sorted(it.no for sd in p.sides for it in sd.items)
    assert nos == list(range(1, 17))
    out = render_sources([], p, s, dummy=True, label="dummy")
    assert len(out.pages) == len(p.sides)
    first = out.pages[0].Contents.read_bytes().decode("latin-1")
    assert "0 0 0 1 k" in first and "(1) Tj" in first


def _pdf_pages(path, sizes_mm, bleed_mm=3):
    """A PDF with pages of the given trim sizes, bleed around, a different fill per page."""
    import pikepdf
    pdf = pikepdf.new()
    for k, (w, h) in enumerate(sizes_mm):
        b = mm(bleed_mm)
        W, H = mm(w) + 2 * b, mm(h) + 2 * b
        pg = pdf.add_blank_page(page_size=(W, H))
        pg.obj.TrimBox = pikepdf.Array([b, b, W - b, H - b])
        pg.obj.BleedBox = pikepdf.Array([0, 0, W, H])
        pg.obj.Contents = pdf.make_stream(f"{0.2 * k} 0 0 0 k 0 0 {W} {H} re f".encode())
    pdf.save(path)


def test_cover():
    import tempfile, pikepdf
    from imprimo.cover import assemble, caliper, crease_positions, spine_width, write_template
    from imprimo.core import ImposeError, analyze
    assert abs(caliper(80, 1.25) - 0.1) < 1e-9
    assert abs(spine_width(128, 0.1) - 6.4) < 1e-9 and abs(spine_width(127, 0.1) - 6.4) < 1e-9
    assert crease_positions(148, 6.4) == [148, 154.4]
    assert crease_positions(148, 6.4, 7) == [141, 148, 154.4, 161.4]
    d = tempfile.mkdtemp()
    tpl = os.path.join(d, "tpl.pdf")
    write_template(tpl, 148, 210, 6.4, 3, 7, "info")
    with pikepdf.open(tpl) as pdf:
        pg = pdf.pages[0]
        assert abs(float(pg.TrimBox[2]) - float(pg.TrimBox[0]) - mm(302.4)) < 0.01
        assert abs(float(pg.MediaBox[2]) - mm(308.4)) < 0.01
        assert "/OCProperties" in pdf.Root
    # front + back as pages of the book size
    src = os.path.join(d, "fb.pdf")
    _pdf_pages(src, [(148, 210)] * 2)
    out = os.path.join(d, "fb_cover.pdf")
    r = assemble(src, out, 148, 210, 6.4)
    assert r.blank_spine and not r.two_sided and r.spine_mm == 6.4
    with pikepdf.open(out) as pdf:
        info = analyze(pdf)[0]
        assert abs(info.vis_w - mm(302.4)) < 0.01 and abs(info.vis_h - mm(210)) < 0.01
        body = pdf.pages[0].Contents.read_bytes().decode()
        # back (page 2) on the left, front (page 1) on the right
        assert body.index("/P1 Do") < body.index("/P0 Do")
    # 4 pages: printed inside too
    _pdf_pages(src, [(148, 210)] * 4)
    r = assemble(src, out, 148, 210, 6.4)
    assert r.two_sided
    # the whole cover as one page: its spine is used, with a warning when it differs
    _pdf_pages(src, [(300.0, 210)])
    r = assemble(src, out, 148, 210, 6.4)
    assert not r.blank_spine and r.spine_mm == 4.0 and r.warnings
    # one step: a whole cover is used as it is, separate pages are joined next to it
    from imprimo.cover import prepare
    r = prepare(src, 148, 210, 4.0)
    assert r.path == src and not r.blank_spine
    _pdf_pages(src, [(148, 210)] * 2)
    r1, r2 = prepare(src, 148, 210, 4.0), prepare(src, 148, 210, 4.0)
    assert r1.blank_spine and os.path.dirname(r1.path) == d and r1.path != r2.path
    # wrong size
    _pdf_pages(src, [(105, 148)] * 2)
    try:
        assemble(src, out, 148, 210, 6.4)
        assert False
    except ImposeError:
        pass


def test_report_info():
    from imprimo.report_dialog import changed_settings, info_text, system_name
    assert changed_settings(Settings()) == "–"
    assert changed_settings(Settings(mode="signatures", bleed=2.0)) == "mode=signatures, bleed=2"
    txt = info_text(None, with_log=False)
    assert txt.startswith("Imprimo ") and "System: " in txt and system_name() in txt


def test_page_size_label():
    from imprimo.preview import page_size_label
    assert page_size_label(mm(148), mm(210)) == "A5" and page_size_label(mm(210), mm(148)) == "A5"
    assert page_size_label(mm(99), mm(210)) == "DL" and page_size_label(mm(90), mm(50)) == "90×50"


def test_updates():
    import json, tempfile
    from imprimo import updates
    assert updates.is_newer("0.8.1", "0.8.0") and updates.is_newer("0.10.0", "0.9.9")
    assert not updates.is_newer("0.8.0", "0.8.0") and not updates.is_newer("v0.7.9", "0.8.0")
    info = {"version": "9.0.0", "downloads": {"win": "W", "mac": "M", "linux": "L"},
            "notes": {"sk": ["novinka"], "en": ["news"]}}
    assert updates.download_url(info) in ("W", "M", "L")
    assert updates.notes(info, "sk") == ["novinka"] and updates.notes(info, "de") == ["news"]
    if updates._curl():                    # the fallback used by the packaged app
        p = os.path.join(tempfile.mkdtemp(), "latest.json")
        with open(p, "w") as f:
            json.dump(info, f)
        assert json.loads(updates._via_curl("file://" + p, 5))["version"] == "9.0.0"


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("OK", k)
