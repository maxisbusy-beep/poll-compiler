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


# ---- Minnesota: Secretary of State results file (semicolon separated, statewide) ---------
MN_URL = f"https://electionresultsfiles.sos.mn.gov/{CYCLE_DATE}/ushouse.txt"
MN_PARTY = {"DFL": "DEM", "R": "REP", "IND": "IND", "LIB": "LIB", "GP": "GRN", "WI": "OTH"}


def minnesota() -> dict:
    text = get(MN_URL).decode("utf-8", "replace")
    races = defaultdict(dict)
    rep = {}
    for line in text.splitlines():
        f = line.split(";")
        if len(f) < 16 or not f[5].strip().isdigit():
            continue
        name, party = f[7].strip(), f[10].strip()
        if party == "WI" or name.upper() == "WRITE-IN":
            continue
        rid = f"2026-HOUSE-MN-{int(f[5])}"
        races[rid][name] = {"name": name, "party": MN_PARTY.get(party, "OTH"), "votes": int(f[13] or 0)}
        if int(f[12] or 0):
            rep[rid] = 100 * int(f[11] or 0) / int(f[12])
    return {rid: finish(c, rep.get(rid), "Minnesota Secretary of State") for rid, c in races.items()}


# ---- Georgia and Virginia: state results sites run on Enhanced Voting (same data API) -----
GA_URL = "https://results.sos.ga.gov/results/public/api/elections/Georgia/11032026GeneralAndSpecialElection/data"
VA_URL = "https://enr.elections.virginia.gov/results/public/api/elections/virginia/2026-November-General/data"
EV_PARTY = {"d": "DEM", "r": "REP", "l": "LIB", "i": "IND", "g": "GRN"}


def _en(x) -> str:
    if isinstance(x, list):
        return next((i.get("text", "") for i in x if i.get("languageId") == "en"), x[0].get("text", "") if x else "")
    return x or ""


def enhanced_voting(url: str, st: str, pattern: str, source: str) -> dict:
    d = json.loads(get(url, timeout=90))
    out = {}
    for b in d.get("ballotItems") or []:
        m = re.match(pattern, _en(b.get("name")))
        if not m:
            continue
        rid = f"2026-HOUSE-{st}-{int(m.group(1))}"
        cands = {}
        for o in (b.get("summaryResults") or {}).get("ballotOptions") or []:
            if o.get("isWriteIn"):
                continue
            name = re.sub(r"\s*\((Rep|Dem|Lib|Ind|Grn|I|R|D)\)\s*$", "", _en(o.get("name"))).strip()
            ab = ((o.get("party") or {}).get("abbreviation") or "").strip().lower()
            cands[name] = {"name": name, "party": EV_PARTY.get(ab[:1], "OTH"), "votes": int(o.get("voteCount") or 0)}
        # reportingUnits are whole counties/localities ("reporting" once any votes are in), so
        # they say little about how much is counted: no % reporting for these states.
        out[rid] = finish(cands, None, source)
    return out


def georgia() -> dict:
    return enhanced_voting(GA_URL, "GA", r"US House of Representatives - District (\d+)", "Georgia Secretary of State")


def virginia() -> dict:
    return enhanced_voting(VA_URL, "VA", r"Member, House of Representatives \((\d+)", "Virginia Department of Elections")


# ---- California: Secretary of State results API, one request per district ----------------
CA_URL = "https://api.sos.ca.gov/returns/us-rep/district/{d}"
CA_DISTRICTS = 52


def _ca_one(d: int):
    j = json.loads(get(CA_URL.format(d=d)))
    cands = {}
    for c in j.get("candidates") or []:
        name = (c.get("Name") or "").strip()
        if name:
            cands[name] = {"name": name, "party": EV_PARTY.get((c.get("Party") or "").strip().lower()[:1], "OTH"),
                           "votes": int(re.sub(r"[^\d]", "", str(c.get("Votes") or "0")) or 0)}
    m = re.search(r"\(([\d,]+) of ([\d,]+)\)", j.get("Reporting") or "")
    rep = None
    if m and int(m.group(2).replace(",", "")):
        rep = 100 * int(m.group(1).replace(",", "")) / int(m.group(2).replace(",", ""))
    return f"2026-HOUSE-CA-{d}", finish(cands, rep, "California Secretary of State")


def california() -> dict:
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for res in ex.map(lambda d: _safe(_ca_one, d), range(1, CA_DISTRICTS + 1)):
            if res:
                out[res[0]] = res[1]
    if not out:
        raise RuntimeError("no California district answered")
    return out


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None

SOURCES = {
    "NC": ("NC State Board of Elections", NC_URL, north_carolina),
    "FL": ("Florida Division of Elections", FL_URL, florida),
    "MN": ("Minnesota Secretary of State", MN_URL, minnesota),
    "GA": ("Georgia Secretary of State", GA_URL, georgia),
    "VA": ("Virginia Department of Elections", VA_URL, virginia),
    "CA": ("California Secretary of State", "https://api.sos.ca.gov/returns/us-rep/district/", california),
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
