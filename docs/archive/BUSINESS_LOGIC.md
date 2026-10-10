# Empowered Care - Business Logic & System Documentation

## 1. System Overview
Empowered Care is a high-performance, multi-agent disease outbreak detection and document processing system. It leverages Large Language Models (Gemini 1.5), automated web research (Crawl4AI), and advanced document processing (OCR/Layout Detection) to identify potential epidemiological threats from diverse data sources.

---

## 2. Core Business Logic Pipeline

### Phase 1: Data Ingestion & Extraction
The system accepts raw text, PDF documents, clinical images, and CSV files.
- **Document Pipeline**: PDFs and images are processed via a vision-to-text pipeline:
    1. **Layout Detection**: Identifies regions of interest (tables, signatures, text blocks).
    2. **Preprocessing**: Enhances image quality for better OCR.
    3. **OCR Engine**: Extracts raw text using a combination of Gemini Vision and Tesseract fallback.
- **Extraction Agent**: A specialized LLM-driven agent that converts unstructured text into a list of `OutbreakReport` objects. 
    - *Key Logic*: It is instructed to split "messy" inputs into individual reports based on location and disease type.

### Phase 2: Validation
- **Validation Agent**: Every extracted report is scrutinized for:
    - Statistical plausibility (e.g., impossible case counts).
    - Clinical consistency (do symptoms match the reported disease/environment?).
    - Data completeness.

### Phase 3: Contextual Intelligence
- **Research Agent**: For every unique location identified, the system spawns a background research task.
    - **Scraping**: Uses `Crawl4AI` to search Google and Bing for real-time situational data.
    - **Extraction**: Gemini extracts specific risk factors: **Security Status**, **Water Quality**, **Temperature**, and **Conflict Zone status**.

### Phase 4: Risk Analysis & Consensus
This is the "Brain" of the system, employing a hierarchical multi-agent architecture.

#### Risk Perspectives
The `RiskAnalysisAgent` evaluates the report through four distinct lenses:
1. **Symptoms Perspective**: Focuses on clinical patterns and diagnostic matches.
2. **Statistical Perspective**: Analyzes case growth and compares it against historical baselines for that specific location.
3. **Historical Perspective**: Evaluates seasonal trends and known regional hotspots.
4. **Environmental Perspective**: Analyzes how local conditions (from Phase 3) like water quality or conflict impact transmission.

#### Consensus Calculation (The Logic)
The `SuperAgent` merges these four opinions into a final determination:
- **Risk Mapping**: 
  - `HIGH` = 3
  - `MEDIUM` = 2
  - `LOW` = 1
  - `UNKNOWN` = 0
- **Final Risk Level**: `Round(Average(Risk Scores))`
- **Average Confidence**: `Mean(Confidence Percentages)`
- **Reasoning**: A concatenated summary of all four perspectives.

### Disease Classification Logic
The system automatically classifies every detected outbreak signal into one of three categories:
1. **Suspected**: Initial reports based on symptom clusters without lab confirmation.
2. **Probable**: Reports with strong clinical alignment or strong epidemiological links to known outbreaks.
3. **Confirmed**: Signals explicitly mentioning laboratory confirmation or medical verification.

---

## 3. Calculation & Logic Details

### Case Metric Definitions
1. **Total Historical Cases**: The cumulative sum of all cases ingested into the system's long-term memory. It represents the total scale of surveillance.
2. **Active Filtered Cases**: The sum of cases currently matching the user's dashboard filters. This allows focused monitoring of "Last 24h" or specific "High Risk" outbreaks.

### Risk Scoring Formula
Let $P = \{p_1, p_2, p_3, p_4\}$ be the set of risk perspectives.
Let $S(p)$ be the score mapping function where $S(\text{HIGH}) = 3, S(\text{MEDIUM}) = 2, S(\text{LOW}) = 1$.
Let $C(p)$ be the confidence value of a perspective.

$$ \text{Final Risk Score} = \text{round}\left( \frac{\sum_{i=1}^{4} S(p_i)}{4} \right) $$
$$ \text{Consensus Confidence} = \frac{\sum_{i=1}^{4} C(p_i)}{4} $$

### Validation & Alert Monitoring
The system maintains a "Live Surveillance" status even for non-alert signals:
- **Validation Score**: Shows the AI's internal assessment of the report's statistical and clinical plausibility.
- **Cognitive Audit**: Every record in the **Intelligence Vault** provides a full trace of the agent's internal reasoning, allowing users to validate why a signal was or was not upgraded to an alert status.

### Alert Prioritization
Alerts are generated with varying urgency levels based on the Consensus Risk Level. 
- **Urgent Alerts**: Triggered when Risk Level is `HIGH`. Includes immediate prevention strategies and specific hospital recommendations.

---

## 4. Data Management & RAG
- **Historical Context**: The `DataAssistantAgent` maintains a local JSON store (`models/outbreak_data.json`). 
- **Retrieval Augmented Generation (RAG)**: When a new report is analyzed, the system retrieves the last 20 relevant records for that location to provide the LLM with historical baseline data, ensuring the "Statistical" and "Historical" perspectives are grounded in reality.

---

## 5. Security & Roles
- **Admin**: Full system access, user management, and report approval.
- **Data Entry**: Specialized for clinical record uploads.
- **Viewer/Worker (VW)**: Access to dashboards and alerts.
- **Token-based Auth**: JWT with 24-hour expiration.

---

## 7. Frontend Integration
The frontend is a Vite-powered React application using Tailwind CSS and Shadcn UI.
- **State Management**: Uses `Zustand` for auth and global state.
- **API Client**: `Axios` based with interceptors for JWT injection.
- **Dashboards**: Real-time visualization of `outbreak/summary` and `outbreak/reports`.
- **Deep Analysis Table**: A specialized view in the **Intelligence Vault** (`/vault`) for high-density inspection.
- **Record Audit Page**: A dedicated detail view (`/vault/details/:sessionId`) providing a "Signal-to-Logic" audit trail, including structured CSV-like tables of all metadata, validation scores, and raw transmission logs.
- **Workflows**:
    - **Report Processing**: Direct text input or file upload (CSV).
    - **Medical Record Ingestion**: specialized OCR-based processing for scanned clinical forms.

## 9. API Architecture & Endpoints
The backend uses **FastAPI** to expose high-concurrency asynchronous endpoints:
- **`POST /outbreak/process`**: The entry point for raw text analysis. Triggers the full multi-agent pipeline (Extraction -> Research -> Consensus).
- **`POST /outbreak/upload`**: Similar to process, but accepts CSV/PDF/Images.
- **`GET /outbreak/summary`**: Provides aggregated statistics (total cases, high-risk counts, locations) for the frontend dashboard.
- **`GET /outbreak/reports`**: Fetches the historical list of analyzed reports from `outbreak_data.json`.
- **`POST /auth/login`**: Role-based authentication returning a JWT.

## 10. Technical Stack
- **Backend**: Python 3.12, FastAPI, Uvicorn, APScheduler.
- **AI/ML**: Google Gemini 1.5 (Pro/Flash), YOLO-based Layout Detection.
- **Scraping**: Crawl4AI (Async Playwright-based).
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Shadcn UI, Recharts.
- **Data**: JSON-based persistent storage (expandable to PostgreSQL/MongoDB).
