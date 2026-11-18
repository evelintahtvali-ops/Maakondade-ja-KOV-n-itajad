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
import tehik  # noqa: E402

ROOT = os.path.join(HERE, "..")
CONFIG = os.path.join(ROOT, "config", "indicators.json")
CATALOG = os.path.join(ROOT, "data", "catalog.json")
OUT = os.path.join(ROOT, "site", "data", "indicators.json")
LOG = os.path.join(ROOT, "data", "fetch_log.json")

STAT_BASE = "https://andmed.stat.ee/api/v1/et/stat"
TAI_BASE = "https://statistika.tai.ee/api/v1/et/Andmebaas"
EESTI_RE = re.compile(r"^(kogu eesti|eesti kokku|eesti|kokku|eesti keskmine)$", re.I)


def clean(name):
    n = re.sub(r"^[.\s\u2026]+", "", str(name)).strip().rstrip("*").strip()
    if n.isupper():  # nt "RAPLA MAAKOND" -> "Rapla maakond"
        n = n.lower()
        n = "-".join(w[:1].upper() + w[1:] for w in n.split("-"))
    return n


def level_of(name):
    n = clean(name).lower()
    if EESTI_RE.match(n):
        return "eesti"
    if "v.a" in n or "linnasisene" in n or "kuni 20" in n:
        return None
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


def extract(rows, info, key=None):
    """Tagastab {aasta: {piirkond: väärtus}}; key andmisel {aasta: {key_väärtus: {piirkond: väärtus}}}."""
    tcode, acode = info.get("time"), info.get("area")
    if not acode:
        raise RuntimeError("Piirkonna dimensiooni ei tuvastatud")
    by_year = {}
    for r in rows:
        if r["value"] is None:
            continue
        y = r.get(tcode, "") if tcode else ""
        d = by_year.setdefault(y, {})
        if key:
            d = d.setdefault(r[key], {})
        d[clean(r[acode])] = r["value"]
    return by_year


def var_code(m, rx):
    for v in m["variables"]:
        if re.search(rx, v["text"], re.I) or re.search(rx, v["code"], re.I):
            return v["code"]
    raise RuntimeError(f"Muutujat {rx} ei leitud")


def compute(ind, m, info, rows):
    """Tagastab {aasta: {piirkond: väärtus}} arvestades ratio/avg_years seadeid."""
    r = ind.get("ratio")
    if r:
        code = var_code(m, r["var"])
        raw = extract(rows, info, key=code)
        out = {}
        for y, parts in raw.items():
            num = next((v for k, v in parts.items() if re.search(r["num"], k, re.I)), {})
            den = next((v for k, v in parts.items() if re.search(r["den"], k, re.I)), {})
            out[y] = {a: round(num[a] / den[a] * r.get("scale", 100), 2) for a in num if den.get(a)}
        return out
    return extract(rows, info)


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    catalog = json.load(open(CATALOG, encoding="utf-8")) if os.path.exists(CATALOG) else {}
    out = {"generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "indicators": [], "areas": {"maakond": [], "kov": []}, "kov_county": {}}
    log = []
    for ind in cfg["indicators"]:
        entry = {"id": ind["id"], "ok": False}
        try:
            if ind["source"] == "tehik_flu":
                res = tehik.flu_coverage(ind.get("age_filter", "AgeGroup2"), tuple(ind.get("ages", ["60-79", "80+"])))
                seasons = sorted(res)
                entry["seasons"] = {k: {"date": v["date"], "eesti": v["eesti"], "n": len(v["values"]), "sample": dict(list(v["values"].items())[:3])} for k, v in res.items()}
                idx = -1 if ind.get("season", "current") == "current" else -2
                season = seasons[idx]
                cur = res[season]
                values = {clean(k): v for k, v in cur["values"].items() if level_of(k) == "maakond"}
                if not values:
                    raise RuntimeError(f"Maakondi ei leitud: {list(cur['values'])[:5]}")
                base = {k: ind[k] for k in ("id", "group", "name", "unit", "higher_is_better")}
                rec = {**base, "year": f"{season}" + (f" seis {cur['date']}" if idx == -1 else ""), "source": "tehik",
                       "source_url": "https://teabekeskus.tehik.ee/et/avaandmed/gripp/", "table": "TEHIK avaandmed", "eesti": cur["eesti"], "values": values}
                if ind.get("note"):
                    rec["note"] = ind["note"]
                if idx == -2 and len(seasons) >= 3:
                    ps = seasons[idx - 1]
                    pv = res[ps]
                    rec["prev"] = {"year": ps, "eesti": pv["eesti"], "values": {clean(k): v for k, v in pv["values"].items() if clean(k) in values}}
                out["indicators"].append(rec)
                entry.update(ok=True, year=rec["year"], n_areas=len(values), eesti=cur["eesti"])
                print(f"OK  {ind['id']}: {rec['year']}, {len(values)} maakonda, Eesti={cur['eesti']}")
                log.append(entry)
                continue
            url = resolve_table(ind, catalog)
            entry["url"] = url
            sel = dict(ind.get("select") or {})
            if ind.get("ratio"):
                r = ind["ratio"]
                sel[r["var"]] = f"({r['num']})|({r['den']})"
            nyears = max(ind.get("years", 1), ind.get("avg_years", 1), ind.get("trend_years", 1))
            m, info, rows = pxweb.fetch_table(url, years=nyears, select=sel, area_var=ind.get("area_var"))
            entry["title"] = m.get("title")
            entry["variables"] = [{"code": v["code"], "text": v["text"], "n": len(v["values"]), "sample": v.get("valueTexts", v["values"])[:8]} for v in m["variables"]]
            by_year = compute(ind, m, info, rows)
            years = sorted(by_year)
            last = years[-1]
            vals = dict(by_year[last])
            year_label = last
            if ind.get("avg_years", 1) > 1:
                use = years[-ind["avg_years"]:]
                keys = set().union(*(by_year[y] for y in use))
                vals = {k: round(sum(by_year[y][k] for y in use) / len(use), 2) for k in keys if all(k in by_year[y] for y in use)}
                year_label = f"{use[0]}–{use[-1]}"
            eesti = next((v for k, v in vals.items() if level_of(k) == "eesti"), None)
            values = {k: v for k, v in vals.items() if level_of(k) in ("maakond", "kov")}
            if not values:
                raise RuntimeError(f"Piirkondi ei leitud; näiteid: {list(vals)[:10]}")
            prev = None
            if ind.get("trend_years", 1) > 1 and len(years) > 1:
                fy = years[0]
                pv = by_year[fy]
                prev = {"year": fy, "eesti": next((v for k, v in pv.items() if level_of(k) == "eesti"), None),
                        "values": {k: v for k, v in pv.items() if k in values}}
            base = {k: ind[k] for k in ("id", "group", "name", "unit", "higher_is_better")}
            rec = {**base, "year": year_label, "source": ind["source"], "source_url": url, "table": (m.get("title") or "").split(":")[0], "eesti": eesti, "values": values}
            if ind.get("note"):
                rec["note"] = ind["note"]
            if prev:
                rec["prev"] = prev
            out["indicators"].append(rec)
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
            entry.update(ok=True, year=year_label, n_areas=len(values), eesti=eesti)
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
