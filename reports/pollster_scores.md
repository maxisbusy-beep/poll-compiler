# Pollster scores

- Target cycle **2026** · scored polls **6,946** (one final poll per pollster per race, ≤21 days out) · races **1,863** · pollsters **491**
- Windows: Last midterm (2022); Last two cycles (2022, 2024); All time (1998–2024)

## Sanity check against 538

Rank correlation between our shrunk excess error and 538's POLLSCORE, for 64 pollsters with ≥20 scored races: **ρ = 0.52**

Both are 'lower is better'. A strong positive ρ means we rank pollsters much like 538 did, using a simpler method.

## Spot checks (all time)

| Pollster | n | Win-call | Avg error | Bias | Excess | Model weight | 538 POLLSCORE |
|---|---|---|---|---|---|---|---|
| The New York Times/Siena College | 97 | 75% | 3.99 | D+1.4 | -0.62 | 1.20 | -1.50 |
| Selzer & Co. | 35 | 89% | 2.70 | D+0.3 | -1.89 | 1.62 | -1.20 |
| Emerson College | 199 | 80% | 4.22 | D+0.5 | -0.68 | 1.24 | -1.10 |
| Trafalgar Group | 76 | 62% | 4.27 | R+3.1 | -0.18 | 1.05 | 0.60 |
| Rasmussen Reports | 362 | 85% | 4.64 | R+1.4 | 0.14 | 0.96 | -0.30 |
| SurveyUSA | 455 | 90% | 4.28 | R+0.5 | -0.50 | 1.18 | -1.30 |
| Quinnipiac University | 97 | 84% | 4.31 | D+0.8 | -0.32 | 1.10 | -0.50 |
| Public Policy Polling | 225 | 82% | 4.40 | D+1.3 | -0.45 | 1.15 | 0.00 |
| Marist College | 114 | 80% | 4.71 | D+1.1 | 0.09 | 0.97 | -0.90 |
| YouGov | 397 | 90% | 5.18 | D+1.1 | 0.08 | 0.98 | -1.10 |

## Best and worst, all time (≥20 scored races, by shrunk excess error)

| | Pollster | n | Avg error | Bias | Excess | Weight |
|---|---|---|---|---|---|---|
| best | Selzer & Co. | 35 | 2.70 | D+0.3 | -1.89 | 1.62 |
| best | AtlasIntel | 24 | 2.03 | D+0.1 | -1.88 | 1.56 |
| best | Dan Jones & Associates | 30 | 3.85 | D+0.9 | -1.69 | 1.50 |
| best | Cygnal | 38 | 3.96 | D+3.0 | -1.44 | 1.45 |
| best | Research & Polling Inc. | 46 | 4.02 | R+0.8 | -1.08 | 1.31 |
| best | ABC News/The Washington Post | 38 | 3.42 | D+2.6 | -0.81 | 1.24 |
| best | Emerson College | 199 | 4.22 | D+0.5 | -0.68 | 1.24 |
| best | Siena College | 56 | 5.61 | R+2.6 | -0.76 | 1.23 |
| worst | Swayable | 43 | 5.95 | D+5.4 | 0.63 | 0.84 |
| worst | McLaughlin & Associates | 22 | 6.73 | R+4.1 | 0.82 | 0.84 |
| worst | Mellman Group | 23 | 5.50 | D+5.0 | 0.79 | 0.83 |
| worst | Franklin & Marshall College Center for Opinion Research | 23 | 4.99 | D+1.2 | 0.83 | 0.83 |
| worst | SSRS | 31 | 5.19 | D+4.6 | 0.96 | 0.78 |
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

## Last two cycles (2022, 2024): pollsters with ≥5 scored races, by average error

| Pollster | n | Win-call | Avg error | Bias |
|---|---|---|---|---|
| OnMessage Inc. | 6 | 75% | 1.12 | R+0.2 |
| Suffolk University | 8 | 88% | 1.89 | R+0.1 |
| AtlasIntel | 12 | 79% | 1.93 | R+0.5 |
| Beacon Research/Shaw & Co. Research | 10 | 70% | 2.15 | R+0.4 |
| Echelon Insights | 10 | 70% | 2.17 | R+0.5 |
| Research & Polling Inc. | 8 | 100% | 2.47 | D+1.1 |
| Susquehanna Polling & Research Inc. | 7 | 43% | 2.90 | R+1.7 |
| The New York Times/Siena College | 20 | 88% | 2.95 | D+1.8 |
| Quinnipiac University | 6 | 83% | 2.99 | D+2.5 |
| Marist College | 14 | 86% | 3.27 | D+3.1 |
| Noble Predictive Insights | 9 | 67% | 3.35 | D+1.1 |
| Fabrizio, Lee & Associates | 7 | 79% | 3.45 | R+2.3 |
| Cygnal | 17 | 94% | 3.58 | D+1.8 |
| SSRS | 7 | 86% | 3.65 | D+3.3 |
| Research Co. | 32 | 88% | 3.68 | D+1.4 |
| Patriot Polling | 12 | 75% | 3.68 | R+2.9 |
| ActiVote | 16 | 94% | 3.69 | D+3.2 |
| Emerson College | 66 | 84% | 4.01 | R+0.2 |
| Mitchell Research & Communications | 5 | 80% | 4.06 | R+1.9 |
| Remington Research Group | 10 | 70% | 4.08 | R+2.6 |
| Data for Progress | 30 | 77% | 4.32 | R+1.9 |
| KAConsulting | 10 | 90% | 4.37 | R+4.3 |
| Civiqs | 17 | 88% | 4.42 | D+3.3 |
| InsiderAdvantage | 21 | 62% | 4.70 | R+2.2 |
| Targoz Market Research | 8 | 62% | 4.82 | R+4.8 |
| Rasmussen Reports | 8 | 88% | 4.86 | R+1.5 |
| Trafalgar Group | 32 | 56% | 5.04 | R+4.6 |
| Redfield & Wilton Strategies | 5 | 100% | 5.31 | D+5.3 |
| Siena College | 10 | 90% | 5.38 | D+4.5 |
| SurveyUSA | 17 | 94% | 5.43 | R+0.9 |
| Phillips Academy | 7 | 57% | 5.55 | R+3.5 |
| YouGov | 25 | 88% | 5.57 | D+4.6 |
| Saint Anselm College Survey Center | 6 | 67% | 5.60 | R+4.9 |
| Wick | 9 | 56% | 5.69 | R+4.6 |
| Morning Consult | 10 | 80% | 6.13 | D+5.2 |
| co/efficient | 14 | 54% | 6.39 | R+6.4 |
| Victory Insights | 5 | 100% | 7.32 | D+4.1 |
| University of North Florida Public Opinion Research Lab | 5 | 100% | 7.42 | D+7.4 |
| University of New Hampshire Survey Center | 16 | 94% | 7.80 | R+3.0 |
| Amber Integrated | 7 | 86% | 9.38 | D+7.8 |

Bias: average signed miss on the margin. **D+** = overstated the Democratic (or main non-Republican) side; **R+** = overstated the Republican.
