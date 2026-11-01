"""Phase 4 tests: polling average, lean prior, win probability and Senate simulation."""
from datetime import date

import pytest

from pipeline.model import (
    DEFAULT_PARAMS, RaceForecast, blend, last_pres_cycle, lean_prior, race_average,
    simulate_senate, split_sd, total_sd, win_prob,
)

P = {**DEFAULT_PARAMS, "half_life_days": 14, "use_bias_correction": True}


def poll(pid, margin, end, n=1000, pop="LV", matchup="D-R"):
    return {"race_id": "2026-SEN-XX", "pollster_id": pid, "margin_poll": str(margin),
            "end_date": end, "poll_date": end, "sample_size": str(n), "population": pop,
            "matchup": matchup}


def test_average_ignores_polls_after_as_of():
    ps = [poll("a", 2, "2026-10-01"), poll("b", 10, "2026-10-20")]
    avg = race_average(ps, date(2026, 10, 10), P, {})
    assert avg.mu == pytest.approx(2) and avg.n_polls == 1


def test_recency_half_life():
    ps = [poll("a", 0, "2026-10-01"), poll("b", 10, "2026-10-15")]   # 14 days apart
    avg = race_average(ps, date(2026, 10, 15), P, {})
    assert avg.mu == pytest.approx(10 * 1 / 1.5)                      # weights 1 and 0.5


def test_repeat_pollster_down_weighted():
    ps = [poll("a", 0, "2026-10-15"), poll("a", 0, "2026-10-15"), poll("b", 9, "2026-10-15")]
    avg = race_average(ps, date(2026, 10, 15), P, {})
    assert avg.mu == pytest.approx(9 / 2.5)                            # a: 1 + 1/2, b: 1


def test_population_and_quality_weights():
    ps = [poll("a", 0, "2026-10-15", pop="RV"), poll("b", 10, "2026-10-15", pop="LV")]
    pp = {"b": {"weight": 2.0, "shrunk_bias": 0.0}}
    avg = race_average(ps, date(2026, 10, 15), P, pp)
    assert avg.mu == pytest.approx(10 * 2 / (0.7 + 2))


def test_bias_correction_only_for_d_vs_r():
    pp = {"a": {"weight": 1.0, "shrunk_bias": 3.0}}
    dr = race_average([poll("a", 5, "2026-10-15")], date(2026, 10, 15), P, pp)
    same = race_average([poll("a", 5, "2026-10-15", matchup="same-party")], date(2026, 10, 15), P, pp)
    assert dr.mu == pytest.approx(2) and same.mu == pytest.approx(5)
    off = race_average([poll("a", 5, "2026-10-15")], date(2026, 10, 15),
                       {**P, "use_bias_correction": False}, pp)
    assert off.mu == pytest.approx(5)


def test_effective_number_of_polls():
    ps = [poll(c, 0, "2026-10-15") for c in "abcd"]
    assert race_average(ps, date(2026, 10, 15), P, {}).n_eff == pytest.approx(4)


def test_blend_with_prior():
    assert blend(4.0, 3.0, -8.0, 1.0) == (pytest.approx(1.0), 4.0)
    assert blend(4.0, 3.0, None, 1.0) == (4.0, 3.0)
    assert blend(4.0, 3.0, -8.0, 0.0) == (4.0, 3.0)


def test_lean_prior():
    results = {"2024-PRES-PA": {"margin_actual": "-1.7"}, "2024-PRES-US": {"margin_actual": "-1.5"}}
    assert last_pres_cycle(2026) == 2024 and last_pres_cycle(2024) == 2020
    assert lean_prior("PA", 2026, results, 8.5) == pytest.approx(-1.7 + 1.5 + 8.5)
    assert lean_prior("PA", 2026, {"2024-PRES-PA": {"margin_actual": "-1.7"}}, 8.5, -1.5) == pytest.approx(8.3)
    assert lean_prior("PA", 2026, results, None) == pytest.approx(-1.7)
    assert lean_prior("ZZ", 2026, results, 8.5) is None


def test_sd_and_probability():
    sig = {"a": 3.0, "b": 4.0, "c": 0.0}
    assert total_sd(1, 0, sig) == pytest.approx(5.0)
    assert total_sd(4, 0, sig) < total_sd(1, 0, sig)
    assert win_prob(0, 5) == pytest.approx(0.5)
    assert win_prob(5, 5) == pytest.approx(0.8413, abs=1e-4)
    assert split_sd(5.0, 3.0) == pytest.approx(4.0)


def _race(rid, mu, a="DEM", b="REP"):
    return RaceForecast(rid, "XX", "A", a, "B", b, "D-R", mu, 3.0, 2.0, win_prob(mu, 3), 1, 1, "", "polls")


def test_simulation_counts_seats_and_control():
    races = [_race("r1", 50), _race("r2", 50), _race("r3", -50)]
    cfg = {"not_up": {"dem": 48, "rep": 49}, "dem_needs": 51}
    s = simulate_senate(races, cfg, national_sd=1.0, n_sims=500)
    assert s["dem_seats_median"] == 50 and s["p_rep_control"] == 1.0      # 50-50, VP R


def test_simulation_vp_tiebreak_for_democrats():
    races = [_race("r1", 50), _race("r2", 50), _race("r3", -50)]
    s = simulate_senate(races, {"not_up": {"dem": 48, "rep": 49}, "dem_needs": 50}, 1.0, 500)
    assert s["p_dem_control"] == 1.0


def test_uncommitted_independent_can_decide():
    races = [_race("2026-SEN-NE", 50, a="IND"), _race("r2", 50), _race("r3", -50)]
    cfg = {"not_up": {"dem": 49, "rep": 49}, "dem_needs": 51, "uncommitted": ["2026-SEN-NE"]}
    s = simulate_senate(races, cfg, 1.0, 500)      # D 50, R 50, I 1 -> R 50 with VP
    assert s["p_rep_control"] == 1.0
    cfg["not_up"] = {"dem": 49, "rep": 48}           # D 50, R 49, I 1 -> nobody without Osborn
    s = simulate_senate(races, cfg, 1.0, 500)
    assert s["p_uncommitted_decides"] == 1.0
