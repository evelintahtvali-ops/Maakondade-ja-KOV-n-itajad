"""Koostab andmeallikate kataloogi (TAI tabelite puu + Statistikaameti otsing),
et leida õiged tabelikoodid. Tulemus: data/catalog.json"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import pxweb  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "catalog.json")

TAI_BASE = "https://statistika.tai.ee/api/v1/et/Andmebaas"
STAT_BASE = "https://andmed.stat.ee/api/v1/et/stat"
STAT_QUERIES = ["rahvastik haldusüksus", "oodatav eluiga", "tervena elatud", "brutokuupalk maakond",
                "väärteod", "toimetulekutoetus", "registreeritud töötus", "puudega", "pension maakond"]


def main():
    cat = {"tai": [], "stat_search": {}, "errors": []}
    print("TAI andmebaasi puu ...")
    try:
        cat["tai"] = pxweb.walk(TAI_BASE)
        print(f"  {len(cat['tai'])} tabelit")
    except Exception as e:
        cat["errors"].append(f"TAI: {e}")
    for q in STAT_QUERIES:
        url = STAT_BASE + "?query=" + urllib.parse.quote(q)
        try:
            res = pxweb.get(url)
            cat["stat_search"][q] = [{"id": r.get("id"), "path": r.get("path"), "title": r.get("title")} for r in res][:40]
            print(f"Stat '{q}': {len(res)} tulemust")
        except Exception as e:
            cat["errors"].append(f"Stat {q}: {e}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
