"""Phase 1 tests: race ids, side assignment, alias resolution and the 538 loader."""
import csv
from pathlib import Path

import pytest

from pipeline.load_538_history import convert, parse_race
from pipeline.normalize import (
    PollsterAliases, UnmappedPollsterError, assign_sides, cycle_type, make_race_id,
)

FIX = Path(__file__).parent / "fixtures"


# ---- race ids -------------------------------------------------------------

@pytest.mark.parametrize("args,expected", [
    ((2026, "SEN", "TX"), "2026-SEN-TX"),
    ((2026, "SEN", "OH", "", "S"), "2026-SEN-OH-S"),
    ((2018, "SEN", "MS", "", "SR"), "2018-SEN-MS-SR"),
    ((2026, "HOUSE", "TX", "23"), "2026-HOUSE-TX-23"),
    ((2026, "HOUSE-GEN", "US"), "2026-HOUSE-GEN"),
    ((2024, "PRES", "US"), "2024-PRES-US"),
])
def test_make_race_id(args, expected):
    assert make_race_id(*args) == expected


def test_make_race_id_rejects_unknown():
    with pytest.raises(ValueError):
        make_race_id(2026, "MAYOR", "NY")
    with pytest.raises(ValueError):
        make_race_id(2026, "SEN", "NY", "", "X")


@pytest.mark.parametrize("year,kind", [
    (2022, "midterm"), (2026, "midterm"), (2024, "presidential"), (2028, "presidential"),
    (2017, "off-year"),
])
def test_cycle_type(year, kind):
    assert cycle_type(year) == kind


@pytest.mark.parametrize("race,ts,loc,expected", [
    ("2022_Sen-G_GA", "Sen-G", "GA", ("SEN", "GA", "", "")),
    ("2018_House-GS_NY-25", "House-G", "NY-25", ("HOUSE", "NY", "25", "S")),
    ("2012_House-G_US", "House-G-US", "US", ("HOUSE-GEN", "US", "", "")),
    ("2014_Sen-P_LA", "Sen-P", "LA", None),
    ("2000_Pres-D-P_IA", "Pres-P", "IA", None),
])
def test_parse_race(race, ts, loc, expected):
    assert parse_race(race, ts, loc) == expected


# ---- sides ----------------------------------------------------------------

def test_sides_dem_rep_keeps_order():
    s = assign_sides(("D", "DEM", 50), ("R", "REP", 45))
    assert (s.a_name, s.b_name, s.matchup, s.swapped) == ("D", "R", "D-R", False)


def test_sides_rep_first_is_swapped():
    s = assign_sides(("R", "REP", 45), ("D", "DEM", 50))
    assert (s.a_name, s.a_val, s.matchup, s.swapped) == ("D", 50, "D-R", True)


def test_sides_independent_vs_rep():
    s = assign_sides(("Roberts", "REP", 36), ("Orman", "IND", 37))
    assert (s.a_name, s.b_name, s.matchup) == ("Orman", "Roberts", "X-R")


def test_sides_same_party():
    s = assign_sides(("Harris", "DEM", 44), ("Sanchez", "DEM", 27))
    assert (s.a_name, s.matchup) == ("Harris", "same-party")


# ---- aliases --------------------------------------------------------------

def _aliases(tmp_path, body):
    p = tmp_path / "a.yaml"
    p.write_text(body)
    return PollsterAliases(p)


def test_alias_matching_ignores_case_and_spacing(tmp_path):
    a = _aliases(tmp_path, "pollsters:\n  emerson:\n    name: Emerson College\n"
                           "    aliases: [Emerson Polling]\n")
    assert a.get("emerson  college") == "emerson"
    assert a.get("EMERSON POLLING") == "emerson"
    assert a.get("Emerson") is None


def test_unmapped_names_fail_loudly_and_list_all(tmp_path):
    a = _aliases(tmp_path, "pollsters:\n  x:\n    name: X\n")
    with pytest.raises(UnmappedPollsterError) as e:
        a.resolve_all(["X", "Mystery Poll", "Another One", "Mystery Poll"])
    assert e.value.names == ["Another One", "Mystery Poll"]


def test_conflicting_alias_rejected(tmp_path):
    with pytest.raises(ValueError):
        _aliases(tmp_path, "pollsters:\n  a:\n    name: Same\n  b:\n    name: same\n")


def test_real_alias_table_loads():
    a = PollsterAliases()
    assert a.get("Siena College") is not None
    assert a.get("The New York Times/Siena College") is not None


# ---- 538 loader on fixture -------------------------------------------------

@pytest.fixture
def converted():
    rows = list(csv.DictReader((FIX / "538_sample.csv").open()))
    return convert(rows, PollsterAliases())


def test_primaries_dropped(converted):
    polls, results = converted
    assert len(polls) == 7
    assert all(p["race_type"] != "" for p in polls)
    assert not any("LA" == p["state"] and p["cycle"] == 2014 for p in polls)


def test_dem_rep_poll(converted):
    polls, results = converted
    ga = next(p for p in polls if p["race_id"] == "2022-SEN-GA")
    assert ga["margin_poll"] == 4.0 and ga["matchup"] == "D-R"
    assert ga["cycle_type"] == "midterm"
    assert results["2022-SEN-GA"]["margin_actual"] == pytest.approx(0.957, abs=0.001)


def test_swap_applies_to_poll_and_result(converted):
    polls, results = converted
    ks = next(p for p in polls if p["race_id"] == "2014-SEN-KS")
    assert (ks["side_a_party"], ks["side_b_party"], ks["margin_poll"]) == ("IND", "REP", 1.0)
    # Roberts (R) won by about 10.6, so the non-Rep side's actual margin is negative
    assert results["2014-SEN-KS"]["margin_actual"] == pytest.approx(-10.619, abs=0.001)


def test_special_runoff_house_and_generic_ids(converted):
    _, results = converted
    assert {"2014-SEN-HI-S", "2018-SEN-MS-SR", "2018-HOUSE-AK-1", "2012-HOUSE-GEN",
            "2016-SEN-CA"} <= set(results)
    assert results["2016-SEN-CA"]["matchup"] == "same-party"


def test_every_poll_has_a_result(converted):
    polls, results = converted
    assert {p["race_id"] for p in polls} == set(results)


# ---- full snapshot regression ---------------------------------------------

def test_full_snapshot_matches_committed_outputs():
    """The committed data/polls and data/results must be what the loader produces."""
    from pipeline.load_538_history import SNAPSHOT, POLLS_DIR, RESULTS_DIR
    polls, results = convert(list(csv.DictReader(SNAPSHOT.open())), PollsterAliases())
    committed_polls = sum(1 for f in POLLS_DIR.glob("*.csv")
                          for r in csv.DictReader(f.open()) if r["source"] == "538")
    committed_results = sum(1 for f in RESULTS_DIR.glob("*.csv")
                            for r in csv.DictReader(f.open()) if r["source"] == "538")
    assert (len(polls), len(results)) == (committed_polls, committed_results) == (18250, 2180)
