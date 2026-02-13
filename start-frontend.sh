#!/bin/bash

echo "============================================================"
echo "STARTING TMUX BUILDER FRONTEND"
echo "============================================================"

cd frontend

echo ""
echo "Checking node_modules..."
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo ""
echo "Starting frontend dev server..."
echo "Press Ctrl+C to stop"
echo ""

npm run dev
