#!/usr/bin/env python3
"""
Data Truncation Script for OCPP Backend Module
Clears all data from charging stations, users, sessions, and messages
"""

import asyncio
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import db_manager
from app.models import ChargingSession, ChargingStation, OCPPMessage, User


async def truncate_data():
    """Truncate all data from the database"""

    print("🗑️  Starting data truncation...")

    # Initialize database connection
    await db_manager.initialize()

    async for session in db_manager.get_session():
        try:
            # Get counts before deletion
            from sqlalchemy import func, select

            # Count existing records
            station_count = await session.execute(
                select(func.count(ChargingStation.id))
            )
            user_count = await session.execute(select(func.count(User.id)))
            session_count = await session.execute(
                select(func.count(ChargingSession.id))
            )
            message_count = await session.execute(select(func.count(OCPPMessage.id)))

            stations = station_count.scalar()
            users = user_count.scalar()
            sessions = session_count.scalar()
            messages = message_count.scalar()

            print("📊 That's will delete data:")
            print(f"   Charging Stations: {stations}")
            print(f"   Users: {users}")
            print(f"   Charging Sessions: {sessions}")
            print(f"   OCPP Messages: {messages}")

            if stations == 0 and users == 0 and sessions == 0 and messages == 0:
                print("Database is already empty")
                return

            # Delete in reverse dependency order
            print("\n🗑️  Deleting data...")

            # Delete OCPP messages first
            if messages > 0:
                await session.execute("DELETE FROM ocpp_messages")
                print(f"   Deleted {messages} OCPP messages")

            # Delete charging sessions
            if sessions > 0:
                await session.execute("DELETE FROM charging_sessions")
                print(f"   Deleted {sessions} charging sessions")

            # Delete charging stations
            if stations > 0:
                await session.execute("DELETE FROM charging_stations")
                print(f"   Deleted {stations} charging stations")

            # Delete users
            if users > 0:
                await session.execute("DELETE FROM users")
                print(f"   Deleted {users} users")

            # Commit all deletions
            await session.commit()

            print("\n🎉 Data truncation completed!")
            print(f"   Deleted {stations + users + sessions + messages} total records")

        except Exception as e:
            print(f" Error truncating data: {e}")
            await session.rollback()
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(truncate_data())
