"""Map Wikipedia pollster spellings onto the alias table (Phase 3, reviewed by hand).

TO_EXISTING: Wikipedia spelling -> existing pollster id (same firm, or the
             firm that did the fieldwork for a media partnership).
NEW:         new pollster id -> (display name, [spellings]) for firms 538 never rated.
Anything still unmapped after this is created as its own new pollster by
`--create-rest`, one id per distinct name, and listed for review.
Re-running is safe: existing aliases are kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.normalize import PollsterAliases  # noqa: E402
from tools.build_aliases_from_538 import HEADER, slugify  # noqa: E402

ALIASES = ROOT / "config" / "pollster_aliases.yaml"

TO_EXISTING = {
    # renamed / reworded
    "University of New Hampshire": "university-of-new-hampshire-survey-center",
    "Saint Anselm College": "saint-anselm-college-survey-center",
    "The Trafalgar Group": "trafalgar-group",
    "Franklin & Marshall College": "franklin-and-marshall-college-center-for-opinion-research",
    "Marist University": "marist-college",
    "Marquette University": "marquette-university-law-school",
    "Mason-Dixon": "mason-dixon-polling-and-strategy",
    "Monmouth University": "monmouth-university-polling-institute",
    "Goucher College": "goucher-college-sarah-t-hughes-center-for-politics",
    "Gonzales Research": "gonzales-research-and-marketing-strategies-inc",
    "Roanoke College": "roanoke-college-institute-for-policy-and-opinion-research",
    "Muhlenberg College": "muhlenberg-college-institute-of-public-opinion",
    "Christopher Newport University": "christopher-newport-university-wason-center-for-civic-leadership",
    "Stetson University": "stetson-university-center-for-public-opinion-research",
    "University of North Florida": "university-of-north-florida-public-opinion-research-lab",
    "East Carolina University": "east-carolina-university-center-for-survey-research",
    "UT Tyler": "university-of-texas-at-tyler-center-for-opinion-research",
    "University of Delaware": "university-of-delaware-center-for-political-communication",
    "Dartmouth College": "dartmouth-college-nelson-a-rockefeller-center-for-public-policy-and-the-social-sciences",
    "The Dartmouth Poll": "dartmouth-college-nelson-a-rockefeller-center-for-public-policy-and-the-social-sciences",
    "Ohio Northern University": "ohio-northern-university-institute-for-civics-and-public-policy",
    "Rutgers University Eagleton Institute of Politics": "rutgers-university-eagleton-center-for-public-interest-polling",
    "Rutgers University": "rutgers-university-eagleton-center-for-public-interest-polling",
    "Rutgers-Eagleton": "rutgers-university-eagleton-center-for-public-interest-polling",
    "High Point University": "high-point-university-survey-research-center",
    "University of Houston": "university-of-houston-hobby-school-of-public-affairs",
    "Virginia Commonwealth University": "virginia-commonwealth-university-l-douglas-wilder-school-of-government-and-public-affairs",
    "Michigan State University": "michigan-state-university-institute-for-public-policy-and-social-research",
    "MSU Billings": "montana-state-university-billings",
    "Montana State University": "montana-state-university-billings",
    "Echleon Insights": "echelon-insights",
    "Marketing Resource Group": "marketing-resource-group-mrg",
    "Targoz Media Research": "targoz-market-research",
    "Public Opinon Strategies": "public-opinion-strategies",
    "OnMessage Public Strategies": "onmessage-inc",
    "Rosetta Stone Communications": "landmark-communications-rosetta-stone-communications",
    "Garin-Hart-Yang": "garin-hart-yang-research-group",
    "Sienna College": "siena-college",
    "Siena University": "siena-college",
    "Fabrizio Ward": "fabrizio-lee-and-associates",
    "Susquehanna Polling & Research": "susquehanna-polling-and-research-inc",
    "Susquehanna Polling and Research": "susquehanna-polling-and-research-inc",
    "McLaughlin and Associates": "mclaughlin-and-associates",
    "OnMessage": "onmessage-inc",
    "National Research Inc.": "national-research",
    "Research & Polling": "research-and-polling-inc",
    "The Tarrance Group": "tarrance-group",
    "The Mellman Group": "mellman-group",
    "Fabrizio, Lee, & Associates": "fabrizio-lee-and-associates",
    "Mitchell Research": "mitchell-research-and-communications",
    "USC / CSULB / Cal Poly Pomona": "usc-csu",
    "UC Berkeley": "university-of-california-berkeley-institute-of-governmental-studies",
    "Florida Atlantic University / Mainstreet Research": "mainstreet-research",
    "Meredith College": "meredith-college-department-of-history-political-science-and-international-studies",
    "Berkeley IGS": "university-of-california-berkeley-institute-of-governmental-studies",
    "UC Berkeley Citrin Center / TrueDot / Politico": "university-of-california-berkeley-institute-of-governmental-studies",
    "New York Times / Portland Press Herald / Siena University": "the-new-york-times-siena-college",
    "The New York Times / The Philadelphia Inquirer / Siena University": "the-new-york-times-siena-college",
    "The New York Times / Siena University": "the-new-york-times-siena-college",
    "CBS / YouGov": "yougov",
    "Wesleyan University / YouGov": "yougov",
    "Texas Southern University / YouGov": "yougov",
    "Beacon Research / Cygnal": "cygnal",
    "Echelon Insights / Tusk Strategies": "echelon-insights",
    "Texas A&M University / ReconMR": "recon-mr",
    "BSP Research": "bsp-research-shaw-and-company-research",
    "Arizona State University": "arizona-state-university-morrison-institute-for-public-policy",
    "University of Georgia": "university-of-georgia-school-of-public-and-international-affairs",
    "HighGround, Inc.": "highground-public-affairs",
    "Red Oak Strategic": "red-oak-strategies",
    "PPIC": "public-policy-institute-of-california",
    # joint polls 538 rated as a pair
    "Fabrizio Ward / Impact Research": "fabrizio-lee-and-associates-impact-research",
    "Beacon Research / Shaw & Co. Research": "beacon-research-shaw-and-co-research",
    "BSG / GS Strategy Group": "benenson-strategy-group-gs-strategy-group",
    "Washington Post / Schar School": "the-washington-post-george-mason-university-schar-school-of-policy-and-government",
    "The Washington Post / George Mason University": "the-washington-post-george-mason-university-schar-school-of-policy-and-government",
    # media partnerships -> fieldwork firm (SPEC 3.3)
    "New York Times / Siena College": "the-new-york-times-siena-college",
    "New York Times / Siena University": "the-new-york-times-siena-college",
    "NYT / Siena College": "the-new-york-times-siena-college",
    "The New York Times / Siena College": "the-new-york-times-siena-college",
    "New York Times / The Philadelphia Inquirer / Siena University": "the-new-york-times-siena-college",
    "Fox News": "beacon-research-shaw-and-co-research",
    "CNN / SSRS": "ssrs", "CNN / SRSS": "ssrs", "SSRS / Vanderbilt University": "ssrs",
    "CBS News / YouGov": "yougov", "Economist / YouGov": "yougov", "Univision / YouGov": "yougov",
    "Bowling Green State University / YouGov": "yougov", "UMass Lowell / YouGov": "yougov",
    "High Point University / YouGov": "yougov", "Elon University / YouGov": "yougov",
    "Catawba College / YouGov": "yougov", "UMass Amherst / YouGov": "yougov",
    "Michigan State University / YouGov": "yougov", "UMass / YouGov": "yougov",
    "UMass Amherst / YouGov / WCVB": "yougov", "University of Massachusetts / YouGov": "yougov",
    "University of Houston / YouGov": "yougov", "YouGov / Saint Louis University": "yougov",
    "YouGov Blue": "yougov",
    "KSTP / SurveyUSA": "surveyusa", "KTSP / SurveyUSA": "surveyusa",
    "USA Today / Ipsos": "ipsos",
    "Emerson College / WPRI-TV": "emerson-college",
    "Cascade PBS / Elway Research": "elway-research",
    "Braun Research / Vermont Public": "braun-research",
    "NHJournal / Praecones Analytica": "praecones-analytica",
    "Global Strategy Group / Progress Colorado": "global-strategy-group",
    "Texas Public Opinion Research / Lake Research Partners": "lake-research-partners",
    "Fabrizio Ward / David Binder Research": "david-binder-research",
    "Red Wave Strategy Group / Impact Research": "impact-research",
    "Cygnal / Beacon Research": "cygnal",
    "The Political Matrix / The Listener Group": "the-political-matrix-the-listener-group",
    "Political Matrix / The Listener Group": "the-political-matrix-the-listener-group",
    "Mainstreet Research / FAU": "mainstreet-research",
}

NEW = {
    "mainstreet-research": ("Mainstreet Research", []),
    "quantus-insights": ("Quantus Insights", []),
    "redbox-research": ("RedBox Research", []),
    "bullfinch-group": ("The Bullfinch Group", ["Bullfinch Group", "The Bullfinch Group / Independent Center"]),
    "dccc": ("DCCC", ["DCCC Targeting Team", "DCCC Analytics", "DCCC Analytics Department",
                      "Democratic Congressional Campaign Committee"]),
    "embold-research": ("Embold Research", []),
    "big-data-poll": ("Big Data Poll", []),
    "survation": ("Survation", []),
    "abacus-data": ("Abacus Data", []),
    "hart-research-associates": ("Hart Research Associates", ["Hart Research"]),
    "gqr-research": ("GQR Research", []),
    "harrisx": ("HarrisX", []),
    "normington-petts": ("Normington Petts", []),
    "tavern-research": ("Tavern Research", []),
    "national-public-affairs": ("National Public Affairs", ["NPA Polling"]),
    "peak-insights": ("Peak Insights", []),
    "chism-strategies": ("Chism Strategies", []),
    "socal-strategies": ("SoCal Strategies", []),
    "texas-southern-university": ("Texas Southern University",
                                  ["Public Policy Research / Texas Southern University",
                                   "University of Houston / Texas Southern University"]),
    "texas-politics-project": ("University of Texas / Texas Politics Project", []),
    "the-washington-post": ("The Washington Post", ["The Washington Post / SSPG"]),
    "upswing-research": ("Upswing Research & Strategy", ["Upswing Research"]),
    "votenexus": ("VoteNexus Research", ["VoteNexus"]),
    "guidant-polling": ("Guidant Polling & Strategy", ["Guidant Polling and Strategy",
                                                       "Guidance Polling and Strategy"]),
    "sea-polling": ("SEA Polling", ["Sea Polling"]),
    "american-pulse": ("American Pulse Research", ["American Pulse"]),
    "pulse-decision-science": ("Pulse Decision Science", ["Pulse Science Decision"]),
    "public-sentiment-institute": ("The Public Sentiment Institute",
                                   ["The Public Sentiment Institute / Virginia Project"]),
    "verasight": ("Verasight", ["Verasight / VoteHub", "Michigan State University / Verasight"]),
    "recon-mr": ("ReconMR", ["ReconMR / Siena University", "Texas A&M University / ReconMR / Siena University"]),
    "usc-csu": ("USC / CSU", []),
    "competitive-edge-research": ("Competitive Edge Research", []),
    "center-for-excellence-in-polling": ("Center for Excellence in Polling", ["CEPP"]),
    "sacred-heart-university": ("Sacred Heart University", ["Sacred Heart University / WFSB / CT Insider"]),
    "deep-root-analytics": ("Deep Root Analytics", []),
    "university-of-arizona-truedot": ("University of Arizona / Truedot", []),
}


def main(create_rest: bool, extra_names: list[str]) -> None:
    data = yaml.safe_load(ALIASES.read_text())
    ps = data["pollsters"]
    for pid, (name, aliases) in NEW.items():
        e = ps.setdefault(pid, {"name": name, "aliases": [], "source": "wikipedia"})
        e["aliases"] = list(dict.fromkeys(e.get("aliases", []) + aliases))
    for raw, pid in TO_EXISTING.items():
        if pid not in ps:
            raise SystemExit(f"unknown target id {pid} for {raw!r}")
        if raw != ps[pid]["name"] and raw not in ps[pid].get("aliases", []):
            ps[pid].setdefault("aliases", []).append(raw)
    created = []
    if create_rest:
        ALIASES.write_text(HEADER + yaml.safe_dump({"pollsters": dict(sorted(ps.items()))},
                                                   sort_keys=False, allow_unicode=True, width=120))
        a = PollsterAliases()
        for raw in sorted(set(extra_names)):
            if a.get(raw) is None:
                pid = slugify(raw)
                while pid in ps:
                    pid += "-w"
                ps[pid] = {"name": raw, "aliases": [], "source": "wikipedia"}
                created.append(f"{pid}: {raw}")
    ALIASES.write_text(HEADER + yaml.safe_dump({"pollsters": dict(sorted(ps.items()))},
                                               sort_keys=False, allow_unicode=True, width=120))
    print(f"{len(ps)} pollsters; created {len(created)} more:")
    for c in created:
        print("  ", c)


if __name__ == "__main__":
    from pipeline.parse_tables import parse_cycle
    names = []
    for cyc in (2024, 2026):
        names += [p["pollster_raw"] for p in parse_cycle(cyc)[0]]
    main("--create-rest" in sys.argv, names)
