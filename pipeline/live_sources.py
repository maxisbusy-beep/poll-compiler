"""Election-night lookup table for the browser: where each race's results live on
Wikipedia, and roughly how many votes to expect (for an approximate "% counted").

Writes site/data/live.json:
  {"cycle", "election_date", "turnout_ratio", "races": {race_id: {"page", "district", "expected_votes"}}}

Expected votes = 2024 votes x turnout_ratio. 2024 was a presidential year; midterm
turnout runs lower (2022 vs 2020 House vote was about 0.72). For districts in
states that redrew their maps, the 2024 statewide House vote is split evenly.
This is an estimate and the page labels it as one.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from pipeline.parse_tables import STATES, clean, general_blocks, grid, races_on_page, walk

ROOT = Path(__file__).resolve().parent.parent
TURNOUT_RATIO = 0.72


def total_votes(table) -> int | None:
    header, rows = grid(table)
    h = [x.lower() for x in header]
    if "votes" not in h or "candidate" not in h:
        return None
    vi = h.index("votes")
    for r in rows:
        if clean(r[0]).lower().startswith("total votes"):
            m = re.sub(r"[^\d]", "", r[vi])
            return int(m) if m else None
    return None


def totals_2024() -> dict[str, int]:
    """race_id -> total votes, for 2024 presidential states and House districts."""
    out = {}
    for f in sorted((ROOT / "data" / "raw" / "2024").glob("*.html")):
        text = f.read_text()
        title = json.loads(re.match(r"<!-- (.*?) -->", text).group(1))["title"]
        if "presidential election in" not in title and "House of Representatives" not in title:
            continue
        soup = BeautifulSoup(text, "lxml")
        for race in races_on_page(title, 2024, walk(soup)):
            for b in general_blocks(race.blocks):
                if "result" not in " ".join(b.headings.values()).lower():
                    continue
                t = total_votes(b.table)
                if t:
                    out[race.race_id] = t
                    break
    return out


def build(cycle: int) -> dict:
    src = yaml.safe_load((ROOT / "config" / "sources" / f"{cycle}.yaml").read_text())
    redistricted = set(yaml.safe_load((ROOT / "config" / "house.yaml").read_text())["redistricted"])
    races = json.loads((ROOT / "site" / "data" / "races.json").read_text())["races"]
    t24 = totals_2024()
    state_house = defaultdict(int)
    house_n = defaultdict(int)
    for rid, v in t24.items():
        if "-HOUSE-" in rid:
            state_house[rid.split("-")[2]] += v
    for r in races:
        if r["chamber"] == "house":
            house_n[r["state"]] += 1

    title_by_state_sen = {}
    for t in src.get("senate", []):
        m = re.match(rf"^{cycle} United States Senate (special )?elections? in (.+)$", t)
        if m and m.group(2) in STATES:
            title_by_state_sen[STATES[m.group(2)] + ("-S" if m.group(1) else "")] = t
    title_by_state_house = {}
    for t in src.get("house_states", []):
        m = re.match(rf"^{cycle} United States House of Representatives elections? in (.+)$", t)
        if m and m.group(1) in STATES:
            title_by_state_house[STATES[m.group(1)]] = t

    title_by_state_gov = {}
    for t in src.get("governor", []):
        m = re.match(rf"^{cycle} (.+) gubernatorial election$", t)
        if m and m.group(1) in STATES:
            title_by_state_gov[STATES[m.group(1)]] = t

    out = {}
    for r in races:
        st = r["state"]
        if r["chamber"] == "governor":
            pres = t24.get(f"2024-PRES-{st}")
            out[r["race_id"]] = {"page": title_by_state_gov.get(st), "district": None,
                                 "expected_votes": round(pres * TURNOUT_RATIO) if pres else None}
        elif r["chamber"] == "senate":
            key = st + ("-S" if r["race_id"].endswith("-S") else "")
            pres = t24.get(f"2024-PRES-{st}")
            out[r["race_id"]] = {"page": title_by_state_sen.get(key), "district": None,
                                 "expected_votes": round(pres * TURNOUT_RATIO) if pres else None}
        else:
            d = r["district"]
            base = None
            if st not in redistricted:
                base = t24.get(f"2024-HOUSE-{st}-{d}")
            if base is None and state_house.get(st) and house_n.get(st):
                base = state_house[st] / house_n[st]
            out[r["race_id"]] = {"page": title_by_state_house.get(st), "district": d,
                                 "single_district": house_n[st] == 1,
                                 "expected_votes": round(base * TURNOUT_RATIO) if base else None}
    cfg = yaml.safe_load((ROOT / "config" / "cycles.yaml").read_text())[cycle]
    return {"cycle": cycle, "election_date": cfg["election_date"].isoformat(),
            "turnout_ratio": TURNOUT_RATIO, "races": out}


def main() -> dict:
    from pipeline.score_pollsters import load_config
    data = build(load_config()["target_cycle"])
    (ROOT / "site" / "data" / "live.json").write_text(json.dumps(data, separators=(",", ":")))
    rs = data["races"].values()
    return {"races": len(data["races"]), "with_page": sum(1 for r in rs if r["page"]),
            "with_expected": sum(1 for r in rs if r["expected_votes"])}


if __name__ == "__main__":
    print(main())
