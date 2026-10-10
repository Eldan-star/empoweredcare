# Empowered Care — Methodology

_Status: draft for expert review · Pilot disease: measles · Last revised: October 2026_

This document describes every model and every AI use in Empowered Care, and the evidence
behind each. It is written for an epidemiologist or infectious-disease modeller who has
been asked: **does this hold up?**

Companion documents: `SYSTEM_SPEC.md` (what is built and when), `DATABASE_SETUP.md`,
`DHIS2.md`.

---

## 0. How to review this document

Each method has the same parts: **Purpose · Method · Inputs · Assumptions · Evidence ·
Limitations · Validation · Questions for the reviewer.**

Each method is also marked with a **status**:

| Status | Meaning |
|---|---|
| **Built** | In the code and covered by tests |
| **Planned (M3/M4/M5)** | Specified; build milestone given |
| **Deferred** | Needs data or decisions we don't yet have; the trigger to start is stated |

The **strength of evidence** is marked too:

| Evidence | Meaning |
|---|---|
| **Established** | Standard method with peer-reviewed use for this purpose |
| **Supported** | Peer-reviewed support, but the method is adapted or the evidence comes from other settings |
| **Hypothesis** | Plausible; we will measure it before relying on it |

The questions we most want answered are collected in §11.

---

## 1. Design principles

1. **Statistics produce the numbers; AI handles language and does the compiling.**
   - Every threshold, index and alert level comes from a stated formula or rule that can be
     re-run and audited.
   - AI models read, extract, search, summarise, draft and orchestrate.
   - AI never sets an alert level and never invents a number (§10).
2. **Thresholds first.** A crossing of an official outbreak threshold is never downgraded
   by any model, AI or statistical.
3. **Ranked index, not a probability.** The risk output is a ranking until it has been
   backtested and calibrated against observed outbreaks.
4. **Missing data is information.** A unit that stops reporting is flagged as
   *surveillance silent*, never read as "no cases".
5. **No hidden multipliers.** Context factors (conflict, displacement) act only through
   named, evidence-backed pathways, and they are shown to the user (§4.5).
6. **Uncertainty is carried, not hidden.** Parameters drawn from the literature have
   stated ranges and are run through sensitivity analysis.
7. **Disease-agnostic core, disease-specific modules.** The core is shared across
   diseases: geography, ingestion, signals, fusion, explanation and evaluation. Each
   disease plugs in its own detection and risk methods (§8).
8. **Python only.** All analytics run in Python so that one team can maintain them. Where
   the reference implementation of a method is in R, we either re-implement it and check
   the results against R output, or name a Python alternative (§7).

---

## 2. Overview

| # | Component | Method | Status | Evidence |
|---|---|---|---|---|
| 4.1 | Vaccine protection | Dose-conditional effective-protection formula | **Built** (M3) | Established |
| 4.2 | Susceptible pool | Monthly susceptible accumulation (TSIR-style balance) | **Built**; weak on synthetic data (§5.1) | Established |
| 4.3 | Under-reporting | Reporting rate ρ by susceptible reconstruction | **Built**; recovered well on synthetic data | Established, with a known bias |
| 4.4 | Spatial spread | Gravity importation pressure | **Built** (M3) | Established for measles |
| 4.5 | Conflict and displacement | Three explicit pathways, no multiplier | Planned M3–M5 | Supported |
| 4.6 | Risk output | Ranked risk index, 1- and 3-month horizons | **Built**. Beats baselines for next-quarter burden; **not** for ignition (§5.1) | Supported (burden); not shown (ignition) |
| 4.7 | Outbreak detection | EPHI alert and action thresholds | **Built** (M3) | Established (official) |
| 4.8 | Early rise | EARS C1–C3, Poisson CUSUM, EPHI humanitarian doubling rule | **Built** (M3) | Established |
| 4.9 | Field signals | Hierarchical geocoding, clustering, human verification | Geocoder **built**; rest M4 | Supported |
| 4.10 | Fusion | EPHI levels with priority ordering | Rules **built** (M3); fusion with signals M5 | Official levels; ordering is a design choice |
| 5 | Evaluation | Synthetic data from IDM laser-measles; historical bulletins next | Synthetic **built and run** (§5.1) | Established practice |
| 7 | Later methods | Nowcasting; endemic–epidemic (hhh4-type); Bayesian spatio-temporal; gradient boosting; scan statistics | Deferred | Established |
| 10 | AI uses | 16 uses with guardrails and local metrics | Mixed | Mostly hypothesis |

---

## 3. Data inputs and their known problems

| Input | Source | Resolution | Known problems | How we handle them |
|---|---|---|---|---|
| Boundaries and P-codes | OCHA COD-AB, Dec 2025 (15 regions, 107 zones, 1,148 woredas) | Woreda | Lags recent splits; one "Contested" unit (ET99) | Hand-maintained historical units and crosswalk; contested areas kept separate |
| Population | OCHA COD-PS 2026 (CSA projection, ~111.6 M) | Woreda | UN/WorldPop estimate ~130 M; the gap is uneven across areas | Use one source consistently; run sensitivity with WorldPop |
| Births | WorldPop; DHIS2 later | 100 m grid → woreda | Modelled, not registered | Uncertainty range; sensitivity analysis |
| Routine MCV1 | IHME admin-2 estimates [10]; DHIS2 administrative data later | Zone | Administrative coverage in Ethiopia often exceeds 100% (denominator errors) | Prefer survey-anchored estimates; cap administrative coverage; flag implausible values |
| MCV2 | WUENIC / DHS | National / region | Coarse | Applied at region level, flagged as coarse |
| Campaigns (SIAs) | WHO / EPHI reports | Variable | Post-campaign coverage surveys are rare | Coverage as a range |
| Weekly measles counts | PHEM via DHIS2 (after EPHI approval); EPHI bulletins | Woreda / zone | Delays, completeness gaps, batch backfills | Completeness tracked (`reports_expected` vs `reports_received`); nowcasting later (§7.1) |
| Field signals | Community triggers (CEBS), facility reports | Kebele / free text | Low positive predictive value; free-text places | Verification workflow; hierarchical geocoder (§4.9) |
| Displacement | IOM DTM (HDX) | Site / woreda | Rounds are irregular | Most recent round, dated |
| Conflict events | UCDP (open); ACLED (licence check pending; internal and aggregated only) | Point events | Reporting bias toward accessible areas | Used for triangulation, not as a direct risk term (§4.5) |

**Question for the reviewer:** which population denominator would you use for Ethiopian
measles modelling, and should births come from WorldPop or the CSA projection?

---

## 4. Measles methods

### 4.1 Vaccine protection of a birth cohort

**Purpose.** Estimate the fraction of each birth cohort that is immune because of
routine vaccination.

**Method.**
```
P_eff = MCV1 · VE1 + MCV2 · (1 − VE1) · VE2
```
- MCV2 is given almost only to children who already received MCV1. A second dose
  therefore mainly protects children whose first dose failed.
- VE1 defaults to 0.84 (range 0.80–0.90). VE2 defaults to 0.90 (range 0.85–0.95).

**Inputs.** Cohort MCV1 and MCV2 coverage; VE values from configuration.

**Assumptions.**
- MCV2 recipients are a subset of MCV1 recipients.
- Vaccine failure is independent of who received the vaccine.
- Children who never received a dose (zero-dose children) are captured by 1 − MCV1.

**Evidence.**
- A review of field effectiveness found a median VE of about 84% when the first dose is
  given at 9–11 months, and higher when it is given at 12 months or later [12].
- The Ethiopia subnational modelling study capped VE at 93% [1].

**Limitations.**
- Zero-dose children cluster geographically and socially, so coverage and failure are
  not independent in practice.
- Maternal antibodies and very early infection are ignored.

**Validation.**
- Unit test on a hand-computed example.
- Sensitivity of the risk ranking across the VE ranges.

**Questions for the reviewer.**
- Is the dose-conditional form right for Ethiopia?
- Should a share of MCV2 doses go to MCV1-missed children (catch-up via the second dose)?

### 4.2 Susceptible accumulation

**Purpose.** Track how many children in each zone can still catch measles.

**Method.** Monthly, per zone:
```
S_t = S_{t−1} + B_t · (1 − P_eff) − C_t / ρ − SIA_t − ageing_t
```
- `SIA_t` is the number of susceptible children in the target ages × campaign coverage ×
  VE.
- `S_0` comes from a multi-year burn-in using historical coverage.

**Inputs.** Births, coverage, reported cases, ρ (§4.3), campaign history.

**Assumptions.**
- Closed population apart from births and ageing. Migration is handled through the
  displacement pathway (§4.5).
- Campaigns reach susceptible and immune children alike.

**Evidence.**
- This is the susceptible balance at the core of the time-series SIR (TSIR) framework
  for measles [2, 13].
- It is the same family of methods IDM used to fit sparse measles case data in Pakistan
  [14] (see §6).

**Limitations.**
- Errors accumulate over time: a biased coverage input drifts S steadily.
- Campaigns that preferentially reach already-vaccinated children inflate SIA_t.

**Validation.**
- On synthetic data (§5), the reconstructed S is compared with the simulator's true S.
- Once DHIS2 history exists: check whether zones with high reconstructed S are the ones
  with outbreaks.

**Questions for the reviewer.**
- Is zone level the right resolution given the coverage data?
- How should we initialise S_0 where historical coverage is unreliable?

### 4.3 Reporting rate ρ

**Purpose.** Correct reported cases for under-reporting, place by place, without a
blanket multiplier.

**Method.**
- Susceptible reconstruction: regress cumulative (unvaccinated) births on cumulative
  reported cases. The slope estimates 1/ρ [2].
- Estimated per zone, pooled toward the regional value where data are thin (partial
  pooling).

**Assumptions.**
- Reporting is roughly stable within the estimation window.
- Most susceptible children are eventually infected or vaccinated.

**Evidence.**
- Standard TSIR practice [2, 13].
- Known bias: the estimator is biased once vaccination coverage is substantial [3]. We
  use unvaccinated births to reduce the bias, and report ρ with uncertainty.

**Limitations.**
- Needs several years of case data per zone. Until EPHI DHIS2 access is approved, ρ can
  be estimated only on synthetic data.
- Structural breaks (boundary changes, conflict) violate stability.

**Validation.** On synthetic data with a known reporting rate, check how well ρ is
recovered.

**Question for the reviewer.** Would a state-space or Bayesian estimate of ρ be preferable
at this data volume?

### 4.4 Importation pressure (gravity coupling)

**Purpose.** A large susceptible pool needs infection to arrive. Estimate infectious
pressure from nearby zones.

**Method.**
```
λ_i ∝ (S_i / N_i) · ( I_i + Σ_{j≠i} N_j^a · I_j / d_ij^c )
```
- `I_j = C_j / ρ_j` over the last 4–8 weeks.
- Distances come from the shapely-computed adjacency and centroid table (built in M2).
  Travel time replaces straight-line distance when available.
- The exponents `a` and `c` start from the literature [4] and are fitted when there is
  Ethiopian history.

**Assumptions.**
- Contact between places falls with distance and grows with population.
- Cross-border sources (Sudan, South Sudan, Somalia, Kenya) enter as extra source terms
  when data exist.

**Evidence.** The gravity model of measles coupling is established for metapopulations
[4].

**Limitations.**
- Pastoralist and seasonal movement does not follow gravity well.
- Displacement (§4.5) and market or road networks may dominate.

**Validation.** On synthetic data: a zone next to an outbreak should score higher than an
otherwise identical zone far away. Ranking quality is measured as in §5.

**Question for the reviewer.** Gravity versus radiation or mobile-phone-derived mobility
for Ethiopia: is gravity acceptable as the default?

### 4.5 Conflict and displacement: three pathways, no multiplier

**Purpose.** Represent conflict in a way the evidence supports.

**What we do not do.** We do not multiply risk by a "conflict factor". No published
estimate exists for such a factor, and an unvalidated multiplier would dominate the
ranking without being auditable.

**The three pathways.**

| Pathway | How it enters | Where in the model |
|---|---|---|
| 1. Vaccination disruption | Coverage reduced in affected units for affected months. The size comes from administrative data where available, else a sensitivity range | `P_eff` and `SIA_t` (§4.1–4.2), so the susceptible pool grows with a lag |
| 2. Surveillance degradation | Falls in reporting completeness and long zero runs during conflict mark the unit **surveillance-quality: low** | Shown as "data unreliable", never as "all clear"; ρ is not re-estimated across the break |
| 3. Threat / priority factor | Active conflict and large displacement shown as a named factor, as in the WHO/CDC measles programmatic risk tool | Raises priority within an alert level (§4.10) and appears in explanations; never changes the index number |

**Data.**
- IOM DTM first (displacement figures by woreda).
- UCDP (open) and ACLED for triangulation. ACLED is used only internally, in aggregated
  form, after its licence terms are confirmed [21].

**Evidence.**
- A 193-country structural-equation study found that conflict's association with
  measles incidence operates mainly through reduced vaccination coverage, with a lag
  [15].
- A 192-country negative-binomial analysis also links conflict to measles burden [16].
- A commentary describes the peak in measles arriving years after the conflict begins
  [17].
- Reviews of vaccination in conflict settings, including Sudan [18, 19], and modelling
  of vaccination disruption [20] support pathway 1.
- The WHO/CDC measles programmatic risk assessment tool scores four categories (immunity,
  surveillance quality, programme performance, threat) [22]. Pathways 2 and 3 follow its
  structure.

**Limitations.**
- The size of the disruption is uncertain.
- Conflict-event data under-report remote areas.
- The lag structure is estimated from cross-country data, not Ethiopian data.

**Validation.**
- Sensitivity analysis over the disruption size.
- Historical case study once data allow: the Northern Ethiopia conflict, 2020–2022.

**Question for the reviewer.** Is "coverage disruption + surveillance flag + visible threat
factor" a sound decomposition? Would you add a mixing or crowding effect in displacement
camps?

### 4.6 Risk output

**Purpose.** A monthly ranking of where measles is most likely to ignite next.

**Method.**
- `index_i` = λ_i rescaled to 0–100 within the country for the month.
- Each index is stored with its contributing factors: susceptible share, nearby
  incidence, surveillance quality, threat factors.
- **Horizons.**
  - **1 month:** current λ.
  - **3 months:** S projected forward using expected births and current coverage, with
    incidence held at its recent level.
  - The 3-month horizon is driven mostly by susceptibility, and is labelled that way.

**Evidence.** Each component is supported (§4.1–4.4). The combined index is a
**hypothesis** until validated.

**Validation (§5).**
- precision@k and recall@k on next-quarter outbreaks.
- Lead time.
- Comparison with simple baselines:
  - rank by MCV1 coverage alone;
  - rank by last year's cases;
  - rank at random.
- **The index must beat these baselines to be shown as a risk ranking.**

**Question for the reviewer.** Would you rather see a fitted TSIR forecast as the primary
output once DHIS2 history exists? (We plan that as an upgrade, §6.3.)

### 4.7 Outbreak thresholds

**Purpose.** Apply the official definitions exactly as EPHI does.

| Rule | Definition | Source |
|---|---|---|
| Alert threshold | A single suspected case | EPHI PHEM Guideline 2022, Table 4-5, p. 67 [40] |
| Action threshold | ≥5 suspected **or** ≥3 confirmed (IgM-positive or epidemiologically linked) in a specified area within 1 month | [40], Table 4-5, pp. 67–68; consistent with WHO AFRO [7] |
| Humanitarian alert | Double the average of the last 3 weeks | [40], Table 4-6, p. 71 |
| Approaching action threshold | 3–4 suspected in 1 month, or 2 confirmed | Internal priority flag; not official |

- **Case definitions:**
  - **Suspected:** fever and generalized maculopapular rash with cough, coryza or
    conjunctivitis, or clinician suspicion.
  - **Confirmed:** IgM-positive, or epidemiologically linked ([40], Annex 5, p. 155).
- **Community signals are not cases.** A community "fever and rash" signal is a syndrome
  that also covers chickenpox and mpox. It counts toward thresholds only after a facility
  applies the standard case definition.
- **Configurable values.** All values are configurable. The "specified area" defaults to
  woreda or facility catchment until EPHI confirms which unit they apply.
- The full comparison with the EPHI documents is in `EPHI_ALIGNMENT.md`.

**Validation.** Unit tests on edge cases: window boundaries, epidemiological weeks that
span months, late reports.

### 4.8 Early-rise detection

**Purpose.** Flag rises below the outbreak threshold so that verification starts earlier.

**Method.**
- **EARS C1, C2, C3** [23]: the current count is compared with the mean and standard
  deviation of a short recent baseline. C2 adds a guard band; C3 accumulates. These
  suit short histories.
- **Poisson CUSUM** [24]: accumulates small excesses over expected counts; good for slow
  rises.

**Evidence.**
- Both are standard in public-health surveillance.
- A comparison of EARS with CUSUM-based methods is in [25].

**Limitations.**
- With sparse counts (most woredas report zero most weeks), EARS can over-alarm.
- Flags therefore only raise priority within a level (§4.10). They never set a level.
- Because a single suspected case is already an alert under EPHI rules, early-rise
  methods matter most for ranking alerts, for the humanitarian rule, and for diseases
  whose thresholds are baseline-based (malaria, meningitis).

**Validation.**
- Unit tests computed by hand from the published definitions.
- False-alert rate per unit-year on synthetic data.

**Question for the reviewer.** At woreda level with sparse counts, should early-rise run at
zone level only?

### 4.9 Field signals (event-based surveillance)

**Purpose.** Turn community triggers and free-text reports into located, de-duplicated
signals for human verification.

**Method.**
1. An LLM extracts the fields: disease or syndrome, counts, place hints, onset.
2. The deterministic hierarchical geocoder (**built**) resolves the place:
   - exact or alias match, then fuzzy match within the given parents;
   - names that fit several places are never guessed;
   - contradictory parents are flagged;
   - historical units (SNNPR, pre-2023 South Omo) still resolve.
3. Clustering: same unit and disease within 14 days.
4. Verification: Verify / Duplicate / Dismiss.

**Evidence.**
- Ethiopia's community event-based surveillance model is described in [26] and in EPHI's
  CEBS manual [41]. The manual expects the health extension worker to verify each
  notification within 1 hour, and names positive predictive value and sensitivity among its
  own performance indicators.
- An evaluation of a multi-component early warning system in Doolo zone found a low
  positive predictive value for community triggers (about 6%) [27].
- So verification is not optional, and raw signals are never treated as cases.

**Validation.**
- Geocoder: 17 of 21 real legacy reports resolved correctly. The rest are unmatched or
  flagged; none were resolved wrongly.
- After M4: precision and recall of extraction against officer-corrected records, and
  share of signals verified.

### 4.10 Fusion: the evidence ladder

The levels use the EPHI PHEM Guideline's terms [40]. Red, orange and yellow are not used,
because EPHI reserves them for PHEOC activation levels.

| Level | Condition (measles) |
|---|---|
| **Action threshold** | ≥5 suspected or ≥3 confirmed (lab or epi-linked) in the area within 1 month |
| **Alert threshold** | ≥1 suspected case; in humanitarian settings, double the 3-week average |
| **Signal** | Community trigger, rumour, bulletin or media report awaiting verification |

- **Priority within a level** comes from evidence, shown with the alert:
  - the risk index;
  - early-rise flags;
  - approaching the action threshold;
  - surveillance silence;
  - case fatality above 3%;
  - threat factors.
- **No statistic or index changes a level.** Levels come only from EPHI's rules applied to
  counts. A verified signal becomes an alert only when a facility case meets the standard
  case definition.

**Status of evidence.**
- The levels are EPHI's official thresholds.
- The priority ordering within a level is a design choice. It will be reviewed with EPHI.

**Question for the reviewer.** Is ranking within a level by these factors useful, or would
you rather see them only as evidence?

---

## 5. Evaluation

**Why synthetic data first.**
- No Ethiopian DHIS2 history is available until EPHI approves access.
- Synthetic data also give known true outbreak onsets, which real data never do.

**Simulator.**
- IDM's **laser-measles** (MIT licence; version ≥ 0.13, which IDM marks as the validated
  and supported version) [28].
- Run at zone level and seeded with the same public Ethiopian inputs (§3).

**Reporting layer** (ours), added on top of the simulator's true infections:
- per-zone reporting rates;
- 2–4 week reporting delays;
- about 10% missing reports;
- about 15% late batch backfills.

**Metrics.**

| Target | Metric |
|---|---|
| Detection | Sensitivity, PPV, false alerts per unit-year, days from true onset to detection (the "detect" part of 7-1-7 [11]) |
| Risk ranking | precision@k and recall@k for next-quarter outbreaks, **lead time** (weeks between a zone entering the top-k and its outbreak), comparison with baselines (§4.6) |
| Reconstruction | Error of reconstructed S and ρ against the simulator's true values |

**The circularity risk, stated plainly.**
- If the simulator and our risk model share assumptions (for example, both use gravity
  mixing), good scores partly measure agreement between the two models, not truth.
- **Mitigations:**
  - Run the simulator with mixing and parameters that differ from our model's
    (mis-specification tests).
  - Report results across scenarios.
  - Validate on real history as soon as possible:
    - EPHI weekly bulletins (historical, manually uploaded);
    - outbreak reports from ReliefWeb and WHO AFRO;
    - DHIS2 once approved.

**Question for the reviewer.** Which mis-specification scenarios would convince you?

---

### 5.1 First results (October 2026)

Full numbers: `evaluation/reports/2026-10-10-m3-baseline.md`. Plain-language summary:
`EVALUATION.md`.
- **Set-up:**
  - 400 synthetic woreda-scale units, 15 simulated years with 4 years of burn-in;
  - five scenarios: gravity, radiation and Stouffer mixing, low reporting, and lower
    transmission;
  - detection is scored on data as visible each week.
- **Thresholds:**
  - the alert threshold catches 73–77% of outbreaks within about a week, with 80–84% of
    alarms during true transmission;
  - the action threshold is about 92% reliable but late: 33–36% of outbreaks (about 46%
    of large ones) reach it within 8 weeks of onset;
  - at 5% reporting, sensitivity falls sharply.
- **Risk index, next-quarter burden** (top 10% vs the true top 10%):
  - 44–53% precision, against 28–31% for lowest MCV1, 24–29% for most recent cases, and
    10% for random;
  - the index beats every baseline in every scenario, including mis-specified mixing.
- **Risk index, ignition among quiet units:**
  - no better than random or lowest MCV1;
  - even the simulator's true susceptibles reach only 14–31%.
- **Reconstruction:**
  - the reporting rate is recovered well (median absolute error about 0.015 against a true
    0.11; rank correlation 0.77–0.95);
  - the susceptible pool is recovered poorly (rank correlation about 0.2–0.35).
- **Consequence:** the index is shown only as "where measles will be heaviest next
  quarter". Ignition stays internal until the susceptible estimate improves and is
  validated on real data.

### 5.2 Implementation choices a reviewer should know

| Choice | Value | Why |
|---|---|---|
| "Within 1 month" on weekly data | Last 4 ISO weeks | Routine data is weekly; EPHI to confirm |
| EARS standard-deviation floor | 0.5 | Zero-variance baselines are common in sparse counts |
| Poisson CUSUM | Rolling 8-week baseline after a 2-week guard; shift 2x; h = 4 | Conventional starting values; to be tuned on real data |
| Case-fatality flag | Above 3% with at least 10 cases in the window | Avoids flags from one death in a handful of cases |
| Starting susceptibles | N / R0, R0 = 15 | Endemic equilibrium; burn-in reduces its influence |
| Ageing out of the 0–14 band | S/180 per month | Assumes an even age spread of susceptibles |
| Reporting-rate window | Rolling 96 months, pooled toward the region over 36 months | Reporting changes over years; thin data borrows strength |
| Gravity exponents | a = 0, c = 2, 600 km cut-off | Placeholders for ranking; to be fitted on Ethiopian history |
| Background introductions | 0.1 infection-equivalents per month | Keeps the ranking informative between epidemics |
| Priority points within a level | Approaching action 20; each early-rise method 10 (max 4); CFR flag 20; risk index up to 30; each threat factor 5 (max 2) | Transparent ordering; to be reviewed with EPHI |
| Simulator R0 | β × 14 days, about 8 | Starts laser-measles near its own equilibrium |

## 6. IDM, laser-measles, and why we use them the way we do

### 6.1 What IDM contributes
- **laser-measles** is IDM's spatial measles toolkit. It offers three model types:
  - an agent-based model (daily steps);
  - a biweekly compartmental SIR, recommended for scenarios and policy;
  - a daily compartmental SEIR, recommended for parameter estimation [28].
- IDM's **measles analysis methods** are statistical as well as simulation-based:
  - IDM fitted a TSIR model to sparse Pakistani case data to optimise campaign timing
    [14];
  - later work found that well-timed campaigns can outperform higher coverage [29].

### 6.2 How we incorporate IDM's methodology

| IDM element | Our use | Milestone |
|---|---|---|
| laser-measles simulator | Generates synthetic Ethiopian outbreaks with known truth, to test detection and ranking | M3 |
| TSIR-style susceptible reconstruction (the same family IDM used in Pakistan [14]) | Core of our susceptible pool and reporting rate (§4.2–4.3) | M3 |
| Campaign-timing insight [14, 29] | A future scenario use: "if the SIA in zone X slips by 6 months, how does the risk change?" | After calibration |

### 6.3 Why laser-measles is not the live forecasting engine (yet)
1. **Calibration needs data we don't have yet.**
   - A transmission simulator is only as good as its fit to local case history.
   - Ethiopian subnational history needs EPHI DHIS2 approval.
   - The Ethiopia modelling study [1] (IHME / LSHTM, not IDM) documents how hard such
     fitting is with Ethiopian data.
2. **Transparency for weekly operations.**
   - An officer must see why a zone ranks high.
   - The susceptible-plus-gravity index decomposes into named factors.
   - A stochastic simulation's output is harder to explain week to week.
3. **Compute and maintenance.**
   - Ensembles of calibrated runs every week across 107 zones (or 1,148 woredas) need
     infrastructure and modelling staff that the pilot does not yet have.
4. **Independence for evaluation.**
   - Using the same simulator to generate the test data and to forecast would make the
     evaluation circular (§5).

### 6.4 When it could become one
Once multi-year DHIS2 history is available, calibrate laser-measles (or a fitted TSIR) to
Ethiopian data. Then use it for:
- **scenario analysis:** campaign timing, delayed SIAs, disruption from conflict;
- **probabilistic forecasts:** compared head-to-head with the index.

Whichever ranks better in out-of-sample backtests is shown to users. We would welcome a
collaboration with IDM on that calibration.

---

## 7. Later methods (deferred, with triggers)

| # | Method | Purpose | Evidence | Python route | Trigger to start |
|---|---|---|---|---|---|
| 7.1 | **Nowcasting** of reporting delays | Estimate this week's true count before late reports arrive | Bayesian nowcasting [30]; NobBS [31] | Re-implement in PyMC / NumPyro | Reporting-date history from DHIS2 |
| 7.2 | **Endemic–epidemic model** (hhh4-type) | Decompose counts into endemic, within-unit and neighbour-driven parts; probabilistic forecasts | [32, 33] | It is a negative-binomial regression with autoregressive and neighbourhood terms. Re-implement, and check against R `surveillance` output | Multi-year weekly history |
| 7.3 | **Bayesian spatio-temporal** (BYM2-type) | Smooth risk across small areas with uncertainty | INLA is the usual tool but is R-only | PyMC / NumPyro. **Flag:** departs from common practice | Multi-year history |
| 7.4 | **Gradient boosting** (XGBoost) [34] | (a) Rank incoming signals by probability of verification; (b) a challenger risk model | Supported, but needs labels | Native Python | (a) A few hundred officer verdicts; (b) real history |
| 7.5 | **Space-time scan statistics** [35, 36] | Detect clusters without a fixed unit, useful for zoonoses and new diseases | Established | Re-implement, or use an existing Python library | Disease #2 |
| 7.6 | **Fitted TSIR forecast** [2, 13, 14] | Probabilistic measles forecast | Established | Native Python | Multi-year history |

**Question for the reviewer.** Is PyMC/NumPyro an acceptable substitute for INLA, given our
Python-only constraint?

---

## 8. Beyond measles: disease archetypes

The core (geography, ingestion, signals, fusion, explanation, evaluation) is
disease-agnostic. Each disease adds a module with its own case definition, thresholds,
early-rise method and risk drivers. **Thresholds are taken from the EPHI manuals; the
values below are not final.**

| Archetype | Examples | Detection | Risk drivers | Reuse |
|---|---|---|---|---|
| Vaccine-preventable, susceptible-driven | Measles, diphtheria, pertussis | Thresholds + EARS/CUSUM | Susceptible build-up, importation | This document |
| Climate-sensitive, seasonal | Malaria, dengue | Seasonal baselines (Farrington-type) | Rainfall, temperature, vegetation (CHIRPS, ERA5, MODIS) | **EPIDEMIA** [6]; **DHIS2 CHAP** [37] |
| Water-borne | Cholera / acute watery diarrhoea | Thresholds (a single confirmed case is an alert) | Water access, displacement, flooding, cross-border | Cross-border OSINT |
| Zoonotic / One Health | Anthrax, rabies, Rift Valley fever | Scan statistics; animal-event triggers | Animal outbreaks, livestock movement, rainfall | WOAH WAHIS [38], FAO EMPRES-i [39] |
| Meningitis | Bacterial meningitis | Weekly incidence thresholds | Dry season, dust | WHO meningitis guidance |

**One Health groundwork now, analytics after measles.**
- The source registry and trigger schema already allow animal events: the CEBS trigger
  type "unusual animal deaths", with a species field.
- Analysis of animal data starts after the measles pilot.

---

## 9. Data source registry

Every source is registered with: licence, update frequency, spatial resolution, owner,
access status and the diseases it serves.

| Category | Sources | Status |
|---|---|---|
| Routine surveillance | PHEM weekly / EPI monthly via DHIS2 | Connector built; pull blocked until EPHI written approval |
| Community triggers | CEBS intake (EPHI trigger list) | M4 |
| Official bulletins | EPHI weekly bulletins | Manual upload, plus a historical test set |
| Open-source intelligence | ReliefWeb, WHO AFRO bulletins, WHO Disease Outbreak News; EIOS via partnership | M4 |
| Population / immunity | OCHA COD-PS (loaded), WorldPop, WUENIC, DHS, IHME | M2–M3 |
| Displacement / conflict | IOM DTM (first), UCDP, ACLED (licence check) | M3–M4 |
| Climate | CHIRPS, ERA5, MODIS | With disease #2 |
| One Health | WOAH WAHIS, FAO EMPRES-i | Registered now; analytics later |

---

## 10. AI as a capability multiplier

### 10.1 The rule
**AI proposes, compiles and explains. Statistics decide. People verify.**

AI may:
- read and extract;
- search and retrieve;
- write code and queries;
- run tools, including simulations and models;
- summarise and draft.

AI may not:
- set an alert level;
- declare an outbreak;
- compute a statistic inside a prompt;
- present a number that is not traceable to a stored record or a re-runnable
  computation.

### 10.2 The uses

Every use is treated as a **hypothesis** and measured locally. Evidence that general-purpose
LLMs perform well on these tasks in surveillance settings is still early, so we do not
assume it.

| # | Use | What the AI does | Guardrail | Local measure | Status |
|---|---|---|---|---|---|
| 1 | **Report extraction** | Turns messy text, CSV, PDF and images into structured records | Schema-enforced JSON; human review | Field accuracy vs officer corrections | **Built** |
| 2 | **Place-hint extraction** | Pulls region / zone / woreda hints from free text | The deterministic geocoder decides; ambiguity is flagged | Geocode accuracy | **Built** (geocoder) |
| 3 | **Ask the data** | Answers questions over stored records | Answers cite records | Spot-checked correctness | **Built**; to be upgraded by #9 |
| 4 | **Grounded explanations** | "Why this place, why now" from stored factors | Only stored evidence JSON is in context; citations required | Reviewer rating; unsupported-claim rate | M5 |
| 5 | **Sitrep compiler** | Drafts the weekly situation report from all streams: alerts, counts, signals, context, OSINT | Every number is pulled by code, not written by the model; officer approves | Time saved; error count per sitrep | M5 |
| 6 | **OSINT monitor** | Reads ReliefWeb / WHO AFRO / bulletins daily; extracts event, place, date; de-duplicates against stored signals | Output is a **signal** at most; links to the source | Precision / recall vs manual review | M4 |
| 7 | **Bulletin digitiser** | Converts printed EPHI bulletin tables into indicator rows | Row totals checked against printed totals; mismatches go to review | Cell accuracy | M4 |
| 8 | **Guideline assistant (retrieval over the EPHI manuals)** | Answers "what is the case definition / threshold / response step" with page citations; drafts disease-module configurations from the manuals | Must quote the source passage; a person signs off configurations | Citation accuracy | M4 (after manuals are added) |
| 9 | **Analyst copilot** | Turns a question into a SQL query or chart over the database ("woredas with falling completeness and rising suspected cases") | Read-only database role; the generated query is shown | Query correctness on a test set | M5 |
| 10 | **Data-quality triage** | Reviews weekly statistical checks (completeness drops, impossible values, coverage >100%, sudden zeros) and explains the likely cause | The checks are computed by code; AI only explains and ranks them | Officer usefulness rating | M3–M5 |
| 11 | **Scenario agent** | Translates a what-if ("SIA in Zone X delayed 6 months") into calibrated laser-measles runs and reports the results with ranges | Only after calibration (§6.4); runs are logged and reproducible | Agreement with analyst-run scenarios | After calibration |
| 12 | **Calibration and sensitivity assistant** | Sets up parameter sweeps, reads diagnostics, summarises which parameters drive the ranking | Results come from the runs, not from the model | Analyst review | M3+ |
| 13 | **Alias and boundary curation** | Proposes new place-name aliases from unmatched reports, and crosswalk entries after boundary changes | Proposals go to `place_aliases.csv` only after human approval | Unmatched rate over time | M4 |
| 14 | **Evidence watch** | Monitors new literature and guidelines on methods in this document and flags what may need updating | Human review; this document is the record | Items flagged / adopted | Later |
| 15 | **Evidence checker** | Checks every AI draft (explanation, sitrep, OSINT extraction) against the stored evidence and flags claims, numbers or places the evidence doesn't support | Runs independently of the drafting call; flagged drafts go to a person | Share of unsupported claims caught (seeded test drafts) | M5 |
| 16 | **SMS intake for health extension workers** | Parses free-text SMS reports and confirms the reading back to the sender ("Received: 4 suspected measles, Dubluk. Reply 1 to confirm") | Coded SMS messages are parsed by rules, not AI; the sender confirms every reading; low-confidence messages go to a person | Confirmation rate; field accuracy by language | After the channel decision (SYSTEM_SPEC §11.2) |

Also planned:
- multilingual intake (Amharic, Afaan Oromo, Tigrinya), including voice, once the
  channels are agreed;
- learned triage (§7.4) once verdicts exist.

Time-series foundation models may be tested as **challengers** against the statistical
forecasts. Evidence for them on sparse surveillance counts is limited, so they never
replace a method in this document without winning an out-of-sample backtest.

### 10.3 Risks of AI use and controls

| Risk | Control |
|---|---|
| Hallucinated numbers or places | Numbers come from code; places from the geocoder; citations required |
| Data sovereignty (patient-identifiable text sent to a cloud model) | `LLMProvider` interface allows an on-premises open-weight model (SYSTEM_SPEC §11.1) |
| Quota or outage | Statistical pipeline runs without AI; AI features degrade with a clear message (built) |
| Automation bias | AI output is labelled as AI; levels stay rule-based; verdicts recorded |
| Language bias (weaker performance in Ethiopian languages) | Measure accuracy per language before relying on it |

---

## 11. Questions for the reviewer

1. **Denominators:** CSA projection or WorldPop for population and births?
2. **Vaccine protection:** is the dose-conditional formula and VE ranges appropriate?
3. **Resolution:** zone first, then woreda — right order given the coverage data?
4. **ρ estimation:** susceptible reconstruction with unvaccinated births, or a state-space
   / Bayesian alternative?
5. **Spatial coupling:** gravity as the default for Ethiopia?
6. **Conflict:** do the three pathways cover what matters? Add crowding effects in
   displacement sites?
7. **Fusion:** is ranking within EPHI's alert and action levels by risk, early-rise and
   context factors useful?
8. **Early rise:** zone-level only, given sparse woreda counts?
9. **Evaluation:** which mis-specification scenarios would make a synthetic evaluation
   convincing?
10. **INLA substitute:** is PyMC / NumPyro acceptable?
11. **IDM:** is "simulator for evaluation now, calibrated scenario engine later" the right
    use of laser-measles?
12. **Missing methods:** what would you expect to see that is not here?
13. **Susceptible reconstruction:** given §5.1, which approach would you try first: a
    state-space or Bayesian S, anchoring to coverage surveys, or fitting a full TSIR?

---

## References

Numbers 1–11 match `SYSTEM_SPEC.md`. Entries 15–20 give a short description rather
than the exact article title; follow the link for the full citation.

1. Sbarra AN et al. Fitting dynamic measles models to subnational case notification data from Ethiopia: methodological challenges and key considerations. *PLOS Comput Biol* 2025. https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012922
2. Finkenstädt BF, Grenfell BT. Time series modelling of childhood diseases: a dynamical systems approach. *J R Stat Soc C* 2000; R package `tsiR`. https://www.rdocumentation.org/packages/tsiR/versions/0.2.0
3. Bias in the estimated reporting fraction due to vaccination in the time-series SIR model. *PLOS ONE* 2025. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0330568
4. Xia Y, Bjørnstad ON, Grenfell BT. Measles metapopulation dynamics: a gravity model for epidemiological coupling and dynamics. *Am Nat* 2004. https://www.journals.uchicago.edu/doi/abs/10.1086/422341
5. `farringtonFlexible`, R package `surveillance`. https://surveillance.r-forge.r-project.org/pkgdown/reference/farringtonFlexible.html
6. Merkord CL et al. Integrating malaria surveillance with climate data for outbreak detection and forecasting: the EPIDEMIA system. *Malar J* 2017. https://link.springer.com/article/10.1186/s12936-017-1735-x
7. WHO AFRO. African Regional Guidelines for Measles and Rubella Surveillance (2015). https://www.afro.who.int/sites/default/files/2017-06/who-african-regional-measles-and-rubella-surveillance-guidelines_updated-draft-version-april-2015_1.pdf
8. Measles outbreak investigation in Guji zone of Oromia Region, Ethiopia. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5619924/
9. Insights from a measles outbreak root cause analysis in Ethiopia, 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC12595561/
10. LBD Vaccine Coverage Collaborators. Mapping routine measles vaccination in low- and middle-income countries. *Nature* 2021. https://www.nature.com/articles/s41586-020-03043-4
11. Evaluation of measles outbreak response in Geze Gofa district using the 7-1-7 timeliness metrics. https://pmc.ncbi.nlm.nih.gov/articles/PMC13224625/
12. Uzicanin A, Zimmerman L. Field effectiveness of live attenuated measles-containing vaccines: a review of published literature. *J Infect Dis* 2011;204 Suppl 1:S133–48.
13. Bjørnstad ON, Finkenstädt BF, Grenfell BT. Dynamics of measles epidemics: estimating scaling of transmission rates using a time series SIR model. *Ecol Monogr* 2002.
14. Thakkar N, Gilani SSA, Hasan Q, McCarthy KA. Decreasing measles burden by optimizing campaign timing. *PNAS* 2019. https://pmc.ncbi.nlm.nih.gov/articles/PMC6561209
15. Conflict, vaccination coverage and measles: a 193-country structural equation analysis. *PLOS Med*. https://journals.plos.org/plosmedicine/article?id=10.1371%2Fjournal.pmed.1004819
16. Armed conflict and measles burden in 192 countries (negative binomial analysis). https://pubmed.ncbi.nlm.nih.gov/40557289/
17. Commentary on the lagged effect of conflict on measles. https://pmc.ncbi.nlm.nih.gov/articles/PMC13308810/
18. Vaccination in conflict settings: a scoping review. https://pmc.ncbi.nlm.nih.gov/articles/PMC13575017/
19. Measles and immunization during the conflict in Sudan: a review. https://www.sciencedirect.com/science/article/pii/S3050501126000088
20. Modelling the impact of vaccination disruption on measles. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9742850/
21. ACLED access guide (licence terms). https://acleddata.com/knowledge-base/acled-access-guide
22. WHO/CDC Measles Programmatic Risk Assessment Tool. https://stacks.cdc.gov/view/cdc/129658 ; https://stacks.cdc.gov/view/cdc/130371 ; application: https://pmc.ncbi.nlm.nih.gov/articles/PMC10256314
23. Hutwagner L et al. The bioterrorism preparedness and response Early Aberration Reporting System (EARS). *J Urban Health* 2003.
24. Lucas JM. Counted data CUSUM's. *Technometrics* 1985.
25. Fricker RD, Hegler BL, Dunfee DA. Comparing syndromic surveillance detection methods: EARS' versus a CUSUM-based methodology. *Stat Med* 2008.
26. Event-based surveillance in Amhara Region, Ethiopia. *WPSAR*. https://ojs.wpro.who.int/ojs/index.php/wpsar/article/view/330
27. MSF. Evaluation of a multi-component early warning system for pastoralist populations, Doolo zone, Ethiopia. https://scienceportal.msf.org/assets/evaluation-multi-component-early-warning-system-pastoralist-populations-doolo-zone-ethiopia-mixed-methods-study
28. Institute for Disease Modeling. laser-measles (MIT licence). https://github.com/InstituteforDiseaseModeling/laser-measles ; documentation: https://laser.idmod.org/laser-measles/
29. Rosenfeld K, Frey K, McCarthy KA. Optimal timing regularly outperforms higher coverage in preventative measles supplementary immunization campaigns. *Vaccines* 2024. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11281443/
30. Höhle M, an der Heiden M. Bayesian nowcasting during the STEC O104:H4 outbreak in Germany, 2011. *Biometrics* 2014.
31. McGough SF et al. Nowcasting by Bayesian Smoothing: a flexible, generalizable model for real-time epidemic tracking. *PLOS Comput Biol* 2020.
32. Held L, Höhle M, Hofmann M. A statistical framework for the analysis of multivariate infectious disease surveillance counts. *Stat Model* 2005.
33. Meyer S, Held L, Höhle M. Spatio-temporal analysis of epidemic phenomena using the R package surveillance. *J Stat Softw* 2017.
34. Chen T, Guestrin C. XGBoost: a scalable tree boosting system. *KDD* 2016.
35. Kulldorff M. A spatial scan statistic. *Commun Stat Theory Methods* 1997.
36. Kulldorff M et al. A space–time permutation scan statistic for disease outbreak detection. *PLoS Med* 2005.
37. DHIS2 Climate & Health Analytics Platform (CHAP). https://chap.dhis2.org/about/
38. WOAH World Animal Health Information System (WAHIS). https://www.woah.org/en/what-we-do/animal-health-and-welfare/disease-data-collection/
39. FAO EMPRES-i. https://www.fao.org/agroinformatics/projects/projects-detail/empres-i
40. Ethiopian Public Health Institute / Ministry of Health. Public Health Emergency Management (PHEM) Guideline for Ethiopia, 2nd edition, December 2022. Converted text in `docs/references/ephi/`.
41. Ethiopian Public Health Institute. Community and Event Based Surveillance Implementation Manual, September 2021. Converted text in `docs/references/ephi/`.
