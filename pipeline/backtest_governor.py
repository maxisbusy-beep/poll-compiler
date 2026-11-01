"""Governor backtest: same poll averaging as the Senate (settings in config/params.yaml),
but re-fits the two things that differ for governors on past governor races (2004-2024):
how much weight the presidential-lean prior gets, the uncertainty, and how far off the
lean alone is for races with no polls. Governors often run far from their state's
presidential lean (Vermont, Maryland, Kentucky...), so the Senate value isn't reused.

Writes config/params_governor.yaml and reports/backtest_governor.md.
"""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean

import yaml

from pipeline import backtest as bt
from pipeline.model import load_all_polls, load_all_results, load_params

GRID = [0.0, 0.1, 0.25, 0.5, 1.0]


def gov_races(results, cycle):
    return [r for r in results.values()
            if int(r["cycle"]) == cycle and r["race_type"] == "GOV" and r["special"] in ("", "S")]


def run() -> dict:
    params = load_params()
    all_polls = load_all_polls()
    results = load_all_results()
    by_race = defaultdict(list)
    for p in all_polls:
        if p["race_type"] == "GOV":
            by_race[p["race_id"]].append(p)
    bt.senate_races = gov_races          # reuse the Senate machinery on governor races
    cycles = [c for c in bt.CYCLES if gov_races(results, c)]
    bt.CYCLES = cycles
    raw = bt._observations_all(by_race, results, params, all_polls)
    trials = [(w0, bt.rmse(bt.apply_prior(raw, w0))) for w0 in GRID]
    best_w0 = min(trials, key=lambda t: t[1])[0]
    obs = bt.apply_prior(raw, best_w0)
    sig = bt.fit_sigma(obs)
    pri = [(o["prior"] - o["actual"]) for o in obs if o["days"] == 7 and o["prior"] is not None]
    lean_sigma = round(math.sqrt(mean(e * e for e in pri)), 2)
    loco = {c: bt.fit_sigma([o for o in obs if o["cycle"] != c]) for c in cycles}
    scores = bt.prob_scores(obs, lambda c: loco[c])
    called = [o for o in obs if o["days"] == 7]
    right = sum(1 for o in called if (o["mu"] > 0) == (o["actual"] > 0))
    return {"trials": trials, "prior_weight": best_w0, "sigma": sig, "lean_sigma": lean_sigma,
            "scores": scores, "n_obs": len(obs), "races_7d": len(called), "right_7d": right,
            "cycles": cycles}


def main() -> dict:
    res = run()
    out = {"prior_weight": res["prior_weight"], "sigma": res["sigma"], "lean_sigma": res["lean_sigma"]}
    (bt.ROOT / "config" / "params_governor.yaml").write_text(
        "# Written by `python -m pipeline.backtest_governor`. Do not edit by hand.\n" + yaml.safe_dump(out, sort_keys=False))
    lines = ["# Governor backtest", "",
             f"Past governor races with polls, {res['cycles'][0]}-{res['cycles'][-1]}, 7 and 30 days out "
             f"({res['n_obs']} race-days). Poll averaging uses the Senate settings.", "",
             "| Lean prior weight (effective polls) | Error (RMSE, pts) |", "|---|---|"]
    lines += [f"| {w} | {r:.2f} |" for w, r in res["trials"]]
    lines += ["", f"Chosen prior weight: **{res['prior_weight']}**.",
              f"Uncertainty: a={res['sigma']['a']}, b={res['sigma']['b']}, c={res['sigma']['c']}.",
              f"Lean alone misses by {res['lean_sigma']} pts (RMSE), used for races with no polls.",
              f"Leader 7 days out won {res['right_7d']} of {res['races_7d']} races.",
              f"Probability scores (out of sample by cycle): {res['scores']}"]
    (bt.ROOT / "reports" / "backtest_governor.md").write_text("\n".join(lines) + "\n")
    return out | {"right_7d": f"{res['right_7d']}/{res['races_7d']}", "trials": res["trials"]}


if __name__ == "__main__":
    print(main())
