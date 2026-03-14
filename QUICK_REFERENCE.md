# Agent Dashboard - Quick Reference

## 🚀 Quick Start Commands

### Start Everything (Docker)
```bash
docker-compose up --build
```

### Stop Everything
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 🔗 Important URLs

- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📝 Common API Calls

### Chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 10 + 5?"}'
```

### Upload Document
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your document content here",
    "metadata": {"source": "file.txt"}
  }'
```

### Upload File
```bash
curl -X POST http://localhost:8000/api/documents/upload-file \
  -F "file=@document.txt"
```

### Get Tools
```bash
curl http://localhost:8000/api/tools
```

### Get Metrics
```bash
curl http://localhost:8000/api/metrics
```

### Get Document Stats
```bash
curl http://localhost:8000/api/documents/stats
```

## 🛠️ Development Commands

### Backend (Local)
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend (Local)
```bash
cd frontend
npm install
ng serve
npm start
```

### Run Tests
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
ng test
```

## 🔧 Configuration

### Environment Variables (.env)
```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview
VECTOR_DB_PATH=./data/chroma_db
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:4200
```

## 🎯 Example Queries

### Calculator Tool
- "What is 156 / 12?"
- "Calculate 2^10"
- "What's (100 + 50) * 2?"

### Web Search Tool
- "Latest AI news"
- "Who won the World Cup 2022?"
- "What's the weather in Tokyo?"

### RAG Tool (after uploading docs)
- "What does the document say about X?"
- "Summarize the uploaded documents"
- "Find information about Y in the knowledge base"

### Combined
- "Search for the latest Python version and calculate how many years since Python 3.0"

## 📦 Docker Commands

### Rebuild Specific Service
```bash
docker-compose build backend
docker-compose build frontend
```

### Start Specific Service
```bash
docker-compose up backend
docker-compose up frontend
```

### Scale Services
```bash
docker-compose up -d --scale backend=3
```

### Clean Up
```bash
docker-compose down -v  # Remove volumes
docker system prune -a  # Clean all Docker resources
```

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
lsof -ti:8000 | xargs kill -9
```

### OpenAI API Error
- Check `.env` file has correct API key
- Verify API key has credits
- Check network connectivity

### WebSocket Connection Failed
- Ensure backend is running
- Check CORS settings
- Refresh browser

### ChromaDB Error
- Check write permissions: `./data/chroma_db`
- Delete and recreate: `rm -rf data/chroma_db`

### Docker Build Failed
```bash
docker system prune -a
docker-compose build --no-cache
```

## 📊 Monitoring

### Check Service Status
```bash
docker-compose ps
```

### Resource Usage
```bash
docker stats
```

### View Logs in Real-time
```bash
docker-compose logs -f --tail=100
```

## 🔐 Security Checklist

- [ ] Change default ports in production
- [ ] Set strong CORS policies
- [ ] Use secrets manager for API keys
- [ ] Enable HTTPS/TLS
- [ ] Implement rate limiting
- [ ] Add authentication
- [ ] Regular security updates

## 📈 Performance Tips

### Backend
- Enable Redis caching
- Optimize vector search `top_k`
- Use async/await properly
- Monitor token usage

### Frontend
- Enable production build
- Use lazy loading
- Implement virtual scrolling
- Optimize bundle size

## 🎨 Customization

### Add New Tool
1. Create tool in `backend/app/tools/`
2. Register in `agent_service.py`
3. Test with agent

### Add New Endpoint
1. Create router in `backend/app/api/`
2. Register in `main.py`
3. Update API documentation

### Add Frontend Component
```bash
cd frontend
ng generate component components/my-component
```

## 📚 Documentation Links

- [Getting Started](docs/GETTING_STARTED.md)
- [API Documentation](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🆘 Getting Help

1. Check documentation in `docs/`
2. Review API docs at `/docs`
3. Check GitHub issues
4. Review error logs
5. Open new GitHub issue

## 💡 Pro Tips

- Use WebSocket streaming for better UX
- Upload documents before asking RAG questions
- Monitor OpenAI costs regularly
- Use environment variables for configuration
- Test with different LLM models
- Keep dependencies updated
- Use Git branches for features
- Write tests before pushing

## 🎯 Quick Testing Workflow

```bash
# 1. Start services
docker-compose up -d

# 2. Check health
curl http://localhost:8000/health

# 3. Upload test document
echo "AI is artificial intelligence" > test.txt
curl -X POST http://localhost:8000/api/documents/upload-file -F "file=@test.txt"

# 4. Test chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is AI according to the document?"}'

# 5. Check metrics
curl http://localhost:8000/api/metrics

# 6. Open frontend
start http://localhost:4200  # Windows
open http://localhost:4200   # Mac
```

## 🔄 Update Workflow

```bash
# 1. Pull latest changes
git pull origin main

# 2. Update dependencies
cd backend && pip install -r requirements.txt
cd frontend && npm install

# 3. Rebuild containers
docker-compose build --no-cache

# 4. Restart services
docker-compose down
docker-compose up -d
```

---

**⚡ Quick Access**: Bookmark this file for instant reference!
