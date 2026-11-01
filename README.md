# poll-compiler

Compiles public polls into **Senate and House control odds**, and grades every pollster on its track record (last same-type cycle, last two cycles, all time).

- Live site: https://maxisbusy-beep.github.io/poll-compiler/
- Full plan: [SPEC.md](SPEC.md)

## Status

**Election-ready.** Senate map and House district map (Census 2026 lines) with odds from polls + partisan lean (Senate backtested 2004–2024; see [backtest](reports/backtest.md)). Polls refresh from Wikipedia every 6 hours. On election night (from 23:00 Berlin, Nov 3) the page reads live results from Wikipedia every 3 minutes: votes, approximate % counted, calls, and control odds with called races locked in. Test it any time with `?live=2024`, which replays the 2024 results.

| Phase | What | State |
|---|---|---|
| 0 | Repo, Pages, Action | ✅ |
| 1 | 538 history + results, pollster aliases | ✅ |
| 2 | Pollster scoring | ✅ |
| 3 | Wikipedia scraper | ✅ |
| 4 | Senate model + backtest | ✅ |
| 5 | House model (not yet backtested) | ✅ |
| 6 | UI: Senate map, House district map, race sheets, live results | ✅ |
| 7 | Poll refresh every 6 hours | ✅ |
| 8 | Grade 2026 after results are certified | |

## Run locally

```bash
pip install -r requirements.txt
pytest -q
python -m pipeline.run_all
python -m http.server -d site 8000   # then open http://localhost:8000
```

Poll data from Wikipedia is used under CC BY-SA; sources are credited on the site's Method page.
