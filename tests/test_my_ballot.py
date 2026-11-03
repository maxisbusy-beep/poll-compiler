from datetime import date

import yaml

from pipeline import my_ballot


def test_ballot_builds_with_cabinet_odds():
    cfg = yaml.safe_load(my_ballot.CONFIG.read_text())
    d = my_ballot.build(cfg, as_of=date(2026, 11, 3))
    races = {r["id"]: r for s in d["sections"] for r in s["races"]}
    for rid in ("2026-AG-FL", "2026-CFO-FL", "2026-AGRI-FL"):
        o = races[rid]["odds"]
        assert 0 < o["p_a"] < 1 and o["sd"] > 0 and o["n_polls"] >= 1
        assert d["live"][rid]["page"] == races[rid]["page"]
    assert "odds" not in races["HC-BOCC-3"] and races["HC-REF-1"]["kind"] == "measure"
    assert {"2026-SEN-FL-S", "2026-GOV-FL", "2026-HOUSE-FL-15"} <= set(races)


def test_poll_margins_are_dem_minus_rep():
    race = {"id": "X", "polls": [["p", "P", "2026-10-01", 800, 44, 49]]}
    assert my_ballot.poll_rows(race)[0]["margin_poll"] == -5.0
