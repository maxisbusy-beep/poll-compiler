"""Coverage report for the historical data (Phase 1 gate).

Writes reports/history_coverage.md from data/polls and data/results.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = ["SEN", "HOUSE", "HOUSE-GEN", "GOV", "PRES"]


def load(folder: str) -> list[dict]:
    rows = []
    for f in sorted((ROOT / "data" / folder).glob("*.csv")):
        rows += list(csv.DictReader(f.open()))
    return rows


def build() -> str:
    polls, results = load("polls"), load("results")
    by = defaultdict(lambda: {"polls": Counter(), "final": Counter(), "races": Counter(),
                              "pollsters": set()})
    for p in polls:
        c = by[p["cycle"]]
        c["polls"][p["race_type"]] += 1
        c["pollsters"].add(p["pollster_id"])
        if int(p["days_to_election"]) <= 21:
            c["final"][p["race_type"]] += 1
    for r in results:
        by[r["cycle"]]["races"][r["race_type"]] += 1

    out = ["# Historical data coverage", "",
           f"- Polls: **{len(polls):,}** · Races with a result: **{len(results):,}** · "
           f"Pollsters: **{len({p['pollster_id'] for p in polls})}**",
           f"- Cycles: {min(by)}–{max(by)}",
           "- Polls within 21 days of the election are the ones eligible for pollster scoring.", "",
           "## Polls (within 21 days) / races, by cycle", "",
           "| Cycle | Type | Senate | House districts | Generic ballot | Governor | President | Pollsters |",
           "|---|---|---|---|---|---|---|---|"]
    ctype = {p["cycle"]: p["cycle_type"] for p in polls}
    for cyc in sorted(by):
        c = by[cyc]
        cells = []
        for t in TYPES:
            if c["polls"][t]:
                cells.append(f"{c['polls'][t]} ({c['final'][t]}) / {c['races'][t]}")
            else:
                cells.append("—")
        out.append(f"| {cyc} | {ctype[cyc]} | " + " | ".join(cells) + f" | {len(c['pollsters'])} |")
    out += ["", "Cell format: all polls (polls within 21 days) / races.", "",
            "## Matchups", ""]
    m = Counter(r["matchup"] for r in results)
    out += [f"- {k}: {v} races" for k, v in m.most_common()]
    out += ["", "## Largest pollsters by polls within 21 days", "",
            "| Pollster | Polls ≤21d | Cycles |", "|---|---|---|"]
    cnt, cyc = Counter(), defaultdict(set)
    for p in polls:
        if int(p["days_to_election"]) <= 21:
            cnt[p["pollster_id"]] += 1
            cyc[p["pollster_id"]].add(p["cycle"])
    for pid, n in cnt.most_common(15):
        out.append(f"| {pid} | {n} | {min(cyc[pid])}–{max(cyc[pid])} ({len(cyc[pid])}) |")
    return "\n".join(out) + "\n"


def main() -> None:
    path = ROOT / "reports" / "history_coverage.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(build())
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
