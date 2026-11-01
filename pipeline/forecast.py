"""Live forecast for the target cycle (Senate in Phase 4).

Writes site/data/forecast.json (chamber odds) and site/data/races.json
(per-race averages, probabilities and the polls behind them).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from pipeline.generic_ballot import generic_ballot
from pipeline.model import (
    RaceForecast, blend, lean_prior, load_all_polls, load_all_results, load_cycles, load_params,
    pollster_params, race_average, rating, simulate_senate, split_sd, total_sd, win_prob,
)
from pipeline.parse_tables import STATES
from pipeline import house as house_mod
from pipeline.model import simulate_house
from pipeline.score_pollsters import load_config as load_scoring_config

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data"


def senate_race_ids(cycle: int) -> list[str]:
    src = yaml.safe_load((ROOT / "config" / "sources" / f"{cycle}.yaml").read_text())
    titles = (src.get("senate") or []) + ((src.get("extra") or {}).get("senate") or [])
    ids = []
    for t in titles:
        m = re.match(rf"^{cycle} United States Senate (special )?elections? in (.+)$", t)
        if m and m.group(2) in STATES:
            ids.append(f"{cycle}-SEN-{STATES[m.group(2)]}" + ("-S" if m.group(1) else ""))
    return sorted(set(ids))


def build(cycle: int | None = None, as_of: date | None = None) -> tuple[dict, dict]:
    cycle = cycle or load_scoring_config()["target_cycle"]
    cycles = load_cycles()
    ccfg = cycles[cycle]
    eday = ccfg["election_date"]
    as_of = min(as_of or date.today(), eday)
    days = (eday - as_of).days
    params = load_params()

    polls = load_all_polls()
    results = load_all_results()
    pp = pollster_params(cycle, params["shrink_k"], params["quality_scale_s"], polls, results)
    by_race = defaultdict(list)
    for p in polls:
        if int(p["cycle"]) == cycle and p["race_type"] == "SEN":
            by_race[p["race_id"]].append(p)

    env = generic_ballot(cycle)
    env_margin = env["margin"] if env else None
    nat = params["national_sd"]
    races = []
    nat_override = (ccfg.get("lean") or {}).get("pres_national_margin")
    for rid in sorted(set(senate_race_ids(cycle)) | set(by_race)):
        state = rid.split("-")[2]
        ps = by_race.get(rid, [])
        avg = race_average(ps, as_of, params, pp) if ps else None
        prior = lean_prior(state, cycle, results, env_margin, nat_override)
        if avg:
            latest = max(ps, key=lambda p: p.get("end_date") or p["poll_date"])
            use_prior = prior if latest["matchup"] != "same-party" else None
            mu, n_eff = blend(avg.mu, avg.n_eff, use_prior, params["prior_weight"])
            sd = total_sd(n_eff, days, params["sigma"])
            rf = RaceForecast(rid, state, latest["side_a_name"], latest["side_a_party"],
                              latest["side_b_name"], latest["side_b_party"], latest["matchup"],
                              mu, sd, split_sd(sd, nat), win_prob(mu, sd), avg.n_polls,
                              avg.n_eff, avg.last_poll, "polls", avg.contributions)
            rf.poll_avg, rf.prior = avg.mu, prior
        else:
            mu = prior
            if mu is None:
                continue
            sd = params["lean_sigma"]
            rf = RaceForecast(rid, state, "Democrat", "DEM", "Republican", "REP", "D-R", mu, sd,
                              split_sd(sd, nat), win_prob(mu, sd), 0, 0.0, "", "lean")
            rf.poll_avg, rf.prior = None, prior
        races.append(rf)

    sim = simulate_senate(races, ccfg["senate"], nat)
    house_races, house_info = build_house(cycle, as_of, days, params, pp, polls, env_margin, nat)
    hsim = simulate_house(house_races, nat, house_info["control"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    forecast = {
        "cycle": cycle, "as_of": as_of.isoformat(), "election_date": eday.isoformat(),
        "generated_utc": now, "days_to_election": days,
        "generic_ballot": env,
        "senate": {**sim, "races_up": len(races), "not_up": ccfg["senate"]["not_up"],
                   "uncommitted_races": ccfg["senate"].get("uncommitted", []),
                   "races_with_polls": sum(1 for r in races if r.basis == "polls")},
        "house": {**hsim, "races_with_polls": sum(1 for r in house_races if r.basis == "polls"),
                  "lean_sources": house_info["sources"], "assumptions": house_info["assumptions"]},
    }
    racejs = {"cycle": cycle, "as_of": as_of.isoformat(), "generated_utc": now, "races": [
        {"race_id": r.race_id, "chamber": "senate", "state": r.state,
         "side_a": r.side_a, "side_a_party": r.side_a_party,
         "side_b": r.side_b, "side_b_party": r.side_b_party, "matchup": r.matchup,
         "margin": round(r.mu, 2), "sd": round(r.sd_total, 2), "p_a": round(r.p_a, 4),
         "poll_average": None if r.poll_avg is None else round(r.poll_avg, 2),
         "lean_prior": None if r.prior is None else round(r.prior, 2),
         "rating": rating(r.p_a).replace(" A", " " + r.side_a_party[0]).replace(" B", " " + r.side_b_party[0])
         if r.p_a != 0.5 else "Toss-up",
         "uncommitted": r.race_id in ccfg["senate"].get("uncommitted", []),
         "basis": r.basis, "n_polls": r.n_polls, "n_eff": round(r.n_eff, 1),
         "last_poll": r.last_poll, "polls": r.contributions[:60]}
        for r in sorted(races, key=lambda r: abs(r.p_a - 0.5))]
        + [{"race_id": r.race_id, "chamber": "house", "state": r.state,
            "district": r.race_id.split("-")[3],
            "side_a": r.side_a, "side_a_party": r.side_a_party,
            "side_b": r.side_b, "side_b_party": r.side_b_party, "matchup": r.matchup,
            "margin": round(r.mu, 2), "sd": round(r.sd_total, 2), "p_a": round(r.p_a, 4),
            "poll_average": None if r.poll_avg is None else round(r.poll_avg, 2),
            "lean_prior": None if r.prior is None else round(r.prior, 2),
            "lean_source": r.lean_source, "incumbent_party": r.incumbent_party,
            "basis": r.basis, "n_polls": r.n_polls, "n_eff": round(r.n_eff, 1),
            "last_poll": r.last_poll, "polls": r.contributions[:30]}
           for r in house_races]}
    return forecast, racejs


def build_house(cycle, as_of, days, params, pp, polls, env_margin, nat):
    hcfg = house_mod.load_config()
    pvi = house_mod.pvi_table(cycle)
    dists, notes = house_mod.districts(cycle)
    by_race = defaultdict(list)
    for p in polls:
        if int(p["cycle"]) == cycle and p["race_type"] == "HOUSE":
            by_race[p["race_id"]].append(p)
    env = env_margin if env_margin is not None else 0.0
    out, sources = [], defaultdict(int)
    for d in dists:
        prior, src = house_mod.district_prior(d, pvi, env, hcfg)
        sources[src] += 1
        pair = house_mod.main_pair(d["candidates"])
        a, b = pair if pair else (("Democratic nominee", "DEM", False), ("Republican nominee", "REP", False))
        unopposed = b[1] == "NONE"
        ps = by_race.get(d["race_id"], [])
        avg = race_average(ps, as_of, params, pp) if ps else None
        if unopposed:
            mu, sd, basis, n_eff = 50.0, 1.0, "unopposed", 0.0
            b = ("No opponent", a[1], False)
        elif avg:
            latest = max(ps, key=lambda p: p.get("end_date") or p["poll_date"])
            a = (latest["side_a_name"], latest["side_a_party"], False)
            b = (latest["side_b_name"], latest["side_b_party"], False)
            use_prior = prior if latest["matchup"] != "same-party" else None
            mu, n_eff = blend(avg.mu, avg.n_eff, use_prior, params["prior_weight"])
            sd, basis = total_sd(n_eff, days, params["sigma"]), "polls"
        elif prior is not None:
            mu, sd, basis, n_eff = prior, hcfg["lean_sigma"], "lean", 0.0
        else:
            continue
        if a[1] == b[1] and not unopposed:   # same-party top-two: the seat's party is settled
            mu, sd = abs(mu) if mu else 1.0, max(sd, 1.0)
        matchup = ("same-party" if a[1] == b[1] else "D-R" if a[1] == "DEM" and b[1] == "REP" else "X-R")
        rf = RaceForecast(d["race_id"], d["state"], a[0], a[1], b[0], b[1], matchup, mu, sd,
                          split_sd(sd, nat), win_prob(mu, sd),
                          avg.n_polls if avg else 0, avg.n_eff if avg else 0.0,
                          avg.last_poll if avg else "", basis, avg.contributions if avg else [])
        rf.poll_avg = avg.mu if avg else None
        rf.prior = prior
        rf.lean_source = src
        rf.incumbent_party = d["incumbent_party"] if d["incumbent_running"] else None
        out.append(rf)
    info = {"control": hcfg["control"], "sources": dict(sources), "notes": notes,
            "assumptions": {"incumbency_edge": hcfg["incumbency_edge"], "lean_sigma": hcfg["lean_sigma"],
                            "redistricted": hcfg["redistricted"]}}
    return out, info


def main() -> dict:
    forecast, races = build()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "forecast.json").write_text(json.dumps(forecast, separators=(",", ":")))
    (SITE_DATA / "races.json").write_text(json.dumps(races, separators=(",", ":")))
    s = forecast["senate"]
    return {"p_dem": round(s["p_dem_control"], 3), "p_rep": round(s["p_rep_control"], 3),
            "p_uncommitted": round(s["p_uncommitted_decides"], 3),
            "dem_seats": (s["dem_seats_p10"], s["dem_seats_median"], s["dem_seats_p90"]),
            "races": s["races_up"], "with_polls": s["races_with_polls"],
            "house_p_dem": round(forecast["house"]["p_dem_control"], 3),
            "house_seats": (forecast["house"]["dem_seats_p10"], forecast["house"]["dem_seats_median"],
                            forecast["house"]["dem_seats_p90"]),
            "house_sources": forecast["house"]["lean_sources"]}


if __name__ == "__main__":
    print(main())
