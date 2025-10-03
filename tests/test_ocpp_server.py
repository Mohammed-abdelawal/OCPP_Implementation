from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ocpp_server import (
    ChargePoint,
    get_active_charge_points,
    get_charge_point,
    on_connect,
)


class TestChargePoint:
    """Test ChargePoint class functionality."""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection."""
        websocket = AsyncMock()
        websocket.recv = AsyncMock()
        websocket.send = AsyncMock()
        return websocket

    @pytest.fixture
    def charge_point(self, mock_websocket):
        """Create ChargePoint instance."""
        return ChargePoint("TEST_CHARGER_001", mock_websocket)

    def test_charge_point_initialization(self, charge_point):
        """Test ChargePoint initialization."""
        assert charge_point.station_id == "TEST_CHARGER_001"
        assert charge_point.is_online is True
        assert isinstance(charge_point.last_heartbeat, datetime)

    @pytest.mark.asyncio
    @patch("app.ocpp_server.db_manager.get_session")
    async def test_on_boot_notification(self, mock_get_session, charge_point):
        """Test BootNotification handler."""
        # Mock database session
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        # Test BootNotification
        result = await charge_point.on_boot_notification(
            charge_point_model="Test Model", charge_point_vendor="Test Vendor"
        )

        assert result.current_time is not None
        assert result.interval == 300
        assert result.status.value == "Accepted"

    @pytest.mark.asyncio
    async def test_on_heartbeat(self, charge_point):
        """Test Heartbeat handler."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await charge_point.on_heartbeat()

            assert result.current_time is not None

    @pytest.mark.asyncio
    async def test_on_status_notification(self, charge_point):
        """Test StatusNotification handler."""
        result = await charge_point.on_status_notification(
            connector_id=1, error_code="NoError", status="Available"
        )

        assert result is not None
        assert charge_point.connector_status[1]["status"] == "Available"

    @pytest.mark.asyncio
    async def test_on_start_transaction(self, charge_point):
        """Test StartTransaction handler."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await charge_point.on_start_transaction(
                connector_id=1,
                id_tag="USER123",
                meter_start=0,
                timestamp="2024-01-01T00:00:00Z",
            )

            assert result.transaction_id is not None
            assert result.id_tag_info["status"].value == "Accepted"

    @pytest.mark.asyncio
    async def test_on_stop_transaction(self, charge_point):
        """Test StopTransaction handler."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await charge_point.on_stop_transaction(
                transaction_id=12345, timestamp="2024-01-01T00:00:00Z", meter_stop=1000
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_on_authorize(self, charge_point):
        """Test Authorize handler."""
        result = await charge_point.on_authorize(id_tag="USER123")

        assert result.id_tag_info["status"].value == "Accepted"

    @pytest.mark.asyncio
    async def test_send_remote_start_transaction(self, charge_point):
        """Test sending remote start transaction."""
        charge_point.call = AsyncMock(return_value={"status": "Accepted"})

        result = await charge_point.send_remote_start_transaction("USER123", 1)

        assert result is not None
        charge_point.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_remote_stop_transaction(self, charge_point):
        """Test sending remote stop transaction."""
        charge_point.call = AsyncMock(return_value={"status": "Accepted"})

        result = await charge_point.send_remote_stop_transaction(12345)

        assert result is not None
        charge_point.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_change_configuration(self, charge_point):
        """Test sending configuration change."""
        charge_point.call = AsyncMock(return_value={"status": "Accepted"})

        result = await charge_point.send_change_configuration(
            "HeartbeatInterval", "300"
        )

        assert result is not None
        charge_point.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_disconnection(self, charge_point):
        """Test handling disconnection."""
        with patch("app.ocpp_server.db_manager.get_session"):
            await charge_point._handle_disconnection()  # noqa: SLF001

            assert charge_point.is_online is False


class TestOCPPServer:
    """Test OCPP server functionality."""

    def test_get_active_charge_points(self):
        """Test getting active charge points."""
        active_points = get_active_charge_points()
        assert isinstance(active_points, dict)

    @patch("app.ocpp_server.active_charge_points")
    def test_get_charge_point(self, mock_active_points):
        """Test getting specific charge point."""

        mock_cp = MagicMock()
        mock_active_points.get.return_value = mock_cp

        result = get_charge_point("TEST_CHARGER")
        assert result == mock_cp
        mock_active_points.get.assert_called_once_with("TEST_CHARGER")

    @pytest.mark.asyncio
    @patch("app.ocpp_server.db_manager.get_session")
    @patch("app.ocpp_server.ChargePoint")
    async def test_on_connect_success(self, mock_charge_point_class, mock_get_session):
        """Test successful on_connect function."""
        mock_websocket = AsyncMock()
        mock_websocket.request.path = "/CHARGER_001"
        mock_charge_point = AsyncMock()
        mock_charge_point_class.return_value = mock_charge_point

        # Mock database session with existing station
        mock_session = AsyncMock()
        mock_station = MagicMock()
        mock_station.station_id = "CHARGER_001"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_station
        mock_get_session.return_value.__aenter__.return_value = mock_session

        await on_connect(mock_websocket)

        mock_charge_point_class.assert_called_once_with("CHARGER_001", mock_websocket)
        mock_charge_point.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_connect_empty_charge_point_id(self):
        """Test on_connect with empty charge point ID."""
        mock_websocket = AsyncMock()
        mock_websocket.request.path = "/"
        mock_websocket.close = AsyncMock()

        await on_connect(mock_websocket)

        mock_websocket.close.assert_called_once_with(
            code=1008, reason="Empty charge point ID"
        )


class TestOCPPMessageLogging:
    """Test OCPP message logging functionality."""

    @pytest.mark.asyncio
    @patch("app.ocpp_server.db_manager.get_session")
    async def test_log_ocpp_message(self, mock_get_session):
        """Test logging OCPP messages."""
        charge_point = ChargePoint("TEST_CHARGER", AsyncMock())

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock the async context manager properly
        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        await charge_point._log_ocpp_message(  # noqa: SLF001
            "TestMessage", "TestAction", {"test": "data"}
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
class TestAsyncOCPPFunctionality:
    """Test async OCPP functionality."""

    @patch("app.ocpp_server.db_manager.get_session")
    async def test_charge_point_lifecycle(self, mock_get_session):
        """Test complete charge point lifecycle."""
        mock_websocket = AsyncMock()
        charge_point = ChargePoint("TEST_CHARGER", mock_websocket)

        # Mock database session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        # Mock the async context manager properly
        async def mock_session_generator():
            yield mock_session

        mock_get_session.return_value = mock_session_generator()

        # Test initialization
        assert charge_point.station_id == "TEST_CHARGER"
        assert charge_point.is_online is True

        # Test disconnection
        await charge_point._handle_disconnection()  # noqa: SLF001
        assert charge_point.is_online is False

    async def test_connector_status_tracking(self):
        """Test connector status tracking."""
        mock_websocket = AsyncMock()
        charge_point = ChargePoint("TEST_CHARGER", mock_websocket)

        # Test status notification
        await charge_point.on_status_notification(
            connector_id=1, error_code="NoError", status="Available"
        )

        assert 1 in charge_point.connector_status
        assert charge_point.connector_status[1]["status"] == "Available"
        assert charge_point.connector_status[1]["error_code"] == "NoError"
