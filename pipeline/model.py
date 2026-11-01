"""Polling averages, race win probabilities and chamber simulation (SPEC.md section 5).

Everything here is a pure function of (polls, results, parameters, as-of date),
so the same code runs the live forecast and the backtest. Nothing reads a poll
that ended after the as-of date, and pollster quality always comes from cycles
before the one being forecast.
"""
from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

from pipeline.score_pollsters import load_config as load_scoring_config
from pipeline.score_pollsters import score as score_pollsters

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "config" / "params.yaml"
CYCLES = ROOT / "config" / "cycles.yaml"
BIAS_MATCHUPS = {"D-R", "X-R"}

DEFAULT_PARAMS = {
    "half_life_days": 14.0,
    "shrink_k": 10.0,
    "quality_scale_s": 3.0,
    "use_bias_correction": True,
    "population_weight": {"LV": 1.0, "RV": 0.7, "A": 0.3, "": 0.85},
    "default_sample": 600,
    "sigma": {"a": 4.0, "b": 6.0, "c": 0.0},      # sd^2 = a^2 + b^2/n_eff + c*days
    "national_sd": 2.5,
    "lean_sigma": 10.0,
    "prior_weight": 0.0,      # lean prior counted as this many effective polls (tuned in backtest)
}


def load_params() -> dict:
    p = dict(DEFAULT_PARAMS)
    if PARAMS.exists():
        p.update(yaml.safe_load(PARAMS.read_text()) or {})
    return p


def load_cycles() -> dict:
    return yaml.safe_load(CYCLES.read_text())


def read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open())) if path.exists() else []


def load_all_polls() -> list[dict]:
    out = []
    for f in sorted((ROOT / "data" / "polls").glob("*.csv")):
        out += read_csv(f)
    return out


def load_all_results() -> dict[str, dict]:
    out = {}
    for f in sorted((ROOT / "data" / "results").glob("*.csv")):
        for r in read_csv(f):
            out[r["race_id"]] = r
    return out


# ---- pollster parameters (no look-ahead) --------------------------------------

_pp_cache: dict = {}


def pollster_params(target_cycle: int, k: float, s: float, polls: list[dict],
                    results: dict[str, dict]) -> dict[str, dict]:
    """pollster_id -> {"weight", "shrunk_bias"} using only cycles before target_cycle."""
    key = (target_cycle, k, s, len(polls), len(results))
    if key not in _pp_cache:
        cfg = load_scoring_config()
        cfg = {**cfg, "model": {"shrink_k": k, "quality_scale_s": s}}
        summary, _ = score_pollsters(polls, results, target_cycle, cfg)
        _pp_cache[key] = {p["id"]: p["model"] for p in summary["pollsters"]}
    return _pp_cache[key]


# ---- 5.1 race polling average -------------------------------------------------

@dataclass
class Average:
    race_id: str
    mu: float
    n_polls: int
    n_eff: float
    last_poll: str
    contributions: list[dict] = field(default_factory=list)


def poll_end(p: dict) -> date:
    return date.fromisoformat(p.get("end_date") or p["poll_date"])


def race_average(polls: list[dict], as_of: date, params: dict,
                 pp: dict[str, dict]) -> Average | None:
    """Weighted, bias-corrected average margin (side_a minus side_b) as of a date."""
    usable = [p for p in polls if poll_end(p) <= as_of]
    if not usable:
        return None
    usable.sort(key=poll_end, reverse=True)
    seen = defaultdict(int)
    rows, ws = [], []
    hl = params["half_life_days"]
    popw = params["population_weight"]
    for p in usable:
        seen[p["pollster_id"]] += 1
        age = (as_of - poll_end(p)).days
        n = int(p["sample_size"]) if str(p.get("sample_size") or "").isdigit() else params["default_sample"]
        m = pp.get(p["pollster_id"], {"weight": 1.0, "shrunk_bias": 0.0})
        w = (0.5 ** (age / hl)
             * math.sqrt(min(n, 2000))
             * popw.get(p.get("population", ""), popw[""])
             * m["weight"]
             / seen[p["pollster_id"]])
        corr = m["shrunk_bias"] if (params["use_bias_correction"]
                                    and p["matchup"] in BIAS_MATCHUPS) else 0.0
        margin = float(p["margin_poll"]) - corr
        rows.append({"pollster_id": p["pollster_id"], "end": poll_end(p).isoformat(),
                     "margin_raw": float(p["margin_poll"]), "bias_correction": round(corr, 2),
                     "margin": margin, "w": w})
        ws.append(w)
    tot = sum(ws)
    if tot <= 0:
        return None
    mu = sum(r["margin"] * r["w"] for r in rows) / tot
    n_eff = tot * tot / sum(w * w for w in ws)
    for r in rows:
        r["weight_share"] = round(r["w"] / tot, 4)
        r["margin"] = round(r["margin"], 2)
        del r["w"]
    return Average(polls[0]["race_id"], mu, len(usable), n_eff, rows[0]["end"], rows)


def naive_average(polls: list[dict], as_of: date) -> Average | None:
    """Baseline: plain mean of polls ending in the 21 days before as_of (else last 3)."""
    usable = sorted((p for p in polls if poll_end(p) <= as_of), key=poll_end, reverse=True)
    if not usable:
        return None
    recent = [p for p in usable if (as_of - poll_end(p)).days <= 21] or usable[:3]
    mu = sum(float(p["margin_poll"]) for p in recent) / len(recent)
    return Average(polls[0]["race_id"], mu, len(recent), float(len(recent)), poll_end(usable[0]).isoformat())


# ---- prior from partisan lean ------------------------------------------------

def last_pres_cycle(cycle: int) -> int:
    return cycle - (cycle % 4) if cycle % 4 else cycle - 4


def environment(all_polls: list[dict], cycle: int, as_of: date) -> float | None:
    """National environment (Dem minus Rep) as of a date: mean of generic-ballot polls in
    the prior 21 days, or national presidential polls in a presidential year."""
    for rtype, rid in (("HOUSE-GEN", f"{cycle}-HOUSE-GEN"), ("PRES", f"{cycle}-PRES-US")):
        ps = [p for p in all_polls if p["race_id"] == rid and poll_end(p) <= as_of
              and (as_of - poll_end(p)).days <= 21]
        if ps:
            return sum(float(p["margin_poll"]) for p in ps) / len(ps)
    return None


def lean_prior(state: str, cycle: int, results: dict, env: float | None,
               national_override: float | None = None) -> float | None:
    """Expected margin from partisan lean: the state's last presidential margin, moved by
    how the national environment differs from that presidential year."""
    pc = last_pres_cycle(cycle)
    st = results.get(f"{pc}-PRES-{state}")
    if st is None:
        return None
    nat = results.get(f"{pc}-PRES-US")
    nat_m = float(nat["margin_actual"]) if nat else national_override
    if env is None or nat_m is None:
        return float(st["margin_actual"])
    return float(st["margin_actual"]) - nat_m + env


def blend(mu_polls: float, n_eff: float, prior: float | None, w0: float) -> tuple[float, float]:
    """Treat the lean prior as w0 extra 'effective polls'. Returns (mu, effective n)."""
    if prior is None or w0 <= 0:
        return mu_polls, n_eff
    return (mu_polls * n_eff + prior * w0) / (n_eff + w0), n_eff + w0


# ---- 5.2 win probability -----------------------------------------------------

def total_sd(n_eff: float, days: int, sig: dict) -> float:
    return math.sqrt(sig["a"] ** 2 + sig["b"] ** 2 / max(n_eff, 0.5) + sig["c"] * max(days, 0))


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def win_prob(mu: float, sd: float) -> float:
    return phi(mu / sd)


# ---- 5.3 simulation ------------------------------------------------------------

@dataclass
class RaceForecast:
    race_id: str
    state: str
    side_a: str
    side_a_party: str
    side_b: str
    side_b_party: str
    matchup: str
    mu: float
    sd_total: float
    sd_race: float
    p_a: float
    n_polls: int
    n_eff: float
    last_poll: str
    basis: str                      # "polls" or "lean"
    contributions: list[dict] = field(default_factory=list)


def simulate_senate(races: list[RaceForecast], senate_cfg: dict, national_sd: float,
                    n_sims: int = 10000, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    nu = senate_cfg["not_up"]
    uncommitted = set(senate_cfg.get("uncommitted", []))
    dem_needs = senate_cfg["dem_needs"]
    rep_needs = 101 - dem_needs if dem_needs == 51 else 51   # VP-R: R needs 50; VP-D: R needs 51
    dem_seats, outcomes = [], {"dem": 0, "rep": 0, "uncommitted": 0}
    for _ in range(n_sims):
        nat = rng.gauss(0, national_sd)
        d, r, u = nu["dem"], nu["rep"], 0
        for rc in races:
            m = rc.mu + nat + rng.gauss(0, rc.sd_race)
            party = rc.side_a_party if m > 0 else rc.side_b_party
            if party == "REP":
                r += 1
            elif m > 0 and rc.race_id in uncommitted:
                u += 1
            else:                       # Democrat, or a non-Republican who caucuses with them
                d += 1
        dem_seats.append(d)
        if d >= dem_needs:
            outcomes["dem"] += 1
        elif r >= rep_needs:
            outcomes["rep"] += 1
        else:
            outcomes["uncommitted"] += 1
    dem_seats.sort()
    hist = defaultdict(int)
    for x in dem_seats:
        hist[x] += 1
    q = lambda f: dem_seats[min(int(f * n_sims), n_sims - 1)]  # noqa: E731
    return {
        "n_sims": n_sims,
        "p_dem_control": outcomes["dem"] / n_sims,
        "p_rep_control": outcomes["rep"] / n_sims,
        "p_uncommitted_decides": outcomes["uncommitted"] / n_sims,
        "dem_seats_median": q(0.5), "dem_seats_p10": q(0.1), "dem_seats_p90": q(0.9),
        "dem_seats_hist": dict(sorted(hist.items())),
        "dem_needs": dem_needs, "rep_needs": rep_needs,
    }


def split_sd(sd_total: float, national_sd: float) -> float:
    """Race-only sd after removing the shared national part."""
    return math.sqrt(max(sd_total ** 2 - national_sd ** 2, 1.0))


def rating(p: float) -> str:
    x = max(p, 1 - p)
    side = "A" if p >= 0.5 else "B"
    if x < 0.6:
        return "Toss-up"
    label = "Lean" if x < 0.8 else "Likely" if x < 0.95 else "Safe"
    return f"{label} {side}"


def simulate_house(races: list[RaceForecast], national_sd: float, need: int = 218,
                   n_sims: int = 10000, seed: int = 2027) -> dict:
    """Seats won by Democrats (and any non-Republican winner) across all districts."""
    rng = random.Random(seed)
    seats = []
    for _ in range(n_sims):
        nat = rng.gauss(0, national_sd)
        d = 0
        for rc in races:
            m = rc.mu + nat + rng.gauss(0, rc.sd_race)
            party = rc.side_a_party if m > 0 else rc.side_b_party
            if party not in ("REP",):
                d += 1
        seats.append(d)
    seats.sort()
    hist = defaultdict(int)
    for x in seats:
        hist[x] += 1
    q = lambda f: seats[min(int(f * n_sims), n_sims - 1)]  # noqa: E731
    p_dem = sum(1 for x in seats if x >= need) / n_sims
    return {"n_sims": n_sims, "p_dem_control": p_dem, "p_rep_control": 1 - p_dem,
            "dem_seats_median": q(0.5), "dem_seats_p10": q(0.1), "dem_seats_p90": q(0.9),
            "dem_seats_hist": dict(sorted(hist.items())), "need": need, "seats": len(races)}
