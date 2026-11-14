# Imprimo 0.6.3

Imposition of print-ready PDFs for Windows, macOS and Linux – business cards, labels, booklets, cut & stack – with PDF/X export, preflight and extra layers (varnish, white, die-cut, foil).

Pages are placed as vector Form XObjects: fonts, CMYK, spot colours and gradients stay exactly as they were, nothing is rasterised.

The user interface is available in Slovak and English (menu *Language*).

## Running from source

Requires Python 3.10 or newer.

```bash
cd imprimo
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Open a PDF with the button or by dropping it onto the window. The preview updates on every change; ← → switch between sheets. Settings, language and appearance are remembered.

## Features

### Imposition modes

| Mode | Use |
|---|---|
| **Step & repeat** | Business cards, labels: each page fills a whole sheet. |
| **Sequential (n-up)** | Pages in order: 1, 2, 3, 4 on the first sheet, the rest on the next. |
| **Cut & stack** | After cutting and stacking the piles, pieces are in order (numbered tickets). |
| **Saddle-stitch booklet** | Page count padded to a multiple of 4, optional creep. |

### Sheet and layout

- Sheet presets (SRA3, A3+, A3, SRA4, A4, B3, SRA2, B2), custom size or *fit to content*.
- *Automatic* layout fits as many pieces as possible, rotating them by 90° when that helps. *Let me choose* offers a clickable miniature sheet and *across / down* fields.
- Bleed is taken from the PDF (TrimBox/BleedBox). If neighbouring pieces are closer than 2× bleed, the gap is split so bleeds never overlap. *= 2× bleed* sets gaps for double cuts.
- PDFs without a TrimBox: *Trim without TrimBox* says how much bleed surrounds the page.
- PDFs exported as spreads (e.g. from Affinity or InDesign with *Export as spreads*) are detected: pages about twice as wide as the single pages are split into a left and a right page, so a booklet gets the correct page order. *Split spreads into pages* turns this off.

### Double-sided printing

*Printer* must match the printer's duplex setting (flip on long/short edge). Imprimo computes position and rotation of the back from it. A back shown upside down in the preview is correct for a landscape sheet flipped on the long edge. *Piece back* decides how the finished piece is turned: like a book or like a calendar.

### Marks

Crop marks, dashed fold marks, registration targets and an info line (file, sheet, date). Marks use the Registration colour (Separation /All). Targets shrink to fit a narrow margin; if they don't fit at all, Imprimo warns.

### Layers (varnish, white, die-cut, foil)

*+ Add layer (PDF)* adds a PDF that is imposed exactly like the print (positions, rotation, back side, creep). Per layer:

- **Type** – varnish, white, die-cut, foil or custom; sets the defaults below and the file suffix.
- **Spot colour** – *Read from PDF* (default) lists the spot colours used in the layer PDF. If the printer requires a specific name, turn it off and enter the name – Imprimo checks that the layer uses it.
- **Position** – above the print, or below it (white underprint).
- **Overprint** – forces overprint for the whole layer so it doesn't knock out the print.
- **Pages** – page *n* of the layer goes with page *n* of the print, or page 1 is used for all.

The layer type is guessed from the spot colour names in the PDF, then from the file name. The check under each layer reports a missing or different spot colour, missing overprint, a different size or page count. In the preview, layers are shown semi-transparent.

A RIP ignores PDF layers when printing – what makes a separate plate or channel is a **spot colour with overprint**. That is why Imprimo checks for it.

### Export

*Save* offers:

- **Print** – `name_imposed.pdf`
- **Layers separately** – `name_imposed_varnish.pdf`, `name_imposed_white.pdf`, …
- **Everything in one PDF with layers** – `name_imposed_layers.pdf` (PDF optional content; layers below the print come first, then the print, then layers above)

**Standard**: keep from source, none, PDF/X-1a:2001/2003, PDF/X-3:2002/2003, PDF/X-4. **Output intent**: keep from source, bundled FOGRA39L Coated, CMYK profiles installed in the system (including Adobe profiles) or a custom `.icc`. Imprimo fills in what PDF/X requires: output intent, TrimBox/BleedBox, Trapped, Info and XMP metadata, PDF version. PDF/X-1a and X-3 don't allow layers – the combined PDF is then flattened into one.

Imprimo **does not change page content**: no RGB → CMYK conversion, no transparency flattening. Export PDF/X-1a from the design application and let Imprimo keep it. Verify the result in Acrobat Preflight.

### Preflight

After opening, Imprimo shows how the PDF was exported (standard, output intent, PDF version, creator application) and checks it against the chosen standard: embedded fonts, RGB and Lab colour, spot colours, transparency, JPEG 2000, layers, image resolution (warning below 250 ppi) and a different output intent. If the source doesn't comply, Imprimo asks before saving.

### Preview

Two modes in the bottom bar:

- **Sheet** – one sheet side with zoom: − / +, *Whole sheet*, *100 %*, Ctrl/Cmd + wheel or pinch; drag or scroll to pan; double-click toggles zoom. ← → switch sheets.
- **All sheets** – every sheet side as a thumbnail with the pages it carries (e.g. *Sheet 1 · front · pp. 8, 1*); double-sided work shows front | back per row. Click a thumbnail to open it; Ctrl/Cmd + wheel or − / + change the thumbnail size. Hold Space and drag (or drag with the middle mouse button) to move around.

*Page numbers* (next to *Guides*) puts a numbered badge in the middle of every page, in both modes. The badge is turned like the page content, so on the back you can see where the head of each page is; the underline tells 6 from 9. Blank pages added to a booklet show *blank*, pages split from a spread show which PDF page and half they come from. Like the guides, the numbers are never saved to the PDF.

Each source page is rendered once into a cached bitmap and sheets are composed from those bitmaps, so changing settings doesn't decode the images again. Sharper bitmaps are rendered in the background when zooming in; marks and guides are re-rendered from vector data.

Pages with large JPEG photos (typically full-resolution CMYK) are previewed from a proxy: a copy of the page with the photos downscaled. This makes the first render of such a page several times faster. The exported PDF always uses the original images.

### Linux

On first start Imprimo offers to add itself to the applications menu (a `.desktop` file and icons in `~/.local/share`). GNOME and KDE on Wayland take the icon in the dock from it. If the folder is moved later, the entry is updated automatically.

## Project structure

```
main.py                  entry point (splash first, crash report)
imprimo/
  core.py                geometry, imposition plan, rendering, layers, PDF/X export
  gui.py                 user interface (PySide6)
  preview.py             cached page bitmaps and sheet composition for the preview
  splash.py              QApplication, icon, splash screen, macOS app name
  preflight.py           source and layer checks
  pdfinfo.py             PDF/X / PDF/A / output intent detection, ICC profiles
  fonts.py               embedded font for the info line
  i18n.py                Slovak and English texts
  theme.py               light / dark appearance
  desktop_linux.py       Linux menu entry (.desktop) and icons
  cli.py                 command line
  assets/                font, ICC profile, icons
tests/
  make_samples.py        sample PDFs (needs reportlab and pillow)
  test_core.py           page order, PDF/X export, layers
packaging/
  package.py             builds the release zips (see packaging/README.md)
  docs/                  README.txt / CITAJ-MA.txt of the packages
  windows/               source of the Imprimo.exe launcher
tools_make_icons.py      builds .ico / .icns / PNG from the icon master
```

## Command line

```bash
python -m imprimo.cli input.pdf output.pdf --set mode=booklet --set sheet_w=297 --set sheet_h=420
```

Setting names are the fields of `Settings` in `imprimo/core.py`.

## Tests

```bash
pip install reportlab pillow
python tests/make_samples.py
python tests/test_core.py
```

## Icon

The master is `imprimo/assets/icon/imprimo-1024-master.png`. After changing it run:

```bash
python tools_make_icons.py
```

It writes `imprimo.ico` (Windows, 16–256 px; 16–24 px use a simplified target), `imprimo.icns` (macOS, Apple grid 824/1024 with shadow) and PNGs for Linux and the window icon.

## Limitations

- All pages are imposed into a cell the size of the first page; other sizes are centred.
- Booklets are 2 pages per sheet side; multiple spreads per sheet and signatures are not supported yet.
- No colour conversion or transparency flattening.
- Preflight doesn't replace a certified one (Acrobat, pdfToolbox).
- Annotations and form fields are not carried over.

## Bundled files

See `imprimo/assets/README-assets.txt`: DejaVu Sans Condensed (Bitstream Vera / DejaVu licence) and the FOGRA39L Coated ICC profile (free of known copyright restrictions).

---
Author: Maxim Darák
