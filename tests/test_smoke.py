from datetime import datetime, timezone
from pathlib import Path

from pipeline.run_all import build_status

ROOT = Path(__file__).resolve().parent.parent


def test_status_shape():
    s = build_status(datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc))
    assert s["phase"] == 5
    assert s["updated_utc"] == "2026-11-01T12:00:00Z"


def test_site_entry_exists():
    html = (ROOT / "site" / "index.html").read_text()
    assert "<title>Maximum Likelihood</title>" in html and "face.webp" in html


def test_spec_present():
    assert (ROOT / "SPEC.md").exists()
