"""The "My ballot" tab: one voter's ballot, with odds where there is anything to go on.

Reads config/my_ballot.yaml and site/data/races.json (so run after forecast.py).
Writes site/data/my_ballot.json.

- model races: copied from the main forecast (the page shows them from races.json anyway).
- polls races (Florida Cabinet): the entered polls go through the same weighted, bias-corrected
  average and the same error formula as governor races (config/params_governor.yaml). These
  races are not in the backtest, so the page says so.
- local races and measures: no odds; the page links to the county's own results.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from pipeline.model import (load_all_polls, load_all_results, load_params, pollster_params,
                            race_average, total_sd, win_prob)
from pipeline.score_pollsters import load_config as load_scoring_config

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "my_ballot.yaml"
OUT = ROOT / "site" / "data" / "my_ballot.json"


def poll_rows(race: dict) -> list[dict]:
    rows = []
    for pid, name, end, n, d, r in race["polls"]:
        end = str(end)
        rows.append({"race_id": race["id"], "pollster_id": pid, "pollster_name": name,
                     "end_date": end, "poll_date": end, "sample_size": str(n), "population": "LV",
                     "matchup": "D-R", "margin_poll": float(d) - float(r)})
    return rows


def forecast_polls_race(race: dict, as_of: date, days: int, params: dict, pp: dict) -> dict:
    ps = poll_rows(race)
    avg = race_average(ps, as_of, params, pp)
    sd = total_sd(avg.n_eff, days, params["sigma"])
    names = {p["pollster_id"]: p["pollster_name"] for p in ps}
    for c in avg.contributions:
        c["name"] = names.get(c["pollster_id"], c["pollster_id"])
    return {"side_a": race["side_a"][0], "side_a_party": race["side_a"][1],
            "side_b": race["side_b"][0], "side_b_party": race["side_b"][1],
            "margin": round(avg.mu, 2), "sd": round(sd, 2), "p_a": round(win_prob(avg.mu, sd), 4),
            "poll_average": round(avg.mu, 2), "n_polls": avg.n_polls, "n_eff": round(avg.n_eff, 1),
            "last_poll": avg.last_poll, "polls": avg.contributions}


def build(cfg: dict | None = None, as_of: date | None = None) -> dict:
    cfg = cfg or yaml.safe_load(CONFIG.read_text())
    eday = cfg["election_date"] if isinstance(cfg["election_date"], date) else date.fromisoformat(str(cfg["election_date"]))
    as_of = min(as_of or date.today(), eday)
    days = (eday - as_of).days
    params = load_params()
    gp = ROOT / "config" / "params_governor.yaml"
    gparams = {**params, **(yaml.safe_load(gp.read_text()) if gp.exists() else {})}
    target = load_scoring_config()["target_cycle"]
    pp = pollster_params(target, params["shrink_k"], params["quality_scale_s"],
                         load_all_polls(), load_all_results())
    known = set()
    rj = ROOT / "site" / "data" / "races.json"
    if rj.exists():
        known = {r["race_id"] for r in json.loads(rj.read_text())["races"]}

    sections = []
    for sec in cfg["sections"]:
        out = []
        for race in sec["races"]:
            item = {k: race[k] for k in ("id", "kind", "chip", "label") }
            for k in ("candidates", "summary", "page"):
                if k in race:
                    item[k] = race[k]
            if race["kind"] == "model":
                item["in_model"] = race["id"] in known
            elif race["kind"] == "polls":
                item["odds"] = forecast_polls_race(race, as_of, days, gparams, pp)
                item["candidates"] = [race["side_a"], race["side_b"]]
            out.append(item)
        sections.append({"name": sec["name"], "races": out})

    live = {r["id"]: {"page": r["page"], "district": None, "expected_votes": None}
            for s in sections for r in s["races"] if r["kind"] == "polls" and r.get("page")}
    return {"county": cfg["county"], "zip": str(cfg["zip"]), "ballot_style": str(cfg["ballot_style"]),
            "county_results_url": cfg["county_results_url"], "county_results_name": cfg["county_results_name"],
            "as_of": as_of.isoformat(), "sections": sections, "live": live}


def main() -> dict:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    races = [r for s in data["sections"] for r in s["races"]]
    return {"races": len(races),
            "odds": {r["id"]: r["odds"]["p_a"] for r in races if "odds" in r},
            "missing_from_model": [r["id"] for r in races if r["kind"] == "model" and not r["in_model"]]}


if __name__ == "__main__":
    print(main())
