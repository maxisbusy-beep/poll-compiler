"""Parse Wikipedia snapshots into data/polls/<cycle>.csv and data/results/<cycle>.csv.

Usage: python -m pipeline.load_wikipedia --cycle 2024 --cycle 2026
Rows from other sources (538) in the same files are kept.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.normalize import (
    POLL_COLUMNS, RESULT_COLUMNS, PollsterAliases, write_merged,
)
from pipeline.parse_tables import parse_cycle

ROOT = Path(__file__).resolve().parent.parent


def load(cycle: int, aliases: PollsterAliases) -> dict:
    polls, results, notes = parse_cycle(cycle)
    ids = aliases.resolve_all([p["pollster_raw"] for p in polls])
    for p in polls:
        p["pollster_id"] = ids[p["pollster_raw"]]
    write_merged(ROOT / "data" / "polls" / f"{cycle}.csv", POLL_COLUMNS, polls, "wikipedia",
                 lambda r: (r["race_id"], r["poll_date"], r["pollster_id"], r["source_ref"]))
    if results:
        write_merged(ROOT / "data" / "results" / f"{cycle}.csv", RESULT_COLUMNS, results,
                     "wikipedia", lambda r: (r["race_id"],))
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"parse_notes_{cycle}.txt").write_text("\n".join(notes) + "\n")
    return {"polls": len(polls), "races_polled": len({p["race_id"] for p in polls}),
            "results": len(results)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", type=int, action="append", required=True)
    a = ap.parse_args(argv)
    aliases = PollsterAliases()
    for c in a.cycle:
        print(c, load(c, aliases))


if __name__ == "__main__":
    main()
