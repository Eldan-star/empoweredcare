# Empowered Care - Frontend API Documentation

This document provides the API specifications and JSON response examples for the frontend team to integrate with the Empowered Care Multi-Agent Disease Outbreak Detection System.

## 🚀 Base URL
`http://localhost:8000`

---

## 🚨 1. Process Outbreak Report
Processes a raw text report through the **Dynamic Hierarchical Multi-Agent Pipeline** (SuperAgent Orchestrator).

### **Endpoint**
`POST /outbreak/process`

### **Request Body**
```json
{
  "text": "Fever, vomiting, 4 people affected in Jimma"
}
```

### **Success Response (200 OK)**
```json
{
  "extracted_data": {
    "location": "Jimma",
    "symptoms": ["fever", "vomiting"],
    "cases": 4,
    "date": null,
    "additional_info": {}
  },
  "validation": {
    "valid": true,
    "confidence": 0.85,
    "issues": []
  },
  "risk_analysis": {
    "risk_level": "MEDIUM",
    "confidence": "65%",
    "possible_disease": "Malaria",
    "reason": "Jimma is located in a region of Ethiopia endemic for malaria..."
  },
  "consensus": {
    "final_risk_level": "MEDIUM",
    "average_confidence": 72.5,
    "consensus_reached": true,
    "agent_opinions": [
      {
        "risk_level": "MEDIUM",
        "confidence": "75%",
        "possible_disease": "Malaria",
        "reason": "Symptom-based perspective..."
      },
      {
        "risk_level": "HIGH",
        "confidence": "70%",
        "possible_disease": "Cholera",
        "reason": "Statistical pattern perspective..."
      }
    ],
    "final_reasoning": "Consensus reached from multiple perspectives..."
  },
  "alert": {
    "title": "Public Health Alert: Suspected Malaria in Jimma",
    "message": "A cluster of 4 cases showing fever and vomiting has been reported in Jimma.",
    "recommendations": [
      "Use mosquito nets",
      "Visit clinic if fever persists",
      "Remove standing water"
    ],
    "prevention_strategy": "To prevent more cases, everyone should sleep under treated nets and remove any stagnant water around their homes where mosquitoes breed.",
    "why_urgent": "We are seeing more cases than usual for this time of year, which could mean a local outbreak is starting."
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "processed_at": "2026-04-03T17:00:00Z",
    "processing_time_seconds": 3.15,
    "orchestrator": "SuperAgent",
    "consensus_reached": true
  },
  "message": "🚨 Outbreak report processed through dynamic multi-agent pipeline.",
  "human_validation_required": true
}
```

---

## 🔍 2. Query Outbreak Data
Ask natural language questions about the collected data using the Data Assistant Agent.

### **Endpoint**
`POST /outbreak/query`

### **Request Body**
```json
{
  "query": "Which locations have the highest risk?"
}
```

### **Success Response (200 OK)**
```json
{
  "query": "Which locations have the highest risk?",
  "response": "Based on current reports, Hawassa is currently marked as HIGH risk due to a cluster of 10 cases with rash and fever symptoms. Jimma is marked as MEDIUM risk.",
  "data_summary": {
    "total_reports": 15,
    "total_cases": 42,
    "locations": ["Jimma", "Hawassa", "Addis Ababa"],
    "risk_distribution": {
      "HIGH": 1,
      "MEDIUM": 4,
      "LOW": 10
    }
  }
}
```

---

## ✅ 3. Approve Alert
Manually approve or reject a generated alert (Human-in-the-loop).

### **Endpoint**
`POST /outbreak/approve/{session_id}`

### **Request Body (Optional)**
```json
{
  "approved": true
}
```

### **Success Response (200 OK)**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved": true,
  "message": "Alert approved and sent to notification system.",
  "timestamp": "2026-04-03T17:05:00Z"
}
```

---

## 📊 4. Data Summary
Get a high-level statistical overview of all reports.

### **Endpoint**
`GET /outbreak/summary`

### **Success Response (200 OK)**
```json
{
  "total_reports": 3,
  "total_cases": 16,
  "locations": ["Jimma", "Hawassa", "Addis Ababa"],
  "timestamp": "2026-04-03T17:10:00Z",
  "data_points": 3
}
```

---

## 💓 5. Health Check
Check system and agent status.

### **Endpoint**
`GET /health`

### **Success Response (200 OK)**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-03T17:15:00Z",
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

---

## � 6. Multi-Agent Chatbot
Powerful AI assistant with memory that can answer questions about locations, symptoms, and timelines.

### **Endpoint**
`POST /outbreak/chat`

### **Request Body**
```json
{
  "message": "Where are the most cases reported?",
  "session_id": "optional-uuid"
}
```

### **Success Response (200 OK)**
```json
{
  "response": "Most cases are currently reported in Hawassa (10 cases) and Jimma (4 cases).",
  "session_id": "uuid-returned-or-provided",
  "agent_used": "location",
  "history_count": 1
}
```

### **Endpoint (Clear History)**
`DELETE /outbreak/chat/{session_id}`

---

## �🛠️ Integration Notes for Frontend

1. **Human Validation**: If `human_validation_required` is `true` in the `/process` response, the UI should show an "Approve/Reject" interface for a supervisor.
2. **Risk Levels**: Use the following color coding for `risk_level`:
   - `HIGH`: 🔴 Red
   - `MEDIUM`: 🟠 Orange
   - `LOW`: 🟢 Green
3. **Polling**: The system is synchronous, so you can wait for the response directly. If processing takes >5s, consider adding a loading state with "Analyzing with AI Agents...".
4. **CORS**: Enabled for all origins (`*`) in the current development setup.

---
*Document Version: 1.0.0*
*Last Updated: April 3, 2026*
