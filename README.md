# Maakondade ja KOV-ide tervise- ja sotsiaalnäitajad

Ministri visiitide memode tarbeks: iga maakonna ja KOV-i põhinäitajad koos Eesti keskmise, järjekoha ja värvikoodiga.

**Kuidas see töötab**

1. `.github/workflows/update.yml` käivitub iga esmaspäeva hommikul (või käsitsi: *Actions → Andmete uuendamine ja veebileht → Run workflow*).
2. `scripts/catalog.py` koostab TAI andmebaasi tabelite kataloogi (`data/catalog.json`).
3. `scripts/fetch_data.py` tõmbab näitajad vastavalt failile `config/indicators.json` ja kirjutab `site/data/indicators.json`. Iga näitaja õnnestumine või viga on failis `data/fetch_log.json`.
4. Veebileht (`site/index.html`) avaldatakse GitHub Pages'is.

**Näitaja lisamine:** lisa kirje faili `config/indicators.json` (allikas, tabeli kood, valikud). Ülejäänu käib automaatselt.

Andmeallikad: Statistikaamet (andmed.stat.ee), Tervise Arengu Instituut (statistika.tai.ee).
