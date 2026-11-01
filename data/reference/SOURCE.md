# Silver Bulletin pollster ratings (display only)

- File: `silver_bulletin_pollster_stats_2026.xlsx` ("Pollster Stats Full 2026"), supplied by the owner on 2026-11-01
- From: https://www.natesilver.net/p/pollster-ratings-silver-bulletin (January 2026 update)
- © Nate Silver / Silver Bulletin. Used only to show each pollster's letter grade, with attribution on the site.
  The grades do not feed any weight in our model (they are built on data through 2024, so using them would
  leak information into our backtest).
- `silver_grades.csv` is produced by `python tools/load_silver_grades.py` (matches on the 538 rating id, then name).
