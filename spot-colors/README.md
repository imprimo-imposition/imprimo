# Imprimo spot colors

**[Imprimo-spot-colors.ase](Imprimo-spot-colors.ase)** – technical spot colors for finishing, as an
Adobe Swatch Exchange palette. Imprimo saves the same file from *Tools → Spot colors…*.

| Name (exact) | Use | Alternate CMYK | Printed |
|---|---|---|---|
| **Crease** | creasing (score line for a fold) | 100 / 0 / 100 / 0 | no |
| **CutContour** | die-cut, contour cut | 0 / 100 / 0 / 0 | no |
| **Perforation** | perforation | 100 / 0 / 0 / 0 | no |
| **Fold** | fold without crease | 100 / 100 / 0 / 0 | no |
| **White** | white underprint | 0 / 0 / 0 / 25 | yes |
| **Varnish** | spot varnish | 0 / 0 / 100 / 0 | yes |
| **Foil** | hot foil | 0 / 30 / 80 / 20 | yes |

The CMYK values are only the alternate color shown on screen – each spot color is a separation
of its own. *CutContour* is the name Roland, Mimaki and Summa cutters expect.

## Import

- **Illustrator** – Swatches panel → menu → *Open Swatch Library → Other Library…* → choose the `.ase`.
- **InDesign** – Swatches panel → menu → *Load Swatches…*
- **Photoshop** – Swatches panel → menu → *Import Swatches…*
- **Affinity Designer / Publisher** – Swatches panel → menu → *Import Palette…* → **As Application Palette**
  (or *As Document Palette*). **Not** *As System Palette* – a system palette (a macOS color list) has no
  spot colors, so Crease would become a plain color and Imprimo would not find it.
- **CorelDRAW** – Color palettes → *Open palette* → `.ase`.
- **Scribus** – *Edit → Colors and Fills → Import*.

## How to draw a crease

1. Draw the crease as a straight line, 0.25 pt, in **Crease**, set to *overprint*.
2. Put it on a layer of its own (e.g. *Crease*).
3. Export the print PDF **without** that layer, and the crease layer as a second PDF.
4. In Imprimo: open the print PDF, in *Creasing* choose *Crease → From a crease PDF* and
   *Choose PDF…* the second PDF. Imprimo reads the positions and puts crease marks at the sheet edge.

Imprimo also recognizes other names regardless of case, spaces and accents – e.g. *Big*, *Bigovanie*,
*Score* for a crease, *Výsek*, *Die*, *Dieline* for a die-cut.

---

## Spotové farby Imprimo (SK)

**Imprimo-spot-colors.ase** – technické spotové farby na dokončovacie spracovanie. Rovnaký súbor
uloží Imprimo cez *Nástroje → Spotové farby…*.

**Affinity:** paletu importuj ako **aplikačnú** (Application) alebo **dokumentovú** (Document), **nie ako
systémovú** (System) – systémová paleta (zoznam farieb macOS) nepozná spotové farby, Crease by bola
obyčajná farba a Imprimo by ju nenašlo.

**Big nakresli** ako rovnú čiaru 0,25 pt vo farbe **Crease** s prestrieraním (overprint), v samostatnej
vrstve. Tlačové PDF exportuj bez tejto vrstvy, vrstvu s bigmi ako druhé PDF. V Imprime v sekcii
*Bigovanie* zvoľ *Big → Z PDF s bigmi* a cez *Vybrať PDF…* vyber toto druhé PDF. Imprimo spozná aj názvy *Big*, *Bigovanie*, *Výsek*,
*Lak*, *Biela* a ďalšie – bez ohľadu na veľké písmená a diakritiku.
