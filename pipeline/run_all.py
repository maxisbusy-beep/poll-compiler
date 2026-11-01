"""Pipeline entry point. Writes a status file so the site has data to read.

Later phases replace this with fetch -> parse -> score -> model (SPEC.md section 2).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SITE_DATA = Path(__file__).resolve().parent.parent / "site" / "data"


def build_status(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {
        "phase": 5,
        "updated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": "Senate and House forecasts live.",
    }


def main() -> None:
    from pipeline import score_pollsters

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    print("pollster scoring:", score_pollsters.main())
    from pipeline import forecast
    print("forecast:", forecast.main())
    from pipeline import live_sources
    print("election-night table:", live_sources.main())
    (SITE_DATA / "status.json").write_text(json.dumps(build_status(), indent=2) + "\n")


if __name__ == "__main__":
    main()
