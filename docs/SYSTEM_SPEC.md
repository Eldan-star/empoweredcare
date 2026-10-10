# Empowered Care — System Specification (Phase 1)

_Status: living document · Pilot disease: measles · Last revised: October 2026_

This document is the single technical reference for what Empowered Care is, what the
current codebase does, and what Phase 1 will build. It records every model decision
with the evidence behind it, so that anyone (engineer, epidemiologist, funder) can check
the reasoning.

**For reviewers:** `METHODOLOGY.md` sets out every model and AI use in one place, with its
assumptions, evidence, limitations, validation plan and open questions. It is written for
an epidemiologist or disease modeller to check.

**Design principle: multi-disease.** Measles is the first disease, not the only one. The
core is shared by every disease: geography, ingestion, signals, fusion, explanation and
evaluation. Each disease adds its own module of case definitions, thresholds, detection
methods and risk drivers (§13).

---

## 1. What we are building

**Empowered Care is Ethiopia's outbreak intelligence engine.** It reads the signals
available to Ethiopian public health — routine PHEM/DHIS2 counts, field reports,
official bulletins, humanitarian updates — and turns them into verified, explained
alerts and forward-looking risk for national (EPHI) and regional (RHB) epidemiologists.

| Capability | What it outputs | Phase 1 method |
|---|---|---|
| **Predict** | Ranked measles ignition-risk index per zone | Susceptible accumulation + gravity importation pressure (§5) |
| **Detect** | Threshold crossings and early-rise flags every week | WHO/EPHI outbreak thresholds; EARS C1–C3, Poisson CUSUM (§6) |
| **Fuse** | One tiered alert per place and week, with its evidence | Deterministic evidence ladder (§8) |
| **Explain** | "Why this place, why now", draft situation reports | LLM grounded only in stored evidence (§9) |

A thin feedback loop (Verify / Duplicate / Dismiss on every signal and alert) collects
officer verdicts. Those verdicts are the labels for later learned models (§11).

**Integration stance.** Empowered Care feeds and sits beside existing systems rather
than replacing them: DHIS2 (data backbone), DHIS2 CHAP (climate-disease forecasting),
WHO AFRO PDX (regional preparedness intelligence, federated by design), WHO EIOS.

---

## 2. Where the codebase stands (audit, October 2026)

Verified by reading the code; file references are to the repository at this revision.

**What works and is worth keeping**
- FastAPI backend with JWT auth, email invites, roles, admin approve/reject (`main.py`).
- LLM extraction of messy text, CSV, PDF and image reports into structured records
  (`services/agents.py: ExtractionAgent`, `main.py /outbreak/upload`). This becomes the
  extraction core for event-based surveillance.
- Document vision pipeline (Gemini Vision, PaddleOCR fallback) in `main.py /process`. *(Removed in M2; see 11.1.)*

**The intelligence layer is entirely LLM prompting**
- No statistical, machine-learning or predictive model exists anywhere.
- The "risk score" is the average of four Gemini self-reported opinions
  (`SuperAgent._reach_consensus`). LLM self-confidence is not calibrated, and an
  `UNKNOWN` vote counts as zero and drags the average down.
- "Historical comparison" pastes up to 20 JSON records into a prompt. There is no
  baseline, no population denominator, no time series and no seasonality.
- "Clustering" merges reports only on an exact location string plus a free-text disease
  name within 2 hours of *ingestion* time, so it almost never fires.
- The data store is sorted by location, not time, so every "most recent" slice is
  arbitrary and truncation drops arbitrary records.
- The context research agent scrapes Google and Bing result pages.

**Foundations**
- Storage is JSON files (21 records). Location is free text with no administrative code;
  the map places unknown cities at a random position on every render.
- The frontend does not build from a clean clone: `frontend/src/lib/` (API client and
  `cn()` helper) is excluded by a `lib/` rule in `.gitignore`. The YOLO layout weights
  used by `/process` are not in the repository.
- A default `SECRET_KEY` is hardcoded; `models/users.json` (password hashes) and
  `data/patient_records.json` are committed; CORS allows `*`.
- The landing page shows invented metrics (99.1% accuracy, 48,201 records, SMS
  escalation) and the pipeline animation runs on timers, not backend progress.
- The earlier design documents described an SMS gateway, offline sync agent and
  EPHI-guideline RAG that did not exist. They are now in `docs/archive/`, and their ideas
  are reviewed in §11.2.

---

## 3. Data model (Phase 1)

PostgreSQL with SQLAlchemy 2.0 and Alembic migrations (SQLite for tests). JSON columns
are JSONB in Postgres.

| Table | Grain | Key columns |
|---|---|---|
| `org_units` | One administrative or health unit | `code` (OCHA P-code or DHIS2 UID), `name`, `level` (1 region, 2 zone, 3 woreda, 4 kebele/facility, unbounded), `parent_code`, `population`, `lat`, `lon`, `dhis2_uid`, `aliases[]`, `valid_from`, `valid_to` |
| `org_unit_adjacency` | Pair of units | `a`, `b`, `shares_border`, `distance_km` |
| `boundary_crosswalk` | Boundary change | `old_code`, `new_code`, `effective_date`, `note` (e.g. SNNPR → Sidama 2020, South West 2021, Central & South Ethiopia 2023) |
| `indicator_counts` | Unit × disease × ISO week | `suspected`, `confirmed`, `deaths`, `reports_expected`, `reports_received`, `source`, `reported_at` |
| `immunization` | Unit × month | `mcv1_doses`, `mcv2_doses`, `births` |
| `campaigns` | Supplementary immunization activity | `unit`, `start_date`, `age_min_months`, `age_max_months`, `coverage` |
| `signals` | One event-based report | `source_type` (`intake`, `bulletin`, `reliefweb`, `manual`), `raw_text`, `extracted` (JSON), `unit`, `geocode_confidence`, `ambiguous`, `cluster_id`, `status`, `verdict`, `verified_by` |
| `risk_scores` | Unit × month | `S`, `rho`, `p_eff`, `lambda`, `index`, `factors` (JSON) |
| `alerts` | Unit × disease × week | `tier`, `evidence` (JSON), `status`, `verdict` |
| `evaluations` | One evaluation run | `config`, `metrics` (JSON), `created_at` |

Weekly case counts and monthly immunization data live in separate tables because they
have different periods.

### 3.1 Indicator record (JSON schema, abridged)
```json
{
  "unit": "ET0412",            "disease": "measles",
  "iso_year": 2026,            "iso_week": 40,
  "suspected": 7,              "confirmed": 2,     "deaths": 0,
  "reports_expected": 14,      "reports_received": 12,
  "source": "dhis2:phem_weekly", "reported_at": "2026-10-06T09:12:00Z"
}
```

### 3.2 Event record (follows the EPHI community event-based surveillance trigger structure)
```json
{
  "trigger_type": "fever_and_rash_cluster",
  "location": {"region": "Oromia", "zone": "Borena", "woreda": "Dire", "kebele": null, "free_text": "near Dubluk market"},
  "counts": {"cases": 4, "deaths": 0},
  "onset_date": "2026-09-28",
  "reporter": {"role": "HEW", "contact_ref": "opaque-id"},
  "language": "om",           "raw_text": "...",
  "received_via": "intake_api"
}
```

---

## 4. Geography: hierarchical resolution

Ethiopia has repeated place names across zones and regions, and boundaries have changed
(the SNNPR split into Sidama, South West, Central and South Ethiopia between 2020 and 2023).
Flat fuzzy matching would put outbreaks in the wrong region. Rules:

1. **Exact or alias match** on the full path when a parent is known
   (region → zone → woreda).
2. **Fuzzy match** (RapidFuzz) only *within* the parent region/zone given or inferred from
   the text.
3. **Ambiguity is flagged, never auto-resolved.** If a name matches units in more than
   one region and no parent hint disambiguates it, the signal is marked `ambiguous` for a
   human to resolve.
4. The LLM's only job here is to extract parent hints from free text ("near Moyale, Borena").
5. **Master list:** OCHA COD-AB P-codes (admin 1–3) now; DHIS2 org-unit UIDs become the
   master once access is granted, with P-codes kept as a crosswalk. OCHA data may lag
   recent boundary changes, so `boundary_crosswalk` is maintained by hand.
6. Facilities and kebeles (level 4+) attach to woredas through `parent_code`; facility
   lists come from DHIS2 or the Master Facility Registry.

---

## 5. Predict — measles ignition-risk index

Measles is driven by the build-up of unprotected children. A large susceptible pool is
not enough on its own: an outbreak also needs infection arriving from somewhere. The
index therefore combines **how combustible** a place is with **how much infectious
pressure** is near it.

### 5.1 Vaccine protection of a birth cohort
Second-dose (MCV2) recipients are almost all first-dose (MCV1) recipients, so MCV2
mainly protects the children whose first dose did not take:

```
P_eff = MCV1 · VE1  +  MCV2 · (1 − VE1) · VE2
```

- `MCV1`, `MCV2`: coverage fractions for the cohort.
- `VE1`: effectiveness of a first dose at 9 months (default 0.84, range 0.80–0.90).
- `VE2`: probability that a second dose protects a child the first dose failed to protect
  (default 0.90, range 0.85–0.95).
- Both are configuration values with sensitivity analysis; the 2025 Ethiopia modelling
  study capped vaccine effectiveness at 93%. [1]
- Supplementary campaigns are handled separately (§5.2) because they reach children
  regardless of routine dose history.

### 5.2 Susceptible accumulation
Monthly, per zone (zone level first, matching the resolution of public coverage data):

```
S_t = S_{t−1}  +  B_t · (1 − P_eff)  −  C_t / ρ  −  SIA_t  −  ageing_t
```

- `B_t`: births (WorldPop / DHIS2).
- `C_t`: reported measles cases; dividing by the reporting rate `ρ` estimates true infections.
- `SIA_t`: children immunized by a campaign = susceptible children in the target ages ×
  campaign coverage × vaccine effectiveness.
- `ageing_t`: children leaving the modelled age band (0–14 years).
- Initial `S_0` comes from a multi-year burn-in using historical coverage.

### 5.3 Reporting rate ρ (susceptible reconstruction)
Most measles infections are never reported, and reporting varies by place. Instead of a
blanket multiplier, ρ is estimated from data using the established susceptible
reconstruction method: regress cumulative births on cumulative reported cases; the slope
estimates the reporting rate. [2]

- Estimated per zone, with pooling toward the regional value where data are thin.
- **Known caveat:** the standard estimator is biased once vaccination coverage is
  substantial. [3] We correct births to *unvaccinated* births before the regression and
  report ρ with uncertainty.
- Zones that report zero cases for long periods are flagged **"surveillance silent"**,
  not treated as zero risk.

### 5.4 Importation pressure (gravity coupling)
Spatial coupling follows the gravity form established for measles metapopulations [4]:

```
λ_i  ∝  (S_i / N_i) · ( I_i  +  Σ_{j ≠ i}  N_j^a · I_j / d_ij^c )
```

- `I_j = C_j / ρ_j`: estimated recent incidence in zone j (last 4–8 weeks).
- `N_j`: population; `d_ij`: distance (travel time when available).
- `a`, `c`: gravity exponents, initialised from the literature, fitted to Ethiopian data
  when history is available.
- Cross-border pressure (Somalia, Kenya, South Sudan, Sudan) enters as additional source
  terms when data exist. Conflict and displacement enter through the pathways in §5.6,
  not as a multiplier.

### 5.5 Output
- `index_i` = λ_i rescaled to a 0–100 rank within the country for the month, plus the top
  contributing factors (susceptible share, nearby incidence, surveillance silence).
- **It is a ranked index, not a probability.** It will not be presented as a probability
  until it has been backtested against historical outbreaks.
- **Horizons:**
  - **1 month:** current λ.
  - **3 months:** S projected forward with expected births and current coverage. This
    horizon is driven mostly by susceptibility, and is labelled that way.
- **The index must beat simple baselines before it is shown as a risk ranking.** The
  baselines are: rank by MCV1 coverage alone, rank by last year's cases, and rank at
  random (§10).

### 5.6 Conflict and displacement: three pathways, no hidden multiplier (agreed October 2026)
No published estimate supports a single "conflict multiplier", so the model uses none.
Conflict acts through three named pathways:

1. **Vaccination disruption.** Conflict reduces effective routine and campaign coverage
   in affected units and months. This feeds `P_eff` and `SIA_t`, so the susceptible pool
   grows with a lag.
2. **Surveillance quality.** Falls in reporting completeness, or long zero runs during
   conflict, mark a unit **surveillance quality: low**. The unit is shown as "data
   unreliable", never as "all clear", and ρ is not estimated across the break.
3. **Threat / priority factor.** Active conflict and large displacement are shown as a
   named factor, like the threat category of the WHO/CDC measles programmatic risk tool.
   This factor raises priority within a fusion tier (§8). It never changes the index
   number.

**Data:**
- IOM DTM first.
- UCDP and ACLED for triangulation. ACLED is used only internally, in aggregated form,
  after its licence terms are confirmed.

Evidence and references are in `METHODOLOGY.md` §4.5.

---

## 6. Detect — thresholds first, statistics second

### 6.1 Why thresholds, not Farrington, are the core for measles
EPHI declares measles outbreaks with fixed thresholds, and most woredas report zero
cases most weeks; measles cycles over several years with susceptible build-up rather than
following a calendar. Seasonal-baseline algorithms such as Farrington (which does
down-weight past outbreaks [5]) remain useful for endemic, seasonal diseases — Ethiopia's
EPIDEMIA project uses it for malaria in Amhara [6] — but they are not the core engine for
measles.

### 6.2 Outbreak thresholds (checked against the EPHI PHEM Guideline 2022; configurable)
| Rule | Definition | Source |
|---|---|---|
| **Alert threshold** | A single suspected measles case | PHEM Guideline 2022, Table 4-5, p. 67 |
| **Action threshold** | ≥5 suspected **or** ≥3 confirmed cases (IgM-positive **or** epidemiologically linked) in a specified area within 1 month | PHEM Guideline 2022, Table 4-5, pp. 67–68; consistent with WHO AFRO [7] |
| Humanitarian alert | Double the average of the last 3 weeks (IDP and refugee settings) | PHEM Guideline 2022, Table 4-6, p. 71 |
| Approaching action threshold | 3–4 suspected within 1 month, or 2 confirmed | Internal priority flag, not an EPHI rule |
| Case fatality flag | Above 3% in an outbreak | PHEM Guideline 2022, Table 4-5 (acceptable case fatality rate) |

- **"Specified area":** woreda or facility catchment by default. EPHI to confirm.
- **Proposed change to the alert ladder (awaiting decision):** the two triggers of the
  action threshold are one EPHI rule, and our RED/ORANGE/YELLOW colours clash with the PHEOC
  activation levels. See `EPHI_ALIGNMENT.md` §1.

### 6.3 Early-rise flags (sub-threshold)
- **EARS C1, C2, C3** (US CDC): compare the current count with the mean and standard
  deviation of a recent baseline window; C2/C3 add a guard band and C3 accumulates. Used
  where history is short.
- **Poisson CUSUM**: accumulates small excesses over expected counts; good for slow rises.
- Implemented in Python and unit-tested against hand-computed examples from the published
  definitions.

---

## 7. Event-based surveillance (field-first)

Ethiopia's own model of event-based surveillance is community triggers reported by health
extension workers. Public social media rarely carries measles before an outbreak is
already large, so Phase 1 does not scrape it.

Phase 1 sources:
1. **Structured intake API** (`POST /intake/trigger`) using the trigger schema in §3.2.
   - It is channel-agnostic. SMS, Telegram or eCHIS adapters will be chosen after the
     EPHI interviews (`INTERVIEW_GUIDE.md`).
   - **Trigger types are configuration, not code.** They come from the EPHI community
     event-based surveillance trigger list, to be checked against the manuals in
     `docs/references/ephi/`.
   - The list includes "unusual animal deaths", with a `species` field (One Health
     groundwork, §13).
2. **EPHI weekly bulletins** (printed PDFs) are parsed into tables.
   - They come in by manual upload.
   - Past bulletins also form a historical test set (§10).
   - Bulletins are irregular and late, so they are a lagging source, not a live feed.
3. **ReliefWeb API, WHO AFRO bulletins, WHO Disease Outbreak News** for Ethiopia and its
   neighbours. These give context and cross-border signals, and produce at most YELLOW.

Community triggers have low positive predictive value: about 6% in an evaluation in Doolo
zone (`METHODOLOGY.md` §4.9). Verification is therefore part of the design, not an
extra.

### 7.1 Data source registry
Each source is recorded with its licence, update frequency, resolution, owner, access
status and the diseases it serves. The registry lives in `METHODOLOGY.md` §9 and becomes
a database table when the first context feed is added (M4).

| Category | Sources |
|---|---|
| Routine surveillance | PHEM weekly / EPI monthly via DHIS2 (pull blocked until EPHI written approval) |
| Community triggers | CEBS intake |
| Open-source intelligence | ReliefWeb, WHO AFRO, WHO DON; EIOS via partnership |
| Population / immunity | OCHA COD-PS, WorldPop, WUENIC, DHS, IHME |
| Displacement / conflict | IOM DTM, UCDP, ACLED (after licence check) |
| Climate (disease #2 onward) | CHIRPS, ERA5, MODIS; reuse EPIDEMIA and DHIS2 CHAP |
| One Health | WOAH WAHIS, FAO EMPRES-i |

Pipeline: extract (existing `ExtractionAgent`) → hierarchical geocode (§4) → cluster
(same disease, same unit, 14-day window) → `signals` with status *pending* → human
verdict. Verdict-labelled examples are exported as the Ethiopian-language corpus.

Deferred: photo OCR of handwritten forms (digit misreads would trip thresholds; accuracy
must be measured on real forms first) and any channel-specific bot.

---

## 8. Fuse — the evidence ladder

A clinical or laboratory threshold crossing is never downgraded for lack of
corroboration.

| Tier | Condition | Expected action |
|---|---|---|
| **RED** | Confirmed-outbreak threshold crossed | Outbreak response |
| **ORANGE** | Suspected-outbreak threshold crossed, **or** a verified field cluster | Investigate within 48 hours |
| **YELLOW** | Early-rise flag, unverified field trigger, or bulletin/ReliefWeb mention | Verify |

Modifiers — a high ignition-risk index, a surveillance-silent unit, conflict or
displacement — raise priority *within* a tier and are shown as evidence. A high index
plus a verified signal raises YELLOW to ORANGE. Modifiers never lower a tier.

---

## 9. Explain — grounded language generation

- LLMs extract structure from text, extract place hints, and write explanations and
  situation reports.
- Explanations and situation reports are generated **only** from the stored alert and
  evidence JSON, and cite the records they draw on. The LLM never sets a risk level.
- All LLM calls go through one `LLMProvider` interface (`services/llm.py`) with enforced
  JSON output, so the provider can change without touching business logic.

### 9.1 AI beyond language
AI is used as a capability multiplier, not only for reading text. The rule is:

> **AI proposes, compiles and explains. Statistics decide. People verify.**

Planned uses include:
- a sitrep compiler, in which numbers are inserted by code;
- an OSINT monitor that also removes duplicate signals;
- a bulletin digitiser that checks its tables against the printed totals;
- a guideline assistant over the EPHI manuals, which must cite its sources;
- an analyst copilot that turns questions into read-only SQL and charts;
- data-quality triage;
- alias and boundary curation, with every change approved by a person;
- a calibration and sensitivity assistant;
- once laser-measles is calibrated, a scenario agent that runs what-if simulations.

Each use is treated as a hypothesis and measured locally. The full table, with
guardrails and metrics, is in `METHODOLOGY.md` §10.

---

## 10. Evaluation

Detection and prediction are evaluated on **synthetic Ethiopian data**, never tuned on
data from other countries (German data is used only to test that code computes
correctly).

- **Simulator:** IDM's `laser-measles` (Python, MIT licence) spatial compartmental model
  at zone level, seeded with public Ethiopian inputs (WorldPop births, IHME admin-2 MCV1
  estimates [10], campaign history). A reporting layer adds per-zone reporting rates,
  2–4 week delays, ~10% missing reports and ~15% late batch backfills, and records true
  outbreak onsets.
- **Detection metrics:** sensitivity, positive predictive value, false alerts per
  unit-year, days from onset to detection (the "detect" part of the 7-1-7 target [11]).
- **Risk-index metrics:**
  - precision@k and recall@k: do the top-k zones contain next quarter's outbreaks?
  - **lead time:** the weeks between a zone entering the top-k and its outbreak;
  - comparison with the baselines in §5.5.
- **Circularity guard.** The simulator is also run with mixing and parameters that differ
  from the risk model's own, so that good scores are not just two models agreeing.
- **Real-history checks:** past EPHI bulletins and ReliefWeb / WHO AFRO outbreak reports
  now; DHIS2 history once approved.
- Reports are written to `evaluation/reports/`.

**Why laser-measles is the test bed and not the live engine.**
- Calibrating it needs Ethiopian case history.
- Weekly users need factors they can see.
- Using one simulator both to generate the test data and to forecast would make the test
  circular.

Once calibrated, it becomes a scenario engine and a challenger forecast (`METHODOLOGY.md`
§6).

---

## 11. Deferred (with the reason)

| Item | Why deferred | Trigger to start |
|---|---|---|
| Alert-triage classifier (logistic regression / XGBoost) | Needs labelled verdicts | A few hundred officer verdicts |
| Fitted gravity parameters; endemic-epidemic (hhh4-style) model; Bayesian spatio-temporal model (PyMC/NumPyro in place of INLA); fitted TSIR; XGBoost risk | Needs real multi-year history | EPHI DHIS2 access |
| Nowcasting of reporting delays | Needs reporting-date history | EPHI DHIS2 access |
| Calibrated laser-measles scenarios | Needs calibration to Ethiopian history | EPHI DHIS2 access |
| One Health analytics (WAHIS, EMPRES-i, scan statistics) | Measles pilot first; the groundwork (registry entries, animal-death trigger) is done now | After the measles pilot |
| Photo OCR of paper forms (see 11.1) | Error-prone on handwriting; the old cloud pipeline was removed | Accuracy measured on real forms |
| SMS / Telegram / eCHIS channels | Governance and channel choice | EPHI interviews and agreement |
| Disease #2 (cholera/AWD, zoonoses) | Measles pilot first | Pilot results |
| Feeds out to CHAP and WHO PDX | Needs a stable engine | After Phase 1 |

### 11.1 Sovereign, on-premises document processing (decided October 2026)

**What changed.** The old document pipeline (`POST /process`: YOLO layout detection,
then PaddleOCR, then Gemini Vision) was removed at the start of M2. Its model weights
were never in the repository, it pulled several GB of packages (PyTorch, PaddlePaddle,
NVIDIA libraries) that fail to install on ordinary PCs, and no page used it. Uploads of
images and PDF pages still work through Gemini vision in `/outbreak/upload`.

**Target design.**
- **Model:** an open-weight vision-language model (VLM) running on infrastructure in
  Ethiopia, for example in the EPHI data centre, so documents never leave the country.
  The Qwen2.5-VL family is a candidate; choose the best open model available at
  implementation time by benchmark, not by name.
- **Serving:** Ollama for a single workstation, or vLLM for a shared GPU server.
- **Integration:** it plugs in behind the `LLMProvider` interface (`services/llm.py`),
  so the agents do not change.

**Prerequisites and open risks. Each must be resolved before adoption.**
1. **The interface is text-only today.** `LLMProvider` has `generate_text` and
   `generate_json`. Image reading bypasses it and calls
   `GeminiService.generate_vision_text` directly. Step one is to add a
   `generate_vision(images, prompt)` method and route uploads through it. Any local
   model needs this.
2. **Script and handwriting accuracy is unproven.** Forms are written in Amharic and
   Tigrinya (Ge'ez script) and Afaan Oromo (Latin script), often by hand. Accuracy of
   open VLMs on handwritten Ge'ez is not established.
   - *Acceptance test:* a labelled sample of real Ethiopian forms, measured by
     character error rate and by exact-match accuracy on case counts and dates.
   - *Why the bar is high:* a misread digit can trip, or hide, an outbreak threshold
     (section 6).
3. **Hardware is needed.**
   - A 7B-class VLM needs a GPU with roughly 16 GB of memory at 16-bit precision
     (about half that when quantized).
   - 70B-class models need a multi-GPU server.
   - Budget, hosting and maintenance must be agreed with EPHI.
4. **Sovereignty is wider than documents.** Today every text agent sends report text,
   which can identify patients, to a cloud model (Gemini). If EPHI requires data
   residency, the text agents also need a local open-weight model.
   - This works through the same `LLMProvider` interface. vLLM and Ollama both expose
     an OpenAI-compatible endpoint, so one adapter covers both.
   - Confirm the requirement in the data-governance questions of
     `docs/INTERVIEW_GUIDE.md`.

**Trigger to start:** EPHI confirms its data-residency requirement, a labelled sample
of forms is available, and the GPU hardware is identified.

### 11.2 Ideas carried over from the earlier design documents (reviewed October 2026)

The hackathon-era documents (now in `docs/archive/`) described several features that were
never built. Each idea was reviewed on its merits. Ideas worth having are **kept** or
**reshaped** and given a place in the plan. Ideas the evidence or the new design makes
unnecessary are **retired**, with the reason.

**Field reporting and connectivity**

| Idea | Decision | Future design | When |
|---|---|---|---|
| **SMS gateway for health extension workers (HEWs)** | **Keep** | <ul><li>An SMS adapter on `POST /intake/trigger`, through a short code with Ethio Telecom or an aggregator.</li><li>Two message forms:<ul><li>a short coded syntax, for example `MSL 4 0 KEBELE-NAME` (trigger, cases, deaths, place), parsed by rules with no AI;</li><li>free text, parsed by the extraction agent and confirmed back to the sender by SMS ("Received: 4 suspected measles, Dubluk. Reply 1 to confirm").</li></ul></li><li>USSD menus are an alternative for structured entry.</li><li>Works on any phone without mobile data.</li></ul> | After the EPHI interviews settle the channel (SMS vs Telegram vs eCHIS, §7). The intake API it plugs into is M4 |
| **Two-way SMS to officers: alert notices and a daily or weekly digest** | **Keep** | <ul><li>A RED or ORANGE alert sends an SMS to the responsible woreda and zone officers, who acknowledge it by reply.</li><li>A short digest of top alerts per area is sent on a schedule.</li><li>Acknowledgement time feeds the 7-1-7 "notify" metric.</li></ul> | With M5 alerts, through the same gateway |
| **Offline working** | **Reshape** | <ul><li>The data-entry pages become an installable web app that saves reports on the device and sends them when a connection returns.</li><li>The SMS path already works without data.</li><li>This replaces the old idea of a sync agent on a woreda laptop: a second server to maintain at every woreda is not realistic.</li></ul> | After M5, once the field workflow is agreed |
| **"Safe capture": never lose input when AI is down** | **Keep. Partly built** | <ul><li>Raw input is stored first, and AI processing follows.</li><li>**Built:** analyses that fail partway are flagged and re-run by `scripts/reprocess_failed.py`.</li><li>**Gap:** when AI quota runs out, or extraction fails completely, the report is not stored and must be resubmitted.</li><li>**To do:** store the raw input first, then queue it for automatic retry.</li></ul> | M4 |

**AI agents**

| Idea | Decision | Future design | When |
|---|---|---|---|
| **Multi-agent orchestration (SuperAgent)** | **Reshape** | <ul><li>Agents stay, with a different job: **agents that use tools**, not agents that give opinions.</li><li>An orchestrator calls deterministic tools (database queries, the geocoder, detection rules, the risk model, the simulator) and composes the result.</li><li>This is how the sitrep compiler, OSINT monitor, analyst copilot and scenario agent work (`METHODOLOGY.md` §10).</li></ul> | M4–M5, then ongoing |
| **Four-perspective risk vote and confidence averaging** | **Retire** as the risk engine | <ul><li>It averages a language model's opinion of its own risk call, and that self-reported confidence is not calibrated.</li><li>A single HIGH vote is diluted by the others.</li><li>Replaced by the statistical risk index (§5) and the alert tiers (§8).</li><li>The code stays until M5 so the current pages keep working.</li></ul> | Removed at M5 |
| **Generator plus checker (the useful part of "multi-agent consensus")** | **Keep, as a new pattern** | <ul><li>A second, independent check reviews every AI draft (explanation, sitrep, OSINT extraction) against the stored evidence.</li><li>It flags any claim, number or place that the evidence does not support.</li><li>Flagged drafts go to a person.</li></ul> | M5, with the sitrep compiler |
| **Validation agent** | **Reshape** | <ul><li>Plausibility checks become rules: impossible counts, missing required fields, a date in the future, a duplicate of an existing cluster.</li><li>AI only explains a failed check.</li><li>Today it is AI-only and marks a report valid when the call fails. That default is a known flaw, to be fixed in M4.</li></ul> | M4 |
| **Chat specialists (Location / Infection / History)** | **Reshape** | Becomes the analyst copilot: questions are answered by generated, read-only database queries and charts, with the query shown to the user. Separate "specialist" prompts add little once answers come from data | M5 |
| **Parallel sub-agents for large batches** | **Keep, as an implementation detail** | Bounded parallel processing for bulk uploads and bulletin backfills, within the AI quota pacing that is already built | M4 |

**Knowledge, trust and models**

| Idea | Decision | Future design | When |
|---|---|---|---|
| **Retrieval over EPHI guidelines (RAG)** | **Keep** | <ul><li>A guideline assistant over the public manuals in `docs/references/ephi/`.</li><li>Every answer quotes its source passage and page.</li><li>It also drafts disease-module configurations for a person to approve.</li></ul> | M4, after the manuals are added |
| **Source trust ranking** | **Reshape** | <ul><li>Trust is measured, not judged by AI.</li><li>Each source, and later each reporter, gets a positive predictive value: the share of its signals that officers verify.</li><li>This then informs triage priority.</li></ul> | Once a few hundred verdicts exist (with the triage model, §11) |
| **Gold-standard dataset for local models** | **Keep** | <ul><li>Officer-verified extractions are exported (`scripts/export_corpus.py`, M4).</li><li>They become the test set, and later fine-tuning data, for an on-premises open-weight model (§11.1).</li><li>They also measure accuracy per language (Amharic, Afaan Oromo, Tigrinya).</li></ul> | M4 export; fine-tuning with §11.1 |
| **Suspected / probable / confirmed classification** | **Keep. Built** | Already a field on every signal. Align the definitions with the EPHI manuals | M4 |
| **Full reasoning audit trail per record** | **Keep. Built** | The record detail page. Extend it to show geocode candidates and rule outcomes | M5 |

**Retired**

| Idea | Decision | Reason |
|---|---|---|
| **Alert agent writing public health messages** ("boil water…") | **Reshape** | <ul><li>Public messaging belongs to EPHI's risk communication team.</li><li>Drafts are for officers only, clearly labelled as drafts.</li><li>Nothing goes to the public from this system.</li></ul> |
| **Web research by scraping Google and Bing** | **Retire** | <ul><li>The results are unreliable and against the search engines' terms.</li><li>Replaced by the data source registry (§7.1): ReliefWeb, IOM DTM, UCDP/ACLED and WHO AFRO through their published access routes.</li><li>Targeted fetching of a known official page is allowed where no API exists.</li></ul> |
| **YOLO layout detection and PaddleOCR** | **Retire** | Removed in M2. Superseded by the open-weight vision model route (§11.1) |
| **"Gemini 1.5 Flash for Amharic and a 1M-token context" rationale** | **Retire** | <ul><li>That model is retired.</li><li>The claims were not measured.</li><li>Model choice is now a configuration setting (`GEMINI_MODELS` / `LLM_PROVIDER`).</li><li>Language accuracy is measured on the verified corpus.</li></ul> |

---

## 12. Integration roadmap
- **EPHI PHEOC / PHEM directorate:** primary user and data partner; DHIS2 access via
  agreement; field intake channel decided jointly.
- **DHIS2 CHAP:** contribute measles models as CHAP-compatible models; consume CHAP
  forecasts for climate-sensitive diseases later.
- **WHO AFRO PDX:** federated design — publish Ethiopian risk indicators to PDX rather
  than duplicating it.
- **WHO EIOS / Africa CDC Eastern Africa RCC:** cross-border signals as inputs.

---

## 13. Multi-disease design and One Health (agreed October 2026)

| Archetype | Examples | Detection | Risk drivers |
|---|---|---|---|
| Vaccine-preventable | Measles, diphtheria, pertussis | Thresholds + EARS/CUSUM | Susceptible build-up, importation |
| Climate-sensitive | Malaria, dengue | Seasonal baselines (reuse EPIDEMIA, DHIS2 CHAP) | Rainfall, temperature, vegetation |
| Water-borne | Cholera / AWD | Thresholds | Water, displacement, flooding, cross-border |
| Zoonotic / One Health | Anthrax, rabies, Rift Valley fever | Scan statistics; animal-event triggers | Animal outbreaks, livestock movement, rainfall |

- Thresholds and case definitions for each disease come from the EPHI manuals. The public
  PDFs go in `docs/references/ephi/`.
- **One Health:**
  - **Now:** registry entries for WOAH WAHIS and FAO EMPRES-i, and an animal-death trigger
    with a species field.
  - **After measles:** analytics.

---

## 14. Glossary (plain language)
- **Baseline:** the count that is normal for a place and time; alarms compare against it.
- **Threshold rule:** a fixed count that defines an outbreak (e.g. ≥3 confirmed cases a month).
- **Sensitivity:** of the real outbreaks, the share the system caught.
- **Positive predictive value (PPV):** of the system's alerts, the share that were real.
- **Susceptible:** a person who can still catch measles (not vaccinated successfully, never infected).
- **Reporting rate (ρ):** the share of true infections that appear in the data.
- **Importation pressure:** how much infection is nearby and likely to arrive.
- **Supervised vs unsupervised:** supervised models learn from labelled examples; threshold
  and baseline methods need no labels.
- **Backtesting:** running a model on past data as if in real time, then checking it
  against what actually happened.
- **Calibration:** tuning a simulator or model until its output matches reality.

---

## References
1. Sbarra AN et al. Fitting dynamic measles models to subnational case notification data from Ethiopia. *PLOS Comput Biol* 2025. https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012922
2. Finkenstädt BF, Grenfell BT. Time series modelling of childhood diseases. *J R Stat Soc C* 2000; implemented in R package `tsiR`. https://www.rdocumentation.org/packages/tsiR/versions/0.2.0
3. Bias in the estimated reporting fraction due to vaccination in the time-series SIR model. *PLOS ONE* 2025. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0330568
4. Xia Y, Bjørnstad ON, Grenfell BT. Measles metapopulation dynamics: a gravity model for epidemiological coupling and dynamics. *Am Nat* 2004. https://www.journals.uchicago.edu/doi/abs/10.1086/422341
5. `farringtonFlexible` documentation, R package `surveillance`. https://surveillance.r-forge.r-project.org/pkgdown/reference/farringtonFlexible.html
6. Merkord CL et al. Integrating malaria surveillance with climate data for outbreak detection and forecasting: the EPIDEMIA system. *Malar J* 2017. https://link.springer.com/article/10.1186/s12936-017-1735-x
7. WHO AFRO. African Regional Guidelines for Measles and Rubella Surveillance (2015). https://www.afro.who.int/sites/default/files/2017-06/who-african-regional-measles-and-rubella-surveillance-guidelines_updated-draft-version-april-2015_1.pdf
8. Measles outbreak investigation in Guji zone of Oromia Region, Ethiopia. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5619924/
9. Insights from a measles outbreak root cause analysis in Ethiopia, 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC12595561/
10. LBD Vaccine Coverage Collaborators. Mapping routine measles vaccination in low- and middle-income countries. *Nature* 2021. https://www.nature.com/articles/s41586-020-03043-4
11. Evaluation of measles outbreak response in Geze Gofa district using the 7-1-7 timeliness metrics. https://pmc.ncbi.nlm.nih.gov/articles/PMC13224625/
