# Imprimo sample files – 11 lessons

Samples for trying Imprimo and for teaching imposition. Every lesson has a PDF, a preset, steps,
what to look at and a small exercise. In Imprimo open them via **Help → Sample files…**.
Slovak version: [CITAJ-MA.md](CITAJ-MA.md).

> **Using Affinity?** Its exported PDF may have an inexact page size (e.g. 50.038 mm instead of 50).
> Why and how to avoid it: [affinity-page-size.md](affinity-page-size.md).

All colors are CMYK or spot colors and the font is embedded, so the samples pass the preflight –
except lesson 08, which is wrong on purpose. They are built by `make_examples.py`
(`pip install reportlab pillow`, `python examples/make_examples.py`).

| # | File | You learn |
|---|---|---|
| 01 | `01_vizitky_90x50_obojstranne.pdf` | step & repeat, double-sided printing, 3 vs 2 mm bleed |
| 02 | `02_vizitka_bez_spadavky.pdf` | why bleed matters, generating it |
| 03 | `03_pozvanka_A5_na_polovicu.pdf` + `…_bigy.pdf` | creasing, crease marks |
| 04 | `04_DL_skladacka_zavinovacia.pdf` + `…_bigy.pdf` | roll fold 100/100/97, creases from a PDF |
| 05 | `05_brozura_A5_12_stran.pdf` | saddle stitching, page order, creep |
| 06 | `06_vstupenky_cut_and_stack.pdf` | cut & stack – numbers in order after cutting |
| 07 | `07_vizitka_s_lakom.pdf` + `07_vizitka_lak.pdf` | layers, spot color, overprint |
| 08 | `08_chybne_pdf_na_preflight.pdf` | preflight: find 5 mistakes |
| 09 | `09_plagat_A2.pdf` | poster in pieces on A4 / A3, overlap, scaling to A1 |
| 10 | `10_vizitky_jana.pdf`, `…_peter.pdf`, `…_eva.pdf` | several jobs on one sheet (gang run) |
| 11 | `11_zbornik_A6_48_stran.pdf` + `…_obalka.pdf` | perfect binding: signatures, collation marks, cover with spine |

(File names are Slovak: *vizitky* = business cards, *obojstranne* = double-sided, *bez spadávky* =
without bleed, *pozvánka* = invitation, *bigy* = creases, *skladačka* = leaflet, *brožúra* = booklet,
*vstupenky* = tickets, *lak* = varnish, *chybné* = faulty, *plagát* = poster.)

## 01 – Business cards 90×50, double-sided
Preset ★ *Business cards … 3 mm bleed*: 21 cards per SRA3. Switch to ★ *… 2 mm bleed (24 pcs)*: the same
PDF gives 24. In *All sheets* with *Page numbers* on, the back is mirrored so it lines up after turning the sheet.
*Exercise:* why don't 24 cards of 85×55 fit even with 2 mm bleed?

## 02 – A card without bleed
The warning says the PDF has 0 mm bleed; zoomed in, there is white between the pieces. Try
*Bleed → Missing: Generate by mirroring the edge*, then *by stretching*. *Exercise:* which method suits a photo,
which a flat color – and why is exporting with bleed still best?

## 03 – Invitation A5 folded in half
Preset ★ *Invitation folded in half*: a crease at 105 mm, crease marks **B** at the sheet edge, green guides.
Then *Crease → From a crease PDF* with `03_pozvanka_A5_bigy.pdf` (a line in the **Crease** spot color) –
the same result. *Exercise:* open the crease PDF as the print PDF – what does the preflight say?

## 04 – DL roll (C) fold leaflet
Page 1 is the inside (100 / 100 / 97 mm), page 2 the outside. Preset ★ *DL roll fold*: creases at 100 and 200 mm;
the back gets them mirrored (97 and 197 mm). The narrow panel folds in. *Exercise:* switch to *Z-fold* –
what positions does Imprimo compute?

## 05 – Saddle-stitch booklet A5, 12 pages
Preset ★ *Saddle-stitch booklet*: 3 sheets, sheet 1 has pages 12 | 1, its back 2 | 11. Set *creep* to 0.5 mm and
watch the orange bar 4 mm from the outer edge move on the inner sheets. *Exercise:* how many sheets for 20 pages,
and what happens with 18?

## 06 – Tickets, cut & stack
28 tickets No. 001–028, 14 per SRA3 = 2 sheets. Sheet 1 carries 1, 3, 5… – after cutting and stacking the piles
the numbers run 001 → 028. *Exercise:* type `1-24` into *Pages* – what does Imprimo warn about?

## 07 – Card with spot varnish
Open the print PDF, *+ Add layer (PDF)…* → `07_vizitka_lak.pdf` (spot **Varnish** with overprint). Save with
*Layers separately*: `…_imposed.pdf` and `…_imposed_varnish.pdf`. *Exercise:* why isn't varnish just a CMYK color
in the print PDF?

## 08 – A faulty PDF for the preflight
Find the 5 mistakes in the preflight (section *PDF export*): RGB color, no bleed, a 27 ppi image, a font that
isn't embedded, and a crease line in the print PDF.

## 09 – Poster A2 in pieces
Preset ★ *Poster in pieces – A4*: 8 A4 pieces (2 × 4), shown assembled in *All sheets*. Pieces are named A1, A2, B1…
(rows by letters, columns by numbers) with a small map in the margin. Change the sheet to A3, or set *Final size* to
A1 – the scale is set automatically. Cut each piece at the crop marks (left and top), lay it over its neighbor's
overlap up to the dashed mark and glue; the diagonal lines and circles must continue without a step.
*Exercise:* how many A4 and how many A3 sheets for an A1 poster?

## 10 – Business cards of three people on one sheet (gang run)
Open the lesson (Jana is job **A**), then under *Jobs on the sheet* add Peter and Eva (*+ Add PDF…* or drop them on
the window). Quantities Jana 100, Peter 250, Eva 50: Imprimo splits the 24 slots into **A 6 · B 15 · C 3** and needs
**17 sheets** (250 / 15 → 17), with 2 + 5 + 1 extra pieces. With *Page numbers* on, the cards show their job letter;
the info line says which slots hold which job (A 1–6, B 7–21, C 22–24) for sorting after cutting. Printed separately
it would be 5 + 11 + 3 = 19 sheets. *Exercise:* set Eva to 300 – how do the slots and sheets change?

## 11 – Small A6 book, perfect binding
Files `11_zbornik_A6_48_stran.pdf` (48 pages A6, a new chapter every 8 pages) and `11_zbornik_A6_obalka.pdf` (the opened
cover, spine 2.4 mm); preset ★ *Signatures – SRA3, perfect binding*. Imprimo splits the book into **6 signatures of
8 pages**, one SRA3 sheet each; the front of sheet 1 has 5 and 4 upside down at the top, 8 and 1 below. Pages next to
each other at the spine always add up to the same number (9 in signature 1, 25 in signature 2). Save with
**Fold dummy** on, print sheet 1 double-sided and fold it along fold **1** (heads together), then fold **2** – the pages
must run 1 → 8 with all heads ▲ up. Stack the folded signatures: the black **collation marks** on the spines form a
staircase. **Tools → Cover with spine…**: 48 pages on 80 g/m² uncoated give a **2.4 mm** spine; *Impose the finished
cover…* with `11_zbornik_A6_obalka.pdf` opens it with creases at 105 and 107.4 mm. *Exercise:* the spine on 100 g/m²
paper with bulk 1.2? How many signatures and sheets for a 52-page book?
