"""Pollster accuracy scoring (SPEC.md section 4).

For every pollster and every race, take the pollster's FINAL poll that ended
within `final_window_days` of the election, and compare its margin to the
actual margin. Summaries are computed for three windows that look back from a
target cycle, using only cycles BEFORE it (no look-ahead):

* same_type: the most recent earlier cycle of the same type (2026 -> 2022)
* last_two:  the two previous federal general elections (2026 -> 2022, 2024)
* all_time:  every earlier cycle

Margins are side_a minus side_b (Dem or main non-Rep minus Rep). Bias is only
averaged over D-R and X-R races, where its sign means something.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import yaml

from pipeline.normalize import PollsterAliases, cycle_type

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "scoring.yaml"
SITE_DATA = ROOT / "site" / "data"
BIAS_MATCHUPS = {"D-R", "X-R"}


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def _read(folder: str) -> list[dict]:
    rows = []
    for f in sorted((ROOT / "data" / folder).glob("*.csv")):
        rows += list(csv.DictReader(f.open()))
    return rows


def load_polls() -> list[dict]:
    return _read("polls")


def load_results() -> dict[str, dict]:
    return {r["race_id"]: r for r in _read("results")}


# ---- step 1: final poll per pollster per race ------------------------------

def _poll_day(p: dict) -> str:
    return p.get("end_date") or p["poll_date"]


def final_polls(polls: list[dict], results: dict[str, dict], window_days: int,
                race_types: list[str]) -> list[dict]:
    """One scored record per (pollster, race): that pollster's last eligible poll."""
    best: dict[tuple[str, str], dict] = {}
    for p in polls:
        if p["race_type"] not in race_types or p["race_id"] not in results:
            continue
        if int(p["days_to_election"]) > window_days:
            continue
        key = (p["pollster_id"], p["race_id"])
        rank = (_poll_day(p), int(p["sample_size"] or 0), p["source_ref"])
        if key not in best or rank > best[key][0]:
            best[key] = (rank, p)

    out = []
    for (pid, rid), (_, p) in best.items():
        actual = float(results[rid]["margin_actual"])
        m = float(p["margin_poll"])
        err = m - actual
        if m == 0:
            called = 0.5
        else:
            called = 1.0 if (m > 0) == (actual > 0) else 0.0
        out.append({
            "pollster_id": pid, "race_id": rid, "cycle": int(p["cycle"]),
            "cycle_type": p["cycle_type"], "race_type": p["race_type"],
            "matchup": p["matchup"], "partisan": p["partisan"],
            "poll_date": _poll_day(p), "days_to_election": int(p["days_to_election"]),
            "margin_poll": m, "margin_actual": actual,
            "error": err, "abs_error": abs(err), "called": called,
        })
    return add_excess(out)


def add_excess(records: list[dict]) -> list[dict]:
    """excess_error = abs_error minus the average abs_error of all pollsters in that race.

    Races polled by only one pollster have no comparison, so excess is None there.
    """
    by_race = defaultdict(list)
    for r in records:
        by_race[r["race_id"]].append(r)
    for rs in by_race.values():
        if len(rs) < 2:
            for r in rs:
                r["excess_error"] = None
            continue
        avg = mean(r["abs_error"] for r in rs)
        for r in rs:
            r["excess_error"] = r["abs_error"] - avg
    return records


# ---- step 2: windows -------------------------------------------------------

def windows(target_cycle: int, available: set[int]) -> dict[str, dict]:
    """Which cycles each window covers, and which of those have no data yet."""
    ttype = cycle_type(target_cycle)
    same = [c for c in available if c < target_cycle and c % 2 == 0 and cycle_type(c) == ttype]
    same_cycles = [max(same)] if same else []
    last_two = [target_cycle - 4, target_cycle - 2]
    earlier = sorted(c for c in available if c < target_cycle)
    return {
        "same_type": {"label": f"Last {ttype} ({same_cycles[0]})" if same_cycles else "Last same-type",
                      "cycles": same_cycles, "missing": []},
        "last_two": {"label": f"Last two cycles ({last_two[0]}, {last_two[1]})",
                     "cycles": last_two, "missing": [c for c in last_two if c not in available]},
        "all_time": {"label": f"All time ({earlier[0]}–{earlier[-1]})" if earlier else "All time",
                     "cycles": earlier, "missing": []},
    }


def summarize(records: list[dict]) -> dict:
    n = len(records)
    if not n:
        return {"n": 0}
    bias_rs = [r for r in records if r["matchup"] in BIAS_MATCHUPS]
    exc_rs = [r for r in records if r["excess_error"] is not None]
    return {
        "n": n,
        "win_call_pct": 100 * sum(r["called"] for r in records) / n,
        "mean_abs_error": mean(r["abs_error"] for r in records),
        "bias": mean(r["error"] for r in bias_rs) if bias_rs else None,
        "n_bias": len(bias_rs),
        "excess_error": mean(r["excess_error"] for r in exc_rs) if exc_rs else None,
        "n_excess": len(exc_rs),
    }


def model_params(all_time: dict, k: float, s: float) -> dict:
    """Shrunk excess error and bias, and the resulting quality weight (SPEC 4).

    A pollster with no history gets weight 1.0 (average) and no bias correction.
    """
    ex, nx = all_time.get("excess_error"), all_time.get("n_excess", 0)
    bi, nb = all_time.get("bias"), all_time.get("n_bias", 0)
    shrunk_ex = ex * nx / (nx + k) if ex is not None else 0.0
    shrunk_bi = bi * nb / (nb + k) if bi is not None else 0.0
    return {"shrunk_excess": shrunk_ex, "shrunk_bias": shrunk_bi,
            "weight": math.exp(-shrunk_ex / s)}


# ---- step 3: put it together ----------------------------------------------

def _round(d, nd=2):
    if isinstance(d, dict):
        return {k: _round(v, nd) for k, v in d.items()}
    if isinstance(d, list):
        return [_round(v, nd) for v in d]
    if isinstance(d, float):
        return round(d, nd)
    return d


def score(polls: list[dict], results: dict[str, dict], target_cycle: int, cfg: dict,
          names: dict[str, str] | None = None) -> tuple[dict, dict]:
    """Return (pollsters summary, per-pollster history). Uses only cycles < target_cycle."""
    recs = final_polls(polls, results, cfg["final_window_days"], cfg["race_types"])
    recs = [r for r in recs if r["cycle"] < target_cycle]
    available = {r["cycle"] for r in recs}
    wins = windows(target_cycle, available)
    k, s = cfg["model"]["shrink_k"], cfg["model"]["quality_scale_s"]

    by_p = defaultdict(list)
    for r in recs:
        by_p[r["pollster_id"]].append(r)

    pollsters, history = [], {}
    for pid, rs in by_p.items():
        stats = {w: summarize([r for r in rs if r["cycle"] in spec["cycles"]])
                 for w, spec in wins.items()}
        pollsters.append({
            "id": pid, "name": (names or {}).get(pid, pid),
            "cycles": sorted({r["cycle"] for r in rs}),
            "windows": stats,
            "model": model_params(stats["all_time"], k, s),
        })
        history[pid] = sorted(
            ({key: r[key] for key in ("race_id", "cycle", "poll_date", "margin_poll",
                                      "margin_actual", "error", "called", "excess_error",
                                      "matchup", "partisan")} for r in rs),
            key=lambda r: (-r["cycle"], r["race_id"]))

    # Best first by shrunk excess error, so small-sample lucky streaks don't top the list.
    pollsters.sort(key=lambda p: (p["model"]["shrunk_excess"], p["id"]))
    summary = {
        "target_cycle": target_cycle,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": {"final_window_days": cfg["final_window_days"],
                     "race_types": cfg["race_types"], "min_n_display": cfg["min_n_display"],
                     "shrink_k": k, "quality_scale_s": s},
        "windows": wins,
        "scored_races": len({r["race_id"] for r in recs}),
        "scored_polls": len(recs),
        "pollsters": pollsters,
    }
    return _round(summary), _round(history)


def main() -> dict:
    cfg = load_config()
    aliases = PollsterAliases()
    names = {pid: info["name"] for pid, info in aliases.pollsters.items()}
    summary, history = score(load_polls(), load_results(), cfg["target_cycle"], cfg, names)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "pollsters.json").write_text(json.dumps(summary, separators=(",", ":")))
    (SITE_DATA / "pollster_history.json").write_text(json.dumps(history, separators=(",", ":")))
    return {"pollsters": len(summary["pollsters"]), "scored_polls": summary["scored_polls"],
            "scored_races": summary["scored_races"]}


if __name__ == "__main__":
    print(main())
