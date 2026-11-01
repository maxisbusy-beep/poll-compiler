# poll-compiler

Compiles public polls into **Senate and House control odds**, and grades every pollster on its track record (last same-type cycle, last two cycles, all time).

- Live site: https://maxisbusy-beep.github.io/poll-compiler/
- Full plan: [SPEC.md](SPEC.md)

## Status

**Phase 3 — Wikipedia polls.** 1,125 polls (2024) and 881 polls (2026) parsed from Wikipedia Senate and House pages, plus 397 race results for 2024. Pollsters now scored on 1998–2024 (491 pollsters, 6,946 final polls). Reports: [pollster scores](reports/pollster_scores.md), [data coverage](reports/history_coverage.md).

| Phase | What | State |
|---|---|---|
| 0 | Repo, Pages, Action | ✅ |
| 1 | 538 history + results, pollster aliases | ✅ |
| 2 | Pollster scoring | ✅ |
| 3 | Wikipedia scraper | ✅ awaiting sign-off |
| 4 | Senate model + backtest | next |
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
