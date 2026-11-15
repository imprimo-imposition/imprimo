# Vzorové súbory Imprimo – 10 lekcií

Vzory na vyskúšanie Imprima a na výučbu vyraďovania. Každá lekcia má PDF, predvoľbu,
postup, na čo sa pozrieť a malú úlohu. V Imprime ich otvoríš cez **Pomocník → Vzorové súbory…**,
na GitHube sú v priečinku [`examples/`](.).

Chceš vzory navrhnúť graficky po svojom? Technické požiadavky sú v [ZADANIE.md](ZADANIE.md).

Všetky farby sú CMYK alebo spotové, písmo je vložené – vzory prejdú preflightom
(okrem lekcie 08, tá je chybná naschvál). Vytvára ich skript `make_examples.py`.

| # | Súbor | Naučíš sa |
|---|---|---|
| 01 | `01_vizitky_90x50_obojstranne.pdf` | step & repeat, obojstranná tlač, spadávka 3 vs 2 mm |
| 02 | `02_vizitka_bez_spadavky.pdf` | prečo spadávka, jej doplnenie |
| 03 | `03_pozvanka_A5_na_polovicu.pdf` + `…_bigy.pdf` | bigovanie, značky B |
| 04 | `04_DL_skladacka_zavinovacia.pdf` + `…_bigy.pdf` | zavinovacia skladačka 100/100/97, big z PDF |
| 05 | `05_brozura_A5_12_stran.pdf` | väzba V1, poradie strán, posun (creep) |
| 06 | `06_vstupenky_cut_and_stack.pdf` | cut & stack – čísla po rezaní v poradí |
| 07 | `07_vizitka_s_lakom.pdf` + `07_vizitka_lak.pdf` | vrstvy, spotová farba, prestrieranie |
| 08 | `08_chybne_pdf_na_preflight.pdf` | preflight: nájdi 5 chýb |
| 09 | `09_plagat_A2.pdf` | plagát po dieloch na A4 / A3, prekryv, zväčšenie na A1 |
| 10 | `10_vizitky_jana.pdf`, `…_peter.pdf`, `…_eva.pdf` | viac zákaziek na jednom hárku (gang run) |

---

## 01 – Vizitky 90×50, obojstranne

**Súbor:** `01_vizitky_90x50_obojstranne.pdf` – strana 1 líc, strana 2 rub, spadávka 3 mm.
**Predvoľba:** ★ *Vizitky 90×50 / 85×55 – SRA3 obojstranne, spadávka 3 mm*

1. Otvor PDF, zvoľ predvoľbu. Na hárku je **21 vizitiek** (3 × 7).
2. Prepni na predvoľbu ★ *…spadávka 2 mm (24 ks)*. Rovnaké PDF – **24 vizitiek**.
3. Prepni náhľad **Prehľad hárkov**: líc a rub hárku vedľa seba.

**Pozri sa:** zapni *Čísla strán* – na rube sú vizitky zrkadlovo, aby po otočení hárku sedeli na líc.
Medzera medzi kusmi je 2 × spadávka, takže každá vizitka má vlastnú spadávku a reže sa dvakrát.

**Úloha:** prečo sa pri vizitke 85×55 ani s 2 mm spadávkou nezmestí 24 kusov? (Spočítaj výšku hárku.)

## 02 – Vizitka bez spadávky

**Súbor:** `02_vizitka_bez_spadavky.pdf` – farba končí presne na oreze.
**Predvoľba:** ★ *Vizitky … jednostranne, spadávka 3 mm*

1. Pod hárkom sa objaví upozornenie, že PDF má spadávku 0 mm.
2. Priblíž sa k okraju vizitky: medzi kusmi je **biela medzera** – po rezaní by na okraji mohla ostať biela linka.
3. V sekcii **Spadávka → Chýbajúca** zvoľ *Doplniť zrkadlením okraja*, potom *natiahnutím*.

**Pozri sa:** ako vyzerajú pruhy pri zrkadlení a pri natiahnutí. Ktorá metóda sa hodí na fotku, ktorá na jednofarebné pozadie?

**Úloha:** prečo je stále najlepšie exportovať PDF so spadávkou priamo z Affinity / InDesignu?

## 03 – Pozvánka A5 na polovicu

**Súbory:** `03_pozvanka_A5_na_polovicu.pdf` (strana 1 vonkajšok, strana 2 vnútro),
`03_pozvanka_A5_bigy.pdf` (čiara bigu vo farbe **Crease**).
**Predvoľba:** ★ *Pozvánka na polovicu – SRA3, big*

1. Zvoľ predvoľbu – big je **na polovicu**, Imprimo vypočíta 105 mm.
2. Zapni *Pomocné čiary*: big je zelená bodkočiarkovaná čiara. Na okraji hárku sú značky **B** pre ručnú bigovačku.
3. Prepni *Big* na **Z PDF s bigmi** a cez *Vybrať PDF…* vyber `03_pozvanka_A5_bigy.pdf`. Imprimo nájde 1 big na 105 mm.

**Pozri sa:** v informačnom riadku na okraji hárku je *„Big zvislý: 105 mm od kraja“* – podľa toho nastavíš doraz, keď bigujete až po rezaní.

**Úloha:** otvor `03_pozvanka_A5_bigy.pdf` ako tlačové PDF. Čo hovorí preflight a prečo?

## 04 – DL zavinovacia skladačka

**Súbory:** `04_DL_skladacka_zavinovacia.pdf` (strana 1 vnútro 100 / 100 / 97 mm, strana 2 vonkajšok),
`04_DL_skladacka_bigy.pdf` (bigy na 100 a 200 mm).
**Predvoľba:** ★ *DL zavinovacia skladačka – SRA3, 2 bigy*

1. Predvoľba nastaví bigy **100 a 200 mm** – posledný diel je o 3 mm užší.
2. Zvoľ *Big → Z PDF s bigmi* a vyber `04_DL_skladacka_bigy.pdf` – výsledok je rovnaký.
3. Pozri rub v *Prehľade hárkov*: bigy sú na rube zrkadlovo (97 a 197 mm), lebo skladačka nie je súmerná.

**Pozri sa:** prečo je vnútorný diel užší? (Pri zložení sa zasúva dovnútra – keby bol rovnako široký, krčil by sa.)

**Úloha:** zmeň *Big* na **Z skladačka** (3 rovnaké diely). Aké polohy vypočíta Imprimo a kedy sa Z skladačka používa?

## 05 – Brožúra A5, 12 strán

**Súbor:** `05_brozura_A5_12_stran.pdf` – 12 strán A5, oranžový pruh 4 mm od vonkajšieho okraja.
**Predvoľba:** ★ *Brožúra V1 – SRA3*

1. Imprimo vyradí 12 strán na **3 hárky** – v *Prehľade hárkov* je na prvom hárku strana 12 vedľa 1, na rube 2 vedľa 11.
2. Zapni *Čísla strán* a skontroluj poradie: po zložení a zošití musia ísť strany 1 → 12.
3. V sekcii *Brožúra* nastav **posun (creep)** napr. 0,5 mm a sleduj oranžový pruh na vnútorných hárkoch.

**Pozri sa:** pri hrubšej brožúre vnútorné hárky po zložení vytŕčajú – posun ich obsah odsunie ku chrbtu,
aby po orezaní ostal pruh všade rovnako ďaleko od okraja.

**Úloha:** koľko hárkov treba na 20-stranovú brožúru? A na 18-stranovú (čo urobí Imprimo so stranami navyše)?

## 06 – Vstupenky, cut & stack

**Súbor:** `06_vstupenky_cut_and_stack.pdf` – 28 lístkov č. 001 až 028.
**Predvoľba:** ★ *Vstupenky – cut & stack, SRA3*

1. Na hárok sa zmestí **14 lístkov**, 28 lístkov = **2 hárky**.
2. Pozri čísla na prvom hárku: 1, 3, 5… nie sú za sebou – sú rozložené do **kôpok**.
3. Po vytlačení sa hárky položia na seba, rozrežú a kôpky sa položia na seba – čísla idú **001 → 028 po poradí**.

**Pozri sa:** cut & stack sa používa pri všetkom číslovanom – vstupenky, tombola, poukážky, bloky.

**Úloha:** do poľa *Strany* napíš `1-24`. Aké upozornenie Imprimo ukáže a prečo?

## 07 – Vizitka s parciálnym lakom

**Súbory:** `07_vizitka_s_lakom.pdf` (tlač), `07_vizitka_lak.pdf` (lak vo farbe **Varnish** s prestrieraním).
**Predvoľba:** ★ *Vizitky … jednostranne, spadávka 3 mm*

1. Otvor tlačové PDF, potom **+ Pridať vrstvu (PDF)…** a vyber `07_vizitka_lak.pdf`. Imprimo spozná typ **Lak**.
2. V náhľade je lak polopriehľadný – presne na nápise a kruhoch.
3. Pri uložení zapni *Vrstvy samostatne* – vznikne `…_imposed.pdf` (tlač) a `…_imposed_varnish.pdf` (lak).

**Pozri sa:** kontrola pod vrstvou píše, či má lak spotovú farbu a prestrieranie. Bez nich by lak na stroji
„vykrojil“ tlač pod sebou.

**Úloha:** prečo sa lak nedáva do tlačového PDF ako obyčajná farba (napr. žltá CMYK)?

## 08 – Chybné PDF na preflight

**Súbor:** `08_chybne_pdf_na_preflight.pdf` – pohľadnica s piatimi chybami.

1. Otvor PDF v Imprime a pozri **preflight** v sekcii *Export PDF*.
2. Nájdi všetkých 5 chýb a pri každej povedz, ako by si ju opravil v Affinity / InDesigne.

<details><summary>Riešenie</summary>

1. **RGB farba** pozadia – treba CMYK (alebo prevod pri exporte do PDF/X).
2. **Bez spadávky** – pozadie končí na oreze (Imprimo vie doplniť, ale lepšie je exportovať so spadávkou).
3. **Obrázok s rozlíšením 27 ppi** – na tlač treba aspoň 250–300 ppi.
4. **Nevložené písmo** Helvetica – pri exporte treba písma vložiť.
5. **Čiara bigu vo farbe Crease v tlačovom PDF** – vytlačila by sa; patrí do samostatného PDF.

</details>

## 09 – Plagát A2 po dieloch

**Súbor:** `09_plagat_A2.pdf` – plagát 420 × 594 mm so šikmými čiarami a kruhmi na kontrolu lepenia.
**Predvoľba:** ★ *Plagát po dieloch – A4, prekryv 10 mm*

1. Imprimo rozdelí plagát na **8 dielov A4** (2 × 4). V *Prehľade hárkov* sú poskladané ako hotový plagát.
2. Diely sa volajú **A1, A2, B1…** (riadky písmenami, stĺpce číslami); na okraji každého je **mapka**, kde diel leží.
3. Zmeň *Tlačový hárok* na **A3** – dielov je menej. V sekcii *Plagát* zvoľ *Výsledná veľkosť* **A1** – mierka sa nastaví sama.

**Ako lepiť:** každý diel odrež pri **orezových ryskách** (vľavo a hore), polož ho na susedný diel tak, aby
prekryl jeho okraj po **prerušovanú rysku**, a zlep. Šikmé čiary a kruhy musia nadväzovať bez schodíka.

**Pozri sa:** *Okraj hárka* = okraj, ktorý tlačiareň nevytlačí (zvyčajne 5–10 mm). Prekryv musí byť menší ako diel.

**Úloha:** koľko hárkov A4 a koľko A3 treba na plagát A1? Čo je lacnejšie a čo sa ľahšie lepí?

## 10 – Vizitky troch ľudí na jednom hárku (gang run)

**Súbory:** `10_vizitky_jana.pdf`, `10_vizitky_peter.pdf`, `10_vizitky_eva.pdf` – každé líc a rub.
**Predvoľba:** ★ *Vizitky viacerých ľudí (gang run) – SRA3 obojstranne, spadávka 2 mm*

1. Otvor lekciu – Jana je prvá zákazka (**A**). V sekcii **Zákazky na hárku** klikni **+ Pridať PDF…**
   a pridaj Petra a Evu (alebo ich pretiahni do okna).
2. Nastav počty: Jana **100 ks**, Peter **250 ks**, Eva **50 ks**.
3. Imprimo rozdelí 24 miest na hárku podľa počtov: **A 6 · B 15 · C 3** a vypočíta **17 hárkov**
   (Peter potrebuje 250 / 15 = 16,7 → 17). Navyše vznikne 2 + 5 + 1 kusov.
4. Zapni *Čísla strán*: namiesto čísel sú na vizitkách písmená zákaziek A, B, C.

**Pozri sa:** v informačnom riadku na okraji hárka je, na ktorých miestach je ktorá zákazka (A 1–6, B 7–21, C 22–24) –
podľa toho sa po rezaní kôpky roztriedia. Bez gang runu by to boli 3 samostatné tlače: 5 + 11 + 3 = 19 hárkov.

**Úloha:** zmeň Evu na 300 ks. Ako sa zmení rozdelenie miest a počet hárkov? Kedy sa gang run neoplatí?

---

Ďalšie lekcie pribudnú s ďalšími funkciami Imprima.
