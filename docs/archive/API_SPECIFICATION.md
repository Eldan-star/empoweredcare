# Empowered Care - API Specification & JSON Examples

This document serves as the definitive guide for integrating with the Empowered Care API.

## 🚀 Base URL
`http://127.0.0.1:8000`

---

## 1. Process Raw Text Report
Submit an unstructured text message for multi-agent analysis.

**Endpoint:** `POST /outbreak/process`

### **Request Body**
```json
{
  "text": "10 children with high fever and rash in Hawassa city. Very urgent."
}
```

### **Success Response (200 OK)**
```json
{
  "extracted_data": {
    "location": "Hawassa",
    "symptoms": ["high fever", "rash"],
    "cases": 10,
    "date": null,
    "additional_info": {}
  },
  "validation": {
    "valid": true,
    "confidence": 0.9,
    "issues": []
  },
  "risk_analysis": {
    "risk_level": "HIGH",
    "confidence": "85%",
    "possible_disease": "Measles",
    "reason": "Large cluster of children with classic fever/rash pattern in a dense urban area."
  },
  "consensus": {
    "final_risk_level": "HIGH",
    "average_confidence": 82.5,
    "consensus_reached": true,
    "agent_opinions": [
      { "risk_level": "HIGH", "confidence": "85%", "possible_disease": "Measles", "reason": "Symptoms match..." },
      { "risk_level": "MEDIUM", "confidence": "80%", "possible_disease": "Unknown Virus", "reason": "Case count high..." }
    ],
    "final_reasoning": "Consensus reached from multiple perspectives..."
  },
  "alert": {
    "title": "URGENT HEALTH ALERT: Suspected Measles Outbreak in Hawassa",
    "message": "A cluster of 10 cases has been identified in Hawassa...",
    "recommendations": ["Vaccination drive", "Isolation"],
    "prevention_strategy": "Ensure all children are vaccinated...",
    "why_urgent": "Measles spreads fast in urban areas..."
  },
  "session_id": "uuid-here",
  "metadata": {
    "processed_at": "2026-04-03T20:00:00Z",
    "processing_time_seconds": 3.45,
    "orchestrator": "SuperAgent"
  },
  "message": "🚨 Outbreak report processed through dynamic multi-agent pipeline.",
  "human_validation_required": true
}
```

---

## 2. Process File Upload (PDF, CSV, Image)
Upload an epidemiological document or field note for analysis.

**Endpoint:** `POST /outbreak/upload`
**Content-Type:** `multipart/form-data`

### **Request**
- `file`: The binary file (CSV, PDF, or JPG/PNG image).

### **Success Response (200 OK)**
*Structure is identical to `/outbreak/process` response.*

---

## 3. Multi-Agent Chatbot
Ask questions about the outbreak data with session-based memory.

**Endpoint:** `POST /outbreak/chat`

### **Request Body**
```json
{
  "message": "Which cities are currently affected?",
  "session_id": "optional-uuid-to-continue-convo"
}
```

### **Success Response (200 OK)**
```json
{
  "response": "The affected cities are Hawassa (10 cases) and Jimma (4 cases).",
  "session_id": "uuid-for-next-turn",
  "agent_used": "location",
  "history_count": 1
}
```

---

## 4. Clear Chat Session
Reset conversation history.

**Endpoint:** `DELETE /outbreak/chat/{session_id}`

### **Success Response (200 OK)**
```json
{
  "message": "Session uuid-here cleared successfully"
}
```

---

## 5. Statistical Summary
Get high-level dashboard data.

**Endpoint:** `GET /outbreak/summary`

### **Success Response (200 OK)**
```json
{
  "total_reports": 5,
  "total_cases": 24,
  "locations": ["Hawassa", "Jimma", "Addis Ababa"],
  "timestamp": "2026-04-03T20:05:00Z",
  "data_points": 5
}
```

---

## 6. System Health Check
Check status of all internal agents.

**Endpoint:** `GET /health`

### **Success Response (200 OK)**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-03T20:10:00Z",
  "version": "1.0.0",
  "agents": {
    "extraction": "active",
    "validation": "active",
    "risk_analysis": "active",
    "alert_generation": "active",
    "data_assistant": "active"
  }
}
```
