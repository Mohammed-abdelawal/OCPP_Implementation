"""Pytest configuration and fixtures."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = AsyncMock()
    websocket.recv = AsyncMock()
    websocket.send = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


@pytest.fixture
def mock_database_session():
    """Mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_charging_station():
    """Sample charging station data."""
    return {
        "id": 1,
        "station_id": "TEST_CHARGER_001",
        "name": "Test Charger",
        "location": "Test Location",
        "is_online": True,
        "last_heartbeat": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_transaction():
    """Sample transaction data."""
    return {
        "id": 1,
        "session_id": "TEST_SESSION_001",
        "station_id": "TEST_CHARGER_001",
        "status": "active",
        "energy_delivered": 1000,
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": None,
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_ocpp_message():
    """Sample OCPP message data."""
    return {
        "id": 1,
        "station_id": "TEST_CHARGER_001",
        "message_type": "CALL",
        "action": "BootNotification",
        "message_id": "unique-id-1",
        "payload": '{"chargePointModel": "Test Model"}',
        "timestamp": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_boot_notification():
    """Sample BootNotification message."""
    return [
        2,
        "boot-001",
        "BootNotification",
        {
            "chargePointModel": "Tesla Wall Connector",
            "chargePointVendor": "Tesla",
            "chargePointSerialNumber": "TW123456789",
            "chargeBoxSerialNumber": "CB123456789",
            "firmwareVersion": "1.0.0",
        },
    ]


@pytest.fixture
def sample_heartbeat():
    """Sample Heartbeat message."""
    return [2, "heartbeat-001", "Heartbeat", {}]


@pytest.fixture
def sample_status_notification():
    """Sample StatusNotification message."""
    return [
        2,
        "status-001",
        "StatusNotification",
        {"connectorId": 1, "errorCode": "NoError", "status": "Available"},
    ]


@pytest.fixture
def sample_start_transaction():
    """Sample StartTransaction message."""
    return [
        2,
        "start-001",
        "StartTransaction",
        {
            "connectorId": 1,
            "idTag": "john_doe",
            "meterStart": 0,
            "timestamp": "2024-01-01T12:00:00Z",
        },
    ]


@pytest.fixture
def sample_remote_start_transaction():
    """Sample RemoteStartTransaction message."""
    return [
        2,
        "remote-start-001",
        "RemoteStartTransaction",
        {"idTag": "john_doe", "connectorId": 1},
    ]


@pytest.fixture(autouse=True)
def mock_db_manager():
    """Mock database manager for all tests."""
    with pytest.MonkeyPatch().context() as m:
        from app import database

        m.setattr(database, "db_manager", AsyncMock())
        yield


@pytest.fixture
def mock_ocpp_server():
    """Mock OCPP server functions."""
    with pytest.MonkeyPatch().context() as m:
        from app import ocpp_server

        m.setattr(ocpp_server, "get_active_charge_points", MagicMock(return_value={}))
        m.setattr(ocpp_server, "get_charge_point", MagicMock(return_value=None))
        yield


# Pytest markers
pytest_plugins = ["pytest_asyncio"]
