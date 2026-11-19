"""Justiitsandmete statistika (statistika.justdigi.ee): lehe sees olev CSV-fail."""
import csv
import io
import re
import urllib.parse
import urllib.request

BASE = "https://statistika.justdigi.ee"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (maakondade-naitajad)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def page_csv(page_path):
    """Leiab lehelt CSV lingi ja tagastab (csv_url, read listina)."""
    html = _get(BASE + page_path).decode("utf-8", "replace")
    links = re.findall(r'["\'](/sites/default/files/[^"\']+?\.csv)["\']', html)
    if not links:
        raise RuntimeError("Lehelt ei leitud CSV-faili")
    url = BASE + links[0]
    raw = _get(url)
    for enc in ("utf-8-sig", "cp1257", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dialect = csv.Sniffer().sniff(text[:2000], delimiters=";,\t")
    rows = list(csv.reader(io.StringIO(text), dialect))
    return url, rows
