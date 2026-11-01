# Archived FiveThirtyEight poll data

- File: `538_raw_polls.csv`
- Source: https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv
- Repo: https://github.com/fivethirtyeight/data (pollster-ratings/)
- Downloaded: 2026-11-01
- SHA-256: `9f0b185506e59117c150fb988e73b612346effe8e3a8f0d90fdafcad07f54756`
- Rows: 20466
- License: Creative Commons Attribution 4.0 International (CC BY 4.0), per the repo's LICENSE file.
  Attribution: FiveThirtyEight / ABC News.

## Coverage

General elections 1998–2022 (Senate, House districts, House generic ballot, Governor, President),
plus a few primaries and 2023 primaries. **No 2024 cycle** — 538 closed before publishing it.
2024 and later come from Wikipedia (Phase 3).

538 kept only polls with a median field date within ~60 days of the election, and the file
already includes each race's actual result (`cand1_actual`, `cand2_actual`).

Column definitions: see the pollster-ratings README in the 538 repo.
This file is a frozen snapshot. Do not edit it; all cleaning happens in `pipeline/load_538_history.py`.

---

# 538 published pollster ratings (comparison only)

- File: `538_pollster_ratings.csv`
- Source: https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/pollster-ratings-combined.csv
- Downloaded: 2026-11-01 · License: CC BY 4.0 (FiveThirtyEight / ABC News)
- Used only by `pipeline/report_pollsters.py` to sanity-check our own scores. Not used by the model.
