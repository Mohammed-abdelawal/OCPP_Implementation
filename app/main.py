from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_manager
from app.ocpp_server import (
    get_active_charge_points,
    get_charge_point,
    start_ocpp_server,
)
from app.pydantic_models import (
    ChargerResponse,
    ConfigurationRequest,
    RemoteStartRequest,
    RemoteStopRequest,
    TransactionResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to store OCPP server
ocpp_server = None


async def get_db_session() -> AsyncSession:
    """FastAPI dependency for database sessions"""
    async for session in db_manager.get_session():
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ocpp_server

    try:
        await db_manager.initialize()
        await db_manager.create_all(db_manager.engine)
        logger.info("Database initialized")

        ocpp_server = await start_ocpp_server("0.0.0.0", 9000)  # nosec
        logger.info("OCPP server started")

    except Exception as e:
        logger.exception(f"Failed to startup the Application: {e}")
        raise

    yield

    # Shutdown
    if ocpp_server:
        ocpp_server.close()
        await ocpp_server.wait_closed()
    await db_manager.close()


app = FastAPI(
    title="OCPP Module Nexus Analyica",
    description="Electric Vehicle Charger Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# Handle static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health() -> dict:
    """Health check endpoint for app and ocpp server"""
    health_status = {"status": "healthy", "services": {}}

    db_health = await db_manager.health_check()
    health_status["services"]["database"] = db_health

    ocpp_health = {"status": "healthy" if ocpp_server else "unhealthy"}
    health_status["services"]["ocpp_server"] = ocpp_health

    if db_health["status"] != "healthy" or ocpp_health["status"] != "healthy":
        health_status["status"] = "unhealthy"

    return health_status


@app.get("/chargers", response_model=list[ChargerResponse])
async def get_chargers(
    session: AsyncSession = Depends(get_db_session),
) -> list[ChargerResponse]:
    """Get all charging stations with their status"""
    from sqlalchemy import select

    from app.models import ChargingStation

    result = await session.execute(select(ChargingStation))
    stations = result.scalars().all()

    return [
        ChargerResponse(
            id=station.station_id,
            name=station.name,
            location=station.location,
            is_online=station.is_online,
            last_heartbeat=station.last_heartbeat.isoformat()
            if station.last_heartbeat
            else None,
            created_at=station.created_at.isoformat(),
        )
        for station in stations
    ]


@app.get("/chargers/active")
async def get_active_chargers() -> dict:
    """Get currently active (connected) chargers"""
    active_chargers = get_active_charge_points()

    return {
        "active_chargers": list(active_chargers.keys()),
        "count": len(active_chargers),
        "chargers": [
            {
                "station_id": cp.station_id,
                "is_online": cp.is_online,
                "last_heartbeat": cp.last_heartbeat.isoformat(),
                "connector_status": cp.connector_status,
            }
            for cp in active_chargers.values()
        ],
    }


@app.post("/chargers/{charger_id}/start")
async def start_charging(charger_id: str, request: RemoteStartRequest) -> dict:
    """Send remote start transaction to a charger"""
    charge_point = get_charge_point(charger_id)

    if not charge_point:
        raise HTTPException(
            status_code=404, detail="Charger not found or not connected"
        )

    try:
        response = await charge_point.send_remote_start_transaction(
            id_tag=request.id_tag, connector_id=request.connector_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to send remote start: {e!s}"
        ) from e
    else:
        return {
            "status": "success",
            "message": "Remote start command sent",
            "response": response,
        }


@app.post("/chargers/{charger_id}/stop")
async def stop_charging(charger_id: str, request: RemoteStopRequest) -> dict:
    """Send remote stop transaction to a charger"""
    charge_point = get_charge_point(charger_id)

    if not charge_point:
        raise HTTPException(
            status_code=404, detail="Charger not found or not connected"
        )

    try:
        response = await charge_point.send_remote_stop_transaction(
            transaction_id=request.transaction_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to send remote stop: {e!s}"
        ) from e
    else:
        return {
            "status": "success",
            "message": "Remote stop command sent",
            "response": response,
        }


@app.post("/chargers/{charger_id}/configure")
async def configure_charger(charger_id: str, request: ConfigurationRequest) -> dict:
    """Send configuration change to a charger"""
    charge_point = get_charge_point(charger_id)

    if not charge_point:
        raise HTTPException(
            status_code=404, detail="Charger not found or not connected"
        )

    try:
        response = await charge_point.send_change_configuration(
            key=request.key, value=request.value
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to send configuration: {e!s}"
        ) from e
    else:
        return {
            "status": "success",
            "message": "Configuration change sent",
            "response": response,
        }


@app.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    session: AsyncSession = Depends(get_db_session),
) -> list[TransactionResponse]:
    """Get all charging transactions"""
    from sqlalchemy import select

    from app.models import ChargingSession

    result = await session.execute(select(ChargingSession))
    transactions = result.scalars().all()

    return [
        TransactionResponse(
            id=tx.id,
            session_id=tx.session_id,
            station_id=tx.station_id,
            status=tx.status,
            energy_delivered=tx.energy_delivered,
            start_time=tx.start_time.isoformat() if tx.start_time else None,
            end_time=tx.end_time.isoformat() if tx.end_time else None,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]


@app.get("/transactions/{station_id}")
async def get_station_transactions(
    station_id: str, session: AsyncSession = Depends(get_db_session)
) -> list[TransactionResponse]:
    """Get transactions for a specific station"""
    from sqlalchemy import select

    from app.models import ChargingSession

    result = await session.execute(
        select(ChargingSession).where(ChargingSession.station_id == station_id)
    )
    transactions = result.scalars().all()

    return [
        TransactionResponse(
            id=tx.id,
            session_id=tx.session_id,
            station_id=tx.station_id,
            status=tx.status,
            energy_delivered=tx.energy_delivered,
            start_time=tx.start_time.isoformat() if tx.start_time else None,
            end_time=tx.end_time.isoformat() if tx.end_time else None,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]


@app.get("/messages/{station_id}")
async def get_station_messages(
    station_id: str, session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Get Websocket messages for a specific station"""
    from sqlalchemy import select

    from app.models import OCPPMessage

    result = await session.execute(
        select(OCPPMessage)
        .where(OCPPMessage.station_id == station_id)
        .order_by(OCPPMessage.timestamp.desc())
        .limit(100)
    )
    messages = result.scalars().all()

    return {
        "station_id": station_id,
        "messages": [
            {
                "id": msg.id,
                "message_type": msg.message_type,
                "action": msg.action,
                "message_id": msg.message_id,
                "payload": msg.payload,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ],
        "count": len(messages),
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend page"""
    with open("app/static/index.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "message": "OCPP Backend Module for Electric Vehicle Chargers",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "chargers": "/chargers",
            "active_chargers": "/chargers/active",
            "transactions": "/transactions",
            "docs": "/docs",
        },
    }
