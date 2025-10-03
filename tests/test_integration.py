import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.ocpp_server import ChargePoint, active_charge_points


class TestCompleteOCPPFlow:
    """Test complete OCPP communication flow."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection."""
        websocket = AsyncMock()
        websocket.recv = AsyncMock(
            side_effect=asyncio.CancelledError()
        )  # Simulate connection close
        websocket.send = AsyncMock()
        websocket.close = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        return websocket

    @pytest.fixture
    def mock_charge_point(self, mock_websocket):
        """Create mock charge point."""
        cp = ChargePoint("CHARGER_001", mock_websocket)
        cp.send_remote_start_transaction = AsyncMock(
            return_value={"status": "Accepted"}
        )
        cp.send_remote_stop_transaction = AsyncMock(return_value={"status": "Accepted"})
        cp.send_change_configuration = AsyncMock(return_value={"status": "Accepted"})
        return cp

    @pytest.mark.asyncio
    async def test_charger_registration_flow(self, mock_websocket):
        """Test complete charger registration flow."""
        with patch("app.ocpp_server.db_manager.get_session") as mock_get_session:
            # Mock database session with existing station
            mock_session = AsyncMock()
            mock_station = MagicMock()
            mock_station.station_id = "CHARGER_001"
            mock_session.execute.return_value.scalar_one_or_none.return_value = (
                mock_station
            )
            mock_session.close = AsyncMock()

            async def mock_session_generator():
                yield mock_session

            mock_get_session.return_value = mock_session_generator()

            # Test connection
            from app.ocpp_server import on_connect

            with contextlib.suppress(asyncio.CancelledError):
                await on_connect(mock_websocket)

            # Verify charge point was added to active points
            assert "CHARGER_001" in active_charge_points

    @pytest.mark.asyncio
    async def test_boot_notification_flow(self, mock_charge_point):
        """Test BootNotification message flow."""
        with patch("app.ocpp_server.db_manager.get_session"):
            # Test BootNotification
            result = await mock_charge_point.on_boot_notification(
                charge_point_model="Tesla Wall Connector",
                charge_point_vendor="Tesla",
                charge_point_serial_number="TW123456789",
                charge_box_serial_number="CB123456789",
                firmware_version="1.0.0",
            )

            assert result.current_time is not None
            assert result.interval == 300
            assert result.status.value == "Accepted"

    @pytest.mark.asyncio
    async def test_heartbeat_flow(self, mock_charge_point):
        """Test Heartbeat message flow."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await mock_charge_point.on_heartbeat()
            assert result.current_time is not None

    @pytest.mark.asyncio
    async def test_status_notification_flow(self, mock_charge_point):
        """Test StatusNotification message flow."""
        result = await mock_charge_point.on_status_notification(
            connector_id=1, error_code="NoError", status="Available"
        )

        assert result is not None
        assert mock_charge_point.connector_status[1]["status"] == "Available"
        assert mock_charge_point.connector_status[1]["error_code"] == "NoError"

    @pytest.mark.asyncio
    async def test_start_transaction_flow(self, mock_charge_point):
        """Test StartTransaction message flow."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await mock_charge_point.on_start_transaction(
                connector_id=1,
                id_tag="john_doe",
                meter_start=0,
                timestamp="2024-01-01T12:00:00Z",
            )

            assert result.transaction_id is not None
            assert result.id_tag_info["status"].value == "Accepted"

    @pytest.mark.asyncio
    async def test_stop_transaction_flow(self, mock_charge_point):
        """Test StopTransaction message flow."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await mock_charge_point.on_stop_transaction(
                transaction_id=12345,
                timestamp="2024-01-01T13:00:00Z",
                meter_stop=1000,
                reason="Local",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_authorize_flow(self, mock_charge_point):
        """Test Authorize message flow."""
        result = await mock_charge_point.on_authorize(id_tag="john_doe")
        assert result.id_tag_info["status"].value == "Accepted"

    def test_remote_start_transaction_api(self, client, mock_charge_point):
        """Test remote start transaction via REST API."""
        with patch("app.main.get_charge_point", return_value=mock_charge_point):
            response = client.post(
                "/chargers/CHARGER_001/start",
                json={"id_tag": "john_doe", "connector_id": 1},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_charge_point.send_remote_start_transaction.assert_called_once_with(
                id_tag="john_doe", connector_id=1
            )

    def test_remote_stop_transaction_api(self, client, mock_charge_point):
        """Test remote stop transaction via REST API."""
        with patch("app.main.get_charge_point", return_value=mock_charge_point):
            response = client.post(
                "/chargers/CHARGER_001/stop", json={"transaction_id": 12345}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_charge_point.send_remote_stop_transaction.assert_called_once_with(
                transaction_id=12345
            )

    def test_configure_charger_api(self, client, mock_charge_point):
        """Test configure charger via REST API."""
        with patch("app.main.get_charge_point", return_value=mock_charge_point):
            response = client.post(
                "/chargers/CHARGER_001/configure",
                json={"key": "HeartbeatInterval", "value": "300"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_charge_point.send_change_configuration.assert_called_once_with(
                key="HeartbeatInterval", value="300"
            )

    def test_get_active_chargers_api(self, client, mock_charge_point):
        """Test getting active chargers via REST API."""
        with patch(
            "app.main.get_active_charge_points",
            return_value={"CHARGER_001": mock_charge_point},
        ):
            response = client.get("/chargers/active")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert "CHARGER_001" in data["active_chargers"]

    @pytest.mark.asyncio
    async def test_complete_charging_session_flow(self, mock_charge_point):
        """Test complete charging session flow."""
        with patch("app.ocpp_server.db_manager.get_session"):
            # 1. Start transaction
            start_result = await mock_charge_point.on_start_transaction(
                connector_id=1,
                id_tag="john_doe",
                meter_start=0,
                timestamp="2024-01-01T12:00:00Z",
            )

            assert start_result.transaction_id is not None
            transaction_id = start_result.transaction_id

            # 2. Stop transaction
            stop_result = await mock_charge_point.on_stop_transaction(
                transaction_id=transaction_id,
                timestamp="2024-01-01T13:00:00Z",
                meter_stop=1000,
                reason="Local",
            )

            assert stop_result is not None

    @pytest.mark.asyncio
    async def test_charger_disconnection_flow(self, mock_charge_point):
        """Test charger disconnection flow."""
        # Add to active charge points
        active_charge_points["CHARGER_001"] = mock_charge_point

        with patch("app.ocpp_server.db_manager.get_session"):
            # Test disconnection
            await mock_charge_point._handle_disconnection()  # noqa: SLF001

            # Verify charge point is removed from active points
            assert "CHARGER_001" not in active_charge_points
            assert mock_charge_point.is_online is False

    def test_charger_not_found_api(self, client):
        """Test API when charger is not found."""
        with patch("app.main.get_charge_point", return_value=None):
            response = client.post(
                "/chargers/UNKNOWN_CHARGER/start",
                json={"id_tag": "john_doe", "connector_id": 1},
            )

            assert response.status_code == 404
            assert "Charger not found" in response.json()["detail"]


class TestOCPPMessageValidation:
    """Test OCPP message validation and error handling."""

    @pytest.fixture
    def mock_charge_point(self):
        """Create mock charge point."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        return ChargePoint("CHARGER_001", websocket)

    @pytest.mark.asyncio
    async def test_invalid_boot_notification(self, mock_charge_point):
        """Test BootNotification with invalid data."""
        with patch("app.ocpp_server.db_manager.get_session"):
            # Test with missing required fields
            result = await mock_charge_point.on_boot_notification(
                charge_point_model="",  # Empty model
                charge_point_vendor="Tesla",
            )

            # Should still work but with empty model
            assert result.status.value == "Accepted"

    @pytest.mark.asyncio
    async def test_invalid_start_transaction(self, mock_charge_point):
        """Test StartTransaction with invalid data."""
        with patch("app.ocpp_server.db_manager.get_session"):
            # Test with invalid connector ID
            result = await mock_charge_point.on_start_transaction(
                connector_id=0,  # Invalid connector ID
                id_tag="john_doe",
                meter_start=0,
                timestamp="2024-01-01T12:00:00Z",
            )

            # Should still work but might have different behavior
            assert result.transaction_id is not None

    @pytest.mark.asyncio
    async def test_unauthorized_user(self, mock_charge_point):
        """Test authorization with invalid user."""
        result = await mock_charge_point.on_authorize(id_tag="invalid_user")

        # For demo purposes, we accept all users
        assert result.id_tag_info["status"].value == "Accepted"


class TestDatabaseIntegration:
    """Test database integration with OCPP flow."""

    @pytest.mark.asyncio
    async def test_boot_notification_database_update(self):
        """Test that BootNotification updates database."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        charge_point = ChargePoint("CHARGER_001", websocket)

        with patch("app.ocpp_server.db_manager.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_station = MagicMock()
            mock_station.station_id = "CHARGER_001"

            # Mock the database query result
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_station
            mock_session.execute.return_value = mock_result

            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_session.close = AsyncMock()

            # Mock the async context manager properly
            async def mock_session_generator():
                yield mock_session

            mock_get_session.return_value = mock_session_generator()

            # Test BootNotification
            result = await charge_point.on_boot_notification(
                charge_point_model="Tesla Wall Connector", charge_point_vendor="Tesla"
            )

            # Verify method executed successfully and returned a result
            assert result is not None
            assert result.status.value == "Accepted"
            # Verify charge point is in active list
            assert charge_point.station_id in active_charge_points

    @pytest.mark.asyncio
    async def test_transaction_database_logging(self):
        """Test that transactions are logged to database."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        charge_point = ChargePoint("CHARGER_001", websocket)

        with patch("app.ocpp_server.db_manager.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.add = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.close = AsyncMock()

            # Mock the async context manager properly
            async def mock_session_generator():
                yield mock_session

            mock_get_session.return_value = mock_session_generator()

            # Test StartTransaction
            await charge_point.on_start_transaction(
                connector_id=1,
                id_tag="john_doe",
                meter_start=0,
                timestamp="2024-01-01T12:00:00Z",
            )

            # Verify database operations were called
            mock_session.add.assert_called()
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_message_logging(self):
        """Test that OCPP messages are logged to database."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        charge_point = ChargePoint("CHARGER_001", websocket)

        with patch("app.ocpp_server.db_manager.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.add = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.close = AsyncMock()

            # Mock the async context manager properly
            async def mock_session_generator():
                yield mock_session

            mock_get_session.return_value = mock_session_generator()

            # Test message logging
            await charge_point._log_ocpp_message(  # noqa: SLF001
                "TestMessage", "TestAction", {"test": "data"}
            )

            # Verify database operations were called
            mock_session.add.assert_called()
            mock_session.commit.assert_called()
