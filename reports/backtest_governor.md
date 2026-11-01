# Governor backtest

Past governor races with polls, 2004-2024, 7 and 30 days out (465 race-days). Poll averaging uses the Senate settings.

| Lean prior weight (effective polls) | Error (RMSE, pts) |
|---|---|
| 0.0 | 7.00 |
| 0.1 | 7.11 |
| 0.25 | 7.44 |
| 0.5 | 8.14 |
| 1.0 | 9.50 |

Chosen prior weight: **0.0**.
Uncertainty: a=3.0, b=10, c=0.2.
Lean alone misses by 20.76 pts (RMSE), used for races with no polls.
Leader 7 days out won 218 of 241 races.
Probability scores (out of sample by cycle): {'brier': 0.06841496781441792, 'logloss': 0.22312148266343287, 'n': 465, 'calibration': [{'bucket': '50–60%', 'n': 39, 'forecast': 0.5490888689382412, 'won': 0.5128205128205128}, {'bucket': '60–70%', 'n': 29, 'forecast': 0.6465480174667713, 'won': 0.7586206896551724}, {'bucket': '70–80%', 'n': 52, 'forecast': 0.7468675785017804, 'won': 0.75}, {'bucket': '80–90%', 'n': 51, 'forecast': 0.8465128589612632, 'won': 0.9607843137254902}, {'bucket': '90–95%', 'n': 46, 'forecast': 0.9273990674617562, 'won': 0.9565217391304348}, {'bucket': '95–99%', 'n': 73, 'forecast': 0.9754942120355203, 'won': 0.9863013698630136}, {'bucket': '99–100%', 'n': 175, 'forecast': 0.9981904179585076, 'won': 0.9942857142857143}]}
