# Pollster scores — Phase 2 gate

- Target cycle **2026** · scored polls **6,685** (one final poll per pollster per race, ≤21 days out) · races **1,802** · pollsters **468**
- Windows: Last midterm (2022); Last two cycles (2022, 2024) — **2024 not loaded yet**; All time (1998–2022)

## Sanity check against 538

Rank correlation between our shrunk excess error and 538's POLLSCORE, for 61 pollsters with ≥20 scored races: **ρ = 0.53**

Both are 'lower is better'. A strong positive ρ means we rank pollsters much like 538 did, using a simpler method.

## Spot checks (all time)

| Pollster | n | Win-call | Avg error | Bias | Excess | Model weight | 538 POLLSCORE |
|---|---|---|---|---|---|---|---|
| The New York Times/Siena College | 89 | 74% | 3.94 | D+1.1 | -0.75 | 1.25 | -1.50 |
| Selzer & Co. | 35 | 89% | 2.70 | D+0.3 | -1.89 | 1.62 | -1.20 |
| Emerson College | 181 | 79% | 4.29 | D+0.3 | -0.69 | 1.24 | -1.10 |
| Trafalgar Group | 70 | 61% | 4.52 | R+3.4 | -0.03 | 1.01 | 0.60 |
| Rasmussen Reports | 359 | 85% | 4.64 | R+1.4 | 0.14 | 0.96 | -0.30 |
| SurveyUSA | 450 | 90% | 4.20 | R+0.5 | -0.52 | 1.18 | -1.30 |
| Quinnipiac University | 94 | 85% | 4.33 | D+0.7 | -0.35 | 1.11 | -0.50 |
| Public Policy Polling | 223 | 82% | 4.42 | D+1.3 | -0.45 | 1.16 | 0.00 |
| Marist College | 110 | 80% | 4.74 | D+1.0 | 0.06 | 0.98 | -0.90 |
| YouGov | 381 | 90% | 5.13 | D+0.9 | 0.03 | 0.99 | -1.10 |

## Best and worst, all time (≥20 scored races, by shrunk excess error)

| | Pollster | n | Avg error | Bias | Excess | Weight |
|---|---|---|---|---|---|---|
| best | Selzer & Co. | 35 | 2.70 | D+0.3 | -1.89 | 1.62 |
| best | Dan Jones & Associates | 30 | 3.85 | D+0.9 | -1.69 | 1.50 |
| best | Cygnal | 32 | 3.80 | D+2.7 | -1.50 | 1.45 |
| best | Siena College | 53 | 5.46 | R+3.2 | -0.94 | 1.28 |
| best | Research & Polling Inc. | 42 | 4.17 | R+1.1 | -1.00 | 1.28 |
| best | The New York Times/Siena College | 89 | 3.94 | D+1.1 | -0.75 | 1.25 |
| best | Emerson College | 181 | 4.29 | D+0.3 | -0.69 | 1.24 |
| best | ABC News/The Washington Post | 38 | 3.42 | D+2.6 | -0.81 | 1.24 |
| worst | Swayable | 43 | 5.95 | D+5.4 | 0.63 | 0.84 |
| worst | McLaughlin & Associates | 21 | 6.61 | R+3.8 | 0.82 | 0.84 |
| worst | Mellman Group | 23 | 5.50 | D+5.0 | 0.79 | 0.83 |
| worst | Franklin & Marshall College Center for Opinion Research | 22 | 5.16 | D+1.2 | 0.95 | 0.81 |
| worst | SSRS | 26 | 5.30 | D+4.6 | 0.90 | 0.80 |
| worst | Zogby Analytics | 183 | 5.80 | R+0.7 | 0.78 | 0.78 |
| worst | Global Strategy Group | 24 | 5.82 | D+3.2 | 1.23 | 0.75 |
| worst | Targoz Market Research | 24 | 5.92 | D+2.2 | 1.36 | 0.73 |

## Last midterm (2022): pollsters with ≥5 scored races, by average error

| Pollster | n | Win-call | Avg error | Bias |
|---|---|---|---|---|
| Suffolk University | 5 | 100% | 1.82 | R+1.3 |
| The New York Times/Siena College | 12 | 88% | 1.90 | D+0.0 |
| Beacon Research/Shaw & Co. Research | 8 | 75% | 1.96 | R+1.3 |
| Echelon Insights | 7 | 57% | 2.44 | R+0.5 |
| SurveyUSA | 12 | 100% | 2.57 | R+0.2 |
| Cygnal | 11 | 91% | 2.91 | D+0.1 |
| Marist College | 10 | 90% | 3.01 | D+2.8 |
| Noble Predictive Insights | 5 | 60% | 3.38 | R+0.7 |
| Research Co. | 21 | 86% | 3.41 | D+0.0 |
| Fabrizio, Lee & Associates | 7 | 79% | 3.45 | R+2.3 |
| Remington Research Group | 10 | 70% | 4.08 | R+2.6 |
| Siena College | 7 | 86% | 4.16 | D+2.9 |
| Emerson College | 48 | 81% | 4.20 | R+1.3 |
| YouGov | 9 | 100% | 4.30 | D+1.7 |
| Data for Progress | 27 | 78% | 4.35 | R+2.6 |
| KAConsulting | 10 | 90% | 4.37 | R+4.3 |
| Civiqs | 17 | 88% | 4.42 | D+3.3 |
| Targoz Market Research | 8 | 62% | 4.82 | R+4.8 |
| Rasmussen Reports | 5 | 80% | 5.09 | R+5.1 |
| University of New Hampshire Survey Center | 7 | 100% | 5.53 | R+4.5 |
| Phillips Academy | 7 | 57% | 5.55 | R+3.5 |
| Patriot Polling | 7 | 71% | 5.59 | R+5.6 |
| Wick | 9 | 56% | 5.69 | R+4.6 |
| InsiderAdvantage | 16 | 66% | 5.78 | R+3.0 |
| Trafalgar Group | 26 | 54% | 5.89 | R+5.6 |
| co/efficient | 13 | 58% | 6.63 | R+6.6 |
| Amber Integrated | 7 | 86% | 9.38 | D+7.8 |

Bias: average signed miss on the margin. **D+** = overstated the Democratic (or main non-Republican) side; **R+** = overstated the Republican.
