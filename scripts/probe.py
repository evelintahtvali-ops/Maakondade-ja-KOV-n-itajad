"""Abiskript: salvestab kandidaattabelite muutujad ja väärtused (data/probe.json)."""
import json, sys, time
sys.path.insert(0, "scripts")
from pxweb import meta, get

TAI = "https://statistika.tai.ee/api/v1/et/Andmebaas/"
STAT = "https://andmed.stat.ee/api/v1/et/stat/"
cat = {t["id"].split(".")[0].upper(): t["url"] for t in json.load(open("data/catalog.json"))["tai"]}
tai_ids = ["KU121", "PTU700", "SD23", "SD35", "SD40", "EH04", "PK40", "NH11", "NH10", "COSI02", "PO03", "PO02", "VIG14", "SD29", "UP03", "LO01"]
stat_ids = ["LES85", "PA119", "PA107", "PA117", "UA07", "SK410", "THV21", "THV23", "SK154", "RV063U", "UA16", "RV49U", "RV112U"]
out = {"tables": {}, "search": {}}
for tid in tai_ids + stat_ids:
    url = cat.get(tid) if tid in tai_ids else STAT + tid
    try:
        m = meta(url)
        out["tables"][tid] = {"url": url, "title": m.get("title"),
            "variables": [{"code": v["code"], "text": v["text"], "time": v.get("time", False),
                           "values": v.get("valueTexts", v["values"])[:400]} for v in m["variables"]]}
    except Exception as e:
        out["tables"][tid] = {"url": url, "error": str(e)[:300]}
    time.sleep(0.3)
import urllib.parse
for q in ["lastekaitse", "asendushooldus", "abivajav laps", "laste vaesus", "noored", "puudega lapsed", "perekonnas hooldamine", "huviharidus", "koolist väljalangenud", "NEET"]:
    try:
        out["search"][q] = [(t["id"], t["title"]) for t in get(STAT + "?query=" + urllib.parse.quote(q))][:30]
    except Exception as e:
        out["search"][q] = str(e)[:200]
json.dump(out, open("data/probe.json", "w"), ensure_ascii=False, indent=1)
print("ok", len(out["tables"]))
