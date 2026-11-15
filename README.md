# Imprimo 0.7.1

Imposition of print-ready PDFs for Windows, macOS and Linux – business cards, labels, booklets, cut & stack – with PDF/X export, preflight and extra layers (varnish, white, die-cut, foil).

Pages are placed as vector Form XObjects: fonts, CMYK, spot colours and gradients stay exactly as they were, nothing is rasterised.

The user interface is available in Slovak and English (menu *Language*).

**Website:** https://imprimo-imposition.github.io/imprimo/ · **Download:** [latest release](https://github.com/imprimo-imposition/imprimo/releases/latest)

## Sample files

[`examples/`](examples/) has 10 lessons with sample PDFs – business cards, a card without bleed, an invitation
and a DL leaflet with creases, a booklet, cut & stack tickets, spot varnish, a faulty PDF for the preflight, a poster in pieces and a gang run –
each with a preset, steps and an exercise ([Slovak guide](examples/CITAJ-MA.md), [English](examples/README.md)).
In Imprimo: **Help → Sample files…** opens a lesson with its preset.

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
| **Poster in pieces** | A page bigger than the sheet is split into overlapping pieces for gluing (see below). |
| **Several jobs on a sheet (gang run)** | Different PDFs of the same size on one sheet, each with its own quantity (see below). |

### Presets

**Preset** at the top of the panel sets everything for a kind of job in one click: sheet, layout, bleed, double-sided printing, marks, creasing and export. Imprimo comes with presets for single- and double-sided business cards (90×50 or 85×55 – the size always comes from the PDF; with 3 mm bleed 21 per SRA3, with 2 mm bleed 24 cards 90×50), an invitation folded in half, a DL roll fold leaflet, a saddle-stitch booklet, tickets, business cards of several people (gang run) and a poster in A4 pieces (★). *Save…* stores the current settings as your own preset; *Presets → Manage* renames, reorders and deletes them, *Export / Import* moves them to another computer as a `.json` file – a teacher prepares presets once and the class imports them. When a setting is changed, the preset field switches to *custom settings*.

### Sheet and layout

- Sheet presets (SRA3, A3+, A3, SRA4, A4, B3, SRA2, B2), custom size or *fit to content*.
- *Automatic* layout fits as many pieces as possible, rotating them by 90° when that helps. *Let me choose* offers a clickable miniature sheet and *across / down* fields.
- Bleed is taken from the PDF (TrimBox/BleedBox). If neighbouring pieces are closer than 2× bleed, the gap is split so bleeds never overlap. *= 2× bleed* sets gaps for double cuts.
- PDFs without a TrimBox: *Trim without TrimBox* says how much bleed surrounds the page.
- **Missing bleed** can be generated: *mirroring the edge* (photos, patterns) or *stretching the edge* (flat colours, gradients). Only the sides that lack bleed get it; the page itself is not changed – mirrored or stretched copies of its edge are drawn under it, in the preview and in the export.
- PDFs exported as spreads (e.g. from Affinity or InDesign with *Export as spreads*) are detected: pages about twice as wide as the single pages are split into a left and a right page, so a booklet gets the correct page order. *Split spreads into pages* turns this off.

### Double-sided printing

*Printer* must match the printer's duplex setting (flip on long/short edge). Imprimo computes position and rotation of the back from it. A back shown upside down in the preview is correct for a landscape sheet flipped on the long edge. *Piece back* decides how the finished piece is turned: like a book or like a calendar.

### Marks

Crop marks, dashed fold marks, registration targets and an info line (file, sheet, date). Marks use the Registration colour (Separation /All). Targets shrink to fit a narrow margin; if they don't fit at all, Imprimo warns.

### Gang run

*Several jobs on a sheet* puts different PDFs of the same size on one sheet – e.g. business cards of several people.
The open file is job **A**; *Jobs on the sheet → + Add PDF…* (or dropping PDFs on the window) adds B, C… Each job has a
quantity; Imprimo splits the slots of the sheet so the number of sheets is as small as possible (every job gets at
least one slot, spare slots are spread evenly) and shows how many pieces of each job are printed. Every sheet is the
same. Page 1 of every PDF is used, double-sided page 1 front and page 2 back. The info line lists which slots hold
which job (A 1–6, B 7–21…), *Page numbers* show the job letters. Layers are not available in a gang run.

### Poster in pieces

For posters printed on an office printer: the page is scaled (*Scale* in %, or *Final size* A3 … A0, B2, B1)
and split into pieces of the chosen sheet, so that every piece overlaps the next one by *Glue overlap* (10 mm).
The sheet margin is the printer's unprintable edge. Imprimo picks the sheet orientation with the fewest pieces.
Each piece has crop marks where it is cut (left and top, plus the poster edges), dashed marks showing how far the
next piece is glued, its name (A1, A2, B1… – rows by letters, columns by numbers) in the info line and a small
map of the poster. *All sheets* lays the pieces out as the assembled poster. Every selected page becomes its own poster.

### Creasing

For invitations, cards and folded leaflets (section *Creasing*):

- **Presets** – *in half*, *Z-fold* (3 equal panels), *roll (C) fold* (the inner panel 3 mm narrower, e.g. A4 → 100 / 100 / 97 mm), *custom positions* (`99; 198`) or *from the PDF*.
- Positions are in mm on the **finished product** (without bleed): vertical creases from the left edge, horizontal ones from the top. Imprimo carries them to every copy on the sheet – rotated pieces and the back side included.
- **Crease marks at the sheet edge** – dash-dot marks labelled *B* (Slovak *big*) / *CR* outside the bleed, for setting the stop of a manual creaser. The positions are also printed in the info line.
- **From a crease PDF** – Imprimo finds straight lines in the spot colour **Crease** (or an alias such as *Big*, *Bigovanie*, *Score*) and fills in the positions. *Source* is the PDF exported from the crease layer (*Choose PDF…*); without it, Imprimo looks in the print PDF and warns that a digital press would print the lines. A PDF with Crease lines added under *Layers* is moved to the Creasing section automatically. Direction and positions appear once creases are found.
- The preview shows the creases as green dash-dot lines (with *Guides*). A booklet is creased at the fold, so creasing is off there.

### Spot colours

*Tools → Spot colours…* lists the technical spot colours Imprimo works with and saves them as an **Adobe Swatch Exchange (.ase)** palette for Illustrator, InDesign, Photoshop, Affinity, CorelDRAW or Scribus. The palette is also in [`spot-colors/`](spot-colors/).

| Name | Use | Printed |
|---|---|---|
| **Crease** | creasing | no |
| **CutContour** | die-cut, contour cut | no |
| **Perforation** | perforation | no |
| **Fold** | fold without crease | no |
| **White** | white underprint | yes |
| **Varnish** | spot varnish | yes |
| **Foil** | hot foil | yes |

Names are matched regardless of case, spaces and accents; Slovak names (*Big*, *Výsek*, *Lak*, *Biela*, …) are recognised too.

### Layers (varnish, white, die-cut, foil, crease)

*+ Add layer (PDF)* adds a PDF that is imposed exactly like the print (positions, rotation, back side, creep). Per layer:

- **Type** – varnish, white, die-cut, foil, crease or custom; sets the defaults below and the file suffix. A crease PDF is handled in the Creasing section; with *Layers separately* it is also exported as `name_imposed_crease.pdf` (e.g. for a plotter), never printed.
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
- **All sheets** – every sheet side as a thumbnail with the pages it carries (e.g. *Sheet 1 · front · pp. 8, 1*); double-sided work shows front | back per row. Zoom works like in *Sheet* (up to 200 %); click a thumbnail to open it.

In both modes: Ctrl/Cmd + wheel or pinch zooms at the cursor, drag, Space + drag or the middle mouse button pans.

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
  crease.py              crease presets and positions, finding crease lines in a PDF
  spots.py               spot colour library (Crease, CutContour, …), .ase export
  presets.py             job presets (built-in, user's, .json import / export)
  examples_dialog.py     Help → Sample files (lessons in examples/)
  gui.py                 user interface (PySide6)
  about.py               About dialog (licence, versions)
  spots_dialog.py        Spot colours window
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
  test_core.py           page order, PDF/X export, layers, creasing, spot colours
spot-colors/             Imprimo spot colour palette (.ase) and how to import it
examples/                sample PDFs (lessons), guides, make_examples.py
packaging/
  package.py             builds the release zips (see packaging/README.md)
  docs/                  README.txt / CITAJ-MA.txt of the packages
  windows/               source of the Imprimo.exe launcher
tools_make_icons.py      builds .ico / .icns / PNG from the icon master
tools_web_screenshots.py macOS window screenshots for the website
docs/                    the website (GitHub Pages): index.html, mac/ screenshots
```

## Command line

```bash
python -m imprimo.cli input.pdf output.pdf --set mode=booklet --set sheet_w=297 --set sheet_h=420
```

Setting names are the fields of `Settings` in `imprimo/core.py`, e.g. `--set crease=c3`,
`--set crease=custom --set crease_pos="99; 198"` or `--set crease=pdf`.

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

## How Imprimo is made

Imprimo is designed and tested by **Maxim Darák**, a teacher of print media, together with students of
**SOŠ služieb, Košická 20, Prešov** (Slovakia), field of study **GTM – grafik tlačových médií**
(print media graphic designer), as part of their SOČ project (Slovak secondary-school
research competition). Maxim is not a programmer: the code is written with AI assistance
([Claude Code](https://claude.com/claude-code) by Anthropic) under his direction. He brings the know-how
of print production, decides what Imprimo does and how it works, and tests it on real print jobs
with his students. Every change is checked by automated tests.

Found a problem or have an idea? Please [open an issue](https://github.com/imprimo-imposition/imprimo/issues).

## Support the project

Imprimo is free. If it saves you time at school or in your print shop, you can support its development with a
voluntary donation on **[Ko-fi](https://ko-fi.com/imprimo)** – thank you! (*Help → Support the project…* in the app.)

## Licence

Imprimo is free software, licensed under the **GNU General Public License v3.0 or later** ([LICENSE](LICENSE)).
You may use it free of charge – at school, at home and in companies, also for commercial print work –
share it and change it. If you distribute a modified version, it has to be under the GPL too, with its source code.

**Commercial licence:** companies that want to build Imprimo into a closed-source product, or need other
terms, can get a separate licence from the author – open an issue on GitHub.

**Contributions:** by sending a pull request you agree that your contribution is licensed under
GPL-3.0-or-later and may also be included in the author's commercial licence.

## Bundled files

Third-party libraries and their licences: [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
Assets – see `imprimo/assets/README-assets.txt`: DejaVu Sans Condensed (Bitstream Vera / DejaVu licence) and the FOGRA39L Coated ICC profile (free of known copyright restrictions).

---
Author: Maxim Darák, with students of SOŠ služieb, Košická 20, Prešov, field of study GTM · developed with AI assistance (Claude Code)
