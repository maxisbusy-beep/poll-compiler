"""Fetch Wikipedia pages that hold poll tables and results (SPEC.md 3.2).

Two steps, both run on GitHub's servers (this needs network access to Wikipedia):

  python -m pipeline.fetch_wikipedia discover --cycle 2026
      Finds the pages for one cycle and writes config/sources/<cycle>.yaml:
      every Senate race page, every "House elections in <State>" page, and
      candidate pages for the national generic ballot. Review that file; it is
      the list of what gets scraped. Re-running keeps manual edits under `extra`.

  python -m pipeline.fetch_wikipedia fetch --cycle 2026
      Downloads each page through the MediaWiki API, keeps only headings and
      tables (to keep the repo small), and saves data/raw/<cycle>/<slug>.html
      with the page title and revision id in a header comment, so every number
      traces to an exact revision.

Etiquette: descriptive User-Agent, one request at a time, >= 1 s apart.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "config" / "sources"
RAW_DIR = ROOT / "data" / "raw"
API = "https://en.wikipedia.org/w/api.php"
UA = ("poll-compiler/0.3 (https://github.com/maxisbusy-beep/poll-compiler; "
      "open-source poll aggregator) python-urllib")
_last_call = 0.0


def api(params: dict) -> dict:
    """One MediaWiki API call, rate-limited, with simple retry on 429/5xx."""
    global _last_call
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        wait = 1.0 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def page_links(title: str) -> list[str]:
    out, cont = [], {}
    while True:
        d = api({"action": "query", "prop": "links", "titles": title, "pllimit": "max",
                 "plnamespace": 0, "redirects": 1, **cont})
        for p in d["query"]["pages"]:
            out += [link["title"] for link in p.get("links", [])]
        if "continue" not in d:
            return out
        cont = d["continue"]


def search_titles(query: str, limit: int = 10) -> list[str]:
    d = api({"action": "query", "list": "search", "srsearch": query, "srlimit": limit,
             "srnamespace": 0})
    return [h["title"] for h in d["query"]["search"]]


def discover(cycle: int) -> dict:
    y = str(cycle)
    sen_hub = f"{y} United States Senate elections"
    house_hub = f"{y} United States House of Representatives elections"
    sen_re = re.compile(rf"^{y} United States Senate (special )?elections? in [A-Z][\w .]+$")
    house_re = re.compile(rf"^{y} United States House of Representatives elections? in [A-Z][\w .]+$")

    senate = sorted({t for t in page_links(sen_hub) if sen_re.match(t)})
    house = sorted({t for t in page_links(house_hub) if house_re.match(t)})
    generic = [house_hub]
    for t in search_titles(f'intitle:"{y}" intitle:"opinion polling" House of Representatives'):
        if y in t and "House" in t and t not in generic:
            generic.append(t)

    path = SOURCES_DIR / f"{cycle}.yaml"
    extra = {}
    if path.exists():
        extra = (yaml.safe_load(path.read_text()) or {}).get("extra", {}) or {}
    doc = {
        "cycle": cycle,
        "discovered_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "senate": senate,
        "house_states": house,
        "generic_ballot": generic,
        "extra": extra,  # manual additions: {senate: [...], house_states: [...], generic_ballot: [...]}
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Wikipedia pages scraped for this cycle. Written by "
                    "`python -m pipeline.fetch_wikipedia discover`.\n# Add pages by hand under "
                    "`extra`; discovery keeps them.\n" + yaml.safe_dump(doc, sort_keys=False, width=200))
    return {k: len(v) for k, v in doc.items() if isinstance(v, list)}


def slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")


def reduce_html(html: str) -> str:
    """Keep headings and tables only, in page order. Drops nav boxes and references."""
    soup = BeautifulSoup(html, "lxml")
    keep = []
    for el in soup.find_all(["h2", "h3", "h4", "h5", "table"]):
        if el.name == "table":
            if el.find_parent("table") is not None:
                continue  # nested; kept with its parent
            classes = el.get("class") or []
            if "navbox" in classes or "sidebar" in classes or "metadata" in classes:
                continue
            for sup in el.find_all("sup", class_="reference"):
                sup.decompose()
        keep.append(str(el))
    return "\n".join(keep)


def fetch_page(title: str) -> tuple[str, dict]:
    d = api({"action": "parse", "page": title, "prop": "text|revid", "redirects": 1,
             "disableeditsection": 1, "disabletoc": 1})
    p = d["parse"]
    meta = {"title": p["title"], "revid": p["revid"], "requested": title,
            "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return reduce_html(p["text"]), meta


def fetch(cycle: int) -> dict:
    src = yaml.safe_load((SOURCES_DIR / f"{cycle}.yaml").read_text())
    extra = src.get("extra") or {}
    groups = {g: list(dict.fromkeys((src.get(g) or []) + (extra.get(g) or [])))
              for g in ("senate", "house_states", "generic_ballot")}
    out_dir = RAW_DIR / str(cycle)
    out_dir.mkdir(parents=True, exist_ok=True)
    index, failures = [], []
    for group, titles in groups.items():
        for t in titles:
            try:
                html, meta = fetch_page(t)
            except Exception as e:  # keep going; report at the end
                failures.append(f"{t}: {e}")
                continue
            fn = f"{slug(meta['title'])}.html"
            header = "<!-- " + json.dumps({**meta, "group": group}) + " -->\n"
            (out_dir / fn).write_text(header + html)
            index.append({**meta, "group": group, "file": fn})
    (out_dir / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    if failures:
        print("FAILED:\n  " + "\n  ".join(failures), file=sys.stderr)
    return {"pages": len(index), "failed": len(failures)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["discover", "fetch"])
    ap.add_argument("--cycle", type=int, action="append", required=True)
    a = ap.parse_args(argv)
    bad = 0
    for c in a.cycle:
        res = discover(c) if a.step == "discover" else fetch(c)
        print(a.step, c, res)
        bad += res.get("failed", 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
