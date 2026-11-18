"""Tõmbab näitajad konfiguratsiooni järgi ja kirjutab site/data/indicators.json.
Iga näitaja vead logitakse, aga need ei peata teisi."""
import datetime as dt
import json
import os
import re
import sys
import traceback

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import pxweb  # noqa: E402

ROOT = os.path.join(HERE, "..")
CONFIG = os.path.join(ROOT, "config", "indicators.json")
CATALOG = os.path.join(ROOT, "data", "catalog.json")
OUT = os.path.join(ROOT, "site", "data", "indicators.json")
LOG = os.path.join(ROOT, "data", "fetch_log.json")

STAT_BASE = "https://andmed.stat.ee/api/v1/et/stat"
TAI_BASE = "https://statistika.tai.ee/api/v1/et/Andmebaas"
EESTI_RE = re.compile(r"^(kogu eesti|eesti kokku|eesti|kokku|eesti keskmine)$", re.I)


def clean(name):
    return re.sub(r"^[.\s]+", "", str(name)).strip()


def level_of(name):
    n = clean(name).lower()
    if EESTI_RE.match(n):
        return "eesti"
    if n.endswith("maakond"):
        return "maakond"
    if re.search(r"(vald|linn)(\s*\(.*\))?$", n):
        return "kov"
    return None


def resolve_table(ind, catalog):
    if ind["source"] == "stat":
        return f"{STAT_BASE}/{ind['table']}"
    tables = catalog.get("tai", [])
    if ind.get("table"):
        code = ind["table"].lower()
        for t in tables:
            if t["id"].lower().split(".")[0] == code:
                return t["url"]
        raise RuntimeError(f"TAI tabelit {ind['table']} ei leitud kataloogist")
    rx = re.compile(ind["find_regex"], re.I)
    hits = [t for t in tables if rx.search(t["text"] or "")]
    if not hits:
        raise RuntimeError(f"Ühtegi TAI tabelit ei vasta mustrile {ind['find_regex']}")
    return hits[0]["url"]


def extract(rows, info):
    tcode, acode = info.get("time"), info.get("area")
    if not acode:
        raise RuntimeError("Piirkonna dimensiooni ei tuvastatud")
    by_year = {}
    for r in rows:
        if r["value"] is None:
            continue
        y = r.get(tcode, "") if tcode else ""
        by_year.setdefault(y, {})[clean(r[acode])] = r["value"]
    return by_year


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    catalog = json.load(open(CATALOG, encoding="utf-8")) if os.path.exists(CATALOG) else {}
    out = {"generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "indicators": [], "areas": {"maakond": [], "kov": []}, "kov_county": {}}
    log = []
    for ind in cfg["indicators"]:
        entry = {"id": ind["id"], "ok": False}
        try:
            url = resolve_table(ind, catalog)
            entry["url"] = url
            m, info, rows = pxweb.fetch_table(url, years=ind.get("years", 1), select=ind.get("select"), area_var=ind.get("area_var"))
            entry["title"] = m.get("title")
            entry["variables"] = [{"code": v["code"], "text": v["text"], "n": len(v["values"]), "sample": v.get("valueTexts", v["values"])[:8]} for v in m["variables"]]
            by_year = extract(rows, info)
            years = sorted(by_year)
            last = years[-1]
            vals = by_year[last]
            eesti = next((v for k, v in vals.items() if level_of(k) == "eesti"), None)
            values = {k: v for k, v in vals.items() if level_of(k) in ("maakond", "kov")}
            if not values:
                raise RuntimeError(f"Piirkondi ei leitud; näiteid: {list(vals)[:10]}")
            base = {k: ind[k] for k in ("id", "group", "name", "unit", "higher_is_better")}
            out["indicators"].append({**base, "year": last, "source": ind["source"], "source_url": url, "eesti": eesti, "values": values})
            # KOV -> maakond seos järjekorra põhjal (Statistikaameti haldusüksuste loend)
            if ind["id"] == "rahvaarv":
                cur = None
                for r in rows:
                    if r.get(info.get("time")) != last:
                        continue
                    nm = clean(r[info["area"]])
                    lv = level_of(nm)
                    if lv == "maakond":
                        cur = nm
                    elif lv == "kov" and cur:
                        out["kov_county"][nm] = cur
            d = ind.get("derive_change_from_first_year")
            if d and len(years) > 1:
                first = by_year[years[0]]
                ch = {k: round((v / first[k] - 1) * 100, 1) for k, v in values.items() if first.get(k)}
                ee = round((eesti / first.get(next(k for k in first if level_of(k) == "eesti")) - 1) * 100, 1) if eesti else None
                out["indicators"].append({"id": d["id"], "group": ind["group"], "name": f"{d['name']} {years[0]}–{last}", "unit": d["unit"], "higher_is_better": None,
                                          "year": last, "source": ind["source"], "source_url": url, "eesti": ee, "values": ch})
            entry.update(ok=True, year=last, n_areas=len(values), eesti=eesti)
            print(f"OK  {ind['id']}: {last}, {len(values)} piirkonda, Eesti={eesti}")
        except Exception as e:
            entry["error"] = f"{e}"
            entry["trace"] = traceback.format_exc()[-800:]
            print(f"VIGA {ind['id']}: {e}")
        log.append(entry)
    names = set()
    for i in out["indicators"]:
        names.update(i["values"])
    out["areas"]["maakond"] = sorted(n for n in names if level_of(n) == "maakond")
    out["areas"]["kov"] = sorted(n for n in names if level_of(n) == "kov")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for e in log if e["ok"])
    print(f"Valmis: {ok}/{len(log)} näitajat õnnestus")


if __name__ == "__main__":
    main()
