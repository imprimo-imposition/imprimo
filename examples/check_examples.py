"""Quick check of redesigned sample PDFs (see ZADANIE.md, "Export po súboroch – ťahák").

    python examples/check_examples.py            # all lessons
    python examples/check_examples.py 03 04      # only these lessons

Prints for every PDF: app, PDF/X + output intent, trim size to 3 decimals, bleed, fonts,
preflight warnings and crease positions; flags anything that does not match the brief.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pikepdf                                   # noqa: E402
from imprimo import i18n, pdfinfo                # noqa: E402
from imprimo.core import analyze, mm             # noqa: E402
from imprimo.preflight import evaluate, scan     # noqa: E402

# lesson → (trim w, h in mm, bleed mm, pages); None = any
SIZES = {"01": (90, 50, 3, 2), "02": (90, 50, 0, 1), "03": (210, 148, 3, None),
         "04": (297, 210, 3, None), "05": (148, 210, 3, 12), "06": (140, 50, 3, 28),
         "07": (90, 50, 3, 1), "08": (148, 105, 0, 1), "09": (420, 594, 3, 1),
         "10": (90, 50, 3, 2), "11": (105, 148, 3, 48)}
SPECIAL = {"03_pozvanka_A5_bigy.pdf": (210, 148, 3, 1),
           "04_DL_skladacka_bigy.pdf": (297, 210, 3, 1),
           "11_zbornik_A6_obalka.pdf": (212.4, 148, 3, 1),
           "03_pozvanka_A5_na_polovicu.pdf": (210, 148, 3, 2),
           "04_DL_skladacka_zavinovacia.pdf": (297, 210, 3, 2)}
CREASES = {"03_pozvanka_A5_bigy.pdf": [105.0], "04_DL_skladacka_bigy.pdf": [100.0, 200.0]}


def check(path):
    name = os.path.basename(path)
    want = SPECIAL.get(name) or SIZES.get(name[:2])
    bad = []
    with pikepdf.open(path) as pdf:
        prof = pdfinfo.detect_profile(pdf)
        oi = prof.pdfx_intent
        intent = f"{oi.identifier} / {oi.icc.desc if oi.icc else oi.info}" if oi else "–"
        print(f"\n== {name}  ({os.path.getsize(path) // 1024} kB, {prof.app() or '?'})")
        print(f"   {prof.pdfx or 'no PDF/X'} · intent {intent}")
        infos = analyze(pdf)
        sizes = sorted({(round(i.vis_w / mm(1), 3), round(i.vis_h / mm(1), 3),
                         round(i.bleed_avail / mm(1), 3)) for i in infos})
        print(f"   {len(infos)} pages · trim × bleed: {sizes}")
        fonts = sorted({str(f.get("/BaseFont", "?")).lstrip("/").split("+")[-1]
                        for p in pdf.pages for f in p.Resources.get("/Font", {}).values()})
        print(f"   fonts: {', '.join(fonts) or '– (text as outlines)'}")
        F = scan(pdf)
        msgs = evaluate(F, prof.standard_key, set(range(1, len(infos) + 1)))
        warn = [t for lvl, t in msgs if lvl in ("warn", "error")]
        for t in warn:
            print(f"   preflight: {t}")
        if name in CREASES:
            from imprimo.crease import detect_any
            got = detect_any(pdf, infos).vertical
            print(f"   creases (mm from left): {got}")
            if got != CREASES[name]:
                bad.append(f"creases {got}, want {CREASES[name]}")
    lesson08 = name.startswith("08")
    if want:
        w, h, bleed, pages = want
        for tw, th, tb in sizes:
            if abs(tw - w) > 0.005 or abs(th - h) > 0.005:
                bad.append(f"trim {tw} × {th}, want {w} × {h}")
            if not lesson08 and abs(tb - bleed) > 0.05:
                bad.append(f"bleed {tb}, want {bleed}")
        if pages and len(infos) != pages:
            bad.append(f"{len(infos)} pages, want {pages}")
    if lesson08:
        if len(warn) < 4:
            bad.append("lesson 08 must keep its errors (preflight finds < 4)")
    else:
        if prof.pdfx != "PDF/X-4":
            bad.append("not PDF/X-4")
        if not oi or oi.identifier != "FOGRA39":
            bad.append("output intent is not FOGRA39 (Color Settings → Europe Prepress 3)")
        layer = name.endswith(("_bigy.pdf", "_lak.pdf"))     # Crease / Varnish on purpose
        if warn and not layer:
            bad.append("preflight warnings")
    print("   " + ("OK" if not bad else "PROBLEM: " + "; ".join(bad)))
    return not bad


def main(args):
    i18n.set_language("sk")
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".pdf"))
    if args:
        files = [f for f in files if f[:2] in args]
    ok = [check(os.path.join(HERE, f)) for f in files]
    print(f"\n{sum(ok)} / {len(ok)} OK")


if __name__ == "__main__":
    main(sys.argv[1:])
