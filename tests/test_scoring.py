"""Phase 2 tests: pollster scoring math, windows and no-look-ahead (SPEC.md section 4)."""
import math

import pytest

from pipeline.score_pollsters import (
    final_polls, load_config, model_params, score, summarize, windows,
)

CFG = {"final_window_days": 21, "race_types": ["SEN", "HOUSE", "HOUSE-GEN", "GOV", "PRES"],
       "min_n_display": 5, "model": {"shrink_k": 10, "quality_scale_s": 3.0}}


def poll(pid, rid, margin, days=5, date="2022-11-01", cycle=2022, matchup="D-R",
         race_type="SEN", sample=800, ref="x"):
    return {"pollster_id": pid, "race_id": rid, "margin_poll": str(margin),
            "days_to_election": str(days), "poll_date": date, "end_date": "",
            "cycle": str(cycle), "cycle_type": "midterm" if cycle % 4 else "presidential",
            "matchup": matchup, "race_type": race_type, "sample_size": str(sample),
            "source_ref": ref, "partisan": ""}


def res(rid, margin, matchup="D-R"):
    return {rid: {"race_id": rid, "margin_actual": str(margin), "matchup": matchup}}


def test_only_final_poll_in_window_counts():
    polls = [poll("a", "R1", 10, days=30, date="2022-10-09"),   # outside window
             poll("a", "R1", 2, days=10, date="2022-10-29"),
             poll("a", "R1", 4, days=3, date="2022-11-05")]     # final -> counts
    recs = final_polls(polls, res("R1", 1), 21, CFG["race_types"])
    assert len(recs) == 1 and recs[0]["margin_poll"] == 4
    assert recs[0]["error"] == 3 and recs[0]["abs_error"] == 3


def test_no_poll_in_window_means_not_scored():
    recs = final_polls([poll("a", "R1", 3, days=40)], res("R1", 1), 21, CFG["race_types"])
    assert recs == []


def test_win_call_and_tie():
    polls = [poll("a", "R1", 3), poll("b", "R1", -2), poll("c", "R1", 0)]
    recs = {r["pollster_id"]: r for r in final_polls(polls, res("R1", 1), 21, CFG["race_types"])}
    assert (recs["a"]["called"], recs["b"]["called"], recs["c"]["called"]) == (1.0, 0.0, 0.5)


def test_excess_error_relative_to_race_average():
    polls = [poll("a", "R1", 2), poll("b", "R1", 6)]           # actual 2: errors 0 and 4
    recs = {r["pollster_id"]: r for r in final_polls(polls, res("R1", 2), 21, CFG["race_types"])}
    assert recs["a"]["excess_error"] == -2 and recs["b"]["excess_error"] == 2


def test_single_pollster_race_has_no_excess():
    recs = final_polls([poll("a", "R1", 2)], res("R1", 2), 21, CFG["race_types"])
    assert recs[0]["excess_error"] is None


def test_bias_ignores_same_party_races():
    polls = [poll("a", "R1", 5), poll("a", "R2", -5, matchup="same-party")]
    results = {**res("R1", 1), **res("R2", 3, "same-party")}
    s = summarize(final_polls(polls, results, 21, CFG["race_types"]))
    assert s["n"] == 2 and s["n_bias"] == 1 and s["bias"] == 4
    assert s["mean_abs_error"] == 6  # (4 + 8) / 2


def test_windows_for_2026():
    w = windows(2026, {1998, 2018, 2020, 2021, 2022})
    assert w["same_type"]["cycles"] == [2022]
    assert w["last_two"]["cycles"] == [2022, 2024] and w["last_two"]["missing"] == [2024]
    assert w["all_time"]["cycles"] == [1998, 2018, 2020, 2021, 2022]


def test_windows_for_2028_use_presidential():
    w = windows(2028, {2016, 2020, 2022, 2024, 2026})
    assert w["same_type"]["cycles"] == [2024]
    assert w["last_two"]["cycles"] == [2024, 2026] and w["last_two"]["missing"] == []


def test_shrinkage_and_weight():
    m = model_params({"excess_error": -2.0, "n_excess": 10, "bias": 3.0, "n_bias": 30}, k=10, s=3)
    assert m["shrunk_excess"] == pytest.approx(-1.0)
    assert m["shrunk_bias"] == pytest.approx(2.25)
    assert m["weight"] == pytest.approx(math.exp(1 / 3))


def test_new_pollster_is_average():
    m = model_params({"n": 0}, k=10, s=3)
    assert m == {"shrunk_excess": 0.0, "shrunk_bias": 0.0, "weight": 1.0}


def test_no_look_ahead():
    polls = [poll("a", "R18", 2, cycle=2018, date="2018-11-01"),
             poll("a", "R22", 9, cycle=2022)]
    results = {**res("R18", 2), **res("R22", 1)}
    summary, history = score(polls, results, 2020, CFG)
    a = summary["pollsters"][0]
    assert a["windows"]["all_time"]["n"] == 1 and a["windows"]["all_time"]["mean_abs_error"] == 0
    assert [h["race_id"] for h in history["a"]] == ["R18"]


def test_config_file_is_valid():
    cfg = load_config()
    assert cfg["target_cycle"] % 2 == 0
    assert cfg["final_window_days"] == 21
    assert {"SEN", "HOUSE"} <= set(cfg["race_types"])
