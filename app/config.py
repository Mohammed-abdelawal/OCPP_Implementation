import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(".") / ".env"
if not load_dotenv(dotenv_path=env_path):
    msg = "No .env file found or Issue loading .env file"
    raise ValueError(msg)


class Settings:
    PROJECT_NAME: str = "Nexus Analyica EV Charging Station"
    PROJECT_VERSION: str = (
        "1.0.0"  # maybe need to use version and support multiple versions
    )

    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tdd")
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"


settings = Settings()
