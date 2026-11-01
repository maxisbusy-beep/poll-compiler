"""Turn the frozen 538 snapshot into normalized polls and results (SPEC.md 3.1, 3.2).

Input:  data/history/538_raw_polls.csv  (never edited)
Output: data/polls/<cycle>.csv          (source=538)
        data/results/<cycle>.csv        (one row per race, from 538's actual-result columns)

Kept: general elections, specials and runoffs for Senate, House, House generic
ballot, Governor and President. Dropped: primaries.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from pipeline.normalize import (
    POLL_COLUMNS, RESULT_COLUMNS, PollsterAliases, assign_sides, cycle_type,
    make_race_id,
)

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "history" / "538_raw_polls.csv"
POLLS_DIR = ROOT / "data" / "polls"
RESULTS_DIR = ROOT / "data" / "results"

# 538 race-string middle part -> (race_type, kind)
_TYPE_MAP = {
    "Sen-G": ("SEN", ""), "Sen-GS": ("SEN", "S"), "Sen-R": ("SEN", "R"), "Sen-SR": ("SEN", "SR"),
    "House-G": ("HOUSE", ""), "House-GS": ("HOUSE", "S"), "House-R": ("HOUSE", "R"),
    "House-SR": ("HOUSE", "SR"),
    "Gov-G": ("GOV", ""), "Gov-GS": ("GOV", "S"), "Gov-R": ("GOV", "R"),
    "Pres-G": ("PRES", ""),
}

_PARTISAN = {"NA": "", "DEM": "D", "REP": "R", "IND": "I", "LIB": "L", "CRV": "C",
             "REP,DEM": "R,D", "DEM,REP": "D,R"}


def parse_race(race: str, type_simple: str, location: str) -> tuple[str, str, str, str] | None:
    """'2018_House-GS_NY-25' -> (race_type, state, district, kind). None = skip (primaries)."""
    mid = race.split("_")[1]
    if type_simple == "House-G-US":
        return ("HOUSE-GEN", "US", "", "")
    if mid not in _TYPE_MAP:
        return None
    race_type, kind = _TYPE_MAP[mid]
    if race_type == "HOUSE":
        state, _, district = location.partition("-")
        return (race_type, state, district, kind)
    return (race_type, location, "", kind)


def _num(x: str) -> float:
    return round(float(x), 3)


def convert(rows: list[dict], aliases: PollsterAliases) -> tuple[list[dict], dict[str, dict]]:
    """Return (normalized polls, results keyed by race_id). Raises on unmapped pollsters."""
    keep = []
    for r in rows:
        parsed = parse_race(r["race"], r["type_simple"], r["location"])
        if parsed:
            keep.append((r, parsed))

    ids = aliases.resolve_all([r["pollster"] for r, _ in keep])

    polls, results = [], {}
    for r, (race_type, state, district, kind) in keep:
        cycle = int(r["cycle"])
        rid = make_race_id(cycle, race_type, state, district, kind)
        poll = assign_sides((r["cand1_name"], r["cand1_party"], float(r["cand1_pct"])),
                            (r["cand2_name"], r["cand2_party"], float(r["cand2_pct"])))
        act = assign_sides((r["cand1_name"], r["cand1_party"], float(r["cand1_actual"])),
                           (r["cand2_name"], r["cand2_party"], float(r["cand2_actual"])))
        base = {
            "cycle": cycle, "cycle_type": cycle_type(cycle), "election_date": r["electiondate"],
            "race_id": rid, "race_type": race_type, "state": state, "district": district,
            "special": kind,
        }
        polls.append({
            **base,
            "pollster_id": ids[r["pollster"]], "pollster_raw": r["pollster"], "sponsor": "",
            "partisan": _PARTISAN.get(r["partisan"], r["partisan"]),
            "methodology": r["methodology"], "start_date": "", "end_date": "",
            "poll_date": r["polldate"], "days_to_election": int(r["time_to_election"]),
            "sample_size": int(float(r["samplesize"])), "population": "",
            "side_a_name": poll.a_name, "side_a_party": poll.a_party, "side_a_pct": _num(poll.a_val),
            "side_b_name": poll.b_name, "side_b_party": poll.b_party, "side_b_pct": _num(poll.b_val),
            "other_pct": "", "undecided_pct": "",
            "margin_poll": _num(poll.a_val - poll.b_val), "matchup": poll.matchup,
            "source": "538", "source_ref": f"poll_id={r['poll_id']};question_id={r['question_id']}",
        })
        res = {
            **base,
            "side_a_name": act.a_name, "side_a_party": act.a_party, "side_a_actual": _num(act.a_val),
            "side_b_name": act.b_name, "side_b_party": act.b_party, "side_b_actual": _num(act.b_val),
            "margin_actual": _num(act.a_val - act.b_val), "matchup": act.matchup, "source": "538",
        }
        prev = results.get(rid)
        if prev and abs(prev["margin_actual"] - res["margin_actual"]) > 0.05:
            raise ValueError(f"{rid}: 538 rows disagree on the actual result")
        results[rid] = res
    return polls, results


def _write(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> dict:
    rows = list(csv.DictReader(SNAPSHOT.open()))
    polls, results = convert(rows, PollsterAliases())

    by_cycle_p, by_cycle_r = defaultdict(list), defaultdict(list)
    for p in polls:
        by_cycle_p[p["cycle"]].append(p)
    for r in results.values():
        by_cycle_r[r["cycle"]].append(r)

    for cyc, ps in by_cycle_p.items():
        ps.sort(key=lambda p: (p["race_id"], p["poll_date"], p["pollster_id"], p["source_ref"]))
        _write(POLLS_DIR / f"{cyc}.csv", POLL_COLUMNS, ps)
    for cyc, rs in by_cycle_r.items():
        rs.sort(key=lambda r: r["race_id"])
        _write(RESULTS_DIR / f"{cyc}.csv", RESULT_COLUMNS, rs)
    return {"polls": len(polls), "races": len(results)}


if __name__ == "__main__":
    print(main())
