> **Note (October 2026):** This document describes a target architecture. Several components it mentions (SMS gateway, woreda offline sync agent, daily digest SMS, RAG over EPHI guidelines, Gemini 1.5) are **not implemented**. See `docs/SYSTEM_SPEC.md` for the current state and the Phase 1 plan.

# System Architecture Inquiry

**Q1: Walk me through exactly where AI runs in your system and where it doesn't.**

---

## Where AI runs:

In our system, Artificial Intelligence is not just a single feature; it is the "clinical brain" that handles tasks requiring interpretation, pattern recognition, and adaptive reasoning. Based on the codebase, here is exactly where the intelligence layer operates:

1.  **Visual Layout Interpretation:** When a document is uploaded, the system uses a **YOLOv10** deep learning model. Unlike a standard scanner, this model "understands" the geometry of a medical record, identifying where the patient headers end and where the vital signs begin. It provides the spatial intelligence needed to navigate complex forms.
2.  **Neural Text Extraction (OCR):** The system employs **Gemini 1.5 Flash Vision** and **PaddleOCR**. This is where the AI "reads" the document. It doesn't just see pixels; it interprets handwriting, faint ink, and medical terminology to convert visual information into high-fidelity digital text.
3.  **The Multi-Agent Orchestration Layer:** This is the most sophisticated use of AI in our system. We have a "SuperAgent" that manages a team of specialized sub-agents:
    *   **Extraction Agent:** Translates messy, unstructured clinical notes into standardized, machine-readable formats.
    *   **Validation Agent:** Acts as a medical peer-reviewer, checking the plausibility of extracted data (e.g., flagging if a recorded temperature is biologically impossible).
    *   **Risk Analysis Agents:** Four distinct agents analyze data from Symptoms, Statistical, Historical, and Environmental perspectives to reach a consensus on outbreak risks.
    *   **Research Agent:** This agent performs autonomous "situational awareness" by searching the web for real-time data on local conflicts, water quality, and environmental hazards that might impact public health.
4.  **Intent-Based Communication:** The chatbot uses a **ChatSupervisor** agent. Instead of looking for keywords, it performs semantic analysis to understand the user's intent—routing questions to specialized sub-agents (Location, Infection, or History specialists) to provide the most accurate response.
5.  **Predictive Trend Analysis:** The system uses LLM-driven comparison logic to analyze new reports against historical data stored in the "Intelligence Vault," identifying emerging anomalies and spikes that a traditional spreadsheet would miss.

## Where AI does NOT run:

To ensure the system is safe, secure, and predictable, we deliberately keep AI away from the "structural skeleton" of the application. These areas are governed by deterministic, rule-based logic:

1.  **Identity and Access Control:** Every aspect of security—from password hashing and JWT (JSON Web Token) generation to Role-Based Access Control (RBAC)—is hard-coded. We do not use AI to "guess" if a user is authenticated; these are strict, binary checks to ensure zero-fault security.
2.  **Data Persistence (Storage):** The actual writing and reading of data to our JSON files and SQLite databases is a standard software process. The AI generates the *insights*, but the *storage* layer is a rigid infrastructure that ensures your data is saved exactly as intended, with no "hallucinations" or variance.
3.  **API Routing and Communication:** The "plumbing" of the system—managed by **FastAPI**—follows standard internet protocols. When a request moves from your screen to our server, it follows a pre-defined path that is optimized for speed and reliability, not autonomous decision-making.
4.  **Background Task Scheduling:** Our system’s "alarm clocks"—such as the nightly analysis of historical data—are managed by **APScheduler**. This is a deterministic timer that triggers tasks at precise intervals; it does not rely on AI to decide "when" to run.
5.  **User Interface Logic:** The React-based frontend is a traditional software environment. Every button, menu, and chart reacts to your clicks based on clear, programmed instructions, providing a stable and responsive user experience.

**Q2: How do you standardize data across such different sources?**

---

## standardization pipeline:

Standardizing data from disparate sources—ranging from handwritten referral forms and structured CSV dumps to messy text-based field reports—is one of the most critical functions of our system. We achieve this through a multi-stage "normalization funnel" that ensures every piece of information, regardless of its origin, ends up in a uniform, clinical format:

1.  **Semantic Extraction (The Intelligence Layer):** The process begins with our **Extraction Agent**. Instead of relying on rigid templates that break when a form changes, we use Large Language Models (LLMs) to perform semantic mapping. Whether a report says "Patient has a fever," "High temp noted," or simply "Febrile," the AI understands the underlying clinical concept and maps it to a single, standardized symptom category.
2.  **Schema Enforcement (The Gatekeeper):** Once the data is extracted, it is passed into our **Pydantic Models**. This is a deterministic layer where we define the "gold standard" for our data. Any record—be it from a PDF or a manual entry—must pass through these models. This enforces strict data types (e.g., ensuring "cases" is always an integer) and ensures that mandatory fields like "location" and "classification" are always present.
3.  **Heuristic Fallbacks (The Safety Net):** For legacy documents or cases where the AI might face ambiguity, we use a **Regex-based Structurer**. This component uses complex pattern matching to identify common medical shorthand (like "Dx" for Diagnosis or "MRN" for Medical Record Number), ensuring that even the most non-standardized text is correctly categorized.
4.  **Intelligent Clustering and Merging:** Our **Data Assistant Agent** performs a "temporal-spatial merge." If multiple reports arrive from the same location regarding the same disease within a short window, the system automatically aggregates them. It sums the case counts and merges the symptom lists into a single consolidated record. This prevents data fragmentation and creates a unified view of an outbreak.
5.  **Uniform Risk Classification:** Across all reports, we standardize the risk assessment using a **Consensus Engine**. By running the data through four different perspectives (Statistical, Historical, Environmental, and Symptomatic), we produce a single, standardized "Risk Level" (HIGH, MEDIUM, or LOW). This ensures that a "HIGH" risk alert in one region means exactly the same thing as a "HIGH" risk alert in another, providing leaders with a reliable baseline for decision-making.

**Q3: How do you decrease hallucination?**

---

To ensure clinical accuracy and minimize the risk of "hallucination" (where AI generates plausible but false information), our system implements a rigorous **Five-layer defense** strategy. We do not trust the AI to operate in a vacuum; instead, we constrain its creativity through the following architectural layers:

### Layer 1 — RAG (Retrieval-Augmented Generation)
The primary cause of hallucination is an AI model lacking specific, real-world context. We solve this by grounding every decision in actual data. Before any agent analyzes an outbreak, the **DataAssistantAgent** retrieves "Historical Context"—a summary of the last 20 relevant reports for that location. This ensures the AI isn't guessing based on its general training, but is instead performing a "data-to-data" comparison against our Intelligence Vault.

### Layer 2 — Structured Output Enforcement
We eliminate "chatty" or rambling AI responses by enforcing strict **Schema Validation**. Our agents are programmed to return results exclusively in JSON format, which is immediately validated by **Pydantic Models**. If the AI tries to invent a field or provide data in an incorrect format, the system rejects it at the code level. This forces the AI to stay within the rigid boundaries of our clinical data structure.

### Layer 3 — Multi-Agent Consensus Verification
Instead of relying on a single "black box" AI, we use a **Peer-Review Architecture**. The SuperAgent spawns four independent sub-agents to analyze the same report from four different perspectives (Statistical, Historical, Environmental, and Symptomatic). A final **Consensus Engine** then merges these opinions. If one agent "hallucinates" a high risk but the others do not see the evidence, the consensus logic filters out the anomaly.

### Layer 4 — Human-in-the-Loop (HITL)
For high-stakes decisions, such as issuing a public health alert, the system includes a mandatory **Admin Approval Gateway**. Every outbreak report with a "Medium" or "High" risk level is flagged with a `human_validation_required` status. An alert is only finalized once a human administrator reviews the AI’s reasoning and confirms the session, ensuring that a human always has the final word on critical signals.

### Layer 5 — Visual Grounding and Fallbacks
For document processing, we use **Visual Grounding** to ensure the AI is "looking" at the right place. Our **YOLOv10 Layout Detector** first identifies the physical coordinates (bounding boxes) of data on a page. The AI is then forced to extract data only from those specific regions. Furthermore, if the primary AI engine (Gemini) provides a low-confidence result, the system automatically triggers a **Local OCR Fallback** (PaddleOCR) to cross-verify the text, ensuring the output is grounded in physical pixels, not just probability.

**Q4: How does the probability scoring work? How do you rank source trust?**

---

## Composite Risk Score (per signal cluster):

The system does not rely on a single "guess." Instead, it uses a multi-dimensional **Consensus-Based Scoring** mechanism that mathematically weighs multiple perspectives to determine the final risk level and the reliability of a signal.

1.  **Consensus Voting Logic:** Our SuperAgent assigns numerical values to risk levels (e.g., HIGH=3, MEDIUM=2, LOW=1). Every specialized risk agent (Historical, Statistical, Environmental, and Symptomatic) "votes" on the risk level. The system calculates the mean risk score across all perspectives. A "HIGH" risk alert is only issued if the average score across these distinct "brains" exceeds a predefined threshold.
2.  **Average Confidence Weighted (ACW):** Each agent provides a self-reported confidence percentage (e.g., "85% confidence based on clinical patterns"). The system averages these values to produce an `average_confidence` for the entire signal cluster. If the confidence is high but the risk is low, the system monitors. If the risk is high but the confidence is low, the system flags it for immediate human verification rather than issuing an automatic alert.
3.  **Trust-Ranking via Validation:** The **Validation Agent** acts as the primary trust filter. It analyzes the "clinical plausibility" of a report. If a report contains statistical outliers (e.g., 500 cases of a rare disease in a tiny village overnight), the Validation Agent assigns it a "Low Trust" score and flags the issues. Reports that pass this check are considered "Validated" and carry more weight in the system’s predictive summaries.
4.  **Signal Strength through Clustering:** Trust is also a factor of volume and consistency. The **DataAssistantAgent** clusters individual reports by location and disease type. As more reports are "merged" into a single cluster (a process we call temporal-spatial clustering), the "Signal Strength" increases. A single report is a "signal," but ten merged reports from the same location constitute a "verified hotspot," which significantly boosts the trust ranking of that data point.

5.  **Historical Grounding:** The system ranks the trustworthiness of new data by comparing it against our **Intelligence Vault**. If a new report aligns with known historical trends for that specific location (e.g., a seasonal spike in a known hotspot), the trust score is high. If a report is completely anomalous, it is treated as a high-risk but low-trust event that requires "Human-in-the-loop" confirmation before action is taken.

### Mathematical Model: Weighted Consensus Scoring

To provide a precise and auditable risk value for every signal cluster, the system utilizes a **Weighted Consensus Formula**. This ensures that no single perspective can trigger a high-alert status without multi-dimensional verification:

**$$Composite\ Risk\ Score = \sum_{n=1}^{4} (Agent\ Opinion_{n} \times 0.25)$$**

Where the four "Agents of Consensus" provide values based on:
*   **Symptomatic Analysis (0.25):** Clinical pattern matching and disease severity identification.
*   **Statistical Magnitude (0.25):** Analysis of case volume, growth rates, and population density impact.
*   **Historical Context Match (0.25):** Comparison against the Intelligence Vault for seasonal and regional baselines.
*   **Environmental Vulnerability (0.25):** Integration of real-time situational data (water quality, security, and conflict status).

**$$Trust-Weighted\ Confidence = \frac{\sum (Agent\ Confidence)}{N} \times Validation\ Factor$$**

This mathematical approach ensures that the **Empowered Care** system remains objective, defensible, and clinically grounded in every decision it makes.

**Q5: Which AI model do you use and why? Why not other models like GPT-4?**

---

Our system is powered by the **Gemini 1.5 Flash** model. The decision to use Gemini over other industry alternatives like GPT-4 was a strategic choice based on three critical "defensibility" factors that are essential for the success of Empowered Care:

1.  **Superior Linguistic Localization (Amharic Support):** Unlike many other frontier models that are heavily optimized for Western languages, Gemini 1.5 Flash demonstrates superior performance in processing and reasoning in **Amharic**. Given that our project is deeply rooted in the Ethiopian healthcare context, having a model that can accurately interpret local clinical nuances and local language field reports is a non-negotiable requirement for clinical safety.
2.  **Native Multimodal Vision Capabilities:** Empowered Care relies heavily on the ability to "see" and "read" medical documents. Gemini 1.5 Flash is natively multimodal, meaning it processes images (PDFs and scans) with the same neural pathways it uses for text. This results in significantly higher accuracy when extracting data from complex, handwritten, or poorly scanned medical referral forms compared to models that rely on external "vision" wrappers.
3.  **The Massive Context Window (1M+ Tokens):** Our "Long-term Outbreak Analysis" requires the model to compare new reports against massive amounts of historical data. Gemini’s industry-leading context window allows us to feed months of historical outbreak data directly into the model's active memory. This enables "Deep Contextual Reasoning" that would be impossible with the smaller context limits of GPT-4, allowing our agents to see the "big picture" of a disease's progression over time.
4.  **Optimized Latency for Real-time Alerting:** The "Flash" variant of Gemini is specifically engineered for high-speed, low-latency performance. In the context of a disease outbreak, every second counts. Gemini 1.5 Flash allows our Multi-Agent system to process, validate, and issue a consensus alert in near real-time, providing field teams with actionable intelligence faster than more computationally "heavy" models.
5.  **Seamless Integration with Live Intelligence:** Our **Research Agent** (using Crawl4AI) requires a model that can rapidly synthesize information from multiple live web sources. Gemini's architecture is uniquely optimized for this type of "Active Research" and "Tool-Use," making it the ideal engine for our situational awareness layer.

**Q6: What happens when there is no or limited internet connectivity?**

---

Empowered Care is designed for the reality of the field, where internet connectivity can be intermittent or unavailable. We utilize a "Resilient-by-Design" architecture that ensures data capture and alerting continue even during a total internet blackout:

1.  **SMS Layer (Always-On Continuity):** Health Extension Workers (HEWs) can report signals via SMS over the standard GSM network—no internet required. Our **SMS Gateway** receives these messages via an Ethio Telecom shortcode and queues them for processing. Because SMS travels over the voice network, messages continue to arrive and buffer even when data services are down.
2.  **Woreda-Level Offline Caching:** Each Woreda health office can run a lightweight **Local Sync Agent** on a standard laptop. This agent caches incoming SMS data, performs preliminary structural parsing, and stores alerts locally. This ensures that even if the connection to the central server is cut, local health officers do not lose situational awareness of their immediate area.
3.  **Asynchronous Central Processing:** The Central AI engine resides on a national server or secure cloud. Once internet connectivity is restored, the local agents automatically "Sync-on-Resume," pushing all cached data to the AI for deep analysis. This batch processing ensures that even with connectivity gaps, our system is still significantly faster than traditional weekly reporting cycles.
4.  **Digest-Mode Chatbot Fallback:** While the real-time chatbot requires an active connection, the system is programmed with a **Daily Digest SMS** feature. It automatically generates and sends a summary of top alerts per Woreda to officers’ mobile phones via GSM. This ensures that critical risk summaries reach decision-makers even if they cannot access the web-based dashboard.
5.  **Degraded Mode Persistence:** If the central AI server itself experiences downtime, the system enters a "Safe Capture" mode. It continues to ingest and store all incoming SMS data, DHIS2 feeds, and EIOS alerts. The moment the AI processing resumes, it automatically handles the backlog. In this architecture, **no data is ever lost**, and every signal is eventually processed.

**Q7: Are you considering running AI locally using open-source models? Why or why not?**

---

Yes, local deployment of open-source models is a core pillar of our long-term roadmap (Phases 3 and 4). While we currently utilize high-performance frontier models for the pilot phase, our architecture is intentionally **Model-Agnostic** to ensure a seamless transition to local infrastructure:

1.  **Phase 1-2 (Pilot/Regional Scale):** During the initial rollout, we utilize high-performance inference via cloud providers. At this scale (~500–2,000 queries per day), this approach is the most cost-effective and allows for rapid iteration of our agentic prompts without the overhead of hardware management.
2.  **Phase 3 (National Infrastructure):** As the system scales to a national level, we plan to transition the central AI engine to a dedicated server located at the EPHI (Ethiopian Public Health Institute) headquarters or an Ethio Telecom data center. A single enterprise-grade GPU (such as an NVIDIA A100 or L40S) running a quantized 8B or 70B open-source model (like Llama 3 or Mistral) can handle the entire national query load.
3.  **Data Sovereignty (The Strategic Moat):** This transition is essential for meeting the Ministry of Health’s requirements for **Data Sovereignty**. By running our own open-source models on Ethiopian soil, we ensure that:
    *   No sensitive health data ever leaves the country.
    *   There is zero dependency on foreign cloud providers or recurring API fees to international corporations.
    *   We have full control over the model's behavior, fine-tuning it specifically for Ethiopian clinical dialects and outbreak patterns.
4.  **Architectural Readiness:** Because we have built our system using a **Multi-Agent Orchestration Layer**, the AI "engine" is separated from the "business logic." Swapping our current service for a local, open-source model is as simple as updating a single service module in our code. This gives us a significant competitive advantage over systems that are "hard-wired" into a single proprietary API, ensuring that **Empowered Care** remains a sustainable, national asset for years to come.

**Q8: How does the RAG system work with EPHI guidelines?**

---

Our system utilizes a sophisticated **Retrieval-Augmented Generation (RAG)** architecture to ensure that every recommendation made by the AI is grounded in the official Ethiopian Public Health Institute (EPHI) protocols. This prevents the model from relying on generic medical knowledge and forces it to adhere to national standards:

1.  **Triple-Category Knowledge Base:** We maintain a structured knowledge repository divided into three distinct layers:
    *   **EPHI Clinical Guidelines:** This contains the 36 priority disease case definitions, IDSR reporting standards, and official investigation checklists. These protocols are indexed and stored as "Ground Truth" for the AI.
    *   **Active Surveillance Data:** This is a real-time stream of current alerts and cluster information stored in our **Intelligence Vault**.
    *   **Historical Epidemiological Patterns:** Past outbreak records and regional baselines used to identify seasonal trends.
2.  **Contextual Retrieval and Injection:** When an officer queries the system (e.g., "Do we need to investigate this cluster?"), the **DataAssistantAgent** performs a semantic search across these three stores. It retrieves the specific EPHI investigation thresholds relevant to the reported symptoms and injects them directly into the AI's "active reasoning space" (the prompt).
3.  **Grounded Decision Support (Example):**
    *   **Officer Query:** "Should we deploy a team to Woreda X for the current fever cluster?"
    *   **System Action:** The RAG engine retrieves (a) the EPHI threshold for Viral Hemorrhagic Fever (VHF), (b) current alert data showing a risk score of 78, and (c) a record of a previous VHF event in the same zone.
    *   **AI Response:** "Based on the **EPHI PHEM Manual (Ch. 4)**, a cluster of 8 signals with a risk score of 78 meets the threshold for immediate investigation within 24 hours. **Action Recommended:** Deploy a rapid response team with sample collection kits."
4.  **Verification and Citation:** To maintain clinical liability, the system is instructed to cite its sources. Every recommendation refers back to a specific EPHI manual or historical alert ID. This transforms the AI from a "black box" into a **Clinical Decision Support Tool** that enhances, rather than replaces, human expertise. **The AI recommends; the officer decides.**
