"""Phase 3 tests: Wikipedia table parsing on small inputs and frozen real pages."""
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from pipeline.parse_tables import (
    _span, candidate_column, grid, parse_end_date, parse_page, parse_pct, parse_sample,
    read_result, split_pollster,
)

FIX = Path(__file__).parent / "fixtures"
ELECTION_2024 = date(2024, 11, 5)


@pytest.mark.parametrize("text,expected", [
    ("November 3–4, 2024", date(2024, 11, 4)),
    ("March 27 – April 7, 2023", date(2023, 4, 7)),
    ("Oct 28 – Nov 1, 2024", date(2024, 11, 1)),
    ("November 2, 2024", date(2024, 11, 2)),
    ("December 30, 2023 – January 2, 2024", date(2024, 1, 2)),
    ("Sept. 5–9, 2026", date(2026, 9, 9)),
    ("no date here", None),
])
def test_parse_end_date(text, expected):
    assert parse_end_date(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("1,840 (LV)", (1840, "LV")), ("800 (RV)", (800, "RV")), ("– (LV)", (None, "LV")),
    ("1,000 (A)", (1000, "A")), ("600 (V)", (600, "RV")), ("", (None, "")),
])
def test_parse_sample(text, expected):
    assert parse_sample(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("49%", 49.0), ("47.5%", 47.5), ("–", None), ("<1%", 1.0), ("4%[b]", 4.0), ("", None),
])
def test_parse_pct(text, expected):
    assert parse_pct(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("The Trafalgar Group (R)", ("The Trafalgar Group", "R")),
    ("Emerson College", ("Emerson College", "")),
    ("Fabrizio Ward (R)/ Impact Research (D)", ("Fabrizio Ward / Impact Research", "R,D")),
    ("CNN /SSRS", ("CNN / SSRS", "")),
])
def test_split_pollster(text, expected):
    assert split_pollster(text) == expected


def test_candidate_column():
    assert candidate_column("Bob Casey Jr. (D)") == ("Bob Casey Jr.", "DEM")
    assert candidate_column("Dan Osborn (I)") == ("Dan Osborn", "IND")
    assert candidate_column("Amy Klobuchar (DFL)") == ("Amy Klobuchar", "DEM")
    assert candidate_column("Undecided") is None
    assert candidate_column("Generic Democrat") is None


def test_span_is_lenient():
    assert (_span("2;"), _span(" 3"), _span(None), _span("x")) == (2, 3, 1, 1)


def test_grid_expands_rowspan_and_colspan():
    html = """<table><tr><th>Poll source</th><th>Date</th><th colspan="2">Cands</th></tr>
      <tr><td rowspan="2">Firm</td><td>Oct 1, 2024</td><td>40%</td><td>45%</td></tr>
      <tr><td>Oct 2, 2024</td><td>41%</td><td>44%</td></tr></table>"""
    header, rows = grid(BeautifulSoup(html, "lxml").table)
    assert header == ["Poll source", "Date", "Cands", "Cands"]
    assert rows == [["Firm", "Oct 1, 2024", "40%", "45%"], ["Firm", "Oct 2, 2024", "41%", "44%"]]


def test_fusion_voting_results_use_total_line():
    html = """<table><tr><th>Party</th><th>Party</th><th>Candidate</th><th>Votes</th><th>%</th></tr>
      <tr><td></td><td>Democratic</td><td>Josh Riley</td><td>170,049</td><td>45.1</td></tr>
      <tr><td></td><td>Working Families</td><td>Josh Riley</td><td>22,598</td><td>6.0</td></tr>
      <tr><td></td><td>Total</td><td>Josh Riley</td><td>192,647</td><td>51.1</td></tr>
      <tr><td></td><td>Republican</td><td>Marc Molinaro</td><td>164,001</td><td>43.5</td></tr>
      <tr><td></td><td>Conservative</td><td>Marc Molinaro</td><td>20,289</td><td>5.4</td></tr>
      <tr><td></td><td>Total</td><td>Marc Molinaro (incumbent)</td><td>184,290</td><td>48.9</td></tr>
      <tr><td>Total votes</td><td>Total votes</td><td>Total votes</td><td>376,937</td><td>100.0</td></tr>
      </table>"""
    res = read_result(BeautifulSoup(html, "lxml").table)
    assert res == [("Josh Riley", "DEM", 51.1), ("Marc Molinaro", "REP", 48.9)]


# ---- frozen real pages ------------------------------------------------------

def test_pennsylvania_senate_2024_page():
    polls, results, _ = parse_page(FIX / "wiki_2024_sen_pa.html", 2024, ELECTION_2024)
    pa = [p for p in polls if p["race_id"] == "2024-SEN-PA"]
    assert len(pa) == 136
    first = pa[0]
    assert (first["pollster_raw"], first["end_date"], first["side_a_pct"], first["side_b_pct"],
            first["sample_size"], first["population"]) == ("AtlasIntel", "2024-11-04", 49.0, 47.0, 1840, "LV")
    assert first["side_a_name"] == "Bob Casey Jr." and first["side_b_name"] == "Dave McCormick"
    trafalgar = next(p for p in pa if p["pollster_raw"] == "The Trafalgar Group")
    assert trafalgar["partisan"] == "R" and trafalgar["margin_poll"] == -1.0
    assert all("Mastriano" not in p["side_b_name"] for p in pa)  # hypothetical table skipped
    (res,) = [r for r in results if r["race_id"] == "2024-SEN-PA"]
    assert (res["side_a_actual"], res["side_b_actual"]) == (48.56, 48.78)


def test_washington_house_2024_skips_top_two_primary():
    polls, results, _ = parse_page(FIX / "wiki_2024_house_wa.html", 2024, ELECTION_2024)
    wa3 = [p for p in polls if p["race_id"] == "2024-HOUSE-WA-3"]
    assert [(p["pollster_raw"], p["end_date"], p["margin_poll"]) for p in wa3] == [
        ("Public Policy Polling", "2024-10-02", -1.0), ("Cygnal", "2024-06-22", 0.0),
        ("Public Policy Polling", "2024-06-12", -1.0)]
    (res,) = [r for r in results if r["race_id"] == "2024-HOUSE-WA-3"]
    assert (res["side_a_name"], res["side_a_actual"], res["side_b_actual"]) == (
        "Marie Gluesenkamp Perez", 51.7, 47.9)  # general, not the 45.9 / 39.3 primary
    assert len({r["race_id"] for r in results}) == 10


def test_no_results_before_election_day():
    polls, results, _ = parse_page(FIX / "wiki_2024_sen_pa.html", 2024, date(2999, 1, 1))
    assert results == [] and polls
