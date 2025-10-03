import logging
from typing import Optional

from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for API
class ChargerResponse(BaseModel):
    id: str
    name: str
    location: Optional[str]
    is_online: bool
    last_heartbeat: Optional[str]
    created_at: str


class TransactionResponse(BaseModel):
    id: int
    session_id: str
    station_id: str
    status: str
    energy_delivered: int
    start_time: Optional[str]
    end_time: Optional[str]
    created_at: str


class RemoteStartRequest(BaseModel):
    id_tag: str
    connector_id: int = 1


class RemoteStopRequest(BaseModel):
    transaction_id: int


class ConfigurationRequest(BaseModel):
    key: str
    value: str
