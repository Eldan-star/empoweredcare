# What to test before M2, and why

**Why test at all?** M2 replaces the storage layer that every page depends on. If something is already broken now and we build on top of it, we won't know later whether M2 broke it or it was always broken. Checking now gives a known-good starting point.

**What I could and couldn't check myself.** I checked that:
- the code compiles and the website builds from a fresh copy;
- every page renders in light and dark mode, on desktop and phone sizes, with no errors.

I could **not** check:
- real AI calls (I only had a placeholder key);
- real email sending;
- uploads of real files with the AI reading them.

Those are the parts you need to test. Each step below says what to do, what you should see, and why it matters.

Tick the boxes as you go. If anything fails, copy the error text, or take a screenshot of the page and of the backend terminal, and send it to me.

---

## Step 1 — Get it running (must pass)

**Why:** if you can't start it from the instructions, neither can a teammate or an EPHI technical reviewer.

1. **Back up your local data first.** Copy `models/users.json` and `data/patient_records.json` somewhere safe. These files are no longer tracked by git, because they hold accounts and patient data that shouldn't be in a code repository, so `git pull` can delete your local copies.
2. Get the latest `main`: `git checkout main && git pull`. Then put the two backed-up files back.
3. Copy `.env.example` to `.env` and fill in:
   - `SECRET_KEY`: any long random string. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
   - `GEMINI_API_KEY`: your Google AI key.
4. **Install the backend.** Choose one:
   - **Quick install (recommended for testing).** This is enough for everything except the broken scanned-document endpoint, and I tested that the server starts with it:
     ```
     python -m venv .venv
     source .venv/bin/activate        # Windows: .venv\Scripts\activate
     pip install fastapi==0.115.0 "uvicorn[standard]==0.30.6" python-multipart==0.0.9 python-jose==3.5.0 passlib==1.7.4 bcrypt==4.0.1 python-dotenv==1.0.1 google-generativeai==0.8.6 pydantic==2.12.5 email-validator==2.3.0 APScheduler==3.11.2 aiosmtplib==5.1.0 pandas numpy==1.26.4 opencv-python-headless==4.11.0.86 pdf2image==1.17.0 pillow==10.4.0 openpyxl==3.1.5 aiofiles
     ```
   - **Full install:** `pip install -r requirements.txt`. This pulls in PyTorch and NVIDIA GPU packages (several GB), and **those packages won't install on a Mac**.
   - For **PDF uploads** you also need Poppler, a PDF tool installed outside Python:
     - Mac: `brew install poppler`
     - Ubuntu: `sudo apt install poppler-utils`
     - Windows: download Poppler and add it to PATH.
5. Start the backend: `uvicorn main:app --port 8000`. Leave this terminal open; its messages are useful when something fails.
6. In a second terminal, start the website: `cd frontend && npm ci && npm run dev`. Open http://localhost:8080.

**You should see:**
- [ ] The backend terminal shows no red errors.
- [ ] http://localhost:8000/health shows `"status":"healthy"`.
- [ ] The landing page loads and its status line says the system is reachable.

---

## Step 2 — Sign-in and roles (must pass)

**Why:** the system will hold health data. A viewer who can approve alerts, or a data clerk who can open the admin page, is a security and trust problem. I tested the pages by injecting a login token directly, so the **real login form has not been tested**.

**Which account to use:** if `models/users.json` didn't exist, the backend created a default admin when it started:
- email: your `SMTP_USER`, or `admin@aegis-lite.com` if that's empty;
- password: `admin123`.

**Change that password straight away** on the Profile page. Anyone who reads the code knows it.

- [ ] Sign in as the admin through the form. You land on Overview.
- [ ] A wrong password shows a clear error message, not a blank screen.
- [ ] Create a **viewer** and a **data entry** user (step 5 shows how to do this without email).
- [ ] As the viewer: there are no Approve/Reject buttons on Alert review, and typing `/admin` in the address bar sends you away.
- [ ] As data entry: you go straight to the patient form, and `/admin` is blocked.
- [ ] Sign out, then sign back in.
- [ ] Stop the backend and start it again. You should still be signed in, because `SECRET_KEY` is now fixed. If you're logged out, `SECRET_KEY` probably isn't being read from `.env`.

---

## Step 3 — The AI pipeline with your real key (must pass)

**Why:** this is the core of the product, and it is the part I couldn't run. A single report makes about 7 AI calls (section 5 of [CODE_GUIDE.md](CODE_GUIDE.md) explains them). Any one of them can fail if the key, the quota or the model name is wrong.

On the **Process a report** page:
- [ ] Click "Use an example" and process it. After several seconds you should see:
  - the extracted location, cases and symptoms;
  - four risk opinions;
  - a final level;
  - an alert.
- [ ] Paste a long report that mentions **several towns** (more than 1,000 characters). You should get **one record per town and disease**, not one big blob.
  **Why:** combining places would hide outbreaks.
- [ ] Upload `test_data/outbreak_test.csv`, then `outbreak_test.pdf`, then `outbreak_test.jpg`. Each one should produce records.
  **Why:** real data will arrive as files, not typed text.
- [ ] **Check the AI's work.** Do the extracted numbers and places match what you wrote? If the text said 12 cases and it extracted 21, that is a finding worth writing down.
  **Why:** this is your first rough measure of extraction accuracy, which EPHI will ask about.

Then check that the results show up elsewhere:
- [ ] The new records appear on **Overview**, in **Records**, and in **Alert review**.
- [ ] Open one record. Its detail page shows the four opinions with their full reasons.
- [ ] As admin, **approve** one alert and **reject** another. Refresh the page; both statuses stay.
  **Why:** this human verdict is the feedback the future triage model learns from.

---

## Step 4 — Ask the data

**Why:** the answers should be grounded in your stored records, not invented by the AI.

- [ ] On **Ask the data**, ask: "Which location has the most cases?" Check the answer against the Records page.
- [ ] Ask the same question in the side panel (the "Ask the data" button at the bottom right of any console page).
- [ ] Ask about a town you never entered. A good answer says there is no data. A bad answer makes something up; note it if that happens.

---

## Step 5 — Admin features

**Why:** these are how you'll run a pilot: adding people, removing people, scheduling analysis.

**Email without SMTP:** if `SMTP_USER` and `SMTP_PASSWORD` are empty in `.env`, the backend doesn't send email. It **prints the email, including the link, in the backend terminal**. That means you can test invites and resets without an email account.

- [ ] **Invite** a colleague as a viewer. Copy the registration link from the email (or the terminal), open it, and set a password. You can now sign in as that viewer, which is how you create the test users for step 2.
- [ ] **Forgot password:** request a reset, open the link and set a new password. The link expires after 1 hour.
- [ ] **Run now** in Scheduled analysis. A summary appears, labelled "unverified".
- [ ] **Save a schedule.** Pick a preset; "Next run" updates.
- [ ] **Remove** a user. A confirmation appears first, and that user can no longer sign in.
- [ ] Optional: fill in the real SMTP settings and check that the emails actually arrive and aren't in spam.

---

## Step 6 — Data entry portal

- [ ] As a data entry user, fill in and save a patient record. It appears under "My records".
- [ ] Upload a file from the portal and check the results table.

---

## Step 7 — Look and feel

**Why:** epidemiologists will judge trustworthiness partly by whether the numbers and wording look careful.

- [ ] Switch between light and dark mode (the top bar). Both should be readable.
- [ ] Open the site on your phone and check that nothing overflows sideways. To set this up:
  - Put your phone and computer on the same Wi-Fi.
  - Start the backend with `uvicorn main:app --host 0.0.0.0 --port 8000`.
  - Add `http://<your-computer's-IP>:8080` to `ALLOWED_ORIGINS` in `.env`.
  - On the phone, open that address and go to **Settings**. Change the backend address to `http://<your-computer's-IP>:8000`, because on a phone "localhost" means the phone itself.
  - The quickest alternative is your desktop browser's phone preview (developer tools → device toolbar).
- [ ] If you have an iPhone, check that dates show properly in Safari, not as "Invalid date".
- [ ] **Map.** Towns land in the right regions. Towns the map doesn't know are listed under "Not placed on the map" rather than placed at random.
- [ ] **Numbers.** Totals on Overview and Weekly summary match a manual count from Records.
- [ ] **Wording.** Anything that sounds wrong to an Ethiopian public health reader? That feedback is valuable.

---

## Step 8 — A decision for you

The backend endpoint `/process`, for scanned medical documents with layout detection, fails because its model file (`models/doclayout_yolo_ft.pt`) was never added to the repo. **No page in the website uses it**: the website's "Process a report" page uses a different endpoint that works. You have two options:
- whoever trained that model adds the file, and I make sure it works; or
- we remove the endpoint and its heavy dependencies, which would also shrink `requirements.txt` by several GB.

I recommend removing it for now. Measles surveillance in Phase 1 doesn't need it, and photo reading is deferred in the plan anyway.

---

## Optional — Try Claude instead of Gemini

Set `LLM_PROVIDER=claude` and `ANTHROPIC_API_KEY=...` in `.env`, run `pip install anthropic`, restart the backend, and repeat step 3. Compare the extraction accuracy on the same reports.

**Why:** it's a cheap way to see which model extracts Ethiopian place names and counts more reliably before we depend on one.

---

## One security note

`create_admin.py`, which was already in the repo before my changes, contains a **hard-coded admin email and password**. Anyone with access to the repo can read them. If that account exists on any running copy of the app, change its password, and avoid running that script as it is. I can change it to ask for the password instead; say if you want that.

---

## When can we start M2?

When **steps 1–3 pass**. Steps 4–7 can have small issues; I'll fix those alongside M2. Send me what failed (error text or screenshots), or just say "go".
