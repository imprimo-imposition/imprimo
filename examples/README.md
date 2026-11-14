# Imprimo sample files – 8 lessons

Samples for trying Imprimo and for teaching imposition. Every lesson has a PDF, a preset, steps,
what to look at and a small exercise. In Imprimo open them via **Help → Sample files…**.
Slovak version: [CITAJ-MA.md](CITAJ-MA.md).

All colours are CMYK or spot colours and the font is embedded, so the samples pass the preflight –
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
| 07 | `07_vizitka_s_lakom.pdf` + `07_vizitka_lak.pdf` | layers, spot colour, overprint |
| 08 | `08_chybne_pdf_na_preflight.pdf` | preflight: find 5 mistakes |

(File names are Slovak: *vizitky* = business cards, *obojstranne* = double-sided, *bez spadávky* =
without bleed, *pozvánka* = invitation, *bigy* = creases, *skladačka* = leaflet, *brožúra* = booklet,
*vstupenky* = tickets, *lak* = varnish, *chybné* = faulty.)

## 01 – Business cards 90×50, double-sided
Preset ★ *Business cards … 3 mm bleed*: 21 cards per SRA3. Switch to ★ *… 2 mm bleed (24 pcs)*: the same
PDF gives 24. In *All sheets* with *Page numbers* on, the back is mirrored so it lines up after turning the sheet.
*Exercise:* why don't 24 cards of 85×55 fit even with 2 mm bleed?

## 02 – A card without bleed
The warning says the PDF has 0 mm bleed; zoomed in, there is white between the pieces. Try
*Bleed → Missing: Generate by mirroring the edge*, then *by stretching*. *Exercise:* which method suits a photo,
which a flat colour – and why is exporting with bleed still best?

## 03 – Invitation A5 folded in half
Preset ★ *Invitation folded in half*: a crease at 105 mm, crease marks **B** at the sheet edge, green guides.
Then *Crease → From a crease PDF* with `03_pozvanka_A5_bigy.pdf` (a line in the **Crease** spot colour) –
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
*Layers separately*: `…_imposed.pdf` and `…_imposed_varnish.pdf`. *Exercise:* why isn't varnish just a CMYK colour
in the print PDF?

## 08 – A faulty PDF for the preflight
Find the 5 mistakes in the preflight (section *PDF export*): RGB colour, no bleed, a 27 ppi image, a font that
isn't embedded, and a crease line in the print PDF.
