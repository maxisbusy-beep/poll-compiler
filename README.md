# poll-compiler

Compiles public polls into **Senate and House control odds**, and grades every pollster on its track record (last same-type cycle, last two cycles, all time).

- Live site: https://maxisbusy-beep.github.io/poll-compiler/
- Full plan: [SPEC.md](SPEC.md)

## Status

**Phase 1 — historical data.** 18,250 polls and 2,180 race results (1998–2022) from the archived 538 dataset, normalized, with a 593-entry pollster alias table. Coverage: [reports/history_coverage.md](reports/history_coverage.md).

| Phase | What | State |
|---|---|---|
| 0 | Repo, Pages, Action | ✅ |
| 1 | 538 history + results, pollster aliases | ✅ awaiting sign-off |
| 2 | Pollster scoring | next |
| 3 | Wikipedia scraper | |
| 4 | Senate model + backtest | |
| 5 | House model | |
| 6 | UI | |
| 7 | Daily automation | |
| 8 | Grade 2026 after results are certified | |

## Run locally

```bash
pip install -r requirements.txt
pytest -q
python -m pipeline.run_all
python -m http.server -d site 8000   # then open http://localhost:8000
```

Poll data from Wikipedia is used under CC BY-SA; sources are credited on the site's Method page.
