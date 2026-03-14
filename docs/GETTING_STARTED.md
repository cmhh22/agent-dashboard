# Getting Started with Agent Dashboard

This guide will help you set up and run the Agent Dashboard project locally.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker Desktop** (recommended) OR
- **Python 3.11+** and **Node.js 18+** (for local development)
- **OpenAI API Key** (required)

## Quick Start with Docker (Recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/cmhh22/agent-dashboard.git
cd agent-dashboard
```

### 2. Set Up Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
# On Windows: notepad .env
# On Mac/Linux: nano .env
```

Add your OpenAI API key:
```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### 3. Start the Application

```bash
docker-compose up --build
```

This will:
- Build the backend (FastAPI)
- Build the frontend (Angular)
- Start Redis for caching
- Initialize ChromaDB for RAG

### 4. Access the Application

Once all services are running:

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 5. Test the Application

1. Open http://localhost:4200 in your browser
2. Try asking questions:
   - "What is 15 * 24?" (Calculator tool)
   - "What's the latest news about AI?" (Web search tool)
   - Upload a document first, then ask about it (RAG tool)

## Local Development Setup (Without Docker)

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.example ../.env
# Edit ../.env and add your OpenAI API key

# Run the backend
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

Open a new terminal:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run the frontend
npm start
# or
ng serve
```

The frontend will be available at http://localhost:4200

## First Steps

### 1. Upload Documents for RAG

To use the RAG (Retrieval-Augmented Generation) feature:

```bash
# Example using curl
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Python is a high-level programming language known for its simplicity and readability.",
    "metadata": {"source": "python_info.txt"}
  }'
```

Or use the API documentation interface at http://localhost:8000/docs

### 2. Chat with the Agent

Try these example queries:

**Calculator:**
- "What is 156 divided by 12?"
- "Calculate 2 to the power of 10"

**Web Search:**
- "What are the latest developments in AI?"
- "Tell me about the weather in Paris"

**RAG (after uploading documents):**
- "What programming language is Python?"
- "Tell me about the documents I uploaded"

### 3. Try WebSocket Streaming

Click the "Streaming ON" button in the UI to enable real-time streaming responses.

## Project Structure

```
agent-dashboard/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API endpoints
│   │   ├── services/ # Business logic
│   │   ├── tools/    # LangChain tools
│   │   └── main.py   # Entry point
│   └── requirements.txt
├── frontend/         # Angular frontend
│   ├── src/
│   │   ├── app/      # Components & services
│   │   └── environments/
│   └── package.json
├── docs/             # Documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

## Common Issues

### Issue: "OpenAI API key not found"
**Solution**: Make sure you've set `OPENAI_API_KEY` in the `.env` file

### Issue: Port 8000 or 4200 already in use
**Solution**: 
```bash
# Find and kill the process using the port
# On Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# On Mac/Linux:
lsof -ti:8000 | xargs kill -9
```

### Issue: Docker build fails
**Solution**: 
```bash
# Clean Docker cache
docker system prune -a
docker-compose build --no-cache
```

### Issue: WebSocket connection fails
**Solution**: 
- Check that backend is running
- Verify CORS settings in `.env`
- Try refreshing the browser

## Next Steps

- Read the [API Documentation](docs/API.md)
- Learn about [Development](docs/DEVELOPMENT.md)
- See [Deployment Guide](docs/DEPLOYMENT.md)
- Explore [Architecture](docs/ARCHITECTURE.md)

## Getting Help

- Check the [documentation](docs/)
- Review [API docs](http://localhost:8000/docs) when running
- Open an issue on GitHub

## What's Next?

Try these advanced features:

1. **Customize the Agent**: Add new tools in `backend/app/tools/`
2. **Upload Multiple Documents**: Build a knowledge base
3. **Evaluate RAG Performance**: Use the metrics endpoint
4. **Extend the Frontend**: Add new components for visualization

Enjoy building with Agent Dashboard! 🚀
