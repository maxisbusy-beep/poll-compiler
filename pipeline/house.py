"""House model (SPEC.md 5.3, Phase 5).

Every district gets an expected margin from its partisan lean, moved by the
national generic-ballot environment, plus an incumbency edge; where district
polls exist they are blended in exactly like Senate polls.

Lean sources, in order:
  1. A "2026 PVI" table on the state's own 2026 House page (California, redrawn
     for 2026, publishes one).
  2. Expert ratings from the district's "Predictions" table, for states that
     redrew their maps mid-decade (config/house.yaml: redistricted) and have no
     2026 PVI. Ratings are turned into margins (Safe 20, Likely 10, Lean 5, Tilt 2.5).
  3. Cook PVI from Wikipedia's table (lines used in 2024).
  4. Ratings, then nothing (the district is dropped and listed in the report).

Cook PVI R+5 means about 5 points more Republican than the nation on each
party's share, so roughly 10 points of margin: prior = 2 * PVI(D) + environment.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from pipeline.parse_tables import STATES, clean, general_blocks, grid, races_on_page, walk

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "house.yaml"

RATING_MARGIN = {"safe": 20.0, "solid": 20.0, "likely": 10.0, "lean": 5.0, "tilt": 2.5}


def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def parse_pvi(text: str) -> float | None:
    """'R+17' -> -17 (D-positive); 'EVEN' -> 0."""
    t = clean(text).upper().replace("–", "+")
    if t.startswith("EVEN"):
        return 0.0
    m = re.match(r"^(D|R)\s*\+\s*(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    v = float(m.group(2))
    return v if m.group(1) == "D" else -v


def rating_margin(text: str) -> float | None:
    t = clean(text).lower()
    if "toss" in t:
        return 0.0
    m = re.search(r"(safe|solid|likely|lean|tilt)\s*\(?\s*(d|r)\b", t)
    if not m:
        m2 = re.search(r"(safe|solid|likely|lean|tilt)\s+(democratic|republican)", t)
        if not m2:
            return None
        side = "d" if m2.group(2).startswith("d") else "r"
        v = RATING_MARGIN[m2.group(1)]
        return v if side == "d" else -v
    v = RATING_MARGIN[m.group(1)]
    return v if m.group(2) == "d" else -v


def pvi_table(cycle: int) -> dict[str, float]:
    """state-district -> PVI (D-positive) from the Cook PVI article."""
    path = ROOT / "data" / "raw" / str(cycle) / "Cook_Partisan_Voting_Index.html"
    out = {}
    if not path.exists():
        return out
    soup = BeautifulSoup(path.read_text(), "lxml")
    for b in walk(soup):
        header, rows = grid(b.table)
        if not header or header[0].lower() != "district":
            continue
        for r in rows:
            m = re.match(r"^(.+?)\s+(at-large|\d+)$", clean(r[0]), re.I)
            if not m or m.group(1) not in STATES:
                continue
            d = "1" if m.group(2).lower() == "at-large" else str(int(m.group(2)))
            v = parse_pvi(r[1])
            if v is not None:
                out[f"{STATES[m.group(1)]}-{d}"] = v
    return out


def overview_table(soup: BeautifulSoup, state: str) -> dict[str, dict]:
    """A state page's district overview table with a '<year> PVI' column.

    California's 2026 page has no per-district sections, only this table:
    district, 2026 PVI, incumbent, party, ..., candidates ('▌ Name (Party) ▌ ...').
    """
    out = {}
    for b in walk(soup):
        header, rows = grid(b.table)
        if not header or not header[0].lower().startswith("district"):
            continue
        pcol = next((i for i, h in enumerate(header) if "PVI" in h), None)
        if pcol is None:
            continue
        party_col = next((i for i, h in enumerate(header) if h.lower().endswith("party")), None)
        cand_col = next((i for i, h in enumerate(header) if "candidate" in h.lower()), None)
        for r in rows:
            m = re.search(r"(\d+|at-large)\s*$", clean(r[0]), re.I)
            v = parse_pvi(r[pcol])
            if not m or v is None:
                continue
            d = "1" if m.group(1).lower() == "at-large" else str(int(m.group(1)))
            inc_party = None
            if party_col is not None:
                pt = clean(r[party_col]).lower()
                inc_party = "DEM" if "democratic" in pt else "REP" if "republican" in pt else None
            inc_name = clean(r[2]) if len(r) > 2 else ""
            cands = []
            if cand_col is not None:
                for part in clean(r[cand_col]).split("▌"):
                    cm = re.match(r"^\s*(.+?)\s*\((Democratic|Republican|Independent|Libertarian|Green|[^)]*)\)", part)
                    if cm:
                        name = cm.group(1).strip()
                        party = next((c for k, c in PARTY_NAME if k in cm.group(2).lower()), "OTH")
                        last = name.split()[-1].lower()
                        cands.append((name, party, bool(inc_name) and last in inc_name.lower()))
            out[f"{state}-{d}"] = {"pvi": v, "incumbent_party": inc_party, "candidates": cands}
    return out


PARTY_NAME = [("democratic", "DEM"), ("republican", "REP"), ("independent", "IND"),
              ("libertarian", "LIB"), ("green", "GRN")]


def read_candidates(table) -> list[tuple[str, str, bool]] | None:
    header, rows = grid(table)
    h = [x.lower() for x in header]
    if "candidate" not in h or "votes" not in h:
        return None
    ci = h.index("candidate")
    pcs = [j for j, x in enumerate(h) if x == "party"]
    pa = pcs[-1] if pcs else None
    out = []
    for r in rows:
        name = clean(r[ci])
        if not name or re.match(r"total|majority|plurality|turnout|write", name, re.I):
            continue
        inc = bool(re.search(r"\(incumbent\)", name, re.I))
        name = re.sub(r"\s*\((incumbent|write-in)\)", "", name, flags=re.I)
        ptxt = clean(r[pa]).lower() if pa is not None else ""
        party = next((c for k, c in PARTY_NAME if k in ptxt), "OTH")
        if party == "OTH" and ptxt == "total":
            continue
        if name not in [o[0] for o in out]:
            out.append((name, party, inc))
    return out or None


def districts(cycle: int) -> tuple[list[dict], list[str]]:
    """Every district on the 2026 House pages with candidates, incumbent and ratings."""
    raw = ROOT / "data" / "raw" / str(cycle)
    out, notes = [], []
    for f in sorted(raw.glob(f"{cycle}_United_States_House_of_Representatives_election*_in_*.html")):
        text = f.read_text()
        title = re.match(r'<!-- \{"title": "([^"]+)"', text).group(1)
        soup = BeautifulSoup(text, "lxml")
        blocks = walk(soup)
        races = races_on_page(title, cycle, blocks)
        m = re.match(rf"^{cycle} United States House of Representatives elections? in (.+)$", title)
        state = STATES.get(m.group(1)) if m else None
        if not state:
            continue
        overview = overview_table(soup, state)
        # pages with only an overview table (no per-district sections)
        if not races and overview:
            for key, ov in overview.items():
                dnum = key.split("-")[1]
                out.append({"race_id": f"{cycle}-HOUSE-{state}-{dnum}", "state": state, "district": dnum,
                            "candidates": ov["candidates"], "incumbent_party": ov["incumbent_party"],
                            "incumbent_running": any(c[2] for c in ov["candidates"]),
                            "ratings": [], "page_pvi": ov["pvi"]})
            continue
        page_pvi = {k: v["pvi"] for k, v in overview.items()}
        for race in races:
            info = next((b for b in race.blocks if "infobox" in (b.table.get("class") or [])), None)
            inc_party, inc_in_nominees = None, False
            if info is not None:
                it = clean(info.table.get_text(" ", strip=True))
                m = re.search(r"Incumbent U\.S\. Representative (.*?)\s*(Democratic|Republican)", it)
                if m:
                    inc_party = "DEM" if m.group(2) == "Democratic" else "REP"
                    nom = re.search(r"Nominee (.*?) Party", it)
                    last = m.group(1).split()[-1] if m.group(1).split() else ""
                    inc_in_nominees = bool(nom and last and last in nom.group(1))
            gen = general_blocks(race.blocks)
            cands = None
            for b in gen:
                if "result" in " ".join(b.headings.values()).lower():
                    cands = read_candidates(b.table)
                    if cands:
                        break
            ratings = []
            for b in gen:
                header, rows = grid(b.table)
                if header and header[0].lower() == "source" and len(header) > 1 and "rank" in header[1].lower():
                    ratings += [v for v in (rating_margin(r[1]) for r in rows) if v is not None]
            out.append({"race_id": race.race_id, "state": state, "district": race.district,
                        "candidates": cands or [], "incumbent_party": inc_party,
                        "incumbent_running": any(c[2] for c in (cands or [])) or inc_in_nominees,
                        "ratings": ratings, "page_pvi": page_pvi.get(f"{state}-{race.district}")})
            if not cands:
                notes.append(f"{race.race_id}: no candidate list found")
    return out, notes


def district_prior(d: dict, pvi: dict[str, float], env: float, cfg: dict) -> tuple[float | None, str]:
    """Expected margin (D minus R) before district polls, and which source it came from."""
    key = f"{d['state']}-{d['district']}"
    rated = sum(d["ratings"]) / len(d["ratings"]) if d["ratings"] else None
    if d["page_pvi"] is not None:
        base, src = 2 * d["page_pvi"] + env, "2026 PVI"
    elif d["state"] in cfg["redistricted"] and rated is not None:
        return rated, "expert ratings (new map)"
    elif key in pvi and d["state"] not in cfg["redistricted"]:
        base, src = 2 * pvi[key] + env, "PVI"
    elif rated is not None:
        return rated, "expert ratings"
    else:
        return None, "none"
    if d["incumbent_running"] and d["incumbent_party"] in ("DEM", "REP"):
        base += cfg["incumbency_edge"] if d["incumbent_party"] == "DEM" else -cfg["incumbency_edge"]
    return base, src


def main_pair(cands: list[tuple[str, str, bool]]) -> tuple[tuple, tuple] | None:
    """(side_a, side_b): Democrat (or main non-Republican) vs Republican."""
    reps = [c for c in cands if c[1] == "REP"]
    dems = [c for c in cands if c[1] == "DEM"]
    if dems and reps:
        return dems[0], reps[0]
    if reps and len(cands) > 1:
        other = [c for c in cands if c is not reps[0]]
        return other[0], reps[0]
    if len(cands) >= 2:
        return cands[0], cands[1]
    if len(cands) == 1:
        return cands[0], ("(unopposed)", "NONE", False)
    return None
