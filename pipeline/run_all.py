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
        "phase": 4,
        "updated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": "Senate forecast live (polls + partisan lean, backtested 2004-2024). House forecast comes in Phase 5.",
    }


def main() -> None:
    from pipeline import score_pollsters

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    print("pollster scoring:", score_pollsters.main())
    from pipeline import forecast
    print("forecast:", forecast.main())
    (SITE_DATA / "status.json").write_text(json.dumps(build_status(), indent=2) + "\n")


if __name__ == "__main__":
    main()
