# Affinity: exportované PDF nemá presný rozmer strany

*English version below.*

**Skontroluj rozmer každého PDF z Affinity skôr, ako ide do tlače.** Affinity
(Designer, Publisher, Affinity 3) pri exporte do PDF zaokrúhľuje rozmer strany na celé pixely
podľa DPI dokumentu. Zle je pritom zapísaný rozmer strany v PDF, takže chybu nevidíš ani v Affinity,
ani v bežnom prehliadači PDF.

## Čo sa stalo pri vzore 02 (Affinity 3.3.3, november 2026)

| | Dokument v Affinity | Exportované PDF |
|---|---|---|
| Rozmer | 90 × 50 mm | **90,001 × 50,038 mm** |
| V pixeloch pri 300 DPI | 1062,99 × 590,55 px | 1063 × 591 px (zaokrúhlené) |
| V bodoch PDF | 255,118 × 141,732 pt | 255,12 × 141,84 pt |

Export bol PDF/X-4 bez spadávky. Vzor 01 (90 × 50 mm, spadávka 3 mm) z toho istého Affinity
vyšiel presne. Či chyba nastane, teda môže závisieť od nastavenia dokumentu.

## Prečo to vadí

- 0,04 mm na jednom kuse nie je vidieť. Keď sú ale vizitky na hárku pod sebou, rozdiel sa sčíta:
  sedem kusov v stĺpci je dlhších o 0,27 mm, väčšie formáty o viac.
- Tlačiareň alebo preflight môže súbor odmietnuť, keď rozmer nesedí so zákazkou.
- Na zložky, obálky s chrbtom a výseky (die-cut) treba presné rozmery.

## Ako to zistiť

- **Imprimo** ukáže rozmer hneď po otvorení PDF (na 0,1 mm), test v `tests/` ho kontroluje na
  tri desatinné miesta.
- **Acrobat:** *Súbor → Vlastnosti → Popis → Veľkosť strany*, alebo *Preflight → Info o strane*
  (TrimBox, MediaBox).

## Obchádzka v Affinity

DPI dokumentu (*Document Setup*) nastav tak, aby 1 mm dal celý počet pixelov:
**254, 508, 1270 alebo 2540 DPI** (254 DPI = 10 px na 1 mm). DPI dokumentu **nie je**
rozlíšenie obrázkov v PDF – fotky sa pri exporte aj tak prevzorkujú na 300 DPI podľa nastavenia
exportu. Najjednoduchšie je mať pre študentov šablónu dokumentu s 254 DPI.

Hodnota 304,8 DPI (120 px/cm), ktorú radia na fóre, sa v okne *Nový dokument* zaokrúhli na 305
a Publisher desatinné DPI nedovolí vôbec.

Vzory Imprima preto robíme v **Illustratore**.

## Stav chyby u Serifu / Canvy

- Na fóre Affinity: [Size adding 0.05mm when exporting to pdf](https://forum.affinity.serif.com/index.php?/topic/232218-affinity-designer-v2-size-adding-005mm-when-exporting-to-pdf/)
  (máj 2025). Chyba je vedená ako **AF-1340** a podľa používateľov je známa roky.
- V Affinity 3.3.3 (november 2026) stále platí.

Keď to nahlásiš aj ty, pripoj sa radšej do existujúceho vlákna alebo uveď **AF-1340** – nové
duplicitné hlásenia moderátori spájajú. Pomôže presný postup a priložený .af aj PDF.

---

# Affinity: exported PDF does not have the exact page size

**Check the size of every PDF from Affinity before it goes to print.** On PDF export Affinity
(Designer, Publisher, Affinity 3) rounds the page size to whole pixels at the document DPI.
The page size written into the PDF is wrong, so neither Affinity nor a normal PDF viewer shows it.

## What happened with sample 02 (Affinity 3.3.3, November 2026)

| | Document in Affinity | Exported PDF |
|---|---|---|
| Size | 90 × 50 mm | **90.001 × 50.038 mm** |
| Pixels at 300 DPI | 1062.99 × 590.55 px | 1063 × 591 px (rounded) |
| PDF points | 255.118 × 141.732 pt | 255.12 × 141.84 pt |

The export was PDF/X-4 without bleed. Sample 01 (90 × 50 mm, 3 mm bleed) from the same Affinity
came out exact, so whether it happens may depend on the document settings.

## Why it matters

- 0.04 mm on one card is invisible, but it adds up on the sheet: seven cards in a column are
  0.27 mm longer, larger formats more.
- A printer or a preflight may reject a file whose size does not match the job.
- Signatures, covers with a spine and die-cuts need exact sizes.

## How to find it

- **Imprimo** shows the size right after opening the PDF (to 0.1 mm); the test in `tests/` checks
  it to three decimals.
- **Acrobat:** *File → Properties → Description → Page Size*, or *Preflight → Page info*
  (TrimBox, MediaBox).

## Workaround in Affinity

Set the document DPI (*Document Setup*) so that 1 mm is a whole number of pixels:
**254, 508, 1270 or 2540 DPI** (254 DPI = 10 px per mm). The document DPI is **not** the
resolution of images in the PDF – photos are resampled to 300 DPI by the export settings anyway.
The simplest is a document template with 254 DPI.

304.8 DPI (120 px/cm), suggested on the forum, gets rounded to 305 in the *New Document* dialog,
and Publisher does not accept a fractional DPI at all.

That is why the Imprimo samples are made in **Illustrator**.

## Status at Serif / Canva

- Affinity forum: [Size adding 0.05mm when exporting to pdf](https://forum.affinity.serif.com/index.php?/topic/232218-affinity-designer-v2-size-adding-005mm-when-exporting-to-pdf/)
  (May 2025). The bug is logged as **AF-1340** and, according to users, has been known for years.
- Still present in Affinity 3.3.3 (November 2026).

If you report it too, add to the existing thread or quote **AF-1340** – moderators merge new
duplicate reports. Exact steps and the attached .af and PDF help.
