#!/bin/bash

echo "============================================================"
echo "STARTING TMUX BUILDER BACKEND"
echo "============================================================"

cd backend

echo ""
echo "Checking dependencies..."
python3 -c "from fastapi import FastAPI; from uvicorn import run; print('✓ All imports working')" 2>&1

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Missing dependencies. Installing..."
    pip3 install --user fastapi==0.104.1 uvicorn[standard]==0.24.0 pydantic==2.5.0 python-multipart==0.0.6
    echo ""
fi

echo ""
echo "Starting backend server..."
echo "Press Ctrl+C to stop"
echo ""

python3 main.py
