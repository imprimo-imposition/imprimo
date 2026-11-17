# Imprimo – notes for Claude

Imprimo imposes print-ready PDFs (business cards, labels, booklets, cut & stack) – like
Imposition Wizard or Quite Imposing – with PDF/X export, preflight and extra layers
(varnish, white, die-cut, foil). Python 3.12 + PySide6, runs on Windows, macOS, Linux.
Feature overview: `README.md`. Packaging and releases: `packaging/README.md`.

Author: Maxim Darák, with students of SOŠ služieb, Košická 20, Prešov, field of study GTM
(SOČ project) – this
credit is public on purpose (README, About dialog). Code is written with AI assistance, as stated
in README “How Imprimo is made”. Imprimo is used by beginners as well as print shops, so the UI
must be understandable for beginners. Maxim writes in Slovak – answer him in Slovak,
technically precise and practical. Private notes (not in git): `CLAUDE.local.md`.

## Rules

- Code, comments, file names, README.md, CLAUDE.md: **English**, US spelling (color, center, gray, license).
- User interface: Slovak and English, all texts in `imprimo/i18n.py`. Every key must exist
  in both languages (check: the SK and EN key sets are equal).
- Package readmes: `README.txt` (EN) + `CITAJ-MA.txt` (SK), sources in `packaging/docs/`.
- License: GPL-3.0-or-later (`LICENSE`). A new or updated bundled dependency must be
  listed in `THIRD-PARTY-NOTICES.txt` (shipped in every release zip).
- Exported file suffix: `_imposed` (layers: `_imposed_varnish`, …, `_imposed_layers`).
- Releases: zips named with the version – `Imprimo-X.Y.Z-windows.zip`, `-macOS.zip`,
  `-linux-x86_64.zip`, source `imprimo-X.Y.Z.zip`. Bump `__version__` in
  `imprimo/__init__.py` and the README heading with every release.
- Page content is never changed: vector Form XObjects, no rasterizing, no color
  conversion, no transparency flattening.
- The preview must never crash the app; heavy work must not freeze the UI.

## Layout

```
main.py                 entry point (splash first, crash report)
imprimo/core.py         geometry, PageInfo/analyze (incl. splitting spreads), Settings,
                        plan (modes repeat/sequential/cutstack/booklet/signatures/tile/gang),
                        fold dummy, rendering with
                        pikepdf, marks, layers (OCG), PDF/X export
imprimo/preview.py      fast preview: cached pdfium page bitmaps composed with QPainter,
                        JPEG-downscaled proxies for heavy pages, page number badges
imprimo/gui.py          MainWindow, SheetView (zoom/pan), OverviewView (all sheets,
                        Space/middle-button hand tool), collapsible sections, LayerRow
imprimo/crease.py       crease presets/positions (mm on the product), crease line detection
imprimo/signatures.py   signatures (V2 / sewn): folding schemes by virtual folding, splitting pages
imprimo/cover.py        cover with spine: spine width, template PDF, assembling the cover
                        (cover_dialog.py = window, Tools menu and the Signatures section)
imprimo/spots.py        spot color library + aliases, .ase writer (spots_dialog.py = window)
imprimo/presets.py      job presets: built-ins, user presets (QSettings "job_presets"), .json files
examples/               lesson PDFs (built by make_examples.py, committed), CITAJ-MA.md + README.md;
                        examples_dialog.py opens them; packaged into the app folder
imprimo/preflight.py    source and layer checks
imprimo/pdfinfo.py      PDF/X, PDF/A, output intent detection, ICC profiles
imprimo/theme.py        light/dark/system (GNOME portal detection on Linux)
imprimo/splash.py       QApplication, icon, splash, macOS app name
imprimo/desktop_linux.py  .desktop entry + icons
imprimo/cli.py          command line (`--set field=value`, fields of Settings)
tests/                  make_samples.py (needs reportlab, pillow), test_core.py
packaging/              package.py (release zips), docs/, windows/ launcher
tools_make_icons.py     .ico / .icns / PNG from imprimo/assets/icon/imprimo-1024-master.png
docs/                   website on GitHub Pages (https://imprimo-imposition.github.io/imprimo/),
                        one static index.html (SK/EN), screenshots docs/mac/*.webp made by
                        tools_web_screenshots.py (needs Screen Recording permission)
```

Coordinates: PDF points, y up. Affine matrices are tuples `(a, b, c, d, e, f)` in PDF
order; `compose(m1, m2)` applies m1 first, `chain(*ms)` composes left to right.
An `Item` places a page: `matrix` maps the upright page ("card", 0..W × 0..H) to the sheet.

## Working

```bash
pip install -r requirements.txt reportlab
python main.py                                   # run
python tests/make_samples.py && python tests/test_core.py
QT_QPA_PLATFORM=offscreen python …               # headless GUI checks / screenshots
python3 packaging/package.py X.Y.Z --base <folder with previous release zips>
```

Test against real files too: large Affinity/InDesign PDFs with CMYK photos, PDFs exported
as spreads, PDFs without TrimBox, rotated pages.

## Plans (not started)

- V2 binding follow-ups (0.8.0 has signatures, fold dummy, cover with spine): nested signatures
  for thick saddle-stitched magazines, work & turn, parallel folds.
- Custom splash screen from Maxim (PNG 1200 × 720).
- Donations: live at https://ko-fi.com/imprimo (PayPal, no Stripe – Maxim donates privately, not
  through his živnosť; never promise anything in return). Later possibly an o. z. (2 % of tax).
- Windows testing feedback from users.
