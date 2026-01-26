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

# Clear Vite cache to ensure fresh builds
echo ""
echo "Clearing Vite cache..."
rm -rf node_modules/.vite 2>/dev/null || true

echo ""
echo "Starting frontend dev server..."
echo "Press Ctrl+C to stop"
echo ""
echo "NOTE: If you still see errors, do a hard refresh in browser (Ctrl+Shift+R)"
echo ""

npm run dev
