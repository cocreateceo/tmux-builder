#!/bin/bash

echo "============================================================"
echo "STARTING TMUX BUILDER BACKEND"
echo "============================================================"

cd backend

# Prevent Python bytecode cache issues (stale .pyc files)
export PYTHONDONTWRITEBYTECODE=1
rm -rf __pycache__ 2>/dev/null
echo "✓ Bytecode cache cleared"

# Kill any existing server on port 8000 (Chat API) and 8001 (MCP Progress)
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "✓ Killed existing process on port 8000" || true
lsof -ti:8001 | xargs kill -9 2>/dev/null && echo "✓ Killed existing process on port 8001" || true

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
