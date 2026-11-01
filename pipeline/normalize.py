"""Shared poll schema, race ids and pollster alias resolution (SPEC.md section 3).

Sides
-----
Polls and results are stored as two sides rather than strictly Dem / Rep:

* ``side_a`` is the Democrat, or the main non-Republican when no Democrat is in
  the top two (e.g. an independent like Dan Osborn).
* ``side_b`` is the Republican.
* ``margin = side_a_pct - side_b_pct``, so positive means the Dem / non-Rep side leads.

``matchup`` says how much the sign means:

* ``D-R``        Democrat vs Republican. Bias direction is meaningful.
* ``X-R``        Non-Democrat (independent etc.) vs Republican. Bias is meaningful,
                 but flagged so the UI can label it.
* ``same-party`` Top two from one party (e.g. California top-two). Error is
                 meaningful, bias direction is not.
* ``other``      Neither side is a Republican (e.g. Puerto Rico parties).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ALIASES_PATH = ROOT / "config" / "pollster_aliases.yaml"

POLL_COLUMNS = [
    "cycle", "cycle_type", "election_date", "race_id", "race_type", "state",
    "district", "special", "pollster_id", "pollster_raw", "sponsor", "partisan",
    "methodology", "start_date", "end_date", "poll_date", "days_to_election",
    "sample_size", "population", "side_a_name", "side_a_party", "side_a_pct",
    "side_b_name", "side_b_party", "side_b_pct", "other_pct", "undecided_pct",
    "margin_poll", "matchup", "source", "source_ref",
]

RESULT_COLUMNS = [
    "cycle", "cycle_type", "election_date", "race_id", "race_type", "state",
    "district", "special", "side_a_name", "side_a_party", "side_a_actual",
    "side_b_name", "side_b_party", "side_b_actual", "margin_actual", "matchup",
    "source",
]

RACE_TYPES = {"SEN", "HOUSE", "HOUSE-GEN", "GOV", "PRES"}


def cycle_type(year: int) -> str:
    """presidential / midterm / off-year. Used for the 'same type' window."""
    if year % 2:
        return "off-year"
    return "presidential" if year % 4 == 0 else "midterm"


RACE_KINDS = {"", "S", "R", "SR"}  # regular, special, runoff, special runoff


def make_race_id(cycle: int, race_type: str, state: str = "", district: str = "",
                 kind: str = "") -> str:
    """2026-SEN-TX, 2026-SEN-OH-S, 2022-SEN-GA-R, 2026-HOUSE-TX-23, 2026-HOUSE-GEN, 2024-PRES-US."""
    if race_type not in RACE_TYPES:
        raise ValueError(f"unknown race type {race_type!r}")
    if kind not in RACE_KINDS:
        raise ValueError(f"unknown race kind {kind!r}")
    if race_type == "HOUSE-GEN":
        return f"{cycle}-HOUSE-GEN"
    parts = [str(cycle), race_type, state]
    if district:
        parts.append(district)
    rid = "-".join(parts)
    return f"{rid}-{kind}" if kind else rid


@dataclass
class Sides:
    a_name: str
    a_party: str
    a_val: float
    b_name: str
    b_party: str
    b_val: float
    matchup: str
    swapped: bool


def assign_sides(c1: tuple[str, str, float], c2: tuple[str, str, float]) -> Sides:
    """Order two (name, party, value) candidates into side_a / side_b.

    The same swap decision must be applied to a poll's numbers and to its
    race's actual result, so callers pass actual-result tuples through this
    function too (the decision depends only on the parties).
    """
    p1, p2 = c1[1], c2[1]
    if p1 == "DEM" and p2 == "REP":
        a, b, m, sw = c1, c2, "D-R", False
    elif p1 == "REP" and p2 == "DEM":
        a, b, m, sw = c2, c1, "D-R", True
    elif p2 == "REP" and p1 != "REP":
        a, b, m, sw = c1, c2, "X-R", False
    elif p1 == "REP" and p2 != "REP":
        a, b, m, sw = c2, c1, "X-R", True
    elif p1 == p2:
        a, b, m, sw = c1, c2, "same-party", False
    else:
        a, b, m, sw = c1, c2, "other", False
    return Sides(a[0], a[1], a[2], b[0], b[1], b[2], m, sw)


class UnmappedPollsterError(Exception):
    def __init__(self, names: list[str]):
        self.names = sorted(set(names))
        super().__init__(
            f"{len(self.names)} pollster name(s) not in config/pollster_aliases.yaml:\n  "
            + "\n  ".join(self.names)
        )


class PollsterAliases:
    """raw pollster name -> pollster_id. Unknown names fail loudly."""

    def __init__(self, path: Path = ALIASES_PATH):
        data = yaml.safe_load(path.read_text()) or {}
        self.pollsters: dict = data.get("pollsters", {})
        self._lookup: dict[str, str] = {}
        for pid, info in self.pollsters.items():
            for name in [info["name"], *info.get("aliases", [])]:
                key = self._key(name)
                if key in self._lookup and self._lookup[key] != pid:
                    raise ValueError(f"alias {name!r} maps to both {self._lookup[key]} and {pid}")
                self._lookup[key] = pid

    @staticmethod
    def _key(name: str) -> str:
        k = " ".join(name.lower().replace("\u2019", "'").split())
        return k.replace(" /", "/").replace("/ ", "/")

    def get(self, raw: str) -> str | None:
        return self._lookup.get(self._key(raw))

    def resolve_all(self, raws: list[str]) -> dict[str, str]:
        """Resolve every name, or raise one error listing all unmapped names."""
        out, missing = {}, []
        for r in set(raws):
            pid = self.get(r)
            if pid is None:
                missing.append(r)
            else:
                out[r] = pid
        if missing:
            raise UnmappedPollsterError(missing)
        return out


def write_merged(path: Path, columns: list[str], rows: list[dict], source: str,
                 sort_key) -> None:
    """Replace this source's rows in a per-cycle CSV, keeping other sources' rows."""
    import csv

    keep = []
    if path.exists():
        keep = [r for r in csv.DictReader(path.open()) if r.get("source") != source]
    allrows = keep + rows
    allrows.sort(key=lambda r: tuple(str(x) for x in sort_key(r)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(allrows)
