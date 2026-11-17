# Zadanie: nový dizajn vzorových PDF

Vzorové súbory v tomto priečinku vytvára skript `make_examples.py` – technicky správne, ale graficky
jednoduché. Toto zadanie popisuje, čo musí nový dizajn (z Affinity, InDesignu…) dodržať, aby lekcie,
návody, testy aj web Imprima fungovali ďalej. Hodí sa aj ako úloha pre študentov.

## Čo musí ostať rovnaké

| Lekcia | Súbor (názov presne takto) | Formát (mm) | Strany | Dôležité |
|---|---|---|---|---|
| 01 | `01_vizitky_90x50_obojstranne.pdf` | 90 × 50 | 2 (líc, rub) | spadávka 3 mm |
| 02 | `02_vizitka_bez_spadavky.pdf` | 90 × 50 | 1 | **bez** spadávky, farba až po orez (naschvál) |
| 03 | `03_pozvanka_A5_na_polovicu.pdf` | 210 × 148 | 2 (vonkajšok, vnútro) | spadávka 3 mm |
| 03 | `03_pozvanka_A5_bigy.pdf` | 210 × 148 | 1 | len čiara **Crease** na **105 mm** zľava |
| 04 | `04_DL_skladacka_zavinovacia.pdf` | 297 × 210 | 2 (vnútro, vonkajšok) | diely **100 / 100 / 97 mm** zľava na 1. strane |
| 04 | `04_DL_skladacka_bigy.pdf` | 297 × 210 | 1 | čiary **Crease** na **100 a 200 mm** zľava |
| 05 | `05_brozura_A5_12_stran.pdf` | 148 × 210 | **12** | čísla strán, prvok pri vonkajšom okraji (ukáže posun – creep) |
| 06 | `06_vstupenky_cut_and_stack.pdf` | 140 × 50 | **28** | čísla **001–028**, každá strana iné číslo |
| 07 | `07_vizitka_s_lakom.pdf` + `07_vizitka_lak.pdf` | 90 × 50 | 1 + 1 | lak vo farbe **Varnish** s prestrieraním, v samostatnom PDF |
| 08 | `08_chybne_pdf_na_preflight.pdf` | ľubovoľný | 1 | **naschvál chybné** – pozri nižšie |
| 09 | `09_plagat_A2.pdf` | 420 × 594 | 1 | prvky, ktoré prechádzajú cez diely (kontrola lepenia) |
| 10 | `10_vizitky_jana.pdf`, `10_vizitky_peter.pdf`, `10_vizitky_eva.pdf` | 90 × 50 | 2 každé | tri jasne odlíšené osoby (napr. farbou) |
| 11 | `11_zbornik_A6_48_stran.pdf` | 105 × 148 | **48** | čísla strán, vyznačená hlava strany |
| 11 | `11_zbornik_A6_obalka.pdf` | **212,4** × 148 | 1 | roztvorená obálka: zadná · chrbát **2,4 mm** · predná |

Polohy bigov musia sedieť presne – kontrolujú ich testy aj návody k lekciám.

## Export (všetko okrem lekcie 08)

- **PDF/X-4** (alebo *press ready*), **spadávka 3 mm** (TrimBox nastaví program sám).
- Farby **CMYK** alebo spotové, písma **vložené**, obrázky aspoň **300 ppi**.
- Spotové farby z palety Imprimo (`spot-colors/Imprimo-spot-colors.ase`, v Affinity importovaná ako
  **aplikačná** paleta, nie systémová): big = **Crease**, lak = **Varnish**.
- Bigy a lak **ako samostatné PDF**, nie v tlačovom PDF (tlačové PDF sa exportuje bez tejto vrstvy).
- Rozmer strany presne podľa tabuľky – test ho kontroluje na 0,005 mm. **Pozor na Affinity:** pri exporte
  zaokrúhľuje stranu na celé pixely (napr. 90 × 50,038 mm namiesto 90 × 50), pozri
  [affinity-page-size.md](affinity-page-size.md).

## Export po súboroch – ťahák

**Spoločné nastavenie** (Illustrator, InDesign):

- Pred prácou: *Edit → Color Settings* → **Europe Prepress 3** (najlepšie v Bridge pre celé Adobe),
  dokument: *Edit → Assign Profile* → **Coated FOGRA39**. Inak export dá U.S. Web Coated (SWOP).
- Predvoľba **[PDF/X-4:2008]** · *Output*: **No Conversion** · Output Intent: **Coated FOGRA39**
- **Illustrator** si v predvoľbe nepamätá *Output Condition Identifier* a zapíše `Custom`. Nevadí to:
  profil Coated FOGRA39 je vložený a Imprimo do vyimpozovaného PDF zapíše `FOGRA39` (zdrojové PDF nemení).
  (identifikátor `FOGRA39`).
- *Marks and Bleeds*: **žiadne značky** (orezky, pasovky robí Imprimo) · spadávka podľa tabuľky.
- Viac strán = viac kresliacich plôch (Illustrator: *All* artboards) alebo strany v InDesigne –
  **jednotlivé strany, nie dvojstrany**. Pri 28 a 48 stranách (06, 11) je jednoduchší InDesign.
- Po exporte otvor PDF v Imprime: rozmer, spadávka a „PDF/X-4 · Coated FOGRA39“ musia sedieť.

| Súbor | Strany | Orez (mm) | Spadávka | Export | Farby / pozor na |
|---|---|---|---|---|---|
| `01_vizitky_90x50_obojstranne.pdf` ✓ | 2 – líc, rub | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | CMYK |
| `02_vizitka_bez_spadavky.pdf` ✓ | 1 | 90 × 50 | **0 mm** | PDF/X-4, FOGRA39 | farba **až po orez** (nie do spadávky) |
| `03_pozvanka_A5_na_polovicu.pdf` ✓ | 2 – vonkajšok, vnútro | 210 × 148 | 3 mm | PDF/X-4, FOGRA39 | CMYK, bez čiary bigu |
| `03_pozvanka_A5_bigy.pdf` ✓ | 1 | 210 × 148 | 3 mm | PDF/X-4, FOGRA39 | **len** čiara **Crease** na **105 mm** zľava, cez spadávku, prestrieranie (overprint) |
| `04_DL_skladacka_zavinovacia.pdf` ✓ | 2 – vnútro, vonkajšok | 297 × 210 | 3 mm | PDF/X-4, FOGRA39 | diely **100 / 100 / 97 mm** zľava na 1. strane |
| `04_DL_skladacka_bigy.pdf` ✓ | 1 | 297 × 210 | 3 mm | PDF/X-4, FOGRA39 | **len** čiary **Crease** na **100 a 200 mm** zľava, overprint |
| `05_brozura_A5_12_stran.pdf` | **12** | 148 × 210 | 3 mm | PDF/X-4, FOGRA39 | čísla strán, prvok pri vonkajšom okraji (creep) |
| `06_vstupenky_cut_and_stack.pdf` | **28** | 140 × 50 | 3 mm | PDF/X-4, FOGRA39 | čísla **001–028**, každá strana iné (InDesign: *Data Merge*) |
| `07_vizitka_s_lakom.pdf` | 1 | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | CMYK, **bez** laku |
| `07_vizitka_lak.pdf` | 1 | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | **len** plochy vo farbe **Varnish**, overprint, rovnaké miesto ako v tlači |
| `08_chybne_pdf_na_preflight.pdf` | 1 | 148 × 105 | **0 mm** | **nie** PDF/X (obyčajné PDF) | **naschvál chybné** – pozri nižšie |
| `09_plagat_A2.pdf` | 1 | 420 × 594 | 3 mm | PDF/X-4, FOGRA39 | prvky, ktoré prechádzajú cez diely (kontrola lepenia) |
| `10_vizitky_jana.pdf` | 2 – líc, rub | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | osoba 1, vlastná farba |
| `10_vizitky_peter.pdf` | 2 – líc, rub | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | osoba 2, iná farba |
| `10_vizitky_eva.pdf` | 2 – líc, rub | 90 × 50 | 3 mm | PDF/X-4, FOGRA39 | osoba 3, iná farba |
| `11_zbornik_A6_48_stran.pdf` | **48** | 105 × 148 | 3 mm | PDF/X-4, FOGRA39 | čísla strán, vyznačená hlava strany |
| `11_zbornik_A6_obalka.pdf` | 1 – roztvorená | **212,4** × 148 | 3 mm | PDF/X-4, FOGRA39 | zadná 105 · chrbát **2,4** · predná 105 |

✓ = hotové. Súbory s bigmi a lakom majú **rovnaký rozmer aj spadávku** ako tlačové PDF – Imprimo
ich kladie presne na seba.

## Lekcia 08 – chyby, ktoré v PDF musia ostať

Preflight v Imprime ich má nájsť (lekcia je o hľadaní chýb):

1. farba v **RGB**,
2. **bez spadávky**,
3. obrázok s nízkym rozlíšením (**pod 100 ppi**),
4. **nevložené písmo**,
5. čiara vo farbe **Crease** priamo v tlačovom PDF.

Illustrator ani InDesign nevložené písmo pri bežnom exporte neurobia. Ak sa to nepodarí, 08 nechaj
zo skriptu `make_examples.py` (nedávaj ju do `DESIGNED`).

## Obsah

- Texty na vzoroch **po anglicky** (americký pravopis: *color*, *center*), čo najmenej textu – vzory otvárajú aj zahraniční používatelia.
- **Žiadne cudzie fotky ani písma bez licencie** – repozitár je verejný (GPL). Vlastné fotky, fotky študentov
  so súhlasom, voľné zdroje (napr. Unsplash, Pexels) a voľné písma (napr. Google Fonts) sú v poriadku.
- Mená, telefóny a e-maily **vymyslené**.
- Veľkosť súborov ideálne do pár MB – vzory sa pribaľujú ku každej verzii Imprima.

## Po dokončení

1. Súbory s rovnakými názvami dať do priečinka `examples/` (alebo poslať).
2. Spustiť testy: `python tests/test_core.py` – test `test_examples` overí, že lekcie 01–07 a 09–11
   prejdú preflightom, 08 nie, a že sa bigy nájdu na správnych miestach.
3. Číslo lekcie pridať do `DESIGNED` v `make_examples.py` – skript ju potom neprepíše (hotové: 01, 02, 03, 04).
4. Nové snímky pre web: `tools_web_screenshots.py` (návod je na začiatku skriptu).
5. Ak sa niečo v lekcii zmenilo (texty, farby), upraviť `CITAJ-MA.md` a `README.md`.
