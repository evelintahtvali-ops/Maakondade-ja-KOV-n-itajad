# Maakondade ja KOV-ide tervise- ja sotsiaalnäitajad

Ministri visiitide memode tarbeks: iga maakonna ja KOV-i põhinäitajad koos Eesti keskmise, järjekoha ja värvikoodiga.

**Kuidas see töötab**

1. `.github/workflows/update.yml` käivitub iga esmaspäeva hommikul (või käsitsi: *Actions → Andmete uuendamine ja veebileht → Run workflow*).
2. `scripts/catalog.py` koostab TAI andmebaasi tabelite kataloogi (`data/catalog.json`).
3. `scripts/fetch_data.py` tõmbab näitajad vastavalt failile `config/indicators.json` ja kirjutab `site/data/indicators.json`. Iga näitaja õnnestumine või viga on failis `data/fetch_log.json`.
4. Veebileht (`site/index.html`) avaldatakse GitHub Pages'is.

**Näitaja lisamine:** lisa kirje faili `config/indicators.json` (allikas, tabeli kood, valikud). Ülejäänu käib automaatselt.

Andmeallikad: Statistikaamet (andmed.stat.ee), Tervise Arengu Instituut (statistika.tai.ee).

## Vaated
- **Piirkonna profiil** – kõik näitajad valitud maakonna või KOV-i kohta (KOV puhul kõrval ka maakonna väärtus), Eesti keskmine, koht, muutus võrdlusaastaga ja kontekst. „Kopeeri memo tekst“ teeb punktidena memo read.
- **Näitaja võrdlus** – ühe näitaja järjestus: maakonnad, KOV-id, valitud maakonna KOV-id või kõik koos ühes tabelis. Kaardid näitavad kohta ning kes on vahetult ees ja taga. Real klõpsates valitakse piirkond.
- Lehe aadress jätab valiku meelde (nt `#t=cmp&a=Rapla vald&n=palk&f=county`), nii saab lingi kolleegile saata.

## Näitajad
33 näitajat (`config/indicators.json`): rahvastik ja vanuskoosseis, oodatav eluiga ja tervena elatud aastad, suremus (standarditud), haigestumus, laste ülekaal, sõeluuringud, vaktsineerimine, väärteod, palk, pension, vaesus, toimetulekutoetus, puue. KOV tasemel: rahvastik, palk, toimetulekutoetus, väärteod ja joobes juhid; ülejäänud on maakonna tasemel.
