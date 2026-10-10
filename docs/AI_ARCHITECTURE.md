# AI architecture: where AI runs, where it doesn't, and where it's going

_Last revised: October 2026. This replaces the hackathon-era walkthrough, which is now in
`docs/archive/`. Each answer says what is **built today** and what is **planned**, so
nothing here claims more than the code does._

The rule throughout:

> **AI reads, extracts, compiles and explains. Statistics produce the numbers and alert
> levels. People verify.**

---

## The agents today

All agents are prompts to one language model (Gemini by default), each with its own
instructions. They live in `services/agents.py`. "Multi-agent" here means the code is
organised by job. It does not mean independent experts checking each other.

| Agent | What it does | Status | Future |
|---|---|---|---|
| **Extraction** | Turns messy text, CSV, PDF pages and images into structured reports (place, symptoms, cases, dates), splitting a message that covers several reports | Built | Kept. It becomes the core of field-signal and SMS intake |
| **Validation** | One AI call judges plausibility | Built | Reshaped into rules (impossible counts, missing fields, future dates, duplicates), with AI only explaining failures. Today it marks a report valid if the AI call fails, which is a known flaw |
| **Risk (four perspectives)** | One AI call returns four opinions (symptoms, statistical, historical, environmental), which are averaged into HIGH/MEDIUM/LOW | Built | **Retired at M5.** A language model's own confidence is not calibrated, and averaging dilutes a single alarm. Replaced by the statistical risk index and EPHI alert levels |
| **Alert writer** | Drafts the alert text | Built | Officer-facing drafts only. Public messages belong to EPHI risk communication |
| **Ask the data** (chat supervisor plus Location / Infection / History / General prompts) | Answers questions using the most recent reports (up to 10–15, depending on the page) | Built | Becomes the analyst copilot: generated, read-only database queries and charts, with the query shown |
| **Web research** | Scraped search-engine pages for local context | Off by default | **Retired.** Replaced by official data sources (ReliefWeb, IOM DTM, UCDP/ACLED, WHO AFRO) |

The place-name resolver is **not** AI. It is a deterministic matcher against the official
OCHA boundary list (`services/geocoder.py`).

## The agents planned

These agents call **tools** (database queries, the place-name resolver, detection rules,
the risk model, the outbreak simulator) and assemble what the tools return. They do not
give opinions. The full table, with guardrails and how each will be measured, is in
`METHODOLOGY.md` §10. The main ones are:
- **Sitrep compiler:** drafts the weekly situation report. Numbers are inserted by code.
- **OSINT monitor:** reads ReliefWeb and WHO AFRO daily, extracts events, removes
  duplicates, and raises a **signal** at most.
- **Bulletin digitiser:** turns printed EPHI bulletin tables into data and checks them
  against the printed totals.
- **Guideline assistant:** answers from the EPHI manuals, quoting page and passage.
- **Evidence checker:** reviews every AI draft against the stored evidence and flags
  anything unsupported.
- **Analyst copilot:** answers questions with SQL queries and charts.
- **Data-quality triage:** explains completeness drops and impossible values.
- **Scenario agent** (once the simulator is fitted to Ethiopian data): runs "what if the
  campaign is delayed" simulations.
- **SMS intake:** parses free-text SMS from health extension workers and confirms its
  reading back to the sender.

---

## Questions people ask

### 1. Where does AI run, and where doesn't it?

**AI runs in:**
- reading reports and documents;
- extracting place hints;
- answering questions;
- drafting alerts.

Planned, as listed above:
- compiling sitreps;
- monitoring sources;
- digitising bulletins;
- answering from the guidelines;
- explaining.

**AI does not run in:**
- sign-in and permissions;
- storage;
- matching places to official codes;
- outbreak thresholds;
- risk numbers (from M3);
- alert levels (from M5).

These are fixed rules and formulas that can be re-run and audited.

### 2. How is data from different sources standardised?

| Step | What happens |
|---|---|
| Extraction | AI maps free text to one schema |
| Validation | Pydantic models enforce types and required fields |
| Location | The place-name resolver gives every report an official OCHA P-code. It flags names that fit more than one place instead of guessing, and handles old names (SNNPR, pre-2023 South Omo) |
| Grouping | Reports of the same disease in the same place within 14 days share a cluster ID. Each report is kept; counts are not merged |
| Case classification | Suspected / probable / confirmed is stored on each report, to be aligned with the EPHI case definitions |

Routine data from DHIS2 arrives already structured. It is mapped to the same P-codes.

### 3. How is hallucination controlled?

**Built:**
- JSON output checked against a schema.
- Officer approval of every report.
- Places decided by the resolver, not the model.
- When AI quota runs out, the request is refused with a clear message, so no empty analysis is stored.

**Planned:**
- AI explanations may use only stored evidence, and must cite records.
- Numbers in drafts are inserted by code.
- An independent evidence checker flags unsupported claims.
- Rule-based validation replaces AI validation.

The old claim that "four agents reaching consensus filter out hallucinations" does not
hold: the four opinions come from the same model, in the same call.

### 4. How is risk scored, and how is source trust ranked?

- **Today:** the average of the model's four opinions. Treat it as a placeholder.
- **From M3:** a statistical measles risk index, built from:
  - susceptible children, from vaccination coverage, births and campaigns;
  - under-reporting estimated from the data;
  - infection pressure from neighbouring zones.

  It is a ranking, not a probability, until it is backtested (`METHODOLOGY.md` §4).
- **Source trust** will be **measured**, not judged by AI. Each source, and later each
  reporter, gets the share of its signals that officers verify.

### 5. Which AI model, and why?

- Google Gemini through the `google-genai` SDK. The model list is a setting
  (`GEMINI_MODELS`), because Google retires models regularly.
- Claude can be switched in with `LLM_PROVIDER=claude`.
- **No claim is made that any model is best for Amharic, Afaan Oromo or Tigrinya.**
  Accuracy per language will be measured on officer-verified reports before we rely on
  it.

### 6. What happens with little or no internet?

**Today:**
- The web app needs a connection.
- If one AI step fails partway, for example risk analysis, the report is still stored,
  flagged, and re-run later (`scripts/reprocess_failed.py`).
- If AI quota runs out, or extraction fails completely, the report is **not** stored. The
  submitter sees a message and must resubmit. The planned retry queue fixes this.

**Planned** (SYSTEM_SPEC §11.2):
- **SMS reporting for health extension workers**, which works on any phone without
  mobile data:
  - a short coded format parsed by rules;
  - or free text parsed by AI and confirmed back to the sender.
- **SMS alert notices and digests to officers**, acknowledged by reply.
- **An offline-capable data-entry app** that sends saved reports when a connection
  returns.
- **An automatic retry queue** for AI processing.

The channel (SMS, Telegram or eCHIS) is chosen with EPHI after the interviews.

### 7. Will AI run locally on open-source models?

Yes, if EPHI requires data residency (SYSTEM_SPEC §11.1):
- an open-weight model on servers in Ethiopia;
- served with Ollama or vLLM;
- behind the same provider interface.

**Prerequisites:**
- add image support to that interface;
- measure handwriting accuracy on real forms;
- identify GPU hardware.

Officer-verified reports become the test set, and later the fine-tuning data, for that
model.

### 8. Does the AI use the EPHI guidelines?

- **Not yet.** The planned guideline assistant (M4) searches the public EPHI manuals
  stored in `docs/references/ephi/`.
- Every answer quotes the passage and page it used.
- It also drafts disease settings (case definitions, thresholds, trigger lists) for a
  person to approve.
- The AI advises; the officer decides.
