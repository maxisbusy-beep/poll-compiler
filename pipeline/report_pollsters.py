"""Phase 2 gate report: our pollster scores vs 538's published ratings, plus spot checks.

Writes reports/pollster_scores.md. The 538 ratings are a sanity check only.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MIN_N = 20

SPOT = ["the-new-york-times-siena-college", "selzer-and-co", "emerson-college",
        "trafalgar-group", "rasmussen-reports", "surveyusa", "quinnipiac-university",
        "public-policy-polling", "marist-college", "yougov"]


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy)


def fmt(v, signed=False, pct=False):
    if v is None:
        return "—"
    if pct:
        return f"{v:.0f}%"
    if signed:
        return ("D+" if v > 0 else "R+" if v < 0 else "") + f"{abs(v):.1f}"
    return f"{v:.2f}"


def build() -> str:
    data = json.loads((ROOT / "site" / "data" / "pollsters.json").read_text())
    aliases = yaml.safe_load((ROOT / "config" / "pollster_aliases.yaml").read_text())["pollsters"]
    id538 = {}
    for pid, info in aliases.items():
        for i in [info.get("fivethirtyeight_id"), *info.get("merged_fivethirtyeight_ids", [])]:
            id538[str(i)] = pid
    ext = {}
    for r in csv.DictReader((ROOT / "data" / "history" / "538_pollster_ratings.csv").open()):
        pid = id538.get(r["pollster_rating_id"])
        if pid and r["POLLSCORE"] not in ("", "NA"):
            ext.setdefault(pid, float(r["POLLSCORE"]))  # first (main) id wins on merges

    ps = {p["id"]: p for p in data["pollsters"]}
    pairs = [(p["model"]["shrunk_excess"], ext[pid]) for pid, p in ps.items()
             if pid in ext and p["windows"]["all_time"]["n"] >= MIN_N]
    rho = spearman([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) > 2 else None

    w = data["windows"]
    out = ["# Pollster scores", "",
           f"- Target cycle **{data['target_cycle']}** · scored polls **{data['scored_polls']:,}** "
           f"(one final poll per pollster per race, ≤{data['settings']['final_window_days']} days out) · "
           f"races **{data['scored_races']:,}** · pollsters **{len(ps)}**",
           f"- Windows: {w['same_type']['label']}; {w['last_two']['label']}"
           + (f" — **{', '.join(map(str, w['last_two']['missing']))} not loaded yet**"
              if w['last_two']['missing'] else "") + f"; {w['all_time']['label']}",
           "", "## Sanity check against 538", "",
           f"Rank correlation between our shrunk excess error and 538's POLLSCORE, for "
           f"{len(pairs)} pollsters with ≥{MIN_N} scored races: **ρ = {rho:.2f}**"
           if rho is not None else "Not enough overlap to compare.",
           "", "Both are 'lower is better'. A strong positive ρ means we rank pollsters much like 538 "
           "did, using a simpler method.", "",
           "## Spot checks (all time)", "",
           "| Pollster | n | Win-call | Avg error | Bias | Excess | Model weight | 538 POLLSCORE |",
           "|---|---|---|---|---|---|---|---|"]
    for pid in SPOT:
        p = ps.get(pid)
        if not p:
            out.append(f"| {pid} | not found | | | | | | |")
            continue
        a = p["windows"]["all_time"]
        out.append(f"| {p['name']} | {a['n']} | {fmt(a['win_call_pct'], pct=True)} | "
                   f"{fmt(a['mean_abs_error'])} | {fmt(a['bias'], signed=True)} | "
                   f"{fmt(a['excess_error'])} | {p['model']['weight']:.2f} | "
                   f"{fmt(ext.get(pid))} |")

    big = [p for p in data["pollsters"] if p["windows"]["all_time"]["n"] >= MIN_N]
    out += ["", f"## Best and worst, all time (≥{MIN_N} scored races, by shrunk excess error)", "",
            "| | Pollster | n | Avg error | Bias | Excess | Weight |", "|---|---|---|---|---|---|---|"]
    for label, group in (("best", big[:8]), ("worst", big[-8:])):
        for p in group:
            a = p["windows"]["all_time"]
            out.append(f"| {label} | {p['name']} | {a['n']} | {fmt(a['mean_abs_error'])} | "
                       f"{fmt(a['bias'], signed=True)} | {fmt(a['excess_error'])} | "
                       f"{p['model']['weight']:.2f} |")

    for wkey in ("same_type", "last_two"):
        rows = [p for p in data["pollsters"] if p["windows"][wkey]["n"] >= 5]
        rows.sort(key=lambda p: p["windows"][wkey]["mean_abs_error"])
        out += ["", f"## {w[wkey]['label']}: pollsters with ≥5 scored races, by average error", "",
                "| Pollster | n | Win-call | Avg error | Bias |", "|---|---|---|---|---|"]
        for p in rows:
            a = p["windows"][wkey]
            out.append(f"| {p['name']} | {a['n']} | {fmt(a['win_call_pct'], pct=True)} | "
                       f"{fmt(a['mean_abs_error'])} | {fmt(a['bias'], signed=True)} |")
    out += ["", "Bias: average signed miss on the margin. **D+** = overstated the Democratic "
            "(or main non-Republican) side; **R+** = overstated the Republican.", ""]
    return "\n".join(out)


def main() -> None:
    path = ROOT / "reports" / "pollster_scores.md"
    path.write_text(build())
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
