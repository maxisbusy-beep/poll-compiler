"""Parse saved Wikipedia snapshots into normalized polls and results (SPEC.md 3.1).

Input:  data/raw/<cycle>/*.html (from fetch_wikipedia), config/sources/<cycle>.yaml
Output: rows for data/polls/<cycle>.csv and data/results/<cycle>.csv (source=wikipedia)

Rules
-----
* Only general-election sections: any heading mentioning primary, convention,
  caucus or runoff is skipped.
* Poll tables are the ones whose header starts with "Poll source". Tables of
  published averages ("Source of poll aggregation") are ignored.
* A race page often has several poll tables (the real matchup plus
  hypotheticals). We keep ONE: the table whose candidates appear in the page's
  infobox, then the one with the most recent poll, then the most rows.
* One row per poll: when a poll is listed in several versions, keep LV over RV
  over A, then the first listed.
* A pollster written as "Name (R)" or "(D)" is flagged partisan and the marker
  is removed from the name.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Tag

from pipeline.normalize import assign_sides, cycle_type, make_race_id

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CYCLES = ROOT / "config" / "cycles.yaml"

STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
SKIP_HEADING = re.compile(r"primary|convention|caucus|runoff|jungle", re.I)

# party letter in a poll column header -> party code used by normalize.assign_sides
PARTY_LETTER = {"D": "DEM", "DFL": "DEM", "D-NPL": "DEM", "R": "REP", "I": "IND",
                "L": "LIB", "G": "GRN", "C": "CON", "F": "FWD", "WFP": "WFP"}
# party name in a results table -> party code
PARTY_NAME = [("democratic", "DEM"), ("republican", "REP"), ("independent", "IND"),
              ("libertarian", "LIB"), ("green", "GRN"), ("constitution", "CON")]

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---- small parsers ------------------------------------------------------------

def clean(text: str) -> str:
    text = re.sub(r"\[[a-zA-Z0-9 ]{1,4}\]", "", text)      # leftover footnote markers
    return " ".join(text.replace("\xa0", " ").split())


def parse_end_date(text: str) -> date | None:
    """'March 27 – April 7, 2023' -> 2023-04-07; 'Nov 3–4, 2024' -> 2024-11-04."""
    t = clean(text)
    years = re.findall(r"\b(19|20)(\d{2})\b", t)
    if not years:
        return None
    year = int("".join(years[-1]))
    parts = re.split(r"\s*[–—-]\s*", t)
    last, first = parts[-1], parts[0]
    m = re.search(r"([A-Za-z]{3,})\.?\s+(\d{1,2})", last)
    if m and m.group(1)[:3].lower() in MONTHS:
        mon, day = MONTHS[m.group(1)[:3].lower()], int(m.group(2))
    else:
        d = re.match(r"(\d{1,2})", last)
        fm = re.search(r"([A-Za-z]{3,})", first)
        if not d or not fm or fm.group(1)[:3].lower() not in MONTHS:
            return None
        mon, day = MONTHS[fm.group(1)[:3].lower()], int(d.group(1))
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def parse_sample(text: str) -> tuple[int | None, str]:
    t = clean(text)
    n = re.search(r"(\d[\d,]*)", t)
    pop = re.search(r"\((LV|RV|A|V)\)", t)
    size = int(n.group(1).replace(",", "")) if n else None
    p = pop.group(1) if pop else ""
    return size, {"V": "RV"}.get(p, p)


def parse_pct(text: str) -> float | None:
    t = clean(text).replace("<", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*%?", t)
    return float(m.group(1)) if m else None


def split_pollster(text: str) -> tuple[str, str]:
    """'The Trafalgar Group (R)' -> ('The Trafalgar Group', 'R').

    Joint polls carry a marker per firm: 'Fabrizio Ward (R)/ Impact Research (D)'
    -> ('Fabrizio Ward / Impact Research', 'R,D').
    """
    t = clean(text)
    marks = re.findall(r"\((D|R|I|L)\)", t)
    t = re.sub(r"\s*\((D|R|I|L)\)", "", t)
    t = re.sub(r"\s*/\s*", " / ", t).strip()
    return t, ",".join(dict.fromkeys(marks))


def candidate_column(text: str) -> tuple[str, str] | None:
    """'Bob Casey Jr. (D)' -> ('Bob Casey Jr.', 'DEM')."""
    m = re.match(r"^(.*?)\s*\(([A-Z][A-Za-z-]{0,4})\)$", clean(text))
    if not m or m.group(2) not in PARTY_LETTER:
        return None
    return m.group(1).strip(), PARTY_LETTER[m.group(2)]


# ---- table grid -------------------------------------------------------------

def _span(v) -> int:
    """Wikipedia sometimes writes rowspan="2;" or colspan="2 ". Be lenient."""
    m = re.match(r"\s*(\d+)", str(v or "1"))
    return max(1, min(int(m.group(1)), 500)) if m else 1


def grid(table: Tag) -> tuple[list[str], list[list[str]]]:
    """Expand rowspan/colspan. Returns (header row, data rows) as cell text."""
    rows: list[list[str]] = []
    pending: dict[int, tuple[str, int]] = {}
    header_rows = 0
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = tr.find_all(["th", "td"], recursive=False)
        row: list[str] = []
        col = 0
        it = iter(cells)
        while True:
            if col in pending:
                txt, left = pending[col]
                row.append(txt)
                pending[col] = (txt, left - 1)
                if left - 1 == 0:
                    del pending[col]
                col += 1
                continue
            c = next(it, None)
            if c is None:
                break
            txt = c.get_text(" ", strip=True)
            span = _span(c.get("colspan"))
            rspan = _span(c.get("rowspan"))
            for k in range(span):
                row.append(txt)
                if rspan > 1:
                    pending[col + k] = (txt, rspan - 1)
            col += span
        while col in pending:  # trailing spanned cells
            txt, left = pending.pop(col)
            row.append(txt)
            if left - 1:
                pending[col] = (txt, left - 1)
            col += 1
        if cells and all(c.name == "th" for c in cells) and len(rows) == header_rows:
            header_rows += 1
        rows.append(row)
    if not rows:
        return [], []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = [clean(" ".join(dict.fromkeys(rows[i][j] for i in range(max(header_rows, 1)))))
              for j in range(width)]
    return header, rows[max(header_rows, 1):]


# ---- page walking ------------------------------------------------------------

@dataclass
class Block:
    headings: dict = field(default_factory=dict)   # {"h2": ..., "h3": ..., "h4": ...}
    table: Tag | None = None


def walk(soup: BeautifulSoup) -> list[Block]:
    out, heads = [], {}
    for el in soup.find_all(["h2", "h3", "h4", "h5", "table"]):
        if el.find_parent("table") is not None:
            continue
        if el.name == "table":
            out.append(Block(dict(heads), el))
        else:
            heads[el.name] = clean(el.get_text(" ", strip=True))
            for lower in ("h3", "h4", "h5")[("h2", "h3", "h4", "h5").index(el.name):]:
                if lower != el.name:
                    heads.pop(lower, None)
    return out


def in_general(b: Block) -> bool:
    return not any(SKIP_HEADING.search(h) for h in b.headings.values())


def general_blocks(blocks: list[Block]) -> list[Block]:
    """Blocks for the November general election of one race.

    Pages run primary -> general. Where a "General election" heading exists,
    keep everything from it onward (Washington's top-two pages put the primary
    under plain "Polling"/"Results" headings before it, and the general's
    results under a sibling "Results" heading after it). Then drop anything
    under a primary/runoff heading.
    """
    start = next((i for i, b in enumerate(blocks)
                  if any("general election" in h.lower() for h in b.headings.values())), 0)
    return [b for b in blocks[start:] if in_general(b)]


def infobox_text(soup: BeautifulSoup) -> str:
    ib = soup.find("table", class_="infobox")
    return clean(ib.get_text(" ", strip=True)).lower() if ib else ""


@dataclass
class PollTable:
    cands: list[tuple[int, str, str]]        # (column, name, party)
    rows: list[dict]
    latest: date | None


def read_poll_table(table: Tag) -> PollTable | None:
    header, data = grid(table)
    if not header or not header[0].lower().startswith("poll source"):
        return None
    col = {"source": 0}
    cands = []
    for j, h in enumerate(header):
        hl = h.lower()
        if hl.startswith("date"):
            col["dates"] = j
        elif hl.startswith("sample"):
            col["sample"] = j
        elif hl.startswith("other"):
            col["other"] = j
        elif hl.startswith("undecided"):
            col["undecided"] = j
        else:
            c = candidate_column(h)
            if c:
                cands.append((j, c[0], c[1]))
    if "dates" not in col or len(cands) < 2:
        return None
    rows = []
    for r in data:
        name, partisan = split_pollster(r[0])
        end = parse_end_date(r[col["dates"]])
        if not name or end is None:
            continue
        size, pop = parse_sample(r[col["sample"]]) if "sample" in col else (None, "")
        pcts = [parse_pct(r[j]) for j, _, _ in cands]
        rows.append({"pollster_raw": name, "partisan": partisan, "dates": clean(r[col["dates"]]),
                     "end": end, "sample": size, "population": pop, "pcts": pcts,
                     "other": parse_pct(r[col["other"]]) if "other" in col else None,
                     "undecided": parse_pct(r[col["undecided"]]) if "undecided" in col else None})
    rows = [r for r in rows if sum(p is not None for p in r["pcts"]) >= 2]
    if not rows:
        return None  # e.g. ranked-choice round tables with no head-to-head numbers
    return PollTable(cands, rows, max(r["end"] for r in rows))


def pick_main(tables: list[PollTable], ibox: str) -> PollTable | None:
    def score(t: PollTable):
        main = sorted(t.cands, key=lambda c: c[2] not in ("DEM", "REP"))[:2]
        surnames = [c[1].split()[-1].lower().strip(".") for c in main]
        in_box = all(s and s in ibox for s in surnames)
        return (in_box, t.latest, len(t.rows))
    return max(tables, key=score) if tables else None


def main_pair(t: PollTable) -> tuple[int, int]:
    """Indexes (into t.cands) of the two candidates that define the race margin."""
    order = list(range(len(t.cands)))
    reps = [i for i in order if t.cands[i][2] == "REP"]
    dems = [i for i in order if t.cands[i][2] == "DEM"]
    if reps and dems:
        return dems[0], reps[0]
    if reps:  # e.g. independent vs Republican
        other = [i for i in order if i != reps[0]]
        return other[0], reps[0]
    return 0, 1


def dedupe_versions(rows: list[dict]) -> list[dict]:
    rank = {"LV": 0, "RV": 1, "A": 2, "": 3}
    best: dict[tuple, dict] = {}
    for i, r in enumerate(rows):
        key = (r["pollster_raw"], r["dates"])
        cand = (rank.get(r["population"], 3), i)
        if key not in best or cand < best[key][0]:
            best[key] = (cand, r)
    return [r for _, r in sorted(best.values(), key=lambda x: x[0][1])]


def read_result(table: Tag) -> list[tuple[str, str, float]] | None:
    header, data = grid(table)
    h = [x.lower() for x in header]
    if "candidate" not in h or "votes" not in h or "%" not in h:
        return None
    ci, pi = h.index("candidate"), h.index("%")
    party_cols = [j for j, x in enumerate(h) if x == "party"]
    pa = party_cols[-1] if party_cols else None  # first "Party" column is a colour swatch
    # New York and Connecticut list a candidate once per party line (fusion
    # voting) plus a "Total" line. Combine per candidate: use the Total line
    # when there is one, else the sum; the party is the major party line.
    lines: dict[str, list[tuple[str, float]]] = {}
    for r in data:
        name = re.sub(r"\s*\((incumbent|write-in)\)", "", clean(r[ci]), flags=re.I)
        pct = parse_pct(r[pi])
        if not name or pct is None or re.match(r"total|majority|plurality|turnout|write", name, re.I):
            continue
        ptxt = clean(r[pa]).lower() if pa is not None else ""
        lines.setdefault(name, []).append((ptxt, pct))
    out = []
    for name, ls in lines.items():
        totals = [p for t, p in ls if t == "total"]
        pct = totals[0] if totals else sum(p for _, p in ls)
        codes = [next((c for key, c in PARTY_NAME if key in t), "OTH") for t, _ in ls if t != "total"]
        party = next((c for c in ("DEM", "REP") if c in codes), codes[0] if codes else "OTH")
        out.append((name, party, round(pct, 3)))
    if len(out) < 2:
        return None
    return sorted(out, key=lambda x: -x[2])


# ---- races -------------------------------------------------------------------

@dataclass
class Race:
    race_id: str
    race_type: str
    state: str
    district: str
    kind: str
    blocks: list[Block]


def races_on_page(title: str, cycle: int, blocks: list[Block]) -> list[Race]:
    m = re.match(rf"^{cycle} United States Senate (special )?elections? in (.+)$", title)
    if m:
        st = STATES.get(m.group(2))
        if not st:
            return []
        kind = "S" if m.group(1) else ""
        return [Race(make_race_id(cycle, "SEN", st, "", kind), "SEN", st, "", kind, blocks)]
    m = re.match(rf"^{cycle} (.+) gubernatorial (special )?election$", title)
    if m:
        st = STATES.get(m.group(1))
        if not st:
            return []
        kind = "S" if m.group(2) else ""
        return [Race(make_race_id(cycle, "GOV", st, "", kind), "GOV", st, "", kind, blocks)]
    m = re.match(rf"^{cycle} United States presidential election in (.+)$", title)
    if m:
        st = STATES.get(m.group(1))
        return [Race(make_race_id(cycle, "PRES", st), "PRES", st, "", "", blocks)] if st else []
    m = re.match(rf"^{cycle} United States House of Representatives elections? in (.+)$", title)
    if not m or m.group(1) not in STATES:
        return []
    st = STATES[m.group(1)]
    if " election in " in title:  # single at-large district page
        return [Race(make_race_id(cycle, "HOUSE", st, "1"), "HOUSE", st, "1", "", blocks)]
    by_d: dict[str, list[Block]] = {}
    for b in blocks:
        dm = re.match(r"^District (\d+)\b", b.headings.get("h2", ""))
        if dm:
            by_d.setdefault(str(int(dm.group(1))), []).append(b)
    return [Race(make_race_id(cycle, "HOUSE", st, d), "HOUSE", st, d, "", bs)
            for d, bs in by_d.items()]


def parse_page(path: Path, cycle: int, election: date) -> tuple[list[dict], list[dict], list[str]]:
    """Return (poll rows, result rows, notes) for one saved page."""
    text = path.read_text()
    meta = json.loads(re.match(r"<!-- (.*?) -->", text).group(1))
    soup = BeautifulSoup(text, "lxml")
    ibox = infobox_text(soup)
    polls, results, notes = [], [], []
    for race in races_on_page(meta["title"], cycle, walk(soup)):
        general = general_blocks(race.blocks)
        tables = [t for t in (read_poll_table(b.table) for b in general) if t]
        res = next((r for r in (read_result(b.table) for b in general
                                if "result" in " ".join(b.headings.values()).lower()) if r), None)
        base = {"cycle": cycle, "cycle_type": cycle_type(cycle),
                "election_date": election.isoformat(), "race_id": race.race_id,
                "race_type": race.race_type, "state": race.state, "district": race.district,
                "special": race.kind}
        if res and election < date.today():  # no "results" before Election Day
            s = assign_sides(res[0], res[1])
            results.append({**base, "side_a_name": s.a_name, "side_a_party": s.a_party,
                            "side_a_actual": s.a_val, "side_b_name": s.b_name,
                            "side_b_party": s.b_party, "side_b_actual": s.b_val,
                            "margin_actual": round(s.a_val - s.b_val, 3),
                            "matchup": s.matchup, "source": "wikipedia"})
        main = pick_main(tables, ibox)
        if not main:
            continue
        if len(tables) > 1:
            notes.append(f"{race.race_id}: {len(tables)} poll tables, kept "
                         + " vs ".join(c[1] for c in main.cands))
        ia, ib = main_pair(main)
        ca, cb = main.cands[ia], main.cands[ib]
        for r in dedupe_versions(main.rows):
            pa, pb = r["pcts"][ia], r["pcts"][ib]
            if pa is None or pb is None:
                continue
            s = assign_sides((ca[1], ca[2], pa), (cb[1], cb[2], pb))
            polls.append({
                **base, "pollster_id": "", "pollster_raw": r["pollster_raw"], "sponsor": "",
                "partisan": r["partisan"], "methodology": "", "start_date": "",
                "end_date": r["end"].isoformat(), "poll_date": r["end"].isoformat(),
                "days_to_election": (election - r["end"]).days,
                "sample_size": r["sample"] or "", "population": r["population"],
                "side_a_name": s.a_name, "side_a_party": s.a_party, "side_a_pct": s.a_val,
                "side_b_name": s.b_name, "side_b_party": s.b_party, "side_b_pct": s.b_val,
                "other_pct": "" if r["other"] is None else r["other"],
                "undecided_pct": "" if r["undecided"] is None else r["undecided"],
                "margin_poll": round(s.a_val - s.b_val, 3), "matchup": s.matchup,
                "source": "wikipedia",
                "source_ref": f"{meta['title']}#revid={meta['revid']}",
            })
    return polls, results, notes


def parse_cycle(cycle: int) -> tuple[list[dict], list[dict], list[str]]:
    cfg = yaml.safe_load(CYCLES.read_text())
    election = cfg[cycle]["election_date"]
    polls, results, notes = [], [], []
    for f in sorted((RAW_DIR / str(cycle)).glob("*.html")):
        p, r, n = parse_page(f, cycle, election)
        polls += p
        results += r
        notes += n
    polls = [p for p in polls if p["days_to_election"] >= 0]
    return polls, results, notes
