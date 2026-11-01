# poll-compiler

Compiles public polls into **Senate and House control odds**, and grades every pollster on its track record (last same-type cycle, last two cycles, all time).

- Live site: https://maxisbusy-beep.github.io/poll-compiler/
- Full plan: [SPEC.md](SPEC.md)

## Status

**Phase 0 — skeleton.** Folder layout, placeholder page, smoke tests, and a GitHub Action that tests, builds and deploys to Pages on every push.

| Phase | What | State |
|---|---|---|
| 0 | Repo, Pages, Action | ✅ |
| 1 | 538 history + results, pollster aliases | next |
| 2 | Pollster scoring | |
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
