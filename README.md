# poll-compiler

Compiles public polls into **Senate and House control odds**, and grades every pollster on its track record (last same-type cycle, last two cycles, all time).

- Live site: https://maxisbusy-beep.github.io/poll-compiler/
- Full plan: [SPEC.md](SPEC.md)

## Status

**Phase 2 — pollster scoring.** 468 pollsters graded on 6,685 final polls across 1,802 races (1998–2022): win-call %, average error, bias and excess error, for the last same-type cycle, the last two cycles and all time. Report: [reports/pollster_scores.md](reports/pollster_scores.md). Data coverage: [reports/history_coverage.md](reports/history_coverage.md).

| Phase | What | State |
|---|---|---|
| 0 | Repo, Pages, Action | ✅ |
| 1 | 538 history + results, pollster aliases | ✅ |
| 2 | Pollster scoring | ✅ awaiting sign-off |
| 3 | Wikipedia scraper | next |
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
