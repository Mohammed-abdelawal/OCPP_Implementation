"""Test cases for REST API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    with patch("app.main.db_manager") as mock:
        mock.health_check = AsyncMock(
            return_value={"status": "healthy", "message": "OK"}
        )
        yield mock


class TestHealthEndpoint:
    """Test health check endpoint."""

    @patch("app.main.ocpp_server")
    def test_health_check_success(self, mock_ocpp_server, client):
        """Test successful health check."""
        mock_ocpp_server.return_value = "mock_server"

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "database" in data["services"]
        assert "ocpp_server" in data["services"]


class TestChargersEndpoint:
    """Test chargers endpoints."""

    @patch("app.main.db_manager.get_session")
    def test_get_chargers_empty(self, mock_get_session, client):
        """Test getting chargers when none exist."""
        # Mock empty result
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        response = client.get("/chargers")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    @patch("app.main.db_manager.get_session")
    def test_get_chargers_with_data(
        self, mock_get_session, client, sample_charging_station
    ):
        """Test getting chargers with data."""
        # Mock result with sample data
        mock_session = AsyncMock()
        mock_station = MagicMock()
        mock_station.id = sample_charging_station["id"]
        mock_station.station_id = sample_charging_station["station_id"]
        mock_station.name = sample_charging_station["name"]
        mock_station.location = sample_charging_station["location"]
        mock_station.is_online = sample_charging_station["is_online"]
        # Mock last_heartbeat and created_at as datetime objects with isoformat method
        from datetime import datetime

        mock_station.last_heartbeat = datetime.fromisoformat(
            sample_charging_station["last_heartbeat"].replace("Z", "+00:00")
        )
        mock_station.created_at = datetime.fromisoformat(
            sample_charging_station["created_at"].replace("Z", "+00:00")
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_station]
        mock_session.execute.return_value = mock_result

        # Mock the async context manager
        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        response = client.get("/chargers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_charging_station["station_id"]

    @patch("app.main.get_active_charge_points")
    def test_get_active_chargers_empty(self, mock_get_active, client):
        """Test getting active chargers when none are active."""
        mock_get_active.return_value = {}

        response = client.get("/chargers/active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["active_chargers"] == []

    @patch("app.main.get_active_charge_points")
    def test_get_active_chargers_with_data(self, mock_get_active, client):
        """Test getting active chargers with data."""
        # Mock active charge points
        mock_cp = MagicMock()
        mock_cp.station_id = "CHARGER_001"
        mock_cp.is_online = True
        mock_cp.last_heartbeat = MagicMock()
        mock_cp.last_heartbeat.isoformat.return_value = "2024-01-01T00:00:00Z"
        mock_cp.connector_status = {1: {"status": "Available"}}

        mock_get_active.return_value = {"CHARGER_001": mock_cp}

        response = client.get("/chargers/active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert "CHARGER_001" in data["active_chargers"]
        assert len(data["chargers"]) == 1
        assert data["chargers"][0]["station_id"] == "CHARGER_001"


class TestChargerControl:
    """Test charger control endpoints."""

    @patch("app.main.get_charge_point")
    def test_start_charging_charger_not_found(self, mock_get_charge_point, client):
        """Test starting charging when charger not found."""
        mock_get_charge_point.return_value = None

        response = client.post(
            "/chargers/TEST_CHARGER/start",
            json={"id_tag": "USER123", "connector_id": 1},
        )
        assert response.status_code == 404
        assert "Charger not found" in response.json()["detail"]

    @patch("app.main.get_charge_point")
    def test_start_charging_success(self, mock_get_charge_point, client):
        """Test successful remote start transaction."""
        mock_cp = MagicMock()
        mock_cp.send_remote_start_transaction = AsyncMock(
            return_value={"status": "Accepted"}
        )
        mock_get_charge_point.return_value = mock_cp

        response = client.post(
            "/chargers/CHARGER_001/start",
            json={"id_tag": "john_doe", "connector_id": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_cp.send_remote_start_transaction.assert_called_once_with(
            id_tag="john_doe", connector_id=1
        )

    @patch("app.main.get_charge_point")
    def test_stop_charging_charger_not_found(self, mock_get_charge_point, client):
        """Test stopping charging when charger not found."""
        mock_get_charge_point.return_value = None

        response = client.post(
            "/chargers/TEST_CHARGER/stop", json={"transaction_id": 12345}
        )
        assert response.status_code == 404
        assert "Charger not found" in response.json()["detail"]

    @patch("app.main.get_charge_point")
    def test_stop_charging_success(self, mock_get_charge_point, client):
        """Test successful remote stop transaction."""
        mock_cp = MagicMock()
        mock_cp.send_remote_stop_transaction = AsyncMock(
            return_value={"status": "Accepted"}
        )
        mock_get_charge_point.return_value = mock_cp

        response = client.post(
            "/chargers/CHARGER_001/stop",
            json={"transaction_id": 12345},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_cp.send_remote_stop_transaction.assert_called_once_with(
            transaction_id=12345
        )

    @patch("app.main.get_charge_point")
    def test_configure_charger_not_found(self, mock_get_charge_point, client):
        """Test configuring charger when charger not found."""
        mock_get_charge_point.return_value = None

        response = client.post(
            "/chargers/TEST_CHARGER/configure",
            json={"key": "HeartbeatInterval", "value": "300"},
        )
        assert response.status_code == 404
        assert "Charger not found" in response.json()["detail"]

    @patch("app.main.get_charge_point")
    def test_configure_charger_success(self, mock_get_charge_point, client):
        """Test successful configuration change."""
        mock_cp = MagicMock()
        mock_cp.send_change_configuration = AsyncMock(
            return_value={"status": "Accepted"}
        )
        mock_get_charge_point.return_value = mock_cp

        response = client.post(
            "/chargers/CHARGER_001/configure",
            json={"key": "HeartbeatInterval", "value": "300"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_cp.send_change_configuration.assert_called_once_with(
            key="HeartbeatInterval", value="300"
        )


class TestTransactionsEndpoint:
    """Test transactions endpoints."""

    @patch("app.main.db_manager.get_session")
    def test_get_transactions_empty(self, mock_get_session, client):
        """Test getting transactions when none exist."""
        # Mock empty result
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Mock the async context manager
        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        response = client.get("/transactions")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestMessagesEndpoint:
    """Test messages endpoints."""

    @patch("app.main.db_manager.get_session")
    def test_get_messages_empty(self, mock_get_session, client):
        """Test getting messages when none exist."""
        # Mock empty result
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Mock the async context manager
        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        response = client.get("/messages/TEST_STATION")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["messages"] == []


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        # Should return HTML content
        assert "text/html" in response.headers["content-type"]

    def test_api_info_endpoint(self, client):
        """Test API info endpoint."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
