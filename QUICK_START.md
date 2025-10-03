# 🚀 Quick Start Guide

## Simple Docker Setup

This is a **simple, clean Docker setup** with just 2 services and proper permissions handling.

### 🏃‍♂️ Quick Commands

```bash
# Start everything
make up

# Stop everything  
make down

# View logs
make logs

# Run Ruff formatting
make format

# Run Ruff linting
make lint

# Run tests
make test

# Development mode (with logs)
make dev
```

### 📋 What's Included

- **App Service**: FastAPI + OCPP WebSocket server
- **Database Service**: PostgreSQL 15
- **Ruff**: Code formatting and linting (inside Docker)
- **Proper Permissions**: All cache and file permissions handled

### 🔧 Services

| Service | Port | Description |
|---------|------|-------------|
| App | 8000 | FastAPI REST API |
| App | 9000 | OCPP WebSocket Server |
| Database | 5432 | PostgreSQL |

### 🌐 Access Points

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **OCPP Server**: ws://localhost:9000/{charger_id}
- **Health Check**: http://localhost:8000/health

### 🛠️ Development

```bash
# Format code
docker-compose exec app ruff format app/

# Check linting
docker-compose exec app ruff check app/

# Run tests
docker-compose exec app pytest tests/ -v

# Access container shell
docker-compose exec app bash
```

### 🧹 Cleanup

```bash
# Stop and remove everything
make clean

# Or manually
docker-compose down -v
docker system prune -f
```

### ✅ Features

- ✅ **Simple Setup**: Just 2 services
- ✅ **Proper Permissions**: Ruff cache and file permissions handled
- ✅ **Ruff Integration**: Formatting and linting inside Docker
- ✅ **Health Checks**: Automatic health monitoring
- ✅ **Volume Persistence**: Database data persists
- ✅ **Development Ready**: Hot reload and logs

### 🎯 Ready to Go!

Your OCPP Backend Module is now running with a simple, clean Docker setup! 🎉
