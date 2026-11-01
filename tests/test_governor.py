from pipeline.forecast import governor_race_ids, simulate_governors
from pipeline.model import RaceForecast


def test_36_governor_races_2026():
    ids = governor_race_ids(2026)
    assert len(ids) == 36
    assert "2026-GOV-GU" not in " ".join(ids)          # territories aren't states


def _race(rid, a_party, mu):
    return RaceForecast(rid, rid[-2:], "A", a_party, "B", "REP", "X-R", mu, 1.0, 0.5, 0.5, 0, 0.0, "", "lean")


def test_independent_governor_counts_for_neither():
    races = [_race("2026-GOV-AA", "IND", 50.0)]
    sim = simulate_governors(races, {"not_up": {"dem": 25, "rep": 24}, "majority": 26}, 0.1, n_sims=200)
    assert sim["p_dem_control"] == 0 and sim["p_rep_control"] == 0 and sim["p_neither"] == 1


def test_democrat_win_reaches_majority():
    races = [_race("2026-GOV-AA", "DEM", 50.0)]
    sim = simulate_governors(races, {"not_up": {"dem": 25, "rep": 24}, "majority": 26}, 0.1, n_sims=200)
    assert sim["p_dem_control"] == 1
