#!/bin/bash

set -e

echo "Starting OCPP Backend Application..."

# Start the FastAPI application with Uvicorn
echo "Starting FastAPI server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
