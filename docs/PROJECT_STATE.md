# Project state and working agreement (checkpoint)

_Last updated: 11 October 2026. This file is the hand-over point between work sessions.
Read it first._

## Working agreement (from the project owner)

- **No code changes without the owner's OK.** In "discussion time", only discuss. Documents
  may be updated once a decision is agreed.
- **Commits:**
  - authored as **Daniel Gizaw `<70215398+Eldan-star@users.noreply.github.com>`**;
  - no attribution trailers;
  - the assistant's name must not appear in branch names, commit messages, PR text or code.
- **Repository:** work only in `Eldan-star/empoweredcare`, branch **`m2-data-foundation`**.
  Never touch the original upstream repository. No pull requests unless asked.
- **No Ethiopian DHIS2 pull before EPHI written approval.** The code enforces this with
  `DHIS2_PULL_APPROVED=false`. Do not ask for, or use, the owner's personal DHIS2 login.
- **Explanations:** beginner-friendly, plus honest, critical pushback when warranted. The
  owner wants evidence-based methods, not ones made up.
- **Owner's environment:**
  - Windows, PowerShell, Python 3.12 `.venv` (not WSL);
  - PostgreSQL local;
  - project at `C:\Users\danie\Documents\GitHub\Empoweredcare\empoweredcare`.
- **Repo and data:** the repo is public. The EPHI manuals are public documents, kept as
  Markdown in `docs/references/ephi/`.

## Milestones

| Milestone | Status |
|---|---|
| M0 docs, M1 stabilise + redesign, M2 data foundation | Done, merged to `main` at `f766a9a` |
| Strategy agreed | Done (`METHODOLOGY.md`, `SYSTEM_SPEC.md` §5.6, 7.1, 9.1, 11.2, 13) |
| Docs clean-up; prototype docs archived | Done (`docs/archive/`) |
| EPHI manual review | Done (`EPHI_ALIGNMENT.md`) |
| M3 analytics | Done on `m2-data-foundation`; verified by the owner on Windows (78 tests) |
| Improvements round | Done (commits `96b5aad`..`1d564df`): 88 tests pass; the owner has **not yet tested it** |
| M4 (signals intake, review page, CEBS indicators) | Not started |
| M5 (alerts, map, sitreps, frontend colour rework) | Not started |

**Branch state:**
- `m2-data-foundation` is ahead of `main` by all M3 and improvement commits.
- Alembic head is `94a5317d9cae`. Earlier revisions: `e43670afe39f` (initial),
  `9ddb11e10486` (EPHI fields and levels).

## Key decisions (agreed)

- **Alert levels use EPHI terms:** action threshold / alert threshold / signal.
  - Red, orange and yellow are reserved for PHEOC activation.
  - No statistic or index changes a level; they only order within a level.
- **Measles rules** (PHEM Guideline 2022, Table 4-5):
  - alert = 1 suspected case;
  - action = ≥5 suspected **or** ≥3 confirmed (lab or epi-linked) in 4 weeks;
  - humanitarian alert = double the 3-week average;
  - case fatality flag above 3%.
- **Conflict:** three pathways, no hidden multiplier:
  - vaccination disruption (an optional sensitivity setting);
  - surveillance quality (silence and completeness flags);
  - a visible threat factor (IOM DTM displacement).
- **Conflict data:** IOM DTM first; UCDP and ACLED (internal, aggregated, after a licence
  check) later.
- **Multi-disease core** with per-disease modules. One Health groundwork now, analytics
  after measles.
- **IDM laser-measles is the evaluation simulator,** not the live engine. It is installed
  in a separate `.venv-sim` (`requirements-sim.txt`: laser-measles 0.13.3, numba 0.62.1).
- **Births** come from the OCHA COD-PS 2023 under-5 counts (`scripts/load_births.py`).
  - A 2023 code is used only if its region agrees.
  - Fallbacks: zone, then region (with SNNPR successors), then national.
  - Later: WorldPop or DHIS2 expected births.
- **Gemini's model suggestions** were reviewed critically. Adopted: EWMA, the space-time
  scan, Hubverse-style output, and challenger models. Rejected: LSTM, dropping laser,
  TimescaleDB.

## Evaluation results (synthetic; see `EVALUATION.md`)

- **Detection:**
  - the alert threshold catches about 75% of outbreaks within about a week (PPV about 0.8);
  - the action threshold is about 92% PPV but late;
  - EWMA catches about 20–25% (PPV about 0.9);
  - the space-time scan catches 19–27% (PPV about 0.8).
- **Next-quarter burden** (precision@10%):
  - **hybrid regression 61–65%** (best);
  - count regression and boosted trees 58–62%;
  - fitted risk index 53–55% (best at 5% reporting);
  - original index 50–53%;
  - ceiling with perfect nowcast 70–74%.
- **Ignition** (which quiet woreda flares up): **unsolved.** Nothing beats random except the
  simulator's true susceptibles. The weak point is reconstructing susceptible children
  from cases.

## Open decisions for the owner

1. **Adopt the hybrid model in production** as the "heaviest next quarter" ranking (needs
   2–3 years of counts), with the fitted index as fallback and as the source of
   explanatory factors? Asked; no answer yet.
2. **Then M4,** or more modelling first. Ignition needs real data plus a Bayesian or
   state-space susceptible estimate.

## Pending on the owner's side

- Test the improvements round:
  - `git pull`, `alembic upgrade head`, `python -m pytest tests -q` (expect 88 passed, 11
    skipped, no warning);
  - optionally load births, DTM and coverage (`DATABASE_SETUP.md` §6b).
- Retest the AI features when Gemini quota allows; rerun `scripts/reprocess_failed.py`.
- Change the leaked passwords (masri_dev; the `crate_admin.py` account
  dagiteferi2011@gmail.com).
- `create_admin.py` still has a hard-coded password. Offer to make it prompt instead (needs
  OK).
- Delete the old `claude/awesome-lovelace-hxxe3j` branch on GitHub.
- Book EPHI interviews (`INTERVIEW_GUIDE.md`, including the EPHI-manual questions); check
  ACLED licence terms.
- Optional: add the original EPHI PDFs next to the Markdown conversions.
- Known Windows gotcha: the old `README.MD` / `README.md` clash is resolved, but local
  copies that predate it need `git reset --hard origin/m2-data-foundation` after backing
  up `models/outbreak_data.json`.

## Optional items still waiting for an OK

- Show the official place, with an ambiguity filter, on the Records pages.
- Start the backend with a clear message when PostgreSQL is down.
- Frontend tier colours (they map the LLM's HIGH/MEDIUM/LOW) to be reworked in M5.

## Assistant's working environment (cloud sandbox, for reference)

- App venv: `/tmp/claude-0/ecvenv`. Simulator venv: `/tmp/claude-0/simvenv`. Both are
  recreated with `pip install -r requirements*.txt` if the container resets.
- PostgreSQL 16 data directory: `/var/lib/postgresql/ecdata`, port 5432; users and
  databases `empoweredcare` and `empoweredcare_test`.
- Real OCHA, births and DTM test downloads: `/tmp/claude-0/hdx/`; scratch database
  `/tmp/claude-0/real.db`.
- Network: HDX and PyPI reachable; World Bank API blocked.
