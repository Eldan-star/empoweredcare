# Empowered Care - System Design & Codebase Review

## 🏗️ Architecture Overview

Empowered Care is an AI-native epidemiological intelligence system designed for rapid disease outbreak detection. It leverages a **Dynamic Hierarchical Multi-Agent System** to process unstructured data from multiple sources (Text, CSV, PDF, Images).

### 1. Orchestration Layer (`SuperAgent`)
The system follows a "Supervisor-Worker" pattern. The `SuperAgent` is the central brain that:
- **Analyzes Input Complexity**: Decides how to process the incoming data.
- **Parallel Task Spawning**: For high-volume inputs, it spawns multiple sub-agents to process data in parallel using Python's `asyncio`.
- **Consensus Building**: Implements a `Merge Layer` that collects opinions from specialized risk sub-agents and reaches a unified conclusion based on weighted voting and confidence averaging.

### 2. Specialized Multi-Agent Pipeline
- **Extraction Agent**: Uses LLM-driven structured extraction. It is robust against messy, handwritten-style text.
- **Validation Agent**: Performs a dual-layer check. It first applies hard rules (e.g., symptom whitelist, realistic case counts) and then uses AI to check for geographic and medical plausibility.
- **Risk Analysis Sub-Agents**: Spawns multiple agents with different "perspectives":
    - **Clinical Perspective**: Matches symptoms to known disease patterns.
    - **Statistical Perspective**: Analyzes case growth and population density.
    - **Historical Perspective**: Checks regional history and seasonal trends.
- **Alert Generation Agent**: Translates complex epidemiological findings into simple, actionable public health messages, including prevention strategies and urgent justifications.

### 3. Powerful Chatbot System (`ChatSupervisor`)
A separate multi-agent system dedicated to data interaction:
- **Dynamic Routing**: Uses an intent-detection LLM to route queries to specialized agents (`Location`, `Infection`, `History`).
- **Session Memory**: Uses a sliding window history to remember past context while maintaining efficiency.
- **Context Injection**: Automatically injects the latest 10 outbreak reports into the chatbot's context for factual accuracy.

## 💻 Codebase Review

### Strengths
- **Asynchronous Design**: The entire pipeline is `async`, preventing I/O blocking during long LLM calls.
- **Vision Integration**: Moving from local OCR (`PaddleOCR`) to `Gemini Vision` significantly reduced the server footprint and improved accuracy for irregular medical forms.
- **Type Safety**: Heavy use of `Pydantic` models ensures data consistency across the distributed agent pipeline.
- **Modular Services**: Clear separation between `gemini_service`, `ocr_engine`, and `agents`.

### Design Implementation Details
- **Memory Management**: The `DataAssistantAgent` and `ChatSupervisor` both implement storage limits (`MAX_STORED_REPORTS` and history slicing) to prevent memory leaks in long-running sessions.
- **Lazy Loading**: Heavy services like the OCR engine are lazy-loaded to ensure the FastAPI server starts in under 2 seconds.
- **Error Fallbacks**: The `ExtractionAgent` includes robust fallbacks to handle malformed JSON from the LLM, ensuring the pipeline never breaks.

## 🚀 Key Innovation
The **Merge Layer** is the standout feature. By requiring a consensus between multiple agents looking at the data from different angles, the system drastically reduces false positives—a critical requirement for public health systems.

---
*Reviewed on: April 3, 2026*
