#!/usr/bin/env python3

import asyncio
from datetime import datetime, timezone
import logging
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import db_manager
from app.models import ChargingStation, User


async def create_sample_data():
    """Create sample data if it doesn't exist"""

    logging.info("🚀 Starting sample data creation...")

    # Initialize database connection
    await db_manager.initialize()

    # Sample charging stations data
    sample_stations = [
        {
            "station_id": "CHARGER_001",
            "name": "Downtown Charging Station",
            "location": "123 Main Street, Downtown",
            "is_online": True,
        },
        {
            "station_id": "CHARGER_002",
            "name": "Mall Charging Hub",
            "location": "456 Shopping Mall, City Center",
            "is_online": True,
        },
        {
            "station_id": "CHARGER_003",
            "name": "Highway Rest Stop Charger",
            "location": "Highway 101, Exit 15",
            "is_online": False,
        },
        {
            "station_id": "CHARGER_004",
            "name": "Office Building Charger",
            "location": "789 Business District",
            "is_online": True,
        },
        {
            "station_id": "CHARGER_005",
            "name": "Residential Area Charger",
            "location": "321 Residential Street",
            "is_online": True,
        },
    ]

    # Sample users data
    sample_users = [
        {
            "username": "john_doe",
            "email": "john.doe@example.com",
            "is_active": True,
        },
        {
            "username": "jane_smith",
            "email": "jane.smith@example.com",
            "is_active": True,
        },
        {
            "username": "mike_wilson",
            "email": "mike.wilson@example.com",
            "is_active": True,
        },
        {
            "username": "sarah_jones",
            "email": "sarah.jones@example.com",
            "is_active": False,
        },
        {
            "username": "admin_user",
            "email": "admin@evcs.com",
            "is_active": True,
        },
    ]

    async for session in db_manager.get_session():
        try:
            # Create charging stations
            logging.info("📡 Creating charging stations...")
            stations_created = 0
            stations_existing = 0

            for station_data in sample_stations:
                # Check if station already exists
                from sqlalchemy import select

                result = await session.execute(
                    select(ChargingStation).where(
                        ChargingStation.station_id == station_data["station_id"]
                    )
                )
                existing_station = result.scalar_one_or_none()

                if existing_station:
                    logging.info(
                        "   ⚠️  Station %s already exists - skipping",
                        station_data["station_id"],
                    )
                    stations_existing += 1
                else:
                    station = ChargingStation(
                        station_id=station_data["station_id"],
                        name=station_data["name"],
                        location=station_data["location"],
                        is_online=station_data["is_online"],
                        last_heartbeat=datetime.now(timezone.utc)
                        if station_data["is_online"]
                        else None,
                    )
                    session.add(station)
                    logging.info(
                        "   ✅ Created station: %s - %s",
                        station_data["station_id"],
                        station_data["name"],
                    )
                    stations_created += 1

            # Create users
            logging.info("👥 Creating users...")
            users_created = 0
            users_existing = 0

            for user_data in sample_users:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.username == user_data["username"])
                )
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    logging.info(
                        "   ⚠️  User %s already exists - skipping", user_data["username"]
                    )
                    users_existing += 1
                else:
                    user = User(
                        username=user_data["username"],
                        email=user_data["email"],
                        is_active=user_data["is_active"],
                    )
                    session.add(user)
                    logging.info(
                        "   ✅ Created user: %s - %s",
                        user_data["username"],
                        user_data["email"],
                    )
                    users_created += 1

            # Commit all changes
            await session.commit()

            logging.info("\n📊 Summary:")
            logging.info(
                "   Charging Stations: %s created, %s already existed",
                stations_created,
                stations_existing,
            )
            logging.info(
                "   Users: %s created, %s already exist", users_created, users_existing
            )
            logging.info(
                "   Total: %s records created", stations_created + users_created
            )

        except Exception as e:
            logging.exception("❌ Error creating sample data: %s", e.message)
            await session.rollback()
        finally:
            await session.close()

    logging.info("\n🎉 Sample data creation completed!")


if __name__ == "__main__":
    asyncio.run(create_sample_data())
