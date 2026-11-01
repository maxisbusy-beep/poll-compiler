"""Match Silver Bulletin pollster grades to our pollster ids (display only, not used in weights).

Input:  data/reference/silver_bulletin_pollster_stats_2026.xlsx  (Silver Bulletin, Jan 2026 update)
Output: data/reference/silver_grades.csv  (pollster_id, sb_name, sb_id, sb_grade, sb_polls, banned, match)

Matching: Silver Bulletin's "Pollster Rating ID" continues FiveThirtyEight's ids,
so we match on the 538 id stored in config/pollster_aliases.yaml first, then on
the pollster name. Unmatched Silver Bulletin pollsters are listed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.normalize import PollsterAliases  # noqa: E402

# Silver Bulletin names that differ from ours (checked by hand)
MANUAL = {
    "Miami Univerity": "miami-university",
    "Trafalgar Group/Insider Advantage": "trafalgar-insideradvantage",
    "Fabrizio, Lee & Associates/GBAO": "wall-street-journal",   # WSJ polls are fielded by this pair
    "Truedot": "university-of-arizona-truedot",
}

SRC = ROOT / "data" / "reference" / "silver_bulletin_pollster_stats_2026.xlsx"
OUT = ROOT / "data" / "reference" / "silver_grades.csv"


def main() -> None:
    ws = openpyxl.load_workbook(SRC, read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(h or "").strip() for h in rows[0]]
    col = {name: head.index(name) for name in ("Pollster Rating ID", "# of Polls", "SB Grade",
                                               "Banned by Silver Bulletin")}
    name_col = 1   # the first column is the rank; the name sits under the merged "Pollster" header

    aliases = PollsterAliases()
    by_538 = {}
    for pid, info in aliases.pollsters.items():
        for i in [info.get("fivethirtyeight_id"), *info.get("merged_fivethirtyeight_ids", [])]:
            if i is not None:
                by_538[int(i)] = pid

    out, unmatched = {}, []
    for r in rows[1:]:
        if not r or r[name_col] is None or r[col["SB Grade"]] is None:
            continue
        sb_id = int(r[col["Pollster Rating ID"]])
        name = str(r[name_col]).strip()
        pid, how = by_538.get(sb_id), "id"
        if pid is None:
            pid, how = MANUAL.get(name) or aliases.get(name), "name"
        if pid is None:
            unmatched.append(f"{name} (id {sb_id}, {r[col['SB Grade']]})")
            continue
        if pid in out and out[pid]["match"] == "id":
            continue   # keep the id match if a name also points here
        rec = {"pollster_id": pid, "sb_name": name, "sb_id": sb_id,
               "sb_grade": str(r[col["SB Grade"]]).strip(), "sb_polls": int(r[col["# of Polls"]] or 0),
               "banned": str(r[col["Banned by Silver Bulletin"]]).strip().lower() == "yes", "match": how}
        out[pid] = rec
        # one of our separate entries may carry the same name (e.g. a Wikipedia spelling)
        same = aliases.get(name)
        if same and same != pid and same not in out:
            out[same] = {**rec, "pollster_id": same, "match": "name"}

    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pollster_id", "sb_name", "sb_id", "sb_grade", "sb_polls",
                                          "banned", "match"], lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(out.values(), key=lambda x: x["pollster_id"]))
    print(f"matched {len(out)}; unmatched {len(unmatched)}")
    for u in unmatched:
        print("  ", u)


if __name__ == "__main__":
    main()
