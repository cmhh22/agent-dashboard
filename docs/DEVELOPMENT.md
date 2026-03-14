# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+
- Docker & Docker Compose (optional)
- OpenAI API Key

## Backend Development

### Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.example ../.env
# Edit .env and add your OPENAI_API_KEY
```

### Running Backend

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --port 8000

# Access API documentation
# http://localhost:8000/docs
```

### Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── models.py            # Pydantic models
│   ├── api/                 # API endpoints
│   │   ├── chat.py
│   │   ├── documents.py
│   │   ├── metrics.py
│   │   └── tools.py
│   ├── services/            # Business logic
│   │   ├── agent_service.py
│   │   └── rag_service.py
│   ├── tools/               # LangChain tools
│   │   ├── calculator_tool.py
│   │   ├── web_search_tool.py
│   │   └── rag_tool.py
│   └── websocket/           # WebSocket handlers
│       └── connection_manager.py
├── requirements.txt
└── Dockerfile
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_agent_service.py
```

### Adding New Tools

1. Create a new tool class in `app/tools/`:

```python
from langchain.tools import BaseTool

class MyCustomTool(BaseTool):
    name: str = "my_tool"
    description: str = "Description of what the tool does"
    
    def _run(self, query: str) -> str:
        # Implementation
        return "Result"
    
    async def _arun(self, query: str) -> str:
        return self._run(query)
```

2. Register the tool in `app/services/agent_service.py`:

```python
from app.tools.my_custom_tool import MyCustomTool

self.tools = [
    CalculatorTool(),
    WebSearchTool(),
    RAGTool(),
    MyCustomTool()  # Add your tool
]
```

## Frontend Development

### Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file (if not using backend proxy)
```

### Running Frontend

```bash
# Development server
ng serve

# Open browser
# http://localhost:4200
```

### Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   └── chat/
│   │   │       ├── chat.component.ts
│   │   │       ├── chat.component.html
│   │   │       └── chat.component.scss
│   │   ├── services/
│   │   │   ├── chat.service.ts
│   │   │   └── websocket.service.ts
│   │   ├── app.component.ts
│   │   └── app.config.ts
│   ├── environments/
│   │   ├── environment.ts
│   │   └── environment.prod.ts
│   ├── index.html
│   ├── main.ts
│   └── styles.scss
├── angular.json
├── package.json
├── tailwind.config.js
└── Dockerfile
```

### Building

```bash
# Production build
ng build --configuration production

# Output in dist/agent-dashboard-frontend
```

### Testing

```bash
# Run unit tests
ng test

# Run e2e tests
ng e2e
```

## Full Stack Development

### Using Docker Compose

```bash
# Start all services
docker-compose up

# Rebuild after changes
docker-compose up --build

# Stop services
docker-compose down
```

## API Development

### Adding New Endpoints

1. Create a new router in `backend/app/api/`:

```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint(app_request: Request):
    return {"message": "Hello"}
```

2. Register in `app/main.py`:

```python
from app.api import my_router

app.include_router(my_router.router, prefix="/api/my", tags=["my"])
```

## Database Management

### ChromaDB

```python
# Access RAG service
rag_service = app.state.rag_service

# Add documents
await rag_service.add_document(
    content="Document content",
    metadata={"source": "file.txt"}
)

# Search
results = await rag_service.search("query")

# Get stats
stats = rag_service.get_collection_stats()
```

## WebSocket Development

### Testing WebSocket

```python
# Using Python websockets library
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send(json.dumps({
            "message": "Hello, agent!"
        }))
        
        # Receive responses
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(data)
            if data["type"] == "complete":
                break

asyncio.run(test_websocket())
```

## Code Style

### Python (Backend)
- Follow PEP 8
- Use type hints
- Maximum line length: 100
- Use Black for formatting: `black app/`
- Use flake8 for linting: `flake8 app/`

### TypeScript (Frontend)
- Follow Angular style guide
- Use ESLint
- Use Prettier for formatting
- Maximum line length: 100

## Debugging

### Backend
```bash
# Enable debug mode
uvicorn app.main:app --reload --log-level debug
```

### Frontend
```bash
# Angular DevTools
# Install Angular DevTools Chrome extension
# Source maps are enabled by default in development
```

## Common Issues

### Issue: CORS errors
**Solution**: Check `CORS_ORIGINS` in `.env` and ensure it includes your frontend URL

### Issue: WebSocket connection refused
**Solution**: Ensure backend is running and accessible

### Issue: OpenAI API errors
**Solution**: Verify API key is set correctly and has credits

### Issue: ChromaDB errors
**Solution**: Ensure write permissions to `./data/chroma_db` directory

## Performance Tips

1. **Backend**
   - Use async/await for I/O operations
   - Enable response caching for repeated queries
   - Optimize vector search with appropriate `top_k` values

2. **Frontend**
   - Use OnPush change detection
   - Lazy load components
   - Implement virtual scrolling for long chat histories

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
