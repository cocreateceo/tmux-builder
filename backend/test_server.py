#!/usr/bin/env python3
"""Quick test to verify server can start."""

import sys

print("Testing backend server startup...")
print("=" * 60)

# Test imports
try:
    print("1. Testing imports...")
    from fastapi import FastAPI
    from uvicorn import run
    from config import API_HOST, API_PORT, DEFAULT_USER
    from session_controller import SessionController
    print("   ✓ All imports successful")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test config values
print(f"\n2. Configuration:")
print(f"   - API Host: {API_HOST}")
print(f"   - API Port: {API_PORT}")
print(f"   - Default User: {DEFAULT_USER}")

# Test if port is available
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('localhost', API_PORT))
sock.close()

if result == 0:
    print(f"\n   ✗ Port {API_PORT} is already in use!")
    print(f"   Kill existing process: pkill -f 'python3 main.py'")
    sys.exit(1)
else:
    print(f"\n   ✓ Port {API_PORT} is available")

print("\n" + "=" * 60)
print("✓ All checks passed! Server is ready to start.")
print("\nTo start the server, run:")
print("   python3 main.py")
print("=" * 60)
