import json

from pipeline import house_relay as h


def test_minnesota_skips_write_ins(monkeypatch):
    rows = ("MN;;;0104;U.S. Representative District 1;1;0401;Jake Johnson;;;DFL;73;750;8365;40.50;20654\n"
            "MN;;;0104;U.S. Representative District 1;1;0302;Brad Finstad;;;R;73;750;12248;59.30;20654\n"
            "MN;;;0104;U.S. Representative District 1;1;9901;WRITE-IN;;;WI;73;750;41;0.20;20654\n")
    monkeypatch.setattr(h, "get", lambda u, timeout=40: rows.encode())
    r = h.minnesota()["2026-HOUSE-MN-1"]
    assert [c["party"] for c in r["candidates"]] == ["REP", "DEM"] and r["total"] == 20613
    assert abs(r["reporting"] - 9.7) < 0.1


def test_north_carolina(monkeypatch):
    rows = [{"cnm": "US HOUSE OF REPRESENTATIVES DISTRICT 01 (VOTE FOR 1)", "bnm": "Don Davis", "pty": "DEM",
             "vct": "144084", "prt": "263", "ptl": "290"},
            {"cnm": "US HOUSE OF REPRESENTATIVES DISTRICT 01 (VOTE FOR 1)", "bnm": "Laurie Buckhout", "pty": "REP",
             "vct": "138289", "prt": "263", "ptl": "290"},
            {"cnm": "US SENATE (VOTE FOR 1)", "bnm": "Roy Cooper", "pty": "DEM", "vct": "1", "prt": "1", "ptl": "1"}]
    monkeypatch.setattr(h, "get", lambda u, timeout=40: json.dumps(rows).encode())
    out = h.north_carolina()
    assert list(out) == ["2026-HOUSE-NC-1"] and out["2026-HOUSE-NC-1"]["candidates"][0]["name"] == "Don Davis"


def test_enhanced_voting_virginia(monkeypatch):
    d = {"ballotItems": [{"name": [{"languageId": "en", "text": "Member, House of Representatives (2nd District)"}],
                          "summaryResults": {"ballotOptions": [
                              {"name": [{"languageId": "en", "text": "Jen Kiggans"}], "party": {"abbreviation": "R"}, "voteCount": 10},
                              {"name": [{"languageId": "en", "text": "Elaine Luria"}], "party": {"abbreviation": "D"}, "voteCount": 12},
                              {"name": [{"languageId": "en", "text": "Write-In"}], "voteCount": 1, "isWriteIn": True}]}}]}
    monkeypatch.setattr(h, "get", lambda u, timeout=40: json.dumps(d).encode())
    r = h.virginia()["2026-HOUSE-VA-2"]
    assert r["candidates"][0] == {"name": "Elaine Luria", "party": "DEM", "votes": 12} and r["reporting"] is None


def test_failing_source_does_not_stop_others(monkeypatch):
    monkeypatch.setattr(h, "SOURCES", {"XX": ("x", "u", lambda: 1 / 0),
                                       "YY": ("y", "u", lambda: {"2026-HOUSE-YY-1": h.finish({"a": {"name": "a", "party": "DEM", "votes": 5}}, None, "y")})})
    out = h.run()
    assert out["sources"]["XX"]["ok"] is False and "2026-HOUSE-YY-1" in out["races"]
