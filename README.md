# Empowered Care

**An outbreak intelligence and early-warning system for Ethiopia.** It is being built for
national (EPHI) and regional (RHB) epidemiologists.

**Measles is the pilot disease.** The design is multi-disease: a shared core with a
separate module for each disease.

Empowered Care brings together the signals Ethiopian public health already has:
- routine PHEM/DHIS2 case counts;
- community and facility reports;
- official bulletins;
- humanitarian and displacement data.

It aims to answer, every week, **where an outbreak is happening, where one is likely next,
and why.**

| Capability | What it gives | Method |
|---|---|---|
| **Predict** | A monthly ranking of zones by measles ignition risk | Susceptible build-up plus spread from neighbouring zones |
| **Detect** | Outbreak-threshold crossings and early rises | WHO/EPHI thresholds; EARS and CUSUM statistics |
| **Fuse** | One tiered alert (RED / ORANGE / YELLOW) per place and week, with its evidence | Fixed rules; a threshold crossing is never downgraded |
| **Explain** | "Why this place, why now", and draft situation reports | AI writing only from stored evidence, with citations |

> **The rule for AI:** AI reads, extracts, compiles and explains. Statistics produce the
> numbers and the alert tiers. People verify.

## Status (October 2026)

**Built**
- Sign-in with roles (admin, viewer, data entry), invitations and password reset.
- Report intake from text, CSV, PDF and images. AI (Gemini) extracts the location,
  symptoms, cases and dates. Officers approve or reject each report.
- "Ask the data" chat over stored reports.
- PostgreSQL database with migrations.
- Ethiopia's official boundaries (OCHA, Dec 2025): 15 regions, 107 zones and 1,148
  woredas, with populations and neighbouring units.
- A place-name resolver. It turns "Jimma zone, Seka Chekorsa" into an official woreda
  code, flags names that fit more than one place instead of guessing, and still resolves
  old names (SNNPR).
- DHIS2 connector, tested on the public demo server. Pulling Ethiopian data is switched
  off until EPHI approves in writing.
- AI quota handling: requests are paced, the app falls back to another model, and it shows
  a clear message when quota runs out.

**Not built yet** (see `docs/SYSTEM_SPEC.md` for the plan)

| Milestone | What it adds |
|---|---|
| M3 | Measles risk model, outbreak detection, and testing on simulated Ethiopian outbreaks (IDM's laser-measles) |
| M4 | Community trigger intake, the review page for incoming signals, ReliefWeb / WHO AFRO / IOM DTM feeds, bulletin digitiser, assistant over the EPHI guidelines |
| M5 | Tiered alerts, an interactive woreda map, situation-report drafting |
| Later | SMS reporting for health extension workers, SMS alerts to officers, offline data entry, learned models, more diseases, One Health data |

**Today's risk level is a placeholder.** The current HIGH/MEDIUM/LOW risk on each report
is the AI's own opinion, averaged over four prompts. It is not a validated measure, and it
is replaced by the statistical risk index in M3–M5.

## How it fits together

```
Text / CSV / PDF / image ──► AI extraction ──► place-name resolver ──► PostgreSQL ──► dashboard, records, chat
                                                (OCHA P-codes)          (signals)
DHIS2 weekly counts ──(after EPHI approval)──► indicator tables ──► [M3] detection + risk ──► [M5] tiered alerts
```

- **Backend:** Python 3.12, FastAPI, SQLAlchemy and Alembic, PostgreSQL.
- **Frontend:** React, TypeScript, Vite, Tailwind.
- **AI:** Google Gemini through the `google-genai` SDK, behind one provider interface
  (`services/llm.py`). That interface also allows Claude, or later an open-weight model
  hosted in Ethiopia.

## Running it (Windows)

You need Python 3.12, Node.js and PostgreSQL. Full setup steps are in
**[docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md)**.

```powershell
# Backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then fill in SECRET_KEY, GEMINI_API_KEY, DATABASE_URL
alembic upgrade head
uvicorn main:app --port 8000

# Frontend (a second terminal)
cd frontend
npm ci
npm run dev                     # http://localhost:8080
```

Tests: `python -m pytest tests -q`. See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md).

## Documentation

| Document | For |
|---|---|
| [docs/SYSTEM_SPEC.md](docs/SYSTEM_SPEC.md) | What the system is, every design decision, and the build plan |
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Every model and AI use, with evidence and limits, for expert review |
| [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md) | Where AI runs today, where it doesn't, and where it's going |
| [docs/CODE_GUIDE.md](docs/CODE_GUIDE.md) | A plain-language walk through the code |
| [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) | What to test and why |
| [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md) | Installing PostgreSQL and loading the boundaries |
| [docs/DHIS2.md](docs/DHIS2.md) | Connecting to DHIS2 |
| [docs/API.md](docs/API.md) | The API, with the live reference at `/docs` |
| [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md) | Questions for EPHI and regional teams |
| [docs/archive/](docs/archive/) | Earlier hackathon documents (historical) |

## Data governance

- No Ethiopian surveillance data is pulled from DHIS2 without EPHI's written approval. The
  code enforces this.
- Report text is currently sent to a cloud AI model (Gemini). Hosting a model on servers
  in Ethiopia is planned if EPHI requires data residency (SYSTEM_SPEC §11.1).
- Secrets, user accounts and patient records are kept out of git.

## Origin

Empowered Care began at the Global Health Innovation Hackathon 2026 (Addis Ababa hub) as a
multi-agent AI prototype. It is now being rebuilt as an evidence-based surveillance tool.
The prototype documents are in `docs/archive/`.
