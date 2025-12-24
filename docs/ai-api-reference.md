# AI Service API Reference

> **Version:** 1.0  
> **Status:** Experimental  
> **Base URL:** `/api/ai`

The AI Service provides intelligent analysis and natural language querying capabilities for the HOMEPOT Client. It leverages a local LLM (Ollama) and Vector Memory (ChromaDB) to ensure data privacy.

---

## 1. Analyze Device Metrics

Analyze a set of device metrics to detect anomalies and receive actionable recommendations. This endpoint uses a **Hybrid Approach**:
1.  **Rule-Based Detection:** Instantly flags known issues (e.g., CPU > 90%).
2.  **LLM Analysis:** Provides context, explanation, and troubleshooting steps based on the rule-based findings.

### Endpoint
`POST /analyze`

### Request Body
```json
{
  "device_id": "pos-terminal-01",
  "metrics": {
    "cpu_percent": 92.5,
    "memory_percent": 60.0,
    "disk_percent": 45.0,
    "error_rate": 0.05,
    "network_latency_ms": 120
  }
}
```

### Response
```json
{
  "device_id": "pos-terminal-01",
  "anomaly_score": 0.4,
  "is_anomaly": false,
  "analysis": "The CPU usage is high (92.5%), which exceeds the 90% threshold. However, memory and disk usage are within normal limits. This suggests a compute-intensive process is running. Recommendation: Check for stuck background jobs or recent software updates.",
  "status": "processed"
}
```

---

## 2. Natural Language Query

Ask questions about the system, specific devices, or historical incidents. The system uses **RAG (Retrieval-Augmented Generation)** to provide accurate answers based on:
1.  **Long-Term Memory:** Historical logs and documentation stored in ChromaDB.
2.  **Short-Term Memory:** The recent conversation history.

### Endpoint
`POST /query`

### Request Body
```json
{
  "query": "Why is device pos-terminal-01 failing?",
  "device_id": "pos-terminal-01",
  "history": [
    {
      "role": "user",
      "content": "Is the system healthy?"
    },
    {
      "role": "assistant",
      "content": "Yes, most devices are online, but pos-terminal-01 is reporting errors."
    }
  ]
}
```

### Response
```json
{
  "response": "Based on recent logs, pos-terminal-01 is experiencing high CPU usage (92.5%) and intermittent network latency. This pattern matches a known issue with the 'v2.4.1' firmware update. I recommend rolling back to v2.4.0.",
  "context_used": {
    "long_term_memories": 3,
    "short_term_messages": 2
  }
}
```

---

## 3. Health Check

Verify that the AI Service and LLM are operational.

### Endpoint
`GET /health`

### Response
```json
{
  "status": "healthy",
  "llm_connected": true,
  "version": "1.0.0"
}
```
