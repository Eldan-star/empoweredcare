# How the Empowered Care code works

This guide is for someone reading this codebase without a software or data background. It explains what each part does, how a report moves through the system, and where the weak spots are. For how to check that it works, see [TESTING_GUIDE.md](TESTING_GUIDE.md).

---

## 1. The big picture

The app has two halves that talk to each other over the network:

| Half | What it is | Where it lives | Language |
|---|---|---|---|
| **Backend** (the "server") | Does the work: checks passwords, sends text to the AI model, saves records | Repository root: `main.py`, `services/`, `utils/`, `models/`, `config.py` | Python (FastAPI) |
| **Frontend** (the "website") | What people see and click in the browser | `frontend/` | TypeScript + React |

An analogy: the frontend is the waiter and the backend is the kitchen. The waiter takes your order (a form you fill in) and carries it to the kitchen as an **API request**, which is a message to a specific address such as `/outbreak/process`. The kitchen cooks it (calls the AI and saves the result) and sends back a plate, a **JSON response** (structured data). The waiter then lays it out nicely on the page.

There is also a third party: the **AI model** (Google Gemini by default, or Claude if you switch it). The backend sends it text with instructions, called a **prompt**, and gets text back. Most of the app's "intelligence" today is these prompts. There are no statistical or predictive models yet; building those is M2–M5 in the plan.

```
Browser (frontend)  ──API request──▶  Backend (main.py)  ──prompt──▶  Gemini / Claude
        ▲                                   │
        └────────── JSON response ──────────┤
                                            ▼
                               JSON files on disk (the "database" for now)
```

---

## 2. Where the data is stored

Today nothing uses a real database. Everything is saved in plain JSON text files:

| File | What is in it | Tracked in git? |
|---|---|---|
| `models/outbreak_data.json` | Every processed outbreak report: what was extracted, the AI's risk opinions, the alert, and the approval status | Yes |
| `models/users.json` | User accounts. Passwords are stored **hashed**: scrambled one-way, so the original can't be read back | **No** (it holds real accounts). `users.example.json` shows the shape |
| `data/patient_records.json` | Individual patient records entered on the data entry portal | **No** (it holds personal health data). `patient_records.example.json` shows the shape |

**Why this matters:** JSON files are fine for a prototype. But they can't safely handle two people saving at the same instant, they slow down as they grow, and they can't easily answer questions like "cases per woreda per week". Replacing them with a PostgreSQL database is the first step of **M2**.

**Things kept only in memory are lost when the backend restarts:**
- chat conversation history;
- the scheduler's last-run result.

---

## 3. The backend, file by file

### `config.py`: settings
This file reads settings from a `.env` file, which holds secrets that never go into git. Copy `.env.example` to `.env` to get one. Key settings:
- `SECRET_KEY` signs login tokens (explained in 3b). If it changes, everyone is logged out. Outside `APP_ENV=development` it **must** be set, or the server refuses to start. That is deliberate: in development, a missing key falls back to a random throwaway key.
- `GEMINI_API_KEY` is the key for Google's AI.
- `GEMINI_MODELS` lists which Gemini models to use, tried in order. Google retires models regularly; when that happens you change this line, not the code. `python list_models.py` shows the names your key can use.
- `LLM_PROVIDER` picks the AI model: `gemini` (the default) or `claude`.
- `ALLOWED_ORIGINS` lists which website addresses may talk to the backend. Browsers enforce this rule, which is called **CORS**.
- `MAX_TEXT_LENGTH` is the longest report text accepted (20,000 characters by default).
- `ENABLE_WEB_RESEARCH` defaults to off. It controls web scraping, which is disabled on purpose; see the plan.

### `main.py`: the front door
This file defines every **endpoint**, the addresses the frontend can call, and wires the other pieces together. Each block that starts with `@app.post(...)` or `@app.get(...)` is one endpoint. The main groups:

| Endpoints | What they do | Who can use them |
|---|---|---|
| `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/auth/me` | Accounts and passwords | Anyone (login) / signed-in users |
| `/admin/users`, `/admin/invite`, `/admin/analyze/*` | Manage the team; run or schedule the overall analysis | Admins only |
| `/outbreak/process` | Send report text through the AI pipeline | Signed-in users |
| `/outbreak/upload` | Same, for an uploaded CSV, PDF, image or text file | Signed-in users |
| `/outbreak/reports`, `/outbreak/summary` | Read stored reports | Signed-in users |
| `/outbreak/approve/{id}` | A human approves or rejects an AI alert | Admins only |
| `/outbreak/chat`, `/outbreak/query` | Ask questions about the stored data | Signed-in users |
| `/patient/record(s)` | The data entry portal's patient records | Signed-in users |
| `/process` | Reads scanned medical documents with layout detection. **Broken:** the model file `models/doclayout_yolo_ft.pt` is not in the repo. No page in the website calls it | Signed-in users |
| `/health` | "Is the server alive?" It doesn't check whether the AI key works | Anyone |

The "who can use them" column is enforced by two small functions near the top of `main.py`:
- `get_current_user` reads the login token and finds the user; if the token is missing or invalid, the answer is **401 Unauthorized**.
- `get_current_admin` also checks that the role is admin; if not, the answer is **403 Forbidden**.

### `utils/security.py` and `services/auth_service.py`: logins
- **Signing in.** When you sign in, the backend checks your password against the stored hash, using bcrypt. If it matches, it gives you a **JWT token**: a signed note that says "this is user X, valid for 24 hours".
- **Using the token.** The browser attaches the token to every later request, so you don't re-enter your password. The token can't be faked without `SECRET_KEY`.
- **Invites and resets.** Invitation links (valid 48 hours) and password-reset links (valid 1 hour) are tokens of the same kind.
- **Roles:** `admin`, `vw` (viewer) and `data_entry`.

### `services/agents.py`: the AI "agents"
"Agent" here just means a Python class that writes a prompt, sends it to the AI, and turns the reply into structured data. When a report arrives, `SuperAgent.process_outbreak_parallel` runs this sequence:

1. **ExtractionAgent** turns messy text such as *"12 kids with rash and fever in Jinka since Monday, 2 lab confirmed"* into one structured record **per location and disease**: location, symptoms, cases, date, and Suspected/Probable/Confirmed.
2. **ValidationAgent** asks the AI whether the record looks complete and plausible.
3. **RiskAnalysisAgent** asks for four opinions, each from a different "perspective" (symptoms, statistical, historical, environmental), in **one AI call**. It used to make four separate calls; combining them saves quota. Each opinion is HIGH/MEDIUM/LOW with a confidence and a reason. The prompt includes a summary of past reports, which the historical perspective uses.
4. **Consensus** (`_reach_consensus`) is plain arithmetic, not AI. It turns HIGH=3, MEDIUM=2, LOW=1 into numbers, averages them and rounds the result.
   - **Weakness:** averaging dilutes a single alarm. One HIGH and three LOWs becomes MEDIUM. Two HIGHs and two MEDIUMs also becomes MEDIUM, because of how Python rounds 2.5.
   - This is one reason the plan (M5) replaces it with fixed rules where a threshold crossing can never be averaged away.
5. **AlertGenerationAgent** writes the alert message and the recommended actions.
6. **DataAssistantAgent** saves everything to `models/outbreak_data.json` with status `pending`. A HIGH or MEDIUM result is marked as needing human review.

Other agents:
- **ChatSupervisor** sends each question to one of four "specialists" (location, infection, history, general). Each specialist answers using the stored reports.
- **DataAssistantAgent.perform_full_analysis** is what "Run now" on the Admin page runs, and what the scheduler runs on its timetable. It compares recent reports with older ones and lists anomalies. The output is AI-written and **unverified**.

**The honest summary:** every judgement in this pipeline is the AI's opinion, apart from the consensus arithmetic. Nothing checks the AI against epidemiological thresholds or statistics yet. M2–M5 adds those checks.

### `services/llm.py`: switching AI models (new in M1)
The agents used to call Gemini directly. Now they call a small common interface (`LLMProvider`) with two methods:
- `generate_text`: ask, get text back;
- `generate_json`: ask, get structured data back, or a clear error if the reply isn't valid JSON.

`GeminiProvider` and `ClaudeProvider` both implement it, and `LLM_PROVIDER` in `.env` picks one. This makes it a one-line settings change to compare models, or to replace one later. Reading images is still Gemini-only, through `gemini_service.py`.

### The other services
- `gemini_service.py`: the Gemini connection, using Google's current `google-genai` library. It handles Google's limits:
  - **Per-minute limit** (error 429 with a short wait): it waits exactly as long as Google asks, then retries.
  - **Daily limit**, or a wait longer than a minute: it skips that model at once and remembers it is out of quota until it resets.
  - **Busy or dropped connection** (error 503 and similar): it retries after 2, 4 and 8 seconds.
  - **Pacing:** `GEMINI_RPM` keeps each model under its requests-per-minute limit.
  - **Time budget:** `GEMINI_CALL_BUDGET_SECONDS` caps how long one call may take.
  - **Real errors** (bad key, retired model): it moves to the next model straight away.
  - **When every model is out of quota,** the website shows "AI quota reached" (HTTP 503) instead of hanging, and nothing half-analysed is saved.
- `scripts/reprocess_failed.py`: a one-off tool that re-runs stored records whose AI analysis failed and replaces the failed analysis in place.
- `email_service.py`: sends invite and reset emails. It needs the SMTP settings in `.env` (SMTP is the standard for sending email).
- `ocr_engine.py`, `layout_detector.py`, `preprocessor.py`, `structurer.py`: the scanned-document pipeline behind `/process`. These are heavy, so they only load the first time `/process` is used.
- `research_agent.py`: web scraping, which is switched off.
- `utils/pdf_utils.py` and `utils/image_utils.py`: turn PDFs into images and handle image files.

---

## 4. The frontend, folder by folder (`frontend/src/`)

| Folder / file | What it does |
|---|---|
| `main.tsx` | Starts the app and loads the fonts |
| `App.tsx` | The **router**: which page shows at which address (`/dashboard`, `/alerts`, …), and which pages need a login or the admin role |
| `pages/` | One file per screen (listed below) |
| `components/` | Reusable pieces: the sidebar, the top bar, the map, charts, badges, and the chat panel |
| `components/ui/` | Basic building blocks (buttons, inputs, tabs, dialogs) from the shadcn library, restyled |
| `components/editorial.tsx` | The design system's shared pieces: page headers, section rules, number stats, sparklines, tier badges, empty states and date formatting |
| `lib/api.ts` | **The one place that talks to the backend.** Every page calls `api.something()` instead of building requests by hand. It attaches the login token, and if the backend answers 401 (token expired), it signs you out and sends you to the login page |
| `lib/utils.ts` | `cn()`, a helper for combining styling classes |
| `store/` | Small shared memory: `authStore` (who is signed in) and `appStore` (loaded reports and the backend address). Kept in the browser, so a refresh doesn't log you out |
| `index.css`, `tailwind.config.ts` | Colours, fonts and spacing for light and dark mode |

**Pages and what each one calls on the backend:**

| Page | Address | Backend calls |
|---|---|---|
| Landing | `/` | `/health` |
| Login / Register / Forgot password | `/login`, `/register`, `/forgot-password` | `/auth/*` |
| Overview (dashboard) | `/dashboard` | `/outbreak/reports` |
| Process a report | `/process` | `/outbreak/process`, `/outbreak/upload`, `/outbreak/approve` |
| Alert review | `/alerts` | `/outbreak/reports`, `/outbreak/approve` (approve buttons for admins only) |
| Records + record detail | `/vault`, `/vault/details/:id` | `/outbreak/reports` |
| Weekly summary | `/summary` | `/outbreak/reports` (all the weekly maths happens in the browser) |
| Ask the data + side panel | `/query` | `/outbreak/chat` |
| Admin | `/admin` | `/admin/*` |
| Profile / Settings | `/profile`, `/settings` | `/auth/me`, `/auth/change-password` |
| Data entry portal | `/data-entry` | `/patient/record(s)`, `/outbreak/upload` |

Note: the website's `/process` page is the text-report page. It is **not** the broken backend `/process` endpoint; the names just collide.

### What M1 changed in the frontend, and why
- **It wouldn't build before.** `.gitignore` excluded every folder named `lib/`, so `frontend/src/lib/api.ts` and `utils.ts` were never committed. A fresh copy of the repo couldn't compile. I recreated both files and narrowed the ignore rule.
- **Fake numbers were removed.** The landing page showed invented metrics (for example "99.1% accuracy"). Showing these to EPHI would damage trust, so the landing page now only claims what actually works.
- **Bugs fixed:**
  - the approve button was visible to viewers;
  - a crash on the Process page (it called a function that didn't exist);
  - map pins were placed at **random** positions when a town wasn't recognised. They now go into a "Not placed on the map" list;
  - the weekly summary counted unknown risk as LOW;
  - Safari couldn't read some dates.
- **New design ("situation-room editorial").** It is built to look like a briefing document, not a generic AI dashboard:
  - serif headings and monospaced numbers;
  - thin rules instead of shadows;
  - colour used **only** for alert tiers, so red always means something.

---

## 5. One report, start to finish

What happens when someone pastes *"Jinka: 12 suspected measles cases, 2 IgM positive"* and presses Process:

1. `ProcessReport.tsx` calls `api.processReport(text)`.
2. `lib/api.ts` sends a POST request to `/outbreak/process` with the login token attached.
3. `get_current_user` in `main.py` checks the token. If it is valid, the request continues.
4. The text-length limit is checked.
5. `SuperAgent` runs the steps in section 3: extract → validate → 4 risk opinions → consensus → alert. That is **about 4 AI calls per record** (1 for extraction, which covers every record in the text, then 3 per record), which is why processing takes several seconds. On Gemini's free tier (about 20 requests per model per day) that allows only a handful of reports a day.
6. `DataAssistantAgent.add_report` saves the result to `models/outbreak_data.json` as `pending`.
7. The response returns to the browser. The page shows the extracted data, the four opinions, the final level and the alert.
8. Later, an admin opens Alert review and approves or rejects it. That calls `/outbreak/approve/{id}`, which updates the status in the file.

---

## 6. Known gaps (all planned, none hidden)

| Gap | Effect | Fixed in |
|---|---|---|
| JSON files instead of a database | Can't scale; risk of lost writes with many users | M2 |
| Place names are free text, not official codes | "Jinka" and "Jinka town" count as different places; map placement is approximate | M2 (geocoder with OCHA P-codes) |
| All risk judgements are AI opinions | Not explainable or testable against ground truth | M3 (thresholds, early-rise statistics, measles susceptibility model) |
| Consensus averaging dilutes alarms | A single HIGH can be averaged away | M5 (tier rules) |
| Chat history and scheduler state live in memory | Lost on restart | M2 |
| `/process` scanned-document endpoint | Fails without its model file; nothing in the website uses it | Your decision: upload the weights or remove it |
| No automated tests for the pipeline | Changes could break things unnoticed | M2 onward (pytest suite) |
| The old `test_*.py` scripts at the repo root | Manual scripts that need a running server and a real API key; not an automated test suite | Will be replaced by `tests/` |
