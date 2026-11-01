# Pollster scores

- Target cycle **2026** · scored polls **7,211** (one final poll per pollster per race, ≤21 days out) · races **1,908** · pollsters **495**
- Windows: Last midterm (2022); Last two cycles (2022, 2024); All time (1998–2024)

## Sanity check against 538

Rank correlation between our shrunk excess error and 538's POLLSCORE, for 65 pollsters with ≥20 scored races: **ρ = 0.48**

Both are 'lower is better'. A strong positive ρ means we rank pollsters much like 538 did, using a simpler method.

## Spot checks (all time)

| Pollster | n | Win-call | Avg error | Bias | Excess | Model weight | 538 POLLSCORE |
|---|---|---|---|---|---|---|---|
| The New York Times/Siena College | 107 | 73% | 3.94 | D+1.6 | -0.48 | 1.15 | -1.50 |
| Selzer & Co. | 35 | 89% | 2.70 | D+0.3 | -1.89 | 1.62 | -1.20 |
| Emerson College | 216 | 81% | 4.09 | D+0.6 | -0.70 | 1.25 | -1.10 |
| Trafalgar Group | 84 | 64% | 4.04 | R+2.6 | -0.23 | 1.07 | 0.60 |
| Rasmussen Reports | 374 | 85% | 4.56 | R+1.3 | 0.12 | 0.96 | -0.30 |
| SurveyUSA | 460 | 90% | 4.26 | R+0.5 | -0.50 | 1.17 | -1.30 |
| Quinnipiac University | 100 | 83% | 4.24 | D+0.8 | -0.31 | 1.10 | -0.50 |
| Public Policy Polling | 227 | 82% | 4.39 | D+1.2 | -0.44 | 1.15 | 0.00 |
| Marist College | 121 | 78% | 4.60 | D+1.2 | 0.12 | 0.96 | -0.90 |
| YouGov | 414 | 89% | 5.16 | D+1.3 | 0.12 | 0.96 | -1.10 |

## Best and worst, all time (≥20 scored races, by shrunk excess error)

| | Pollster | n | Avg error | Bias | Excess | Weight |
|---|---|---|---|---|---|---|
| best | Selzer & Co. | 35 | 2.70 | D+0.3 | -1.89 | 1.62 |
| best | AtlasIntel | 37 | 1.66 | D+0.2 | -1.75 | 1.58 |
| best | Cygnal | 40 | 4.01 | D+3.1 | -1.56 | 1.50 |
| best | Dan Jones & Associates | 30 | 3.85 | D+0.9 | -1.69 | 1.50 |
| best | Research & Polling Inc. | 46 | 4.02 | R+0.8 | -1.08 | 1.31 |
| best | Emerson College | 216 | 4.09 | D+0.6 | -0.70 | 1.25 |
| best | ABC News/The Washington Post | 38 | 3.42 | D+2.6 | -0.81 | 1.24 |
| best | Siena College | 57 | 5.62 | R+2.4 | -0.71 | 1.21 |
| worst | Swayable | 43 | 5.95 | D+5.4 | 0.63 | 0.84 |
| worst | McLaughlin & Associates | 22 | 6.73 | R+4.1 | 0.82 | 0.84 |
| worst | Mellman Group | 23 | 5.50 | D+5.0 | 0.79 | 0.83 |
| worst | Franklin & Marshall College Center for Opinion Research | 23 | 4.99 | D+1.2 | 0.83 | 0.83 |
| worst | Zogby Analytics | 183 | 5.80 | R+0.7 | 0.78 | 0.78 |
| worst | SSRS | 33 | 5.11 | D+4.6 | 1.03 | 0.77 |
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
| OnMessage Inc. | 10 | 80% | 1.11 | D+0.2 |
| AtlasIntel | 25 | 90% | 1.43 | R+0.0 |
| Suffolk University | 8 | 88% | 1.89 | R+0.1 |
| Beacon Research/Shaw & Co. Research | 14 | 75% | 1.93 | D+0.1 |
| Echelon Insights | 13 | 69% | 2.17 | R+0.5 |
| SoCal Strategies | 7 | 79% | 2.27 | D+2.3 |
| Research & Polling Inc. | 8 | 100% | 2.47 | D+1.1 |
| Quinnipiac University | 9 | 72% | 2.72 | D+2.4 |
| Patriot Polling | 19 | 79% | 2.85 | R+1.3 |
| The New York Times/Siena College | 30 | 75% | 3.11 | D+2.4 |
| Marist College | 21 | 74% | 3.12 | D+3.0 |
| Susquehanna Polling & Research Inc. | 10 | 45% | 3.13 | R+0.7 |
| ActiVote | 41 | 91% | 3.21 | D+3.0 |
| Public Policy Polling | 5 | 100% | 3.22 | R+3.2 |
| Rasmussen Reports | 20 | 90% | 3.34 | R+0.5 |
| Fabrizio, Lee & Associates | 7 | 79% | 3.45 | R+2.3 |
| The Washington Post/George Mason University Schar School of Policy and Government | 8 | 44% | 3.51 | D+3.5 |
| HarrisX | 9 | 67% | 3.54 | D+0.9 |
| Cygnal | 19 | 95% | 3.72 | D+2.1 |
| Emerson College | 83 | 85% | 3.72 | D+0.2 |
| SSRS | 9 | 78% | 3.73 | D+3.4 |
| Noble Predictive Insights | 11 | 64% | 3.79 | D+1.9 |
| RMG Research | 5 | 90% | 3.82 | D+3.8 |
| Mitchell Research & Communications | 7 | 71% | 3.89 | R+0.3 |
| Research Co. | 44 | 84% | 3.99 | D+2.4 |
| Mainstreet Research | 8 | 50% | 3.99 | D+4.0 |
| InsiderAdvantage | 29 | 69% | 4.01 | R+1.0 |
| Data for Progress | 31 | 74% | 4.35 | R+1.7 |
| KAConsulting | 10 | 90% | 4.37 | R+4.3 |
| Trafalgar Group | 40 | 61% | 4.39 | R+3.3 |
| Civiqs | 17 | 88% | 4.42 | D+3.3 |
| Morning Consult | 22 | 77% | 4.51 | D+4.1 |
| SurveyUSA | 22 | 93% | 4.57 | R+0.3 |
| Remington Research Group | 11 | 73% | 4.57 | R+1.5 |
| Targoz Market Research | 8 | 62% | 4.82 | R+4.8 |
| Redfield & Wilton Strategies | 7 | 93% | 5.01 | D+3.1 |
| YouGov | 42 | 83% | 5.25 | D+4.5 |
| Siena College | 11 | 91% | 5.48 | D+4.7 |
| Phillips Academy | 7 | 57% | 5.55 | R+3.5 |
| Wick | 9 | 56% | 5.69 | R+4.6 |
| Saint Anselm College Survey Center | 7 | 71% | 5.70 | R+3.3 |
| co/efficient | 14 | 54% | 6.39 | R+6.4 |
| Victory Insights | 8 | 100% | 6.42 | D+4.1 |
| University of North Florida Public Opinion Research Lab | 6 | 100% | 6.70 | D+6.7 |
| University of New Hampshire Survey Center | 21 | 95% | 7.05 | R+1.2 |
| Amber Integrated | 7 | 86% | 9.38 | D+7.8 |

Bias: average signed miss on the margin. **D+** = overstated the Democratic (or main non-Republican) side; **R+** = overstated the Republican.
