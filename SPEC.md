# poll-compiler — Build Spec

Static web app on GitHub Pages that compiles public polls into win probabilities for **Senate and House control**, and grades every pollster on its track record. Built in phases by Claude Code. Each phase ends at a **stop-and-check gate**. Do not start the next phase until the owner signs off.

Repo: `github.com/maxisbusy-beep/poll-compiler` (public, required for free GitHub Pages)

---

## 1. Decisions (locked)

| Topic | Decision |
|---|---|
| Purpose | Reusable across cycles (2028+). 2026 results are used to backtest and grade pollsters. |
| Current polls | Auto-scraped from Wikipedia poll tables via the MediaWiki API |
| Historical polls | Archived FiveThirtyEight poll dataset (older cycles) + Wikipedia (newer cycles) |
| Accuracy scoring | Win-call %, average absolute error, and signed bias, with sample counts |
| Accuracy windows | (a) last cycle of the same type, (b) last two cycles, (c) all time |
| Model | Weighted polling average → per-race win % → correlated simulation for chamber odds |
| House | Generic ballot + district partisan lean; district polls used where they exist |
| Partisan / sponsored polls | Included, corrected by each pollster's **measured** bias (no hand-made partisan lists) |
| Updates | GitHub Action daily, plus manual "Run workflow" button |
| UI | Phone first, works on desktop. Plain HTML/CSS/JS, no build step |

"Same type": midterm ↔ midterm (2026 → 2022), presidential ↔ presidential (2028 → 2024).
"Last two cycles": the two most recent federal general elections before the current one (2026 → 2022 + 2024).

---

## 2. Architecture

```
GitHub Action (daily cron + manual)
  └─ pipeline/ (Python 3.12)
       ├─ fetch: Wikipedia API → raw HTML snapshots (data/raw/, committed)
       ├─ parse: tables → normalized polls (data/polls/<cycle>.csv)
       ├─ score: pollster accuracy → site/data/pollsters.json
       ├─ model: averages + simulation → site/data/forecast.json, races.json
       └─ commit changed files → Pages redeploys
site/ (static, served by Pages)
  index.html, races.html, race.html, pollsters.html, method.html
  app.js, styles.css, data/*.json
```

No server, no database. All data is versioned in git, so every past forecast is recoverable from history.

### Repo layout
```
pipeline/
  fetch_wikipedia.py   parse_tables.py   normalize.py
  load_538_history.py  load_results.py   score_pollsters.py
  average.py           simulate.py       backtest.py   run_all.py
config/
  cycles.yaml          # per cycle: date, type, races up, seats not up, tiebreak rule
  pollster_aliases.yaml# "Emerson College" / "Emerson Polling" → emerson
  sources.yaml         # Wikipedia page titles per cycle and race
  district_lean/<cycle>.csv
data/
  raw/                 # dated HTML snapshots (for reproducibility + test fixtures)
  polls/<cycle>.csv    # normalized polls
  results/<cycle>.csv  # certified results
tests/
  fixtures/            # frozen Wikipedia HTML + expected parsed CSVs
site/
.github/workflows/update.yml
```

---

## 3. Data

### 3.1 Normalized poll record (one row per poll per race)
`cycle, race_id (e.g. 2026-SEN-TX, 2026-HOUSE-GEN, 2026-HOUSE-TX-23), pollster_id, pollster_raw, sponsor, start_date, end_date, sample_size, population (LV/RV/A), dem_pct, rep_pct, other_pct, undecided_pct, dem_candidate, rep_candidate, source_url, source_revid`

- Independents running as the main non-Republican (e.g. Osborn, NE 2024/2026) are mapped to the `dem` side through a per-race override in `cycles.yaml`, and flagged in the UI.
- Where a poll reports several versions (LV and RV, or with and without leaners), keep **one**: LV over RV over A, then the version with leaners.
- Store the Wikipedia `revid`, so every number traces to an exact page revision.

### 3.2 Sources
- **Wikipedia (current + recent cycles):** MediaWiki API `action=parse` on pages listed in `sources.yaml`. Use a descriptive User-Agent and at most 1 request per second. Wikipedia text is CC BY-SA, so attribute it on the Method page.
  - Page **revision history** lets us rebuild "what the polls looked like on date X". Use this for backtests.
- **Archived FiveThirtyEight data (older cycles):** locate the poll and pollster-ratings CSVs in the `fivethirtyeight/data` GitHub repo. Confirm the license, the column meanings and the year coverage, then **snapshot** them into `data/` (do not depend on the live URL). Record the coverage in the Phase 1 gate report.
- **Results:** MIT Election Data and Science Lab (Harvard Dataverse) Senate and House results, with Wikipedia as the fallback for the newest cycle until MEDSL publishes it.
- **District partisan lean:** presidential vote by congressional district **on the lines in force for that cycle**. Mid-decade redistricting (2025–26) means lines differ from 2024; each cycle has its own `district_lean/<cycle>.csv`. The owner confirms the source at the Phase 5 gate.

### 3.3 Pollster identity
`pollster_aliases.yaml` maps every raw name to one `pollster_id`. Any unmapped name **fails the run loudly** and is listed in the Action log, rather than silently becoming a new pollster. Partnerships ("Siena / NYT") map to the firm doing the fieldwork.

---

## 4. Pollster scoring

**Which polls count:** a pollster's **final poll** in each race, with field end date ≤ 21 days before Election Day. One poll per pollster per race, so a firm cannot pad its record with repeat releases.

**Metrics per poll** (margin = Dem − Rep, in points):
- `error = poll_margin − actual_margin`
- `abs_error = |error|`
- `called = sign(poll_margin) == sign(actual_margin)`. A tied poll counts as half.

**Per pollster, for each window** (same-type cycle, last two cycles, all time):
- `n` (number of races scored)
- `win_call_pct`
- `mean_abs_error`
- `bias` = mean signed error (positive = leaned Dem)
- `excess_error` = mean of (abs_error − average abs_error of all pollsters in the same race). This adjusts for hard races, so a firm that only polls landslides does not look brilliant.

**Display rules:**
- n < 5 in a window → show "—" with the n, not a percentage.
- Always show `n` beside every number.
- Win-call % is shown, but sorting defaults to `excess_error`, since win-call rewards lopsided races.

**Weights and bias correction used by the model** (all-time window, shrunk toward the field average so a firm with three lucky polls is not treated as elite):
- `shrunk_excess = excess_error × n / (n + k)`, with k = 10 to start (tuned in backtest)
- `shrunk_bias = bias × n / (n + k)`
- Quality weight = `exp(−shrunk_excess / s)`, with s tuned in backtest
- Each poll's margin is corrected by `−shrunk_bias` before averaging. This handles partisan and sponsored polls from their own measured records. A brand-new pollster gets average weight and zero correction.

**No look-ahead:** when scoring or weighting for cycle C, use only results from cycles before C. This is what keeps the backtest honest.

---

## 5. Forecast model

### 5.1 Race polling average
Weight per poll = recency × sample × population × quality × dedupe
- recency: half-life 14 days from field end date (tuned)
- sample: `sqrt(min(n, 2000))`
- population: LV 1.0, RV 0.7, A 0.3
- quality: from §4
- dedupe: the k-th most recent poll from the same pollster in a race gets ×1/k

Output: corrected weighted mean margin, and an effective poll count (Kish).

### 5.2 Per-race win probability
`margin ~ Normal(mu, sigma)`
- `mu` = polling average. Races with **no** polls use `partisan lean + national generic-ballot shift`.
- `sigma` comes from the **backtest**: the historical error of poll averages, as a function of days to election and effective poll count. It is never hand-set. No-poll races get the historical error of the lean-based estimate, which will be wider.

### 5.3 Chamber simulation (10,000 runs)
In each run:
1. Draw one **national** error, shared by every race.
2. Draw a **state** error per state, shared by the Senate race and House districts in that state.
3. Draw a **race** error.
4. Count seats.

The split of variance between national, state and race comes from the backtest (how correlated poll misses were in past cycles).

- **Senate:** add `seats_not_up` from `cycles.yaml`. The tiebreak rule (VP party) is in config per cycle. Independents follow the caucus set in config.
- **House:** each district's expected margin = lean + generic ballot average (corrected and weighted like any race) + district poll average where one exists, blended by effective poll count. Then the same correlated errors apply.

**Outputs:** P(control) for each chamber, the seat distribution (histogram), median seats with an 80% range, and per-race win % and margin.

### 5.4 Backtest (the main quality check)
Run the full pipeline **as of 7 and 30 days before** each past election with available data (rebuilding polls from Wikipedia revisions and 538 data, and pollster scores from prior cycles only). Report:
- Brier score and log loss for race calls
- **Calibration table**: races given 70–80% should be won about 75% of the time, and so on
- Chamber outcomes for each cycle
- Comparison against a naive baseline (simple unweighted average) — the weighted model must beat it, or the extra machinery does not ship

Tuned parameters (half-life, k, s, sigma curve, error split) are chosen by backtest and written to `config/params.yaml`, with the backtest report committed alongside.

---

## 6. UI (phone first)

- **Home:** two big cards, Senate and House: "Dem X% / Rep Y%", median seats with range, seat histogram, last-updated time and the number of polls used.
- **Races:** list sorted by closeness. Each row: race, candidates, average margin, win %, poll count. Filter by chamber and rating.
- **Race detail:** polling average over time (chart), table of every poll with pollster grade, bias correction applied, weight share, and a link to the source revision.
- **Pollsters:** sortable table with a toggle for the three windows (same-type / last two cycles / all time). Columns: n, win-call %, average error, bias (shown as "D+1.2" / "R+0.8"), excess error. Tap a pollster for its race-by-race history.
- **Method:** plain-language explanation, backtest calibration chart, parameters, data sources and attribution.
- Light and dark mode. Charts in hand-built SVG or Chart.js from cdnjs. No build tooling.
- An empty state for off-cycle periods ("No active election — see pollster records").

---

## 7. Automation

`.github/workflows/update.yml`
- `schedule: cron: '43 6 * * *'` (daily, 07:43 Berlin winter time) and `workflow_dispatch`
- Steps: checkout → set up Python → `pip install -r requirements.txt` → `pytest` → `python -m pipeline.run_all` → commit `data/` and `site/data/` if changed → Pages deploys from `site/`
- If tests or the alias check fail: **no commit**, so the site keeps the last good forecast, and the run shows red.
- Sanity guards before committing: a race margin moving > 10 pts in a day, the poll count dropping, or a chamber % moving > 25 pts all block the commit and flag for review.

---

## 8. Phases and gates

Each phase: isolated scope, tests written alongside, and a gate report (what was built, test results, numbers to eyeball, open questions) with file and line references.

| # | Phase | Gate: owner checks |
|---|---|---|
| 0 | Repo, Pages "hello", Action that runs tests | Site loads on phone; Action goes green |
| 1 | Load 538 history + results; alias table | Polls and races per cycle; years covered; unmapped names list empty |
| 2 | Pollster scoring (§4) | Spot-check 5 well-known firms against intuition and old published ratings; n counts look right |
| 3 | Wikipedia fetch + parse for 2022, 2024, 2026 | 3 races hand-compared to the live page, row by row; fixture tests pass |
| 4 | Senate average, per-race %, simulation, backtest | Calibration table; beats naive baseline; 2026 Senate output looks sane vs other forecasters |
| 5 | House: generic ballot + district lean + district polls | District lean source confirmed; House backtest |
| 6 | UI (§6) | Owner reviews on phone |
| 7 | Daily automation + guards | One week of clean daily runs |
| 8 | After Nov 3 2026: load certified results, rescore pollsters, rerun backtest | 2026 shows up as a new graded cycle |

---

## 9. Known risks

- **Wikipedia tables change format.** Parsing is the most fragile part. Mitigation: frozen fixtures in tests, failing loudly, and committed raw snapshots.
- **538 data stopped updating** after FiveThirtyEight closed. Everything from then on depends on our own Wikipedia captures, so the committed `data/` folder is the long-term record.
- **Pollster names are messy.** The alias table needs ongoing upkeep; the loud failure keeps it honest.
- **Redistricting** changes House lean between cycles.
- **Small samples:** many firms have few scored races. Shrinkage and the n display keep that visible.
- This is a polling compiler, not a fundamentals model; it will be weakest in races with few or no polls, and the UI says so.
