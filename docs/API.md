# API Documentation

## Base URL

```
Development: http://localhost:8000
Production: https://your-domain.com
```

## Authentication

Currently, the API does not require authentication. In production, implement:
- JWT tokens
- API keys
- OAuth 2.0

## Endpoints

### Health Check

#### GET /health

Check if the API is running.

**Response**
```json
{
  "status": "healthy"
}
```

---

## Chat Endpoints

### Send Chat Message

#### POST /api/chat

Send a message to the AI agent.

**Request Body**
```json
{
  "message": "What is 2 + 2?",
  "conversation_id": "optional-conversation-id"
}
```

**Response**
```json
{
  "response": "The result is: 4",
  "conversation_id": "abc-123-def-456",
  "tool_calls": [
    {
      "tool": "code_interpreter",
      "input": "print(2 + 2)",
      "output": "The result is: 4"
    }
  ],
  "sources": null
}
```

**Status Codes**
- 200: Success
- 400: Invalid request
- 500: Server error

---

### WebSocket Chat

#### WS /ws/chat

Real-time streaming chat with the agent.

**Connection**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');
```

**Send Message**
```json
{
  "message": "Tell me about AI"
}
```

**Receive Responses**
```json
// Streaming chunk
{
  "type": "stream",
  "content": "AI stands for"
}

// Tool usage
{
  "type": "stream",
  "content": "[Using tool: web_search]"
}

// Completion
{
  "type": "complete",
  "content": ""
}

// Error
{
  "type": "error",
  "content": "Error message"
}
```

---

## Document Endpoints

### Upload Document (JSON)

#### POST /api/documents/upload

Upload a document to the RAG knowledge base.

**Request Body**
```json
{
  "content": "This is the document content...",
  "metadata": {
    "source": "document.txt",
    "author": "John Doe",
    "date": "2026-02-24"
  }
}
```

**Response**
```json
{
  "document_id": "doc-abc-123",
  "status": "success",
  "message": "Document uploaded successfully"
}
```

---

### Upload Document (File)

#### POST /api/documents/upload-file

Upload a file to the RAG knowledge base.

**Request**
- Content-Type: multipart/form-data
- Field: `file` (text file)

**Response**
```json
{
  "document_id": "doc-def-456",
  "status": "success",
  "message": "File 'document.txt' uploaded successfully"
}
```

---

### Get Collection Stats

#### GET /api/documents/stats

Get statistics about the document collection.

**Response**
```json
{
  "document_count": 42,
  "collection_name": "agent_documents"
}
```

---

## Metrics Endpoints

### Get Metrics

#### GET /api/metrics

Get current RAG evaluation metrics.

**Response**
```json
{
  "metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.82,
    "context_precision": 0.88,
    "context_recall": 0.79,
    "timestamp": "2026-02-24T10:30:00Z"
  },
  "queries_processed": 150,
  "average_response_time": 1.25
}
```

---

### Trigger RAG Evaluation

#### POST /api/metrics/evaluate

Trigger a new RAG evaluation (requires ground truth data).

**Response**
```json
{
  "status": "success",
  "message": "RAG evaluation completed",
  "metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.82,
    "context_precision": 0.88,
    "context_recall": 0.79
  }
}
```

---

## Tools Endpoints

### Get Available Tools

#### GET /api/tools

List all available agent tools.

**Response**
```json
{
  "tools": [
    {
      "name": "code_interpreter",
      "description": "Execute Python code in a sandbox for calculations and data operations...",
      "parameters": {}
    },
    {
      "name": "web_search",
      "description": "Useful for searching the internet...",
      "parameters": {
        "max_results": 5
      }
    },
    {
      "name": "url_analyzer",
      "description": "Fetch and analyze URL/webpage content...",
      "parameters": {}
    },
    {
      "name": "rag_tool",
      "description": "Useful for retrieving information from documents...",
      "parameters": {}
    }
  ],
  "count": 4
}
```

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes**
- 400: Bad Request - Invalid input
- 404: Not Found - Resource not found
- 500: Internal Server Error - Server-side error

---

## Rate Limiting

Currently not implemented. Recommended for production:
- 100 requests per minute per IP
- 1000 requests per hour per IP

---

## Examples

### Python

```python
import requests

# Send chat message
response = requests.post(
    "http://localhost:8000/api/chat",
    json={"message": "What is 10 * 5?"}
)
print(response.json())

# Upload document
response = requests.post(
    "http://localhost:8000/api/documents/upload",
    json={
        "content": "Python is a programming language.",
        "metadata": {"source": "python.txt"}
    }
)
print(response.json())
```

### JavaScript

```javascript
// Send chat message
fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Hello!' })
})
  .then(res => res.json())
  .then(data => console.log(data));

// WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({ message: 'Hello!' }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

### cURL

```bash
# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is AI?"}'

# Upload document
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Content-Type: application/json" \
  -d '{"content": "Document text", "metadata": {"source": "file.txt"}}'

# Get tools
curl http://localhost:8000/api/tools
```

---

## Interactive Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These interfaces allow you to test all endpoints directly from your browser.
