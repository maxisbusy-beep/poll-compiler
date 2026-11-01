"""National generic-ballot environment from the published averages table on Wikipedia.

Wikipedia no longer lists individual generic-ballot polls, only a table of the
big public averages (owner decision 2026-11-01: use the average of those
averages). Returns Dem minus Rep, in points.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from pipeline.parse_tables import clean, grid, walk

ROOT = Path(__file__).resolve().parent.parent


def parse_margin(text: str) -> float | None:
    t = clean(text)
    m = re.search(r"(Democrats?|Republicans?|D|R)\s*\+\s*(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    v = float(m.group(2))
    return v if m.group(1).startswith("D") else -v


def generic_ballot(cycle: int) -> dict | None:
    path = ROOT / "data" / "raw" / str(cycle) / f"{cycle}_United_States_House_of_Representatives_elections.html"
    if not path.exists():
        return None
    soup = BeautifulSoup(path.read_text(), "lxml")
    for b in walk(soup):
        heads = " ".join(b.headings.values()).lower()
        if "generic" not in heads:
            continue
        header, rows = grid(b.table)
        if not header or "aggregation" not in header[0].lower():
            continue
        mcol = next((i for i, h in enumerate(header) if h.lower().startswith("margin")), None)
        if mcol is None:
            continue
        sources = []
        for r in rows:
            name = clean(r[0])
            m = parse_margin(r[mcol])
            if m is None or name.lower().startswith("average"):
                continue
            sources.append({"source": name, "margin": m, "updated": clean(r[2]) if len(r) > 2 else ""})
        if sources:
            return {"margin": round(sum(s["margin"] for s in sources) / len(sources), 2),
                    "sources": sources}
    return None


if __name__ == "__main__":
    print(generic_ballot(2026))
