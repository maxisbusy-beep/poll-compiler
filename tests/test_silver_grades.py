"""Silver Bulletin grades are matched for display and never touch the weights."""
import csv
from pathlib import Path

from pipeline.model import DEFAULT_PARAMS

ROOT = Path(__file__).resolve().parent.parent


def grades():
    return {r["pollster_id"]: r for r in csv.DictReader((ROOT / "data/reference/silver_grades.csv").open())}


def test_known_pollsters_matched():
    g = grades()
    assert g["the-new-york-times-siena-college"]["sb_grade"] == "A"
    assert g["emerson-college"]["sb_grade"] == "A"
    assert g["trafalgar-group"]["sb_grade"] == "B"
    assert len(g) > 500


def test_grades_not_used_by_model():
    src = (ROOT / "pipeline" / "model.py").read_text() + (ROOT / "pipeline" / "score_pollsters.py").read_text()
    assert "sb_grade" not in src and "silver" not in src.lower()
    assert "sb_grade" not in DEFAULT_PARAMS
