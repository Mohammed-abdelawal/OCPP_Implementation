# OCPP Backend Module for Electric Vehicle Chargers

A comprehensive backend system for managing Electric Vehicle (EV) chargers using the OCPP 1.6 JSON protocol. This system provides WebSocket communication with chargers, REST API for control, and a web interface for monitoring and management.

## 🚀 Features

- **OCPP 1.6 JSON Protocol Support**: Full implementation of OCPP 1.6 message handling
- **WebSocket Server**: Real-time communication with multiple EV chargers
- **REST API**: Complete API for charger management and control
- **Database Integration**: PostgreSQL with SQLAlchemy for data persistence
- **Web Interface**: Modern, responsive frontend for system monitoring
- **Message Logging**: Complete OCPP message audit trail
- **Transaction Management**: Charging session tracking and management
- **Remote Control**: Start/stop charging sessions remotely
- **Configuration Management**: Remote charger configuration updates

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Docker & Docker Compose (optional)

## 🛠️ Installation

### Using Docker Compose

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd OCPP_Implementation
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials if needed
   ```

3. **Start the services**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Web Interface: http://localhost
   - API Documentation: http://localhost:8002/docs
   - OCPP WebSocket Server: ws://localhost:9002

5. ** Create Mock data**:
   ```bash
   python3 scripts create_sample_data.py
   ```
## 🏗️ System Architecture

### Components

1. **OCPP WebSocket Server** (`app/ocpp_server.py`)
   - Handles WebSocket connections from EV chargers
   - Implements OCPP 1.6 message handlers
   - Manages charger sessions and state

2. **REST API** (`app/main.py`)
   - FastAPI-based REST endpoints
   - Charger management and control
   - Transaction and message logging

3. **Database Models** (`app/models.py`)
   - SQLAlchemy models for data persistence
   - Charging stations, sessions, and OCPP messages

4. **Web Interface** (`app/static/index.html`)
   - system monitoring
   - Charger control interface

### Database Schema

- **charging_stations**: Charger information and status
- **charging_sessions**: Charging transaction records
- **ocpp_messages**: OCPP message audit log
- **users**: User management (for future authentication)

## 🔌 OCPP Protocol Support

### Supported Messages

#### From Charger to Backend (Incoming)
- `BootNotification`: Charger startup and registration
- `Heartbeat`: Periodic status updates
- `StatusNotification`: Connector status changes
- `StartTransaction`: Beginning of charging session
- `StopTransaction`: End of charging session

#### From Backend to Charger (Outgoing)
- `RemoteStartTransaction`: Remote charging start
- `RemoteStopTransaction`: Remote charging stop
- `ChangeConfiguration`: Configuration updates

## 📡 API Endpoints

### System Management
- `GET /health` - System health check
- `GET /` - Web interface
- `GET /api` - API information

### Charger Management
- `GET /chargers` - List all chargers
- `GET /chargers/active` - List active chargers
- `POST /chargers/{id}/start` - Start charging
- `POST /chargers/{id}/stop` - Stop charging
- `POST /chargers/{id}/configure` - Update configuration

### Data Access
- `GET /transactions` - List all transactions
- `GET /transactions/{station_id}` - Station-specific transactions
- `GET /messages/{station_id}` - OCPP message log

## 🧪 Testing

### Automated Testing


# Run tests with coverage
pytest .

# Run tests in Docker
make docker-test
```

### OCPP Simulator Testing

1. **Download OCPP Simulator**:
   - Visit: https://github.com/NewMotion/ocpp-simulator
   - Or use online simulators like SteVe

2. **Configure Simulator**:
   - WebSocket URL: `ws://localhost:9000/{charger_id}`
   - Example: `ws://localhost:9000/CHARGER_001`

3. **Test Scenarios**:
   - Boot notification
   - Heartbeat messages
   - Start/stop transactions
   - Remote commands

### Manual Testing

1. **Start the system**:
   ```bash
   docker-compose up -d
   ```

2. **Access web interface**: http://localhost

3. **Test API endpoints**:
   ```bash
   # Check system health
   curl http://localhost/health
   
   # List chargers
   curl http://localhost/chargers
   
   # Start charging (requires active charger)
   curl -X POST http://localhost/chargers/CHARGER_001/start \
        -H "Content-Type: application/json" \
        -d '{"id_tag": "USER_123", "connector_id": 1}'
   ```

## 🛠️ Development

### Development Setup

```bash
# Clone and setup
git clone <repository-url>
cd OCPP_Implementation

# Setup development environment
make dev-setup

# Install pre-commit hooks
pre-commit install
```

### Code Quality

The project uses several tools for code quality:

- **Ruff**: Fast Python linter and formatter
- **Bandit**: Security linter
- **Pytest**: Testing framework
- **Pre-commit**: Git hooks for quality checks

```bash
# Run all quality checks
make ci

# Format code
make format

# Run linting
make lint

# Run security checks
make security
```

### Available Commands

```bash
make help          # Show all available commands
make install       # Install production dependencies
make install-dev   # Install development dependencies
make test          # Run tests
make lint          # Run linting
make format        # Format code
make security      # Run security checks
make clean         # Clean up generated files
make docker-build  # Build Docker image
make docker-up     # Start services
make docker-down   # Stop services
```

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://evuser:evpass@db:5432/evcs
POSTGRES_DB=evcs
POSTGRES_USER=evuser
POSTGRES_PASSWORD=evpass

# Application
APP_ENV=local
```

### OCPP Server Configuration

- **Host**: 0.0.0.0 (all interfaces)
- **Port**: 9000 (WebSocket)
- **Heartbeat Interval**: 300 seconds (5 minutes)

## 📊 Monitoring and Logging

### System Monitoring
- Real-time charger status
- Connection health monitoring
- Transaction tracking
- Message audit trail

### Logging
- OCPP message logging to database
- Application logs via Python logging
- Error tracking and debugging

## 🚀 Deployment

### Production Considerations

1. **Security**:
   - Implement authentication (JWT tokens)
   - Use HTTPS/WSS for secure connections
   - Database encryption

2. **Scalability**:
   - Load balancing for multiple instances
   - Database connection pooling
   - Redis for session management

3. **Monitoring**:
   - Application performance monitoring
   - Database performance metrics
   - OCPP message throughput

### Docker Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/evcs
    ports:
      - "80:8000"
      - "9000:9000"
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: evcs
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Check PostgreSQL is running
   - Verify database credentials
   - Ensure database exists

2. **WebSocket Connection Issues**:
   - Check firewall settings
   - Verify port 9000 is open
   - Test with OCPP simulator

3. **Frontend Not Loading**:
   - Check static file serving
   - Verify file permissions
   - Check browser console for errors

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
uvicorn app.main:app --log-level debug
```

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review OCPP 1.6 specification

## 🔮 Future Enhancements

- OCPP 2.0.1 support
- Advanced authentication
- Mobile app integration
- Real-time notifications
- Advanced analytics
- Multi-tenant support
