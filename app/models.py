from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """User model for OCPP implementation"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ChargingStation(Base):
    """Charging Station model for OCPP"""

    __tablename__ = "charging_stations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    is_online = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChargingSession(Base):
    """Charging Session model"""

    __tablename__ = "charging_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    station_id = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=True)  # Optional user association
    status = Column(String(20), default="pending")  # pending, active, completed, failed
    energy_delivered = Column(Integer, default=0)  # in Wh
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OCPPMessage(Base):
    """OCPP Message log"""

    __tablename__ = "ocpp_messages"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50), nullable=False)
    message_type = Column(String(20), nullable=False)
    action = Column(String(50), nullable=False)
    message_id = Column(String(100), nullable=False)
    payload = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
