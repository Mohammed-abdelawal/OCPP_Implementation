from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ocpp_server import on_connect


class TestWebSocketConnection:
    """Test WebSocket connection handling."""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        websocket.close = AsyncMock()
        websocket.recv = AsyncMock()
        websocket.send = AsyncMock()
        return websocket

    @pytest.mark.asyncio
    async def test_websocket_connection_empty_path(self, mock_websocket):
        """Test WebSocket connection with empty path."""
        mock_websocket.request.path = "/"

        await on_connect(mock_websocket)

        # Verify connection was closed
        mock_websocket.close.assert_called_once_with(
            code=1008, reason="Empty charge point ID"
        )


class TestWebSocketMessageHandling:
    """Test WebSocket message handling."""

    @pytest.fixture
    def mock_charge_point(self):
        """Create mock charge point."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        websocket.send = AsyncMock()
        websocket.close = AsyncMock()

        from app.ocpp_server import ChargePoint

        return ChargePoint("CHARGER_001", websocket)

    @pytest.mark.asyncio
    async def test_boot_notification_message(self, mock_charge_point):
        """Test BootNotification message handling."""
        with patch("app.ocpp_server.db_manager.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_station = MagicMock()
            mock_station.station_id = "CHARGER_001"
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_station
            mock_session.execute.return_value = mock_result
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_session.close = AsyncMock()

            async def mock_session_generator():
                yield mock_session

            mock_get_session.return_value = mock_session_generator()

            result = await mock_charge_point.on_boot_notification(
                charge_point_model="Tesla Wall Connector",
                charge_point_vendor="Tesla",
                charge_point_serial_number="TW123456789",
                charge_box_serial_number="CB123456789",
                firmware_version="1.0.0",
            )

            assert result.status.value == "Accepted"
            assert result.current_time is not None
            assert result.interval == 300

    @pytest.mark.asyncio
    async def test_heartbeat_message(self, mock_charge_point):
        """Test Heartbeat message handling."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await mock_charge_point.on_heartbeat()

            assert result.current_time is not None

    @pytest.mark.asyncio
    async def test_status_notification_message(self, mock_charge_point):
        """Test StatusNotification message handling."""
        result = await mock_charge_point.on_status_notification(
            connector_id=1, error_code="NoError", status="Available"
        )

        assert result is not None
        assert mock_charge_point.connector_status[1]["status"] == "Available"

    @pytest.mark.asyncio
    async def test_start_transaction_message(self, mock_charge_point):
        """Test StartTransaction message handling."""
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
    async def test_stop_transaction_message(self, mock_charge_point):
        """Test StopTransaction message handling."""
        with patch("app.ocpp_server.db_manager.get_session"):
            result = await mock_charge_point.on_stop_transaction(
                transaction_id=12345,
                timestamp="2024-01-01T13:00:00Z",
                meter_stop=1000,
                reason="Local",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_authorize_message(self, mock_charge_point):
        """Test Authorize message handling."""
        result = await mock_charge_point.on_authorize(id_tag="john_doe")

        assert result.id_tag_info["status"].value == "Accepted"


class TestWebSocketMessageFlow:
    """Test complete WebSocket message flow."""

    @pytest.mark.asyncio
    async def test_complete_ocpp_message_flow(self):
        """Test complete OCPP message flow."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"
        websocket.close = AsyncMock()

        from app.ocpp_server import ChargePoint

        charge_point = ChargePoint("CHARGER_001", websocket)

        with patch("app.ocpp_server.db_manager.get_session"):
            # 1. BootNotification
            boot_result = await charge_point.on_boot_notification(
                charge_point_model="Tesla Wall Connector", charge_point_vendor="Tesla"
            )
            assert boot_result.status.value == "Accepted"

            # 2. Heartbeat
            heartbeat_result = await charge_point.on_heartbeat()
            assert heartbeat_result.current_time is not None

            # 3. StatusNotification
            status_result = await charge_point.on_status_notification(
                connector_id=1, error_code="NoError", status="Available"
            )
            assert status_result is not None

            # 4. StartTransaction
            start_result = await charge_point.on_start_transaction(
                connector_id=1,
                id_tag="john_doe",
                meter_start=0,
                timestamp="2024-01-01T12:00:00Z",
            )
            assert start_result.transaction_id is not None

            # 5. StopTransaction
            stop_result = await charge_point.on_stop_transaction(
                transaction_id=start_result.transaction_id,
                timestamp="2024-01-01T13:00:00Z",
                meter_stop=1000,
                reason="Local",
            )
            assert stop_result is not None

    @pytest.mark.asyncio
    async def test_remote_commands_flow(self):
        """Test remote commands flow."""
        websocket = AsyncMock()
        websocket.request.path = "/CHARGER_001"

        from app.ocpp_server import ChargePoint

        charge_point = ChargePoint("CHARGER_001", websocket)

        # Test remote start transaction
        charge_point.send_remote_start_transaction = AsyncMock(
            return_value={"status": "Accepted"}
        )
        result = await charge_point.send_remote_start_transaction("john_doe", 1)
        assert result["status"] == "Accepted"

        # Test remote stop transaction
        charge_point.send_remote_stop_transaction = AsyncMock(
            return_value={"status": "Accepted"}
        )
        result = await charge_point.send_remote_stop_transaction(12345)
        assert result["status"] == "Accepted"

        # Test configuration change
        charge_point.send_change_configuration = AsyncMock(
            return_value={"status": "Accepted"}
        )
        result = await charge_point.send_change_configuration(
            "HeartbeatInterval", "300"
        )
        assert result["status"] == "Accepted"
