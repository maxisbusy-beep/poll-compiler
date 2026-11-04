"""Election-night relay: House counts from official state election results files.

Wikipedia leaves House district results blank on election night, and the page can't read
state election sites directly (no CORS). A GitHub Action runs this every couple of minutes
and pushes the output to the `live-data` branch; the page reads it from
raw.githubusercontent.com.

Only states that publish a plain, public results file are covered. States whose results
sites put up bot challenges (Texas, Pennsylvania) are left out on purpose.

Output (house_live.json):
  {"updated": iso, "sources": {state: {"name", "url", "ok", "races", "error"}},
   "races": {race_id: {"candidates": [{name, party, votes}], "total", "reporting", "source"}}}
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA = "poll-compiler election-night relay (github.com/maxisbusy-beep/poll-compiler)"
CYCLE_DATE = "20261103"

PARTY = {"DEM": "DEM", "REP": "REP", "LIB": "LIB", "LPF": "LIB", "GRE": "GRN", "GRN": "GRN",
         "IND": "IND", "NPA": "IND", "UNA": "IND", "NPP": "IND"}


def get(url: str, timeout: int = 40) -> bytes:
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}nocache={int(time.time())}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def finish(cands: dict[str, dict], reporting: float | None, source: str) -> dict:
    cs = sorted(cands.values(), key=lambda c: -c["votes"])
    total = sum(c["votes"] for c in cs)
    return {"candidates": cs, "total": total,
            "reporting": None if reporting is None else round(reporting, 1), "source": source}


# ---- North Carolina: State Board of Elections, statewide JSON ---------------------------
NC_URL = f"https://er.ncsbe.gov/enr/{CYCLE_DATE}/data/results_0.txt"


def north_carolina() -> dict:
    rows = json.loads(get(NC_URL))
    races = defaultdict(dict)
    rep = {}
    for r in rows:
        m = re.match(r"US HOUSE OF REPRESENTATIVES DISTRICT (\d+)", r.get("cnm", ""))
        if not m:
            continue
        rid = f"2026-HOUSE-NC-{int(m.group(1))}"
        races[rid][r["bnm"]] = {"name": r["bnm"], "party": PARTY.get(r.get("pty", ""), "OTH"),
                                "votes": int(r.get("vct") or 0)}
        ptl = int(r.get("ptl") or 0)
        if ptl:
            rep[rid] = 100 * int(r.get("prt") or 0) / ptl
    return {rid: finish(c, rep.get(rid), "NC State Board of Elections") for rid, c in races.items()}


# ---- Florida: Division of Elections election-night file, one row per county -------------
FL_URL = f"https://flelectionfiles.floridados.gov/enightfilespublic/{CYCLE_DATE}_ElecResultsFL.txt"


def florida() -> dict:
    text = get(FL_URL).decode("utf-8", "replace")
    races = defaultdict(dict)
    prec = defaultdict(dict)    # rid -> county -> (precincts, reporting)
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        name = (r.get("RaceName") or "").lower()
        if r.get("RaceCode") != "USR" and "representative in congress" not in name \
                and "united states representative" not in name:
            continue
        d = (r.get("Juris1num") or "").strip()
        if not d.isdigit():
            continue
        rid = f"2026-HOUSE-FL-{int(d)}"
        who = " ".join(x for x in (r.get("CanNameFirst"), r.get("CanNameLast")) if x and x.strip()).strip()
        if not who:
            continue
        c = races[rid].setdefault(who, {"name": who, "party": PARTY.get(r.get("PartyCode", ""), "OTH"), "votes": 0})
        c["votes"] += int(r.get("CanVotes") or 0)
        prec[rid][r.get("CountyCode")] = (int(r.get("Precincts") or 0), int(r.get("PrecinctsReporting") or 0))
    out = {}
    for rid, c in races.items():
        p = sum(a for a, _ in prec[rid].values())
        rep = 100 * sum(b for _, b in prec[rid].values()) / p if p else None
        out[rid] = finish(c, rep, "Florida Division of Elections")
    return out


SOURCES = {
    "NC": ("NC State Board of Elections", NC_URL, north_carolina),
    "FL": ("Florida Division of Elections", FL_URL, florida),
}


def run() -> dict:
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": {}, "races": {}}
    for st, (name, url, fn) in SOURCES.items():
        try:
            races = fn()
            # a file of all zeros (pre-election test file) is not a count
            races = {k: v for k, v in races.items() if v["total"] > 0}
            out["races"].update(races)
            out["sources"][st] = {"name": name, "url": url, "ok": True, "races": len(races)}
        except Exception as e:     # one state failing must not stop the others
            out["sources"][st] = {"name": name, "url": url, "ok": False, "races": 0, "error": str(e)[:200]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="house_live.json")
    a = ap.parse_args()
    data = run()
    Path(a.out).write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(data["updated"], {k: (v["races"] if v["ok"] else "ERR " + v.get("error", "")) for k, v in data["sources"].items()})


if __name__ == "__main__":
    main()
