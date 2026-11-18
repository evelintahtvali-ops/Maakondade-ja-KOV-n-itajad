"""TEHIK avaandmed (PostgREST): gripi vastu vaktsineerimise hõlmatus maakonna ja vanuserühma järgi."""
import json
import urllib.parse
import urllib.request

FLU = "https://rest-avaandmed.tehik.ee/flu/opendata_flu_vaccination_location_agegroup"


def _get(params):
    url = FLU + "?" + urllib.parse.urlencode(params, safe="(),.+*")
    req = urllib.request.Request(url, headers={"User-Agent": "maakondade-naitajad/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def flu_rows(age_filter, ages):
    rows, off, step = [], 0, 10000
    while True:
        part = _get({
            "select": "VaccinationSeason,StatisticsDate,PatientCounty,AgeGroup,TotalCount,LocationPopulation",
            "Valid": "eq.true", "LocationLevel": "eq.County", "AgeGroupFilter": f"eq.{age_filter}",
            "AgeGroup": "in.(" + ",".join(ages) + ")", "order": "StatisticsDate.asc", "limit": step, "offset": off})
        rows += part
        if len(part) < step:
            return rows
        off += step


def flu_coverage(age_filter="AgeGroup2", ages=("60-79", "80+")):
    """Tagastab {hooaeg: {"date": viimane kuupäev, "values": {maakond: %}, "eesti": %}}."""
    rows = flu_rows(age_filter, ages)
    best = {}  # (hooaeg, maakond, vanus) -> rida suurima TotalCount'iga
    last_date = {}
    for r in rows:
        k = (r["VaccinationSeason"], r["PatientCounty"], r["AgeGroup"])
        if k not in best or (r["TotalCount"] or 0) >= (best[k]["TotalCount"] or 0):
            best[k] = r
        s = r["VaccinationSeason"]
        last_date[s] = max(last_date.get(s, ""), r["StatisticsDate"] or "")
    out = {}
    for (season, county, _age), r in best.items():
        o = out.setdefault(season, {"num": {}, "den": {}, "num_all": 0})
        o["num_all"] += r["TotalCount"] or 0
        if county and r["LocationPopulation"]:
            o["num"][county] = o["num"].get(county, 0) + (r["TotalCount"] or 0)
            o["den"][county] = o["den"].get(county, 0) + r["LocationPopulation"]
    res = {}
    for season, o in out.items():
        vals = {c: round(o["num"][c] / o["den"][c] * 100, 1) for c in o["den"]}
        den = sum(o["den"].values())
        res[season] = {"date": last_date.get(season, "")[:10], "values": vals, "eesti": round(o["num_all"] / den * 100, 1) if den else None,
                       "n_rows": sum(1 for k in best if k[0] == season)}
    return res
