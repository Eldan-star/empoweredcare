# EPHI alignment review

_October 2026. This document checks Empowered Care's design against the four EPHI documents
in `docs/references/ephi/`. Page numbers are the printed page numbers in each source._

| Short name | Document |
|---|---|
| **PHEM 2022** | Public Health Emergency Management Guideline for Ethiopia, 2nd edition, December 2022 (EPHI/MOH) |
| **CEBS 2021** | Community and Event Based Surveillance Implementation Manual, September 2021 (EPHI) |
| **PHEOC 2022** | National Public Health Emergency Operations Center Handbook, April 2022 (EPHI/MOH) |
| **HF-PHEM 2023** | PHEM at Healthcare Facilities: Participant Manual, April 2023 (EPHI/MOH) |

Where the documents differ, PHEM 2022 is treated as the authority. It is the newest
guideline, and CEBS 2021 still cites the 2012 edition.

**Summary.**
- **Confirmed by the manuals:**
  - the data model;
  - the Monday–Sunday weekly periods;
  - completeness tracking;
  - the field-first event-based surveillance design;
  - the verification workflow;
  - the SMS plan.
- **Corrections needed:** three, in the measles rules and alert design (§1).
- **New features worth building:** several, because the manuals define exact formats and
  indicators that Empowered Care can produce automatically (§4).

---

## 1. What must change

### 1.1 Measles thresholds: EPHI uses "alert" and "action", and both triggers are equal

PHEM 2022, Table 4-5, pp. 67–68:

| | EPHI definition | What our spec said | Change |
|---|---|---|---|
| **Alert threshold** | **A single suspected case** | Not modelled. We had an internal "approaching" rule of 3–4 suspected cases | Every suspected measles case is an alert. Response: report, collect a blood sample, investigate |
| **Action threshold** | **5 suspected cases OR 3 confirmed cases in a specified area within 1 month** | Two separate rules: suspected → ORANGE, confirmed → RED | The two triggers are **one** EPHI threshold, joined by "or". Splitting them into two tiers is not EPHI practice |
| Acceptable case fatality rate | 3% of measles cases | Not used | Add as an indicator: case fatality above 3% in an outbreak is flagged |
| Humanitarian settings (Table 4-6, p. 71) | **Alert: double the average of the last 3 weeks**; action defined at country level | Not used | Use this as the official early-rise rule for camps and displaced populations. It is effectively an EARS-type rule, so our statistical approach now has an EPHI basis |

**"Confirmed" includes epidemiological linkage.** The standard case definition (Annex 5,
p. 155) says a confirmed case is "a suspected case with laboratory confirmation (positive
IgM antibody) **or** epidemiological link to confirmed cases in an outbreak". The final
classification on the case-based form (Annex 10) has four values: laboratory confirmed /
confirmed by epidemiological linkage / clinically compatible / discarded. Our count of
confirmed cases must include epi-linked cases. Our `classification` field must use these
four values, not suspected / probable / confirmed.

**"Specified area" is not defined.** The default stays woreda or health-facility catchment,
and it is configurable. Ask EPHI which unit they apply.

### 1.2 Our alert colours clash with the PHEOC activation levels

PHEOC 2022 (§9.1.4–9.1.5, pp. 33–35) uses **Green** (steady state) and **Yellow / Orange /
Red** (activation levels 3 / 2 / 1, with Red the highest) for the **national or regional
emergency operations center's activation**. Our design used RED / ORANGE / YELLOW for a
**woreda's weekly alert tier**.

An EPHI officer seeing "RED" in our tool would read "Level 1 PHEOC activation", which is a
national crisis. That misreading is a real safety and credibility problem.

**Recommendation:** use EPHI's own words for our ladder, and keep the colours for the PHEOC.

| Proposed level | Condition (measles) | EPHI basis |
|---|---|---|
| **Action threshold** | ≥5 suspected or ≥3 confirmed (lab or epi-linked) in the area within 1 month | PHEM 2022 Table 4-5 |
| **Alert threshold** | ≥1 suspected case; or, in humanitarian settings, double the 3-week average | PHEM 2022 Tables 4-5 and 4-6 |
| **Signal (unverified)** | Community trigger, rumour or media report awaiting verification | CEBS 2021 p. 14; PHEM 2022 Annex 4 |

- The risk index, early-rise statistics, "approaching action threshold" (3–4 suspected),
  surveillance silence and threat factors all become **priority and evidence within a
  level**. They are never a level of their own. This keeps our rule that nothing lowers a
  threshold-based level.
- **Open question:** should "high risk index + verified signal" still raise a signal to
  alert? Since a single suspected case is already an alert under EPHI rules, the case for
  that upgrade is weaker. I suggest dropping it.

### 1.3 Measles is immediately reportable, so case-based data is the fast data

PHEM 2022, Table 4-1 (p. 52), lists measles among the 22 **immediately reportable**
diseases. The rules:
- **Immediate notification, at each level** (p. 56): a single suspected case is a suspected
  outbreak and is notified from level to level within **30 minutes**, up to the federal
  level.
- **Case-based reporting** (Annex 8, p. 182): the first 5 suspected cases are reported on
  the case-based reporting form. Beyond 5 in a month, a daily line list is used. After 100
  cases, woredas send daily summaries (DERF-W) and zones and regions send DERF-R.
- **Weekly totals** (pp. 56–57) are still reported. A blank is not allowed: a week with no
  cases must be reported as **zero**.

**What this means for the design:**
- Weekly aggregates (`indicator_counts`) are the backbone, but they are slow. The weekly
  chain runs: facility → woreda by Monday midday, woreda → zone/region by Tuesday, region →
  EPHI by Thursday, EPHI → stakeholders by Friday (p. 57). National weekly data is about
  5–11 days old.
- The fastest measles data is **case-based and line-list data**. We need to know whether it
  exists electronically (a DHIS2 Tracker program, or paper only). This is a new interview
  question.
- **Missing must stay different from zero.** A week with no report stays NULL, and a
  reported zero is stored as 0. "Surveillance silent" means no report, not zero cases.

---

## 2. What the manuals confirm

| Our design | EPHI source | Status |
|---|---|---|
| Weekly periods Monday–Sunday (ISO weeks) | PHEM 2022 p. 57; the weekly forms use the "WHO EPI-week", Monday to Sunday | ✅ Matches `indicator_counts` (iso_year, iso_week) |
| Completeness = facilities reported ÷ facilities expected; timeliness = reports on time | PHEM 2022 pp. 74–75 | ✅ Matches `reports_expected` / `reports_received`. Add a timeliness field |
| Event-based surveillance led by health extension workers through community triggers | CEBS 2021; PHEM 2022 pp. 43–45 | ✅ Field-first design confirmed |
| Signals must be verified before action | CEBS 2021 p. 14: the HEW verifies within **1 hour** using the community case definition. PHEM 2022 Annex 20 indicator: verified within 24 hours | ✅ The signals review page is the right core feature |
| Low positive predictive value is expected and must be measured | CEBS 2021 pp. 30, 38 (PPV and sensitivity are named CEBS indicators) | ✅ Matches METHODOLOGY §4.9 |
| SMS is an accepted notification channel | CEBS 2021 p. 14 (phone, SMS, notification cards); PHEM 2022 p. 57 (weekly reports by SMS allowed); PHEOC 2022 (call center plans voice and SMS) | ✅ Supports the SMS plan (SYSTEM_SPEC §11.2) |
| Media and online monitoring is a legitimate source | PHEM 2022 p. 44 (ProMED, blogs, social media, radio, TV); PHEOC 2022 p. 26: media and web scanning is a **watch-mode duty** of PHEOC staff | ✅ The OSINT monitor supports an existing EPHI duty |
| Animal events belong in community surveillance | CEBS 2021 pp. 4, 7: "people sick after eating meat or contact with dead or sick animals within 7 days"; clusters and rumours of animal deaths. PHEM 2022 Annex 7, p. 181: "increase in number of animal sicknesses and/or deaths… within one week" | ✅ The One Health trigger is confirmed. A `species` field is our addition |
| Displacement matters | PHEM 2022: separate humanitarian thresholds (Table 4-6). PHEOC 2022: incidents among IDPs, refugees and mass gatherings are activation criteria (pp. 30–31) | ✅ Supports the threat/priority factor (METHODOLOGY §4.5) |
| Connectivity is poor at facilities | HF-PHEM 2023 p. 67: 64% of facilities assessed for DHIS2 readiness had no internet, and 70% had no computer dedicated to IDSR | ✅ Supports SMS and offline entry. Expect facility data to be entered at woreda level, with delays |
| Situation reports are a core product | PHEOC 2022 pp. 26, 43: weekly summary, SITREP and SPOTREP | ✅ The sitrep compiler should fill EPHI's own templates (§4.3) |

---

## 3. Details to build in

### 3.1 Case definitions (measles)

| Level | Definition | Source |
|---|---|---|
| Community (health extension worker) | "Any person with fever and rash" | PHEM 2022 Annex 7, p. 181 |
| CEBS health-worker list | "Rashes: any person with fever and vesicular, maculopapular or pustular rashes on any part of the body" | CEBS 2021 Table 1, p. 6 |
| Community member (syndromic) | "Any person with rash and/or fever" | CEBS 2021 p. 5 |
| Standard: suspected | "Any person with fever and maculopapular (non-vesicular) generalized rash and cough, coryza or conjunctivitis (red eyes) or any person in whom a clinician suspects measles" | PHEM 2022 Annex 5, p. 155 |
| Standard: confirmed | Suspected case with positive IgM, or an epidemiological link to confirmed cases in an outbreak | PHEM 2022 Annex 5, p. 155 |

**A community "rash" signal is not a measles case.** The CEBS "rashes" syndrome also
covers chickenpox, mpox and smallpox (vesicular and pustular rashes). Community signals are
stored as **syndromes** with a list of candidate diseases. They only become measles cases
once a facility applies the standard definition.

### 3.2 The rumour log book shapes the field-signal record

PHEM 2022 Annex 12 (p. 195) gives the health-post rumour log columns. Our intake record
(SYSTEM_SPEC §3.2) should carry the same fields, so that CEBS timeliness indicators
compute automatically:
- date of onset;
- date and time first seen by the notifier;
- date and time of notification;
- type of condition;
- village or specific location;
- number of suspected cases;
- date first seen at a health facility;
- tentative diagnosis;
- date and time the HEW verified it;
- date an investigation was requested, and date it was done;
- result (verified / ruled out);
- intervention dates and type (health post, health center).

### 3.3 Timeliness standards to measure against

| Step | Standard | Source |
|---|---|---|
| Community → health post | 30 minutes (target: 80% on time) | CEBS 2021 p. 14 |
| HEW verification | 1 hour | CEBS 2021 p. 14 |
| Notification up each level | 30 minutes per level; MOH → WHO within 24 hours | PHEM 2022 p. 56 |
| Verification of events | Within 24 hours | PHEM 2022 Annex 20 |
| PHEOC activation after risk assessment | 120 minutes | PHEOC 2022 p. 28 |

These sit alongside the 7-1-7 targets (HF-PHEM 2023 cites EPHI's 2022 retrospective 7-1-7
review).

### 3.4 Thresholds for future diseases (for the disease modules)

- **Malaria** (Table 4-5):
  - alert above the 5-year weekly median;
  - action above the third quartile (the second-highest of the previous 5 years for that
    week), or above twice last year's count for that week.

  This is EPHI's own seasonal method. Build it first, and compare Farrington-type methods
  against it.
- **Meningitis:** thresholds depend on population.
  - Under 30,000: alert at 2 cases a week, action at 5.
  - Over 30,000: alert at 5 per 100,000 per week, action at 15 per 100,000.

  The woreda populations we have loaded supply the denominators.
- **Cholera, anthrax, VHF, yellow fever, mpox, Rift Valley fever:** alert at a single
  suspected case, action at a single confirmed case.
- **Dysentery:**
  - alert at ≥5 cases in one location in one day, or double the weekly average;
  - action at the same counts of confirmed cases.

The full table is PHEM 2022 pp. 67–70. Humanitarian variants are on p. 71.

---

## 4. New features the manuals suggest

| # | Feature | Why | When |
|---|---|---|---|
| 1 | **CEBS indicator dashboard**, computed automatically from signals | <ul><li>CEBS 2021 Annex 1 defines the indicators: signals reported, triaged, verified; events responded to; % notified within 1 hour; % meeting the community case definition; positive predictive value.</li><li>Today they are counted by hand from log books.</li><li>HF-PHEM 2023 lists "poor documentation of rumors and a limited verification system" as a national gap.</li></ul> | M4, with the signals review page |
| 2 | **IDSR timeliness and completeness monitor** | Weekly completeness and timeliness by woreda (PHEM 2022 pp. 74–75), plus the time from detection to each notification step | M3 data layer; shown in M5 |
| 3 | **Sitrep compiler using EPHI's templates** | Fills the PHEOC SITREP (Annex 6), SPOTREP (Annex 21) and weekly summary formats, so drafts match what PHEOC staff already produce | M5 |
| 4 | **Rapid risk assessment pre-fill** | <ul><li>The PHEOC RRA template (Annex 12, pp. 71–72) asks for the likelihood and consequence of health impact, spread and control capacity, an overall risk (low → very high) and confidence.</li><li>AI drafts the evidence section from stored data: cases, susceptibility, neighbouring outbreaks, displacement, past outbreaks.</li><li>The **team sets the grade**.</li></ul> | M5 (AI use; METHODOLOGY §10) |
| 5 | **VRAM support** | <ul><li>EPHI's vulnerability risk assessment and mapping ranks hazards for preparedness planning: hazard, vulnerability and capacity (PHEM 2022 pp. 22–23).</li><li>The measles risk index is a data-driven input to VRAM, not a replacement. That is how to position it with EPHI.</li></ul> | M3 output; presentation |
| 6 | **Response checklist per level** | <ul><li>For measles at the alert threshold: report, sample, treat with vitamin A, investigate.</li><li>At the action threshold: supplementary vaccination, community mobilisation (PHEM 2022 Annex 6, p. 170).</li><li>Shown next to each alert, with case fatality monitored against the 3% acceptable rate.</li></ul> | M5 |
| 7 | **eCHIS integration target** | <ul><li>CEBS 2021 (p. 22) assigns MOH to "integrate CEBS into electronic reporting (CHIS)".</li><li>Our intake should feed or read eCHIS, not compete with it.</li></ul> | Interview question; after the channel decision |

---

## 5. Questions for EPHI (added to INTERVIEW_GUIDE.md)

1. Is measles case-based or line-list data captured electronically (a DHIS2 Tracker
   program), or only on paper?
2. Which "specified area" do you use for the measles action threshold: woreda, kebele, or
   facility catchment?
3. Would you prefer our levels to use the PHEM terms (alert / action / signal)? Confirm that
   the RED/ORANGE/YELLOW colours should stay reserved for PHEOC activation.
4. Is the humanitarian alert rule (double the 3-week average) applied in IDP sites today?
5. How far has CEBS been integrated into eCHIS? Is there an API?
6. Do woredas enter facility weekly reports into DHIS2 on the facilities' behalf? This
   changes how completeness should be read.

---

## 6. About the source files

- The manuals were added as Markdown conversions. The original PDFs are not in the
  repository.
- The conversions read well. Tables survived, and printed page numbers appear as lines in
  the text, so citations by page work.
- Two conversion slips to remember:
  - one table row is split across a page break (the measles action threshold, pp. 67–68);
  - "Bruellosis" is a typo in the source list.
- **Suggestion:** add the PDFs next to the conversions when convenient, so any quote can be
  checked against the original.
