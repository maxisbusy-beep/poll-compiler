"""Backtest and tune the Senate model (SPEC.md 5.4).

For each past cycle, rebuild the forecast as it would have looked 7 and 30 days
before Election Day: only polls that had ended by then, and pollster quality
scored only on earlier cycles. Then:

1. choose the averaging settings (half-life, shrinkage, quality scale, bias
   correction) with the lowest error of the average vs the actual margin;
2. fit how uncertain an average is (sd from a floor, poll count and days out)
   and how much of the miss is shared nationally;
3. score calibrated win probabilities out of sample (leave one cycle out),
   against a naive baseline (plain mean of recent polls).

Writes config/params.yaml and reports/backtest.md.
"""
from __future__ import annotations

import itertools
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, pvariance

import yaml

from pipeline.model import (
    DEFAULT_PARAMS, blend, environment, lean_prior, load_all_polls, load_all_results,
    naive_average, pollster_params, race_average, simulate_senate, split_sd, total_sd, win_prob,
    RaceForecast,
)

ROOT = Path(__file__).resolve().parent.parent
CYCLES = list(range(2004, 2026, 2))
DAYS = (7, 30)
GRID = {
    "half_life_days": [7, 14, 28],
    "kq": [(10, 3.0), (10, 6.0), (25, 3.0), (10, 1e9)],      # (shrink_k, quality_scale_s); 1e9 = no quality weighting
    "use_bias_correction": [True, False],
    "prior_weight": [0.0, 0.5, 1.0, 2.0, 4.0],
}


def senate_races(results: dict, cycle: int) -> list[dict]:
    return [r for r in results.values()
            if int(r["cycle"]) == cycle and r["race_type"] == "SEN" and r["special"] in ("", "S")]


def naive_observations(polls_by_race, results) -> list[dict]:
    """Baseline: plain mean of recent polls, no weights, no bias correction."""
    obs = []
    for cyc in CYCLES:
        races = senate_races(results, cyc)
        if not races:
            continue
        eday = date.fromisoformat(races[0]["election_date"])
        for d in DAYS:
            as_of = eday - timedelta(days=d)
            for r in races:
                ps = polls_by_race.get(r["race_id"], [])
                avg = naive_average(ps, as_of)
                if avg is None:
                    continue
                obs.append({"cycle": cyc, "days": d, "race_id": r["race_id"], "mu": avg.mu,
                            "n_eff": avg.n_eff, "actual": float(r["margin_actual"]),
                            "matchup": r["matchup"]})
    return obs


def rmse(obs):
    return math.sqrt(mean((o["mu"] - o["actual"]) ** 2 for o in obs))


def fit_sigma(obs) -> dict:
    """Max-likelihood (a, b, c) for sd^2 = a^2 + b^2/n_eff + c*days on a coarse grid."""
    best, arg = -1e18, None
    for a in [x / 2 for x in range(4, 21)]:           # 2.0 .. 10.0
        for b in [0, 2, 4, 6, 8, 10, 12, 15]:
            for c in [0, 0.1, 0.2, 0.4, 0.8]:
                sig = {"a": a, "b": b, "c": c}
                ll = 0.0
                for o in obs:
                    sd = total_sd(o["n_eff"], o["days"], sig)
                    e = o["mu"] - o["actual"]
                    ll += -math.log(sd) - e * e / (2 * sd * sd)
                if ll > best:
                    best, arg = ll, sig
    return arg


def national_sd(obs) -> float:
    """Shared (cycle-wide) part of the miss, from per-cycle mean errors at 7 days out."""
    by = defaultdict(list)
    for o in obs:
        if o["days"] == 7:
            by[o["cycle"]].append(o["mu"] - o["actual"])
    means = [mean(v) for v in by.values() if len(v) >= 5]
    within = mean(pvariance(v) / len(v) for v in by.values() if len(v) >= 5)
    return round(math.sqrt(max(pvariance(means) - within, 0.25)), 2)


def prob_scores(obs, sig_for) -> dict:
    """Brier / log loss / calibration with sigma fitted leave-one-cycle-out."""
    rows = []
    for o in obs:
        sig = sig_for(o["cycle"])
        p = win_prob(o["mu"], total_sd(o["n_eff"], o["days"], sig))
        y = 1.0 if o["actual"] > 0 else 0.0
        rows.append((p, y, o))
    brier = mean((p - y) ** 2 for p, y, _ in rows)
    ll = -mean(math.log(max(min(p if y else 1 - p, 1 - 1e-6), 1e-6)) for p, y, _ in rows)
    buckets = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 0.99), (0.99, 1.01)]
    cal = []
    for lo, hi in buckets:
        sel = [(max(p, 1 - p), (y == 1) == (p >= 0.5)) for p, y, _ in rows if lo <= max(p, 1 - p) < hi]
        if sel:
            cal.append({"bucket": f"{int(lo*100)}–{min(int(hi*100), 100)}%", "n": len(sel),
                        "forecast": mean(x for x, _ in sel), "won": mean(1.0 if w else 0.0 for _, w in sel)})
    return {"brier": brier, "logloss": ll, "n": len(rows), "calibration": cal}


def run() -> dict:
    polls = [p for p in load_all_polls() if p["race_type"] == "SEN"]
    results = load_all_results()
    by_race = defaultdict(list)
    for p in polls:
        by_race[p["race_id"]].append(p)
    all_polls = load_all_polls()   # pollster scoring uses every race type

    # 1. tune averaging settings
    trials = []
    for hl, (k, s), bias in itertools.product(GRID["half_life_days"], GRID["kq"],
                                              GRID["use_bias_correction"]):
        params = {**DEFAULT_PARAMS, "half_life_days": hl, "shrink_k": k, "quality_scale_s": s,
                  "use_bias_correction": bias}
        raw = _observations_all(by_race, results, params, all_polls)
        for w0 in GRID["prior_weight"]:
            obs = apply_prior(raw, w0)
            trials.append({"params": {**params, "prior_weight": w0}, "rmse": rmse(obs),
                           "n": len(obs), "obs": obs})
    trials.sort(key=lambda t: t["rmse"])
    best = trials[0]
    obs = best["obs"]

    # 2. uncertainty
    sig_all = fit_sigma(obs)
    loco = {c: fit_sigma([o for o in obs if o["cycle"] != c]) for c in CYCLES}
    nat = national_sd(obs)

    # 3. out-of-sample probability scores, model vs naive
    model_scores = prob_scores(obs, lambda c: loco[c])
    naive_obs = naive_observations(by_race, results)
    naive_loco = {c: fit_sigma([o for o in naive_obs if o["cycle"] != c]) for c in CYCLES}
    naive_scores = prob_scores(naive_obs, lambda c: naive_loco[c])

    # 4. chamber check: seats won among polled races, 7 days out
    chamber = []
    for c in CYCLES:
        os7 = [o for o in obs if o["cycle"] == c and o["days"] == 7]
        if len(os7) < 5:
            continue
        rf = []
        for o in os7:
            sd = total_sd(o["n_eff"], 7, loco[c])
            rf.append(RaceForecast(o["race_id"], "", "", "DEM", "", "REP", o["matchup"], o["mu"],
                                   sd, split_sd(sd, nat), 0, 0, o["n_eff"], "", "polls"))
        sim = simulate_senate(rf, {"not_up": {"dem": 0, "rep": 0}, "dem_needs": 51}, nat, 4000)
        actual = sum(1 for o in os7 if o["actual"] > 0)
        chamber.append({"cycle": c, "races": len(os7), "median": sim["dem_seats_median"],
                        "p10": sim["dem_seats_p10"], "p90": sim["dem_seats_p90"], "actual": actual})

    # how far off the lean prior alone is (used for races with no polls)
    pri = [(o["prior"] - o["actual"]) for o in obs if o["days"] == 7 and o["prior"] is not None]
    lean_sigma = round(math.sqrt(mean(e * e for e in pri)), 2)

    params_out = {k: v for k, v in best["params"].items()}
    params_out.update({"sigma": sig_all, "national_sd": nat, "lean_sigma": lean_sigma})
    return {"best": best, "trials": trials, "params": params_out, "model": model_scores,
            "naive": naive_scores, "naive_rmse": rmse(naive_obs), "chamber": chamber,
            "n_obs": len(obs)}


def apply_prior(raw: list[dict], w0: float) -> list[dict]:
    out = []
    for o in raw:
        mu, n = blend(o["mu_polls"], o["n_eff_polls"], o["prior"] if o["matchup"] != "same-party" else None, w0)
        out.append({**o, "mu": mu, "n_eff": n})
    return out


def _observations_all(by_race, results, params, all_polls):
    obs = []
    env_cache = {}
    for cyc in CYCLES:
        races = senate_races(results, cyc)
        if not races:
            continue
        pp = pollster_params(cyc, params["shrink_k"], params["quality_scale_s"], all_polls, results)
        eday = date.fromisoformat(races[0]["election_date"])
        for d in DAYS:
            as_of = eday - timedelta(days=d)
            for r in races:
                avg = race_average(by_race.get(r["race_id"], []), as_of, params, pp)
                if avg is None:
                    continue
                if (cyc, d) not in env_cache:
                    env_cache[(cyc, d)] = environment(all_polls, cyc, as_of)
                prior = lean_prior(r["state"], cyc, results, env_cache[(cyc, d)])
                obs.append({"cycle": cyc, "days": d, "race_id": r["race_id"], "mu_polls": avg.mu,
                            "n_eff_polls": avg.n_eff, "prior": prior,
                            "actual": float(r["margin_actual"]), "matchup": r["matchup"]})
    return obs


def write(res: dict) -> None:
    p = res["params"]
    yaml_txt = ("# Written by `python -m pipeline.backtest`. Do not edit by hand; rerun the backtest.\n"
                + yaml.safe_dump(p, sort_keys=False))
    (ROOT / "config" / "params.yaml").write_text(yaml_txt)

    m, n = res["model"], res["naive"]
    L = ["# Senate model backtest", "",
         f"Cycles {CYCLES[0]}–{CYCLES[-1]}, Senate general and special races with at least one poll, "
         f"forecast as of 7 and 30 days before Election Day: **{res['n_obs']} race-forecasts**. "
         "Pollster quality for each cycle comes only from earlier cycles. "
         "Win probabilities are scored out of sample (uncertainty fitted on the other cycles).", "",
         "## Model vs naive baseline", "",
         "| | Error of the average (RMSE, pts) | Brier (lower is better) | Log loss |",
         "|---|---|---|---|",
         f"| **Model** | {res['best']['rmse']:.2f} | {m['brier']:.4f} | {m['logloss']:.3f} |",
         f"| Naive (plain mean of last 21 days) | {res['naive_rmse']:.2f} | {n['brier']:.4f} | {n['logloss']:.3f} |",
         "", ("**The model beats the baseline on every measure.**"
              if res["best"]["rmse"] < res["naive_rmse"] and m["brier"] < n["brier"] and m["logloss"] < n["logloss"]
              else "**The model does NOT beat the baseline on every measure — see SPEC 5.4.**"), "",
         "## Calibration (model, out of sample)", "",
         "| Forecast confidence | Races | Avg forecast | Favourite won |", "|---|---|---|---|"]
    for c in m["calibration"]:
        L.append(f"| {c['bucket']} | {c['n']} | {c['forecast']*100:.0f}% | {c['won']*100:.0f}% |")
    L += ["", "## Chamber check (7 days out, polled races only)", "",
          "Democratic wins among the races that had polls: forecast median and 80% range vs what happened.", "",
          "| Cycle | Races | Forecast | 80% range | Actual | In range |", "|---|---|---|---|---|---|"]
    for c in res["chamber"]:
        ok = "✅" if c["p10"] <= c["actual"] <= c["p90"] else "❌"
        L.append(f"| {c['cycle']} | {c['races']} | {c['median']} | {c['p10']}–{c['p90']} | {c['actual']} | {ok} |")
    L += ["", "## Chosen settings", "", "```yaml", yaml.safe_dump(p, sort_keys=False).strip(), "```", "",
          "## All settings tried (by error of the average)", "",
          "| Half-life | Shrink k | Quality scale | Bias correction | Lean prior (polls) | RMSE |",
          "|---|---|---|---|---|---|"]
    for t in res["trials"][:25]:
        q = t["params"]
        s = "off" if q["quality_scale_s"] >= 1e8 else q["quality_scale_s"]
        L.append(f"| {q['half_life_days']} | {q['shrink_k']} | {s} | "
                 f"{'on' if q['use_bias_correction'] else 'off'} | {q['prior_weight']} | {t['rmse']:.3f} |")
    (ROOT / "reports" / "backtest.md").write_text("\n".join(L) + "\n")


def main() -> None:
    res = run()
    write(res)
    print({"rmse": round(res["best"]["rmse"], 3), "naive_rmse": round(res["naive_rmse"], 3),
           "brier": round(res["model"]["brier"], 4), "naive_brier": round(res["naive"]["brier"], 4),
           "params": res["params"]})


if __name__ == "__main__":
    main()
