"""Väike PxWeb API klient (Statistikaamet, TAI). Ainult standardteek."""
import json
import re
import time
import urllib.request
import urllib.error

UA = {"User-Agent": "maakondade-naitajad/1.0 (+github actions)", "Content-Type": "application/json"}

TOTAL_RE = re.compile(r"(kokku|mehed ja naised|kõik|total|eesti$|^eesti|kogu eesti|vanuserühmad kokku|sugu kokku)", re.I)
AREA_RE = re.compile(r"(maakond|haldusüksus|elukoht|piirkond|omavalitsus|kov|county)", re.I)


def _req(url, data=None, tries=4):
    body = json.dumps(data).encode() if data is not None else None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=UA, method="POST" if body else "GET")
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            raise RuntimeError(f"HTTP {e.code} {url}: {e.read()[:300]!r}")
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            raise
    raise RuntimeError(f"Päring ebaõnnestus: {url}")


def get(url):
    return _req(url)


def meta(table_url):
    return _req(table_url)


def walk(base, path="", depth=0, max_depth=6, out=None):
    """Käib PxWeb andmebaasi puu läbi ja tagastab tabelite loendi (id, tekst, url)."""
    out = [] if out is None else out
    url = base.rstrip("/") + ("/" + path if path else "")
    try:
        items = _req(url)
    except Exception as e:  # noqa
        print(f"  ! ei saanud {url}: {e}")
        return out
    for it in items if isinstance(items, list) else []:
        nid = it.get("id")
        if it.get("type") == "t":
            out.append({"id": nid, "text": it.get("text"), "url": url + "/" + nid, "updated": it.get("updated")})
        elif it.get("type") == "l" and depth < max_depth:
            walk(base, (path + "/" if path else "") + nid, depth + 1, max_depth, out)
            time.sleep(0.15)
    return out


def build_query(m, years=None, select=None, area_var=None):
    """Koostab päringu. select = {muutuja_teksti_regex: väärtuse_teksti_regex}."""
    select = select or {}
    q = []
    info = {}
    for v in m["variables"]:
        code, text = v["code"], v["text"]
        vals, vtexts = v["values"], v.get("valueTexts", v["values"])
        chosen = None
        for vre, valre in select.items():
            if re.search(vre, text, re.I) or re.search(vre, code, re.I):
                hits = [c for c, t in zip(vals, vtexts) if re.search(valre, t, re.I)]
                if hits:
                    chosen = hits
                    break
        if chosen is None:
            if v.get("time") or re.search(r"^(aasta|vaatlusperiood|periood|year)", text, re.I):
                chosen = vals[-(years or 1):] if years else vals
                info["time"] = code
            elif (area_var and (re.search(area_var, text, re.I) or re.search(area_var, code, re.I))) or (not area_var and AREA_RE.search(text)):
                chosen = vals
                info["area"] = code
            else:
                tot = [c for c, t in zip(vals, vtexts) if TOTAL_RE.search(t.strip(". "))]
                if tot:
                    chosen = tot[:1]
                elif v.get("elimination"):
                    continue
                else:
                    chosen = vals[:1]
        q.append({"code": code, "selection": {"filter": "item", "values": chosen}})
    return {"query": q, "response": {"format": "json-stat2"}}, info


def jsonstat_rows(js):
    """json-stat2 → ridade loend {dimensiooni_kood: väärtuse_tekst, ..., 'value': float}."""
    ids = js["id"]
    sizes = js["size"]
    dims = []
    for d in ids:
        cat = js["dimension"][d]["category"]
        idx = cat["index"]
        order = sorted(idx, key=lambda k: idx[k]) if isinstance(idx, dict) else idx
        labels = cat.get("label", {})
        dims.append([(k, labels.get(k, k)) for k in order])
    vals = js["value"]
    rows = []
    n = len(vals) if isinstance(vals, list) else 0
    for flat in range(n):
        rem = flat
        coords = []
        for s in reversed(sizes):
            coords.append(rem % s)
            rem //= s
        coords.reverse()
        row = {ids[i]: dims[i][c][1] for i, c in enumerate(coords)}
        row.update({ids[i] + "__code": dims[i][c][0] for i, c in enumerate(coords)})
        row["value"] = vals[flat]
        rows.append(row)
    if isinstance(vals, dict):
        for k, val in vals.items():
            rem = int(k)
            coords = []
            for s in reversed(sizes):
                coords.append(rem % s)
                rem //= s
            coords.reverse()
            row = {ids[i]: dims[i][c][1] for i, c in enumerate(coords)}
            row["value"] = val
            rows.append(row)
    return rows


def fetch_table(table_url, years=None, select=None, area_var=None):
    m = meta(table_url)
    q, info = build_query(m, years=years, select=select, area_var=area_var)
    js = _req(table_url, q)
    return m, info, jsonstat_rows(js)
