# Archive: earlier design documents

**These files are historical. They do not describe the current system.**

They come from the hackathon prototype (April 2026) and its early plans. They are kept so
the project's history and original ideas stay visible.

| File | What it was |
|---|---|
| `README_hackathon.md` | The hackathon README |
| `AI_ARCHITECTURE_WALKTHROUGH.md` | Question-and-answer pitch on the AI architecture |
| `BUSINESS_LOGIC.md`, `SYSTEM_DESIGN_REVIEW.md` | Descriptions of the prototype pipeline |
| `API_SPECIFICATION.md`, `FRONTEND_API_DOC.md` | Prototype API examples |
| `use_gemini.md` | The case for Gemini 1.5 Flash, which has since been retired |
| `plan_aegis_lite.md`, `plan_super_agent.md` | Early multi-agent brainstorms |

Many features they describe were never built, or have been removed. Examples are the SMS
gateway, offline sync, retrieval over EPHI guidelines, YOLO/PaddleOCR document reading and
web-search scraping.

Each idea was reviewed in `docs/SYSTEM_SPEC.md` §11.2:
- the good ones (SMS for health extension workers, alert SMS and digests, offline entry,
  agents that use tools, guideline retrieval, a verified dataset for local models) are in
  the plan;
- the rest are retired, with the reason.

For the current system, see:
- `README.md` (repository root);
- `docs/SYSTEM_SPEC.md`;
- `docs/METHODOLOGY.md`;
- `docs/AI_ARCHITECTURE.md`.
