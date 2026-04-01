# Agent Dashboard

**Angular + FastAPI + LangChain Agent + RAG**

Multi-agent AI dashboard with advanced RAG implementation, real-time WebSocket streaming, and modern frontend.

## 🎯 Features

- **LangChain Agent**: Multi-tool agent with 3+ integrated tools
- **Advanced RAG**: Vector database with RAGAS evaluation metrics
- **Angular 17 Frontend**: Modern, responsive UI with real-time updates
- **WebSocket Streaming**: Live streaming of agent responses
- **Docker**: Fully containerized deployment
- **FastAPI Backend**: High-performance async API

## 🏗️ Architecture

```
agent-dashboard/
├── backend/          # FastAPI + LangChain + RAG
├── frontend/         # Angular 17 application
└── docker/           # Docker configurations
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Using Docker (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:4200
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
ng serve
```

## 📋 Environment Variables

Create a `.env` file in the root directory:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Vector Database
VECTOR_DB_PATH=./data/chroma_db

# FastAPI
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:4200

# Angular
FRONTEND_PORT=4200
API_URL=http://localhost:8000
```

## 🛠️ Tech Stack

### Backend
- **FastAPI**: Fast, modern Python web framework
- **LangChain**: Framework for LLM applications
- **ChromaDB**: Vector database for RAG
- **RAGAS**: RAG evaluation metrics
- **WebSocket**: Real-time streaming
- **Pydantic**: Data validation

### Frontend
- **Angular 17**: Modern web framework
- **TypeScript**: Type-safe JavaScript
- **RxJS**: Reactive programming
- **WebSocket Client**: Real-time communication
- **TailwindCSS**: Utility-first CSS

## 📊 Agent Tools

The LangChain agent includes:

1. **Web Search Tool**: DuckDuckGo search integration
2. **Code Interpreter Tool**: Sandboxed Python execution for calculations and data tasks
3. **URL Analyzer Tool**: Fetch and analyze webpage content
4. **RAG Tool**: Document retrieval and QA

## 🎓 RAG Evaluation

RAGAS metrics implemented:
- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

## 📝 API Endpoints

- `POST /api/chat`: Send message to agent
- `WS /ws/chat`: WebSocket streaming connection
- `POST /api/documents`: Upload documents for RAG
- `GET /api/metrics`: Get RAG evaluation metrics
- `GET /api/tools`: List available agent tools

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
ng test
```

## 📦 Deployment

Use `docker-compose.yml` and the production `frontend/nginx.conf` setup for deployment.

## 📄 License

MIT License

## 👨‍💻 Author

Carlos M. Hernández Hernández
- GitHub: [@cmhh22](https://github.com/cmhh22)
- Portfolio: [Agent Dashboard Project](https://github.com/cmhh22/agent-dashboard)

## 🤝 Contributing

Contributions are welcome via issues and pull requests.

---

**Status**: 🚧 In Development (March 2026)
