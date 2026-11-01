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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    forecast = {
        "cycle": cycle, "as_of": as_of.isoformat(), "election_date": eday.isoformat(),
        "generated_utc": now, "days_to_election": days,
        "generic_ballot": env,
        "senate": {**sim, "races_up": len(races), "not_up": ccfg["senate"]["not_up"],
                   "uncommitted_races": ccfg["senate"].get("uncommitted", []),
                   "races_with_polls": sum(1 for r in races if r.basis == "polls")},
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
        for r in sorted(races, key=lambda r: abs(r.p_a - 0.5))]}
    return forecast, racejs


def main() -> dict:
    forecast, races = build()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "forecast.json").write_text(json.dumps(forecast, separators=(",", ":")))
    (SITE_DATA / "races.json").write_text(json.dumps(races, separators=(",", ":")))
    s = forecast["senate"]
    return {"p_dem": round(s["p_dem_control"], 3), "p_rep": round(s["p_rep_control"], 3),
            "p_uncommitted": round(s["p_uncommitted_decides"], 3),
            "dem_seats": (s["dem_seats_p10"], s["dem_seats_median"], s["dem_seats_p90"]),
            "races": s["races_up"], "with_polls": s["races_with_polls"]}


if __name__ == "__main__":
    print(main())
