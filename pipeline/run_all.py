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
        "phase": 1,
        "updated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": "Historical data loaded (538, 1998-2022). No forecast yet.",
    }


def main() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "status.json").write_text(json.dumps(build_status(), indent=2) + "\n")


if __name__ == "__main__":
    main()
