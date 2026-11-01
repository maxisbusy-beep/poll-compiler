# Senate model backtest

Cycles 2004–2024, Senate general and special races with at least one poll, forecast as of 7 and 30 days before Election Day: **662 race-forecasts**. Pollster quality for each cycle comes only from earlier cycles. Win probabilities are scored out of sample (uncertainty fitted on the other cycles).

## Model vs naive baseline

| | Error of the average (RMSE, pts) | Brier (lower is better) | Log loss |
|---|---|---|---|
| **Model** | 6.97 | 0.0525 | 0.171 |
| Naive (plain mean of last 21 days) | 7.21 | 0.0573 | 0.186 |

**The model beats the baseline on every measure.**

## Calibration (model, out of sample)

| Forecast confidence | Races | Avg forecast | Favourite won |
|---|---|---|---|
| 50–60% | 43 | 56% | 72% |
| 60–70% | 49 | 65% | 71% |
| 70–80% | 47 | 76% | 77% |
| 80–90% | 63 | 86% | 94% |
| 90–95% | 57 | 93% | 96% |
| 95–99% | 112 | 97% | 100% |
| 99–100% | 291 | 100% | 100% |

## Chamber check (7 days out, polled races only)

Democratic wins among the races that had polls: forecast median and 80% range vs what happened.

| Cycle | Races | Forecast | 80% range | Actual | In range |
|---|---|---|---|---|---|
| 2004 | 27 | 14 | 12–16 | 12 | ✅ |
| 2006 | 29 | 21 | 19–23 | 22 | ✅ |
| 2008 | 35 | 19 | 17–21 | 20 | ✅ |
| 2010 | 36 | 12 | 10–15 | 13 | ✅ |
| 2012 | 28 | 19 | 15–22 | 21 | ✅ |
| 2014 | 34 | 15 | 12–18 | 12 | ✅ |
| 2016 | 33 | 14 | 11–17 | 12 | ✅ |
| 2018 | 32 | 22 | 19–25 | 22 | ✅ |
| 2020 | 30 | 15 | 12–18 | 11 | ❌ |
| 2022 | 30 | 14 | 11–18 | 16 | ✅ |
| 2024 | 32 | 18 | 15–21 | 18 | ✅ |

## Chosen settings

```yaml
half_life_days: 14
shrink_k: 10
quality_scale_s: 3.0
use_bias_correction: true
population_weight:
  LV: 1.0
  RV: 0.7
  A: 0.3
  ? ''
  : 0.85
default_sample: 600
sigma:
  a: 3.5
  b: 10
  c: 0.2
national_sd: 2.61
lean_sigma: 15.3
prior_weight: 0.5
```

## All settings tried (by error of the average)

| Half-life | Shrink k | Quality scale | Bias correction | Lean prior (polls) | RMSE |
|---|---|---|---|---|---|
| 14 | 10 | 3.0 | on | 0.5 | 6.970 |
| 14 | 10 | 6.0 | on | 0.5 | 6.976 |
| 14 | 25 | 3.0 | on | 0.5 | 6.979 |
| 14 | 10 | off | on | 0.5 | 6.983 |
| 28 | 10 | 3.0 | on | 0.5 | 6.987 |
| 7 | 10 | 3.0 | on | 0.5 | 6.992 |
| 28 | 10 | 6.0 | on | 0.5 | 6.993 |
| 28 | 25 | 3.0 | on | 0.5 | 6.996 |
| 7 | 10 | 6.0 | on | 0.5 | 6.997 |
| 7 | 25 | 3.0 | on | 0.5 | 7.001 |
| 28 | 10 | off | on | 0.5 | 7.002 |
| 14 | 10 | 3.0 | off | 0.5 | 7.002 |
| 7 | 10 | off | on | 0.5 | 7.002 |
| 14 | 25 | 3.0 | off | 0.5 | 7.003 |
| 14 | 10 | 6.0 | off | 0.5 | 7.009 |
| 14 | 10 | off | off | 0.5 | 7.017 |
| 28 | 10 | 3.0 | off | 0.5 | 7.020 |
| 28 | 25 | 3.0 | off | 0.5 | 7.022 |
| 7 | 10 | 3.0 | off | 0.5 | 7.025 |
| 7 | 25 | 3.0 | off | 0.5 | 7.026 |
| 28 | 10 | 6.0 | off | 0.5 | 7.028 |
| 7 | 10 | 6.0 | off | 0.5 | 7.030 |
| 7 | 10 | off | off | 0.5 | 7.037 |
| 28 | 10 | off | off | 0.5 | 7.037 |
| 14 | 25 | 3.0 | on | 0.0 | 7.078 |
