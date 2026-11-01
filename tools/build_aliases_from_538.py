"""One-time: seed config/pollster_aliases.yaml from the 538 snapshot.

One entry per 538 pollster_rating_id (538's own grouping is kept; joint
polls by two firms stay a separate entry, as 538 rated them). Re-running
keeps any aliases already added by hand and only adds new pollsters.
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SNAPSHOT = ROOT / "data" / "history" / "538_raw_polls.csv"
OUT = ROOT / "config" / "pollster_aliases.yaml"

HEADER = """# Pollster identity table (SPEC.md 3.3).
# Every raw pollster name seen in any source must resolve to one id here,
# or the pipeline fails and lists the unmapped names.
# To add a spelling, append it to that pollster's `aliases`.
# Seeded from the 538 snapshot by tools/build_aliases_from_538.py.
"""


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "pollster"


def main() -> None:
    existing = {}
    if OUT.exists():
        existing = (yaml.safe_load(OUT.read_text()) or {}).get("pollsters", {})
    by_538 = {str(v.get("fivethirtyeight_id")): k for k, v in existing.items()}

    names = {}
    for r in csv.DictReader(SNAPSHOT.open()):
        names.setdefault(r["pollster_rating_id"], r["pollster"])

    pollsters = dict(existing)
    used = set(pollsters)
    for rid, name in sorted(names.items(), key=lambda kv: kv[1].lower()):
        if rid in by_538:
            continue
        slug = slugify(name)
        if slug in used:
            slug = f"{slug}-{rid}"
        used.add(slug)
        pollsters[slug] = {"name": name, "fivethirtyeight_id": int(rid), "aliases": []}

    pollsters = dict(sorted(pollsters.items()))
    OUT.write_text(HEADER + yaml.safe_dump({"pollsters": pollsters}, sort_keys=False,
                                           allow_unicode=True, width=120))
    print(f"{len(pollsters)} pollsters -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
