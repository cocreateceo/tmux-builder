# State Preservation on Browser Refresh

## Overview
Preserve chat messages and activity log when browser is refreshed, using GUID stored in localStorage.

## Problem
On browser refresh:
- GUID persists (localStorage) ✓
- Chat messages lost (React state)
- Activity log lost (React state)
- Shows "Create Session" screen instead of resuming

## Solution
Two changes needed:

### Task 1: Reduce WebSocket Server Log Noise
- Change connect/disconnect logs from INFO to DEBUG
- Keep message content logs at INFO level

### Task 2: Frontend - Auto-Resume Session on Load
- If localStorage has valid GUID:
  1. Skip "Create Session" screen
  2. Fetch chat history from `/api/history`
  3. Connect to WebSocket (already sends history)
  4. Set sessionReady=true

### Task 3: Backend - Add Session Validation Endpoint
- Add `/api/session/{guid}/validate` endpoint
- Returns: exists, is_active, has_history
- Frontend uses this to decide resume vs create

## Files to Modify

1. `backend/ws_server.py` - Reduce log verbosity
2. `frontend/src/components/SplitChatView.jsx` - Auto-resume logic
3. `backend/main.py` - Add validate endpoint (if needed)

## Verification
- [ ] Server logs show messages but not connect/disconnect spam
- [ ] Refresh browser with active session → resumes with history
- [ ] Activity log repopulates from WebSocket history
- [ ] Chat messages repopulate from backend
