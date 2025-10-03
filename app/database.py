import logging
import os
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

# Base class for models
Base = declarative_base()


class DatabaseManager:
    """
    Database manager for the application
    ref: https://praciano.com.br/fastapi-and-async-sqlalchemy-20-with-pytest-done-right.html
    """

    def __init__(self):
        self.database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://evuser:evpass@db:5432/evcs"
        )
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            self.engine = create_async_engine(self.database_url)

            self.session_factory = async_sessionmaker(
                bind=self.engine, expire_on_commit=False
            )
        except Exception as e:
            logging.exception("Failed to initialize database")
            raise e from e

    async def health_check(self) -> dict:
        """Simple health check"""
        try:
            if not self.engine:
                return {"status": "error", "message": "Database not initialized"}

            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                if row and row[0] == 1:
                    return {
                        "status": "healthy",
                        "message": "Database connection successful",
                    }
                return {"status": "error", "message": "Database query failed"}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Database connection failed: {e!s}",
            }

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session for ORM operations"""
        if not self.session_factory:
            raise Exception("Database not initialized")

        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None

    async def create_all(self, engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self, engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


db_manager = DatabaseManager()
