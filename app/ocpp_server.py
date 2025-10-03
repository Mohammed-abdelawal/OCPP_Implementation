from datetime import UTC, datetime
import json
import logging
from typing import Dict, Optional

from ocpp.routing import on
from ocpp.v16 import ChargePoint as OCPPChargePoint
from ocpp.v16 import call, call_result
from ocpp.v16.enums import (
    Action,
    AuthorizationStatus,
    RegistrationStatus,
)
import websockets
from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from app.database import db_manager
from app.models import ChargingSession, ChargingStation, OCPPMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global dictionary to store active charge points
active_charge_points: Dict[str, "ChargePoint"] = {}


class ChargePoint(OCPPChargePoint):
    """Extended OCPP ChargePoint with custom handlers"""

    def __init__(self, charge_point_id: str, websocket: WebSocketServerProtocol):
        super().__init__(charge_point_id, websocket)
        self.station_id = charge_point_id
        self.is_online = True
        self.last_heartbeat = datetime.now(UTC)
        self.connector_status = {}

    async def start(self):
        """Start the charge point connection"""
        try:
            await super().start()
        except ConnectionClosed:
            logger.info(f"Charge point {self.station_id} disconnected")
            await self._handle_disconnection()
        except Exception as e:
            logger.error(f"Error in charge point {self.station_id}: {e}")
            await self._handle_disconnection()

    async def _handle_disconnection(self):
        """Handle charge point disconnection"""
        self.is_online = False
        if self.station_id in active_charge_points:
            del active_charge_points[self.station_id]

        # Update database
        async for session in db_manager.get_session():
            try:
                from sqlalchemy import select, update

                result = await session.execute(
                    select(ChargingStation).where(
                        ChargingStation.station_id == self.station_id
                    )
                )
                station = result.scalar_one_or_none()
                if station:
                    await session.execute(
                        update(ChargingStation)
                        .where(ChargingStation.station_id == self.station_id)
                        .values(is_online=False)
                    )
                    await session.commit()
            except Exception as e:
                logger.error(f"Error updating station status: {e}")
            finally:
                await session.close()

    async def send_remote_start_transaction(self, id_tag: str, connector_id: int = 1):
        """Send remote start transaction to charge point"""
        try:
            request = call.RemoteStartTransactionPayload(
                id_tag=id_tag, connector_id=connector_id
            )
            response = await self.call(request)
            logger.info(f"Remote start transaction response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error sending remote start transaction: {e}")
            return None

    async def send_remote_stop_transaction(self, transaction_id: int):
        """Send remote stop transaction to charge point"""
        try:
            request = call.RemoteStopTransactionPayload(transaction_id=transaction_id)
            response = await self.call(request)
            logger.info(f"Remote stop transaction response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error sending remote stop transaction: {e}")
            return None

    async def send_change_configuration(self, key: str, value: str):
        """Send configuration change to charge point"""
        try:
            request = call.ChangeConfigurationPayload(key=key, value=value)
            response = await self.call(request)
            logger.info(f"Change configuration response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error sending change configuration: {e}")
            return None

    @on(Action.BootNotification)
    async def on_boot_notification(
        self, charge_point_model: str, charge_point_vendor: str, **kwargs
    ):
        """Handle BootNotification from charge point"""
        logger.info(
            f"Boot notification from {self.station_id}: {charge_point_model} by {charge_point_vendor}"
        )

        # Log the message
        await self._log_ocpp_message("BootNotification", "BootNotification", kwargs)

        # Update or create charging station in database
        async for session in db_manager.get_session():
            try:
                from sqlalchemy import select

                result = await session.execute(
                    select(ChargingStation).where(
                        ChargingStation.station_id == self.station_id
                    )
                )
                station = result.scalar_one_or_none()

                if station:
                    # Update existing station
                    station.is_online = True
                    station.last_heartbeat = datetime.now(UTC)
                else:
                    # Create new station
                    station = ChargingStation(
                        station_id=self.station_id,
                        name=f"{charge_point_vendor} {charge_point_model}",
                        location="Unknown",
                        is_online=True,
                        last_heartbeat=datetime.now(UTC),
                    )
                    session.add(station)

                await session.commit()
                await session.refresh(station)

            except Exception as e:
                logger.error(f"Error handling boot notification: {e}")
            finally:
                await session.close()

        # Add to active charge points
        active_charge_points[self.station_id] = self

        return call_result.BootNotificationPayload(
            current_time=datetime.now(UTC).isoformat() + "Z",
            interval=300,  # 5 minutes heartbeat interval
            status=RegistrationStatus.accepted,
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self, **kwargs):
        """Handle Heartbeat from charge point"""
        self.last_heartbeat = datetime.now(UTC)
        logger.debug(f"Heartbeat from {self.station_id}")

        # Log the message
        await self._log_ocpp_message("Heartbeat", "Heartbeat", kwargs)

        # Update heartbeat in database
        async for session in db_manager.get_session():
            try:
                from sqlalchemy import update

                await session.execute(
                    update(ChargingStation)
                    .where(ChargingStation.station_id == self.station_id)
                    .values(last_heartbeat=datetime.now(UTC))
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Error updating heartbeat: {e}")
            finally:
                await session.close()

        return call_result.HeartbeatPayload(
            current_time=datetime.now(UTC).isoformat() + "Z"
        )

    @on(Action.StatusNotification)
    async def on_status_notification(
        self, connector_id: int, error_code: str, status: str, **kwargs
    ):
        """Handle StatusNotification from charge point"""
        logger.info(
            f"Status notification from {self.station_id}: Connector {connector_id} - {status}"
        )

        # Update connector status
        self.connector_status[connector_id] = {
            "status": status,
            "error_code": error_code,
            "timestamp": datetime.now(UTC),
        }

        # Log the message
        await self._log_ocpp_message("StatusNotification", "StatusNotification", kwargs)

        return call_result.StatusNotificationPayload()

    @on(Action.StartTransaction)
    async def on_start_transaction(
        self, connector_id: int, id_tag: str, meter_start: int, timestamp: str, **kwargs
    ):
        """Handle StartTransaction from charge point"""
        logger.info(
            f"Start transaction from {self.station_id}: Connector {connector_id}, ID {id_tag}"
        )

        # Log the message
        await self._log_ocpp_message("StartTransaction", "StartTransaction", kwargs)

        # Create charging session
        session_id = (
            f"{self.station_id}_{connector_id}_{int(datetime.now(UTC).timestamp())}"
        )

        async for session in db_manager.get_session():
            try:
                charging_session = ChargingSession(
                    session_id=session_id,
                    station_id=self.station_id,
                    status="active",
                    start_time=datetime.now(UTC),
                )
                session.add(charging_session)
                await session.commit()
                await session.refresh(charging_session)

                logger.info(f"Created charging session: {session_id}")

            except Exception as e:
                logger.error(f"Error creating charging session: {e}")
            finally:
                await session.close()

        return call_result.StartTransactionPayload(
            transaction_id=int(datetime.now(UTC).timestamp()),
            id_tag_info={"status": AuthorizationStatus.accepted},
        )

    @on(Action.StopTransaction)
    async def on_stop_transaction(
        self, transaction_id: int, timestamp: str, meter_stop: int, **kwargs
    ):
        """Handle StopTransaction from charge point"""
        logger.info(
            f"Stop transaction from {self.station_id}: Transaction {transaction_id}"
        )

        # Log the message
        await self._log_ocpp_message("StopTransaction", "StopTransaction", kwargs)

        # Update charging session
        async for session in db_manager.get_session():
            try:
                from sqlalchemy import update

                await session.execute(
                    update(ChargingSession)
                    .where(ChargingSession.session_id.like(f"%{self.station_id}%"))
                    .values(
                        status="completed",
                        end_time=datetime.now(UTC),
                        energy_delivered=meter_stop,
                    )
                )
                await session.commit()

            except Exception as e:
                logger.error(f"Error updating charging session: {e}")
            finally:
                await session.close()

        return call_result.StopTransactionPayload()

    @on(Action.Authorize)
    async def on_authorize(self, id_tag: str, **kwargs):
        """Handle Authorize from charge point"""
        logger.info(f"Authorize request from {self.station_id}: ID {id_tag}")

        # Log the message
        await self._log_ocpp_message("Authorize", "Authorize", kwargs)

        return call_result.AuthorizePayload(
            id_tag_info={"status": AuthorizationStatus.accepted}
        )

    async def _log_ocpp_message(self, message_type: str, action: str, payload: dict):
        """Log OCPP message to database"""
        try:
            async for session in db_manager.get_session():
                try:
                    ocpp_message = OCPPMessage(
                        station_id=self.station_id,
                        message_type=message_type,
                        action=action,
                        message_id=str(int(datetime.now(UTC).timestamp())),
                        payload=json.dumps(payload),
                    )
                    session.add(ocpp_message)
                    await session.commit()
                except Exception as e:
                    logger.error(f"Error logging OCPP message: {e}")
                finally:
                    await session.close()
        except Exception as e:
            logger.error(f"Error in message logging: {e}")


async def on_connect(websocket: WebSocketServerProtocol):
    """Handle new WebSocket connection"""
    charge_point_id = websocket.request.path.strip("/")
    logger.info(f"New connection from charge point: {charge_point_id}")

    if not charge_point_id:
        logger.error("Empty charge point ID - rejecting connection")
        await websocket.close(code=1008, reason="Empty charge point ID")
        return

    # Check if charger exists in database
    async for session in db_manager.get_session():
        try:
            from sqlalchemy import select

            result = await session.execute(
                select(ChargingStation).where(
                    ChargingStation.station_id == charge_point_id
                )
            )
            station = result.scalar_one_or_none()

            if not station:
                logger.error(
                    f"Charge point {charge_point_id} not found in database - rejecting connection"
                )
                await websocket.close(code=1008, reason="Charge point not registered")
                return

            logger.info(
                f"Charge point {charge_point_id} validated - allowing connection"
            )

        except Exception as e:
            logger.error(f"Error validating charge point {charge_point_id}: {e}")
            await websocket.close(code=1011, reason="Database error")
            return
        finally:
            await session.close()

    try:
        # Create charge point instance
        cp = ChargePoint(charge_point_id, websocket)

        # Add to active charge points
        active_charge_points[charge_point_id] = cp

        # Start the charge point
        await cp.start()

    except Exception as e:
        logger.error(f"Error in charge point {charge_point_id}: {e}")
        logger.exception("Full traceback:")
        active_charge_points.pop(charge_point_id, None)

        # Try to close the websocket gracefully
        try:
            await websocket.close()
        except Exception as e:
            logger.exception("Error closing websocket: %s", str(e))


async def start_ocpp_server(host: str = "0.0.0.0", port: int = 9000):  # nosec
    """Start the OCPP WebSocket server"""
    logger.info(f"Starting OCPP server on {host}:{port}")

    async def handler(websocket):
        # Extract path from websocket request
        # In websockets 15.0.1, the path is available in the request
        logger.info(f"WebSocket path: {websocket.request.path}")

        await on_connect(websocket)

    server = await websockets.serve(handler, host, port)

    logger.info(f"OCPP server started on {host}:{port}")
    return server


def get_active_charge_points() -> Dict[str, ChargePoint]:
    """Get dictionary of active charge points"""
    return active_charge_points.copy()


def get_charge_point(station_id: str) -> Optional[ChargePoint]:
    """Get specific charge point by station ID"""
    return active_charge_points.get(station_id)
