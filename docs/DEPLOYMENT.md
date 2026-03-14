# Deployment Guide

## Docker Deployment

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API Key

### Steps

1. **Clone the repository**
```bash
git clone https://github.com/cmhh22/agent-dashboard.git
cd agent-dashboard
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. **Build and run with Docker Compose**
```bash
docker-compose up --build
```

4. **Access the application**
- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Production Deployment

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml agent-dashboard
```

### Using Kubernetes

```bash
# Create namespace
kubectl create namespace agent-dashboard

# Create secret for API key
kubectl create secret generic openai-api-key \
  --from-literal=OPENAI_API_KEY=your-api-key \
  -n agent-dashboard

# Apply manifests
kubectl apply -f k8s/ -n agent-dashboard
```

### Cloud Deployment

#### AWS ECS

1. Create ECR repositories for backend and frontend
2. Build and push images:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com

docker build -t agent-dashboard-backend ./backend
docker tag agent-dashboard-backend:latest your-account.dkr.ecr.us-east-1.amazonaws.com/agent-dashboard-backend:latest
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/agent-dashboard-backend:latest

docker build -t agent-dashboard-frontend ./frontend
docker tag agent-dashboard-frontend:latest your-account.dkr.ecr.us-east-1.amazonaws.com/agent-dashboard-frontend:latest
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/agent-dashboard-frontend:latest
```

3. Create ECS task definitions and services

#### Google Cloud Run

```bash
# Backend
gcloud run deploy agent-dashboard-backend \
  --source ./backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=your-api-key

# Frontend
gcloud run deploy agent-dashboard-frontend \
  --source ./frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Environment Variables

### Required
- `OPENAI_API_KEY`: Your OpenAI API key

### Optional
- `OPENAI_MODEL`: Model to use (default: gpt-4-turbo-preview)
- `VECTOR_DB_PATH`: Path for ChromaDB (default: ./data/chroma_db)
- `BACKEND_PORT`: Backend port (default: 8000)
- `CORS_ORIGINS`: Allowed CORS origins

## Monitoring

### Health Checks
- Backend: `http://localhost:8000/health`
- Frontend: `http://localhost:4200`

### Logs
```bash
# View all logs
docker-compose logs -f

# View backend logs
docker-compose logs -f backend

# View frontend logs
docker-compose logs -f frontend
```

## Scaling

### Horizontal Scaling
```bash
# Scale backend replicas
docker-compose up -d --scale backend=3
```

### Redis Setup for Load Balancing
Included in docker-compose.yml for session management and caching.

## Security

### Production Checklist
- [ ] Use HTTPS/TLS certificates
- [ ] Set strong CORS policies
- [ ] Secure API keys in secrets manager
- [ ] Enable rate limiting
- [ ] Set up authentication/authorization
- [ ] Configure firewall rules
- [ ] Enable container security scanning
- [ ] Set up logging and monitoring

## Backup

### Vector Database Backup
```bash
# Backup ChromaDB data
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz ./data/chroma_db
```

### Restore
```bash
# Restore ChromaDB data
tar -xzf chroma_backup_YYYYMMDD.tar.gz -C ./data/
```

## Troubleshooting

### Backend not starting
- Check OpenAI API key is set correctly
- Verify network connectivity
- Check logs: `docker-compose logs backend`

### WebSocket connection failed
- Verify CORS settings
- Check network/firewall rules
- Ensure backend is accessible

### Frontend can't connect to backend
- Check API_URL in environment
- Verify backend is running
- Check network configuration
