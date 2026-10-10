# API reference

The backend documents its own API. With the backend running (`uvicorn main:app --port 8000`), open:

- **http://localhost:8000/docs**: every endpoint, with its inputs and outputs. You can try
  calls from the page: click **Authorize** and sign in first.
- **http://localhost:8000/redoc**: the same information as a single readable page.

These pages are generated from the code, so they are always current. Hand-written API
documents went out of date, so the old ones are in `docs/archive/`.

## Things the generated pages don't spell out

- **Sign-in.** Almost every endpoint needs a login token.
  - `POST /auth/login` takes form fields `username` (your email) and `password`, and returns
    the token.
  - Send it on later calls as `Authorization: Bearer <token>`.
  - Approving reports and the `/admin/*` endpoints need the admin role.
- **AI quota.** When every configured Gemini model is out of quota, the AI endpoints
  return **HTTP 503** with a message saying the quota was reached. Nothing is stored as an
  analysis. Retry later.
- **Main groups:**

| Group | Endpoints |
|---|---|
| Sign-in and accounts | `/auth/*`; `/admin/users`, `/admin/invite` |
| Reports | `/outbreak/process` (text), `/outbreak/upload` (CSV, PDF, image), `/outbreak/reports`, `/outbreak/summary`, `/outbreak/approve/{session_id}` |
| Ask the data | `/outbreak/query`, `/outbreak/chat` |
| Scheduled analysis | `/admin/analyze/*` |
| Data entry portal | `/patient/record`, `/patient/records` |
| Status | `/health` |

The surveillance endpoints (`/surveillance/*` and `/intake/trigger`) arrive with M3–M5
(see `SYSTEM_SPEC.md`).
