# Evaluation report: m3-improvements

_Generated 2026-10-11 by `evaluation/harness.py`._

## What was run

- **Units:** 400 synthetic woreda-scale units (seeded, illustrative); median population 107,994.
- **Simulator:** IDM laser-measles biweekly SIR, split into weeks; Ethiopia crude birth rate 31.9/1,000.
- **Reporting layer:** per-unit reporting rates, 0-4 week delays, ~10% missing weeks, ~15% backfilled 4-12 weeks late.
- **True outbreak onset:** 4-week true infections reach 20 per 100,000 after 8+ weeks below 5 per 100,000. **Large** outbreaks reach 100 true infections per 100,000 within 12 weeks of onset.
- **Detection:** EPHI measles thresholds applied each week to the data visible that week. A detection is a new episode within 4 weeks before to 8 weeks after onset. PPV: share of episodes starting while true transmission was under way (4-week true infections >= 20 per 100,000).
- **Risk ranking:** each month, the top 10% of units by each ranking, scored against two targets: the units with the highest true incidence next quarter, and (among units reporting no cases) the units where a new outbreak starts next quarter. The simulator's true susceptible pool is shown as a reference: the best a ranking on susceptibility alone could do.

## Results

### gravity

_Simulator mixing is gravity (laser defaults); our model uses its own gravity exponents_ · mixing `gravity`, mean reporting rate 12%, 572 weeks scored, 826 true outbreaks (399 large).

| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |
|---|---|---|---|---|---|---|
| Action threshold, all outbreaks | 826 | 33% | 92% | 0.09 | 21 | 16% |
| Action threshold, large outbreaks | 399 | 46% | 92% | 0.09 | 28 | 9% |
| Alert threshold, all outbreaks | 826 | 73% | 83% | 0.57 | 7 | 44% |
| Alert threshold, large outbreaks | 399 | 79% | 83% | 0.57 | 7 | 41% |
| EWMA flag, all outbreaks | 826 | 20% | 91% | 0.04 | 14 | 33% |
| Space-time scan (every 4th week), all outbreaks | 826 | 21% | 81% | 0.16 | 14 | 38% |
| Space-time scan (every 4th week), large outbreaks | 399 | 27% | 81% | 0.16 | 14 | 41% |

**Risk ranking: top 10% vs the 10% of units with the highest true incidence next quarter (all units)** (base rate 10%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 50% | 50% |
| Risk index (3-month horizon) | 51% | 51% |
| Risk index, settings fitted on warm-up years | 53% | 53% |
| Risk index, susceptibles half coverage-anchored | 52% | 52% |
| Risk index, depletion capped at 30%/month | 51% | 51% |
| Risk index without nowcasting (ablation) | 51% | 51% |
| Our susceptible share alone (ablation) | 15% | 15% |
| Challenger: gradient-boosted trees | 62% | 62% |
| **Hybrid: count regression + risk-model covariates** | 65% | 65% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 62% | 62% |
| Challenger: ARIMA(1,0,0) on log counts | 49% | 49% |
| Challenger: EWMA of reported incidence | 47% | 47% |
| Challenger: reported incidence, last 3 months | 54% | 54% |
| Baseline: lowest MCV1 | 29% | 29% |
| Baseline: most cases last 12 months | 25% | 25% |
| Baseline: random | 10% | 10% |
| _Reference: simulator's true susceptibles_ | 27% | 27% |
| _Reference: true recent infections (perfect nowcast)_ | 71% | 71% |
| _Reference: risk formula with true inputs (its ceiling)_ | 55% | 55% |

**Risk ranking: top 10% vs the top 20% by true incidence next quarter (near misses count)** (base rate 20%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 78% | 39% |
| Risk index (3-month horizon) | 79% | 39% |
| Risk index, settings fitted on warm-up years | 80% | 40% |
| Risk index, susceptibles half coverage-anchored | 81% | 40% |
| Risk index, depletion capped at 30%/month | 79% | 39% |
| Risk index without nowcasting (ablation) | 79% | 39% |
| Our susceptible share alone (ablation) | 29% | 14% |
| Challenger: gradient-boosted trees | 86% | 43% |
| **Hybrid: count regression + risk-model covariates** | 89% | 44% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 86% | 43% |
| Challenger: ARIMA(1,0,0) on log counts | 74% | 37% |
| Challenger: EWMA of reported incidence | 70% | 35% |
| Challenger: reported incidence, last 3 months | 79% | 39% |
| Baseline: lowest MCV1 | 44% | 22% |
| Baseline: most cases last 12 months | 46% | 23% |
| Baseline: random | 20% | 10% |
| _Reference: simulator's true susceptibles_ | 42% | 21% |
| _Reference: true recent infections (perfect nowcast)_ | 93% | 47% |
| _Reference: risk formula with true inputs (its ceiling)_ | 84% | 42% |

**Risk ranking: top 10% vs a new outbreak next quarter, among units with no reported case in the last 2 months** (base rate 15%, 128 months, median k 6)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 11% | 6% |
| Risk index (3-month horizon) | 10% | 6% |
| Risk index, settings fitted on warm-up years | 15% | 10% |
| Risk index, susceptibles half coverage-anchored | 12% | 6% |
| Risk index, depletion capped at 30%/month | 11% | 6% |
| Risk index without nowcasting (ablation) | 10% | 5% |
| Our susceptible share alone (ablation) | 13% | 8% |
| Challenger: gradient-boosted trees | 12% | 8% |
| **Hybrid: count regression + risk-model covariates** | 11% | 7% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 12% | 7% |
| Challenger: ARIMA(1,0,0) on log counts | 12% | 7% |
| Challenger: EWMA of reported incidence | 8% | 5% |
| Challenger: reported incidence, last 3 months | 6% | 4% |
| Baseline: lowest MCV1 | 19% | 14% |
| Baseline: most cases last 12 months | 9% | 5% |
| Baseline: random | 16% | 10% |
| _Reference: simulator's true susceptibles_ | 26% | 19% |
| _Reference: true recent infections (perfect nowcast)_ | 1% | 0% |
| _Reference: risk formula with true inputs (its ceiling)_ | 2% | 1% |

Ignitions whose unit was in the top 10% of quiet units one month before: 10%; three months before: 5%.

Reconstruction: reporting rate estimated for 400 units, median absolute error 0.016 (true median 0.112), rank correlation 0.89; susceptible-share rank correlation with truth 0.26.
Fitted settings (warm-up years, reported data): {'precision': 0.5154761904761905, 'c': 1.0, 'background': 0.01, 's_anchor_weight': 0.5, 'months_used': 21}.

### radiation

_Mis-specified: simulator uses radiation mixing_ · mixing `radiation`, mean reporting rate 12%, 572 weeks scored, 834 true outbreaks (424 large).

| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |
|---|---|---|---|---|---|---|
| Action threshold, all outbreaks | 834 | 36% | 92% | 0.08 | 21 | 20% |
| Action threshold, large outbreaks | 424 | 46% | 92% | 0.08 | 21 | 19% |
| Alert threshold, all outbreaks | 834 | 75% | 82% | 0.59 | 7 | 45% |
| Alert threshold, large outbreaks | 424 | 79% | 82% | 0.59 | 7 | 44% |
| EWMA flag, all outbreaks | 834 | 24% | 91% | 0.04 | 10 | 35% |

**Risk ranking: top 10% vs the 10% of units with the highest true incidence next quarter (all units)** (base rate 10%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 52% | 52% |
| Risk index (3-month horizon) | 53% | 53% |
| Risk index, settings fitted on warm-up years | 54% | 54% |
| Risk index, susceptibles half coverage-anchored | 54% | 54% |
| Risk index, depletion capped at 30%/month | 53% | 53% |
| Risk index without nowcasting (ablation) | 53% | 53% |
| Our susceptible share alone (ablation) | 18% | 18% |
| Challenger: gradient-boosted trees | 60% | 60% |
| **Hybrid: count regression + risk-model covariates** | 62% | 62% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 59% | 59% |
| Challenger: ARIMA(1,0,0) on log counts | 49% | 49% |
| Challenger: EWMA of reported incidence | 46% | 46% |
| Challenger: reported incidence, last 3 months | 52% | 52% |
| Baseline: lowest MCV1 | 28% | 28% |
| Baseline: most cases last 12 months | 26% | 26% |
| Baseline: random | 10% | 10% |
| _Reference: simulator's true susceptibles_ | 26% | 26% |
| _Reference: true recent infections (perfect nowcast)_ | 71% | 71% |
| _Reference: risk formula with true inputs (its ceiling)_ | 58% | 58% |

**Risk ranking: top 10% vs the top 20% by true incidence next quarter (near misses count)** (base rate 20%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 76% | 38% |
| Risk index (3-month horizon) | 77% | 39% |
| Risk index, settings fitted on warm-up years | 78% | 39% |
| Risk index, susceptibles half coverage-anchored | 79% | 40% |
| Risk index, depletion capped at 30%/month | 77% | 39% |
| Risk index without nowcasting (ablation) | 77% | 39% |
| Our susceptible share alone (ablation) | 30% | 15% |
| Challenger: gradient-boosted trees | 85% | 42% |
| **Hybrid: count regression + risk-model covariates** | 87% | 44% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 84% | 42% |
| Challenger: ARIMA(1,0,0) on log counts | 74% | 37% |
| Challenger: EWMA of reported incidence | 69% | 34% |
| Challenger: reported incidence, last 3 months | 77% | 39% |
| Baseline: lowest MCV1 | 40% | 20% |
| Baseline: most cases last 12 months | 44% | 22% |
| Baseline: random | 20% | 10% |
| _Reference: simulator's true susceptibles_ | 40% | 20% |
| _Reference: true recent infections (perfect nowcast)_ | 93% | 46% |
| _Reference: risk formula with true inputs (its ceiling)_ | 83% | 42% |

**Risk ranking: top 10% vs a new outbreak next quarter, among units with no reported case in the last 2 months** (base rate 15%, 124 months, median k 6)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 9% | 7% |
| Risk index (3-month horizon) | 9% | 6% |
| Risk index, settings fitted on warm-up years | 16% | 13% |
| Risk index, susceptibles half coverage-anchored | 9% | 6% |
| Risk index, depletion capped at 30%/month | 9% | 7% |
| Risk index without nowcasting (ablation) | 9% | 7% |
| Our susceptible share alone (ablation) | 14% | 9% |
| Challenger: gradient-boosted trees | 10% | 7% |
| **Hybrid: count regression + risk-model covariates** | 10% | 8% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 12% | 9% |
| Challenger: ARIMA(1,0,0) on log counts | 15% | 10% |
| Challenger: EWMA of reported incidence | 6% | 3% |
| Challenger: reported incidence, last 3 months | 6% | 5% |
| Baseline: lowest MCV1 | 19% | 14% |
| Baseline: most cases last 12 months | 6% | 3% |
| Baseline: random | 14% | 9% |
| _Reference: simulator's true susceptibles_ | 27% | 21% |
| _Reference: true recent infections (perfect nowcast)_ | 1% | 0% |
| _Reference: risk formula with true inputs (its ceiling)_ | 2% | 2% |

Ignitions whose unit was in the top 10% of quiet units one month before: 10%; three months before: 5%.

Reconstruction: reporting rate estimated for 400 units, median absolute error 0.014 (true median 0.112), rank correlation 0.89; susceptible-share rank correlation with truth 0.27.
Fitted settings (warm-up years, reported data): {'precision': 0.4666666666666668, 'c': 1.0, 'background': 0.01, 's_anchor_weight': 0.0, 'months_used': 21}.

### stouffer

_Mis-specified: simulator uses intervening-opportunities mixing_ · mixing `stouffer`, mean reporting rate 12%, 572 weeks scored, 728 true outbreaks (375 large).

| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |
|---|---|---|---|---|---|---|
| Action threshold, all outbreaks | 728 | 36% | 92% | 0.10 | 21 | 24% |
| Action threshold, large outbreaks | 375 | 45% | 92% | 0.10 | 28 | 19% |
| Alert threshold, all outbreaks | 728 | 77% | 84% | 0.57 | 7 | 46% |
| Alert threshold, large outbreaks | 375 | 79% | 84% | 0.57 | 7 | 43% |
| EWMA flag, all outbreaks | 728 | 25% | 90% | 0.05 | 14 | 31% |

**Risk ranking: top 10% vs the 10% of units with the highest true incidence next quarter (all units)** (base rate 10%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 50% | 50% |
| Risk index (3-month horizon) | 51% | 51% |
| Risk index, settings fitted on warm-up years | 54% | 54% |
| Risk index, susceptibles half coverage-anchored | 54% | 54% |
| Risk index, depletion capped at 30%/month | 52% | 52% |
| Risk index without nowcasting (ablation) | 51% | 51% |
| Our susceptible share alone (ablation) | 18% | 18% |
| Challenger: gradient-boosted trees | 58% | 58% |
| **Hybrid: count regression + risk-model covariates** | 61% | 61% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 59% | 59% |
| Challenger: ARIMA(1,0,0) on log counts | 48% | 48% |
| Challenger: EWMA of reported incidence | 45% | 45% |
| Challenger: reported incidence, last 3 months | 52% | 52% |
| Baseline: lowest MCV1 | 31% | 31% |
| Baseline: most cases last 12 months | 26% | 26% |
| Baseline: random | 10% | 10% |
| _Reference: simulator's true susceptibles_ | 28% | 28% |
| _Reference: true recent infections (perfect nowcast)_ | 70% | 70% |
| _Reference: risk formula with true inputs (its ceiling)_ | 57% | 57% |

**Risk ranking: top 10% vs the top 20% by true incidence next quarter (near misses count)** (base rate 20%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 76% | 38% |
| Risk index (3-month horizon) | 76% | 38% |
| Risk index, settings fitted on warm-up years | 78% | 39% |
| Risk index, susceptibles half coverage-anchored | 78% | 39% |
| Risk index, depletion capped at 30%/month | 76% | 38% |
| Risk index without nowcasting (ablation) | 76% | 38% |
| Our susceptible share alone (ablation) | 31% | 16% |
| Challenger: gradient-boosted trees | 83% | 41% |
| **Hybrid: count regression + risk-model covariates** | 84% | 42% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 82% | 41% |
| Challenger: ARIMA(1,0,0) on log counts | 72% | 36% |
| Challenger: EWMA of reported incidence | 68% | 34% |
| Challenger: reported incidence, last 3 months | 76% | 38% |
| Baseline: lowest MCV1 | 48% | 24% |
| Baseline: most cases last 12 months | 46% | 23% |
| Baseline: random | 20% | 10% |
| _Reference: simulator's true susceptibles_ | 43% | 22% |
| _Reference: true recent infections (perfect nowcast)_ | 92% | 46% |
| _Reference: risk formula with true inputs (its ceiling)_ | 82% | 41% |

**Risk ranking: top 10% vs a new outbreak next quarter, among units with no reported case in the last 2 months** (base rate 17%, 113 months, median k 4)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 5% | 3% |
| Risk index (3-month horizon) | 5% | 3% |
| Risk index, settings fitted on warm-up years | 10% | 6% |
| Risk index, susceptibles half coverage-anchored | 6% | 3% |
| Risk index, depletion capped at 30%/month | 5% | 3% |
| Risk index without nowcasting (ablation) | 5% | 3% |
| Our susceptible share alone (ablation) | 9% | 6% |
| Challenger: gradient-boosted trees | 9% | 5% |
| **Hybrid: count regression + risk-model covariates** | 6% | 3% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 6% | 3% |
| Challenger: ARIMA(1,0,0) on log counts | 15% | 10% |
| Challenger: EWMA of reported incidence | 5% | 3% |
| Challenger: reported incidence, last 3 months | 4% | 2% |
| Baseline: lowest MCV1 | 12% | 8% |
| Baseline: most cases last 12 months | 9% | 4% |
| Baseline: random | 17% | 10% |
| _Reference: simulator's true susceptibles_ | 24% | 14% |
| _Reference: true recent infections (perfect nowcast)_ | 0% | 0% |
| _Reference: risk formula with true inputs (its ceiling)_ | 1% | 1% |

Ignitions whose unit was in the top 10% of quiet units one month before: 6%; three months before: 4%.

Reconstruction: reporting rate estimated for 400 units, median absolute error 0.015 (true median 0.112), rank correlation 0.89; susceptible-share rank correlation with truth 0.20.
Fitted settings (warm-up years, reported data): {'precision': 0.48571428571428577, 'c': 1.0, 'background': 0.01, 's_anchor_weight': 0.5, 'months_used': 21}.

### low-reporting

_Only ~5% of infections reported_ · mixing `gravity`, mean reporting rate 5%, 572 weeks scored, 788 true outbreaks (377 large).

| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |
|---|---|---|---|---|---|---|
| Action threshold, all outbreaks | 788 | 10% | 97% | 0.02 | 28 | 17% |
| Action threshold, large outbreaks | 377 | 12% | 97% | 0.02 | 35 | 16% |
| Alert threshold, all outbreaks | 788 | 44% | 88% | 0.27 | 14 | 36% |
| Alert threshold, large outbreaks | 377 | 47% | 88% | 0.27 | 14 | 34% |
| EWMA flag, all outbreaks | 788 | 9% | 96% | 0.01 | 14 | 24% |

**Risk ranking: top 10% vs the 10% of units with the highest true incidence next quarter (all units)** (base rate 10%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 44% | 44% |
| Risk index (3-month horizon) | 45% | 45% |
| Risk index, settings fitted on warm-up years | 49% | 49% |
| Risk index, susceptibles half coverage-anchored | 48% | 48% |
| Risk index, depletion capped at 30%/month | 45% | 45% |
| Risk index without nowcasting (ablation) | 44% | 44% |
| Our susceptible share alone (ablation) | 20% | 20% |
| Challenger: gradient-boosted trees | 44% | 44% |
| **Hybrid: count regression + risk-model covariates** | 46% | 46% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 44% | 44% |
| Challenger: ARIMA(1,0,0) on log counts | 37% | 37% |
| Challenger: EWMA of reported incidence | 37% | 37% |
| Challenger: reported incidence, last 3 months | 41% | 41% |
| Baseline: lowest MCV1 | 30% | 30% |
| Baseline: most cases last 12 months | 23% | 23% |
| Baseline: random | 10% | 10% |
| _Reference: simulator's true susceptibles_ | 26% | 26% |
| _Reference: true recent infections (perfect nowcast)_ | 71% | 71% |
| _Reference: risk formula with true inputs (its ceiling)_ | 57% | 57% |

**Risk ranking: top 10% vs the top 20% by true incidence next quarter (near misses count)** (base rate 20%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 69% | 35% |
| Risk index (3-month horizon) | 71% | 35% |
| Risk index, settings fitted on warm-up years | 77% | 38% |
| Risk index, susceptibles half coverage-anchored | 75% | 37% |
| Risk index, depletion capped at 30%/month | 70% | 35% |
| Risk index without nowcasting (ablation) | 69% | 35% |
| Our susceptible share alone (ablation) | 34% | 17% |
| Challenger: gradient-boosted trees | 68% | 34% |
| **Hybrid: count regression + risk-model covariates** | 71% | 36% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 69% | 35% |
| Challenger: ARIMA(1,0,0) on log counts | 59% | 29% |
| Challenger: EWMA of reported incidence | 59% | 30% |
| Challenger: reported incidence, last 3 months | 65% | 32% |
| Baseline: lowest MCV1 | 46% | 23% |
| Baseline: most cases last 12 months | 42% | 21% |
| Baseline: random | 20% | 10% |
| _Reference: simulator's true susceptibles_ | 41% | 20% |
| _Reference: true recent infections (perfect nowcast)_ | 93% | 46% |
| _Reference: risk formula with true inputs (its ceiling)_ | 85% | 43% |

**Risk ranking: top 10% vs a new outbreak next quarter, among units with no reported case in the last 2 months** (base rate 9%, 126 months, median k 15)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 3% | 4% |
| Risk index (3-month horizon) | 3% | 4% |
| Risk index, settings fitted on warm-up years | 5% | 5% |
| Risk index, susceptibles half coverage-anchored | 4% | 4% |
| Risk index, depletion capped at 30%/month | 3% | 4% |
| Risk index without nowcasting (ablation) | 3% | 4% |
| Our susceptible share alone (ablation) | 4% | 6% |
| Challenger: gradient-boosted trees | 9% | 9% |
| **Hybrid: count regression + risk-model covariates** | 4% | 4% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 4% | 4% |
| Challenger: ARIMA(1,0,0) on log counts | 12% | 16% |
| Challenger: EWMA of reported incidence | 6% | 7% |
| Challenger: reported incidence, last 3 months | 4% | 5% |
| Baseline: lowest MCV1 | 8% | 8% |
| Baseline: most cases last 12 months | 5% | 7% |
| Baseline: random | 8% | 10% |
| _Reference: simulator's true susceptibles_ | 13% | 17% |
| _Reference: true recent infections (perfect nowcast)_ | 0% | 0% |
| _Reference: risk formula with true inputs (its ceiling)_ | 0% | 0% |

Ignitions whose unit was in the top 10% of quiet units one month before: 6%; three months before: 3%.

Reconstruction: reporting rate estimated for 392 units, median absolute error 0.007 (true median 0.032), rank correlation 0.95; susceptible-share rank correlation with truth 0.11.
Fitted settings (warm-up years, reported data): {'precision': 0.4690476190476191, 'c': 3.0, 'background': 0.01, 's_anchor_weight': 0.0, 'months_used': 21}.

### episodic

_Lower transmission: more woredas between outbreaks, closer to Ethiopia's reported pattern_ · mixing `gravity`, mean reporting rate 12%, 572 weeks scored, 798 true outbreaks (365 large).

| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |
|---|---|---|---|---|---|---|
| Action threshold, all outbreaks | 798 | 34% | 91% | 0.10 | 21 | 27% |
| Action threshold, large outbreaks | 365 | 45% | 91% | 0.10 | 28 | 18% |
| Alert threshold, all outbreaks | 798 | 74% | 80% | 0.65 | 7 | 49% |
| Alert threshold, large outbreaks | 365 | 77% | 80% | 0.65 | 7 | 44% |
| EWMA flag, all outbreaks | 798 | 23% | 88% | 0.05 | 14 | 37% |
| Space-time scan (every 4th week), all outbreaks | 798 | 19% | 80% | 0.15 | 21 | 35% |
| Space-time scan (every 4th week), large outbreaks | 365 | 21% | 80% | 0.15 | 21 | 34% |

**Risk ranking: top 10% vs the 10% of units with the highest true incidence next quarter (all units)** (base rate 10%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 53% | 53% |
| Risk index (3-month horizon) | 54% | 54% |
| Risk index, settings fitted on warm-up years | 55% | 55% |
| Risk index, susceptibles half coverage-anchored | 55% | 55% |
| Risk index, depletion capped at 30%/month | 54% | 54% |
| Risk index without nowcasting (ablation) | 54% | 54% |
| Our susceptible share alone (ablation) | 18% | 18% |
| Challenger: gradient-boosted trees | 60% | 60% |
| **Hybrid: count regression + risk-model covariates** | 63% | 63% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 60% | 60% |
| Challenger: ARIMA(1,0,0) on log counts | 47% | 47% |
| Challenger: EWMA of reported incidence | 49% | 49% |
| Challenger: reported incidence, last 3 months | 54% | 54% |
| Baseline: lowest MCV1 | 29% | 29% |
| Baseline: most cases last 12 months | 27% | 27% |
| Baseline: random | 10% | 10% |
| _Reference: simulator's true susceptibles_ | 27% | 27% |
| _Reference: true recent infections (perfect nowcast)_ | 74% | 74% |
| _Reference: risk formula with true inputs (its ceiling)_ | 59% | 59% |

**Risk ranking: top 10% vs the top 20% by true incidence next quarter (near misses count)** (base rate 20%, 129 months, median k 40)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 79% | 39% |
| Risk index (3-month horizon) | 80% | 40% |
| Risk index, settings fitted on warm-up years | 81% | 40% |
| Risk index, susceptibles half coverage-anchored | 81% | 40% |
| Risk index, depletion capped at 30%/month | 80% | 40% |
| Risk index without nowcasting (ablation) | 79% | 40% |
| Our susceptible share alone (ablation) | 30% | 15% |
| Challenger: gradient-boosted trees | 84% | 42% |
| **Hybrid: count regression + risk-model covariates** | 87% | 43% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 84% | 42% |
| Challenger: ARIMA(1,0,0) on log counts | 74% | 37% |
| Challenger: EWMA of reported incidence | 73% | 37% |
| Challenger: reported incidence, last 3 months | 80% | 40% |
| Baseline: lowest MCV1 | 46% | 23% |
| Baseline: most cases last 12 months | 50% | 25% |
| Baseline: random | 20% | 10% |
| _Reference: simulator's true susceptibles_ | 41% | 21% |
| _Reference: true recent infections (perfect nowcast)_ | 94% | 47% |
| _Reference: risk formula with true inputs (its ceiling)_ | 86% | 43% |

**Risk ranking: top 10% vs a new outbreak next quarter, among units with no reported case in the last 2 months** (base rate 14%, 125 months, median k 7)

| Ranking | Precision@k | Recall@k |
|---|---|---|
| **Risk index (1 month)** | 9% | 6% |
| Risk index (3-month horizon) | 9% | 6% |
| Risk index, settings fitted on warm-up years | 16% | 10% |
| Risk index, susceptibles half coverage-anchored | 10% | 6% |
| Risk index, depletion capped at 30%/month | 9% | 6% |
| Risk index without nowcasting (ablation) | 9% | 6% |
| Our susceptible share alone (ablation) | 13% | 9% |
| Challenger: gradient-boosted trees | 10% | 7% |
| **Hybrid: count regression + risk-model covariates** | 9% | 6% |
| Challenger: endemic-epidemic count regression (hhh4-type) | 10% | 7% |
| Challenger: ARIMA(1,0,0) on log counts | 10% | 8% |
| Challenger: EWMA of reported incidence | 5% | 3% |
| Challenger: reported incidence, last 3 months | 6% | 4% |
| Baseline: lowest MCV1 | 16% | 12% |
| Baseline: most cases last 12 months | 5% | 3% |
| Baseline: random | 13% | 9% |
| _Reference: simulator's true susceptibles_ | 20% | 14% |
| _Reference: true recent infections (perfect nowcast)_ | 0% | 0% |
| _Reference: risk formula with true inputs (its ceiling)_ | 2% | 1% |

Ignitions whose unit was in the top 10% of quiet units one month before: 10%; three months before: 5%.

Reconstruction: reporting rate estimated for 400 units, median absolute error 0.021 (true median 0.111), rank correlation 0.77; susceptible-share rank correlation with truth 0.23.
Fitted settings (warm-up years, reported data): {'precision': 0.5678571428571428, 'c': 1.0, 'background': 0.01, 's_anchor_weight': 0.0, 'months_used': 21}.

## How to read this

- **The risk index is shown as a risk ranking only where it beats every baseline** (METHODOLOGY 4.6). Where it does not, it stays internal.
- **Circularity:** the gravity scenario shares the gravity idea with our model, so its scores are optimistic; the radiation and stouffer scenarios test robustness to a different spread mechanism.
- **Synthetic data cannot validate the model for Ethiopia.** It tests that the code and methods behave sensibly. Real validation needs EPHI bulletins and DHIS2 history.
