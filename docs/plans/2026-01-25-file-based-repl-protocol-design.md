# File-Based REPL Protocol Design

**Date**: 2026-01-25
**Status**: Implemented

## Overview

A marker-file based synchronization protocol for reliable communication between the FastAPI backend and Claude CLI running in tmux sessions. Inspired by RLM (Recursive Language Models) patterns where context is stored as programmatically accessible variables.

## Problem

The original implementation had timing issues:
- Sending instructions while Claude was still processing previous commands
- No reliable way to know when Claude was ready for input
- Terminal output parsing is fragile and unreliable

## Solution

File-based IPC using marker files as synchronization signals:

```
Backend                          Claude CLI (in tmux)
   │                                   │
   │  [create session, start CLI]      │
   │ ─────────────────────────────────>│
   │                                   │
   │  "Create ready.marker"            │
   │ ─────────────────────────────────>│
   │                                   │
   │     [Claude: touch ready.marker]  │
   │ <─────────────────────────────────│
   │                                   │
   │  [write system_prompt.txt]        │
   │  "Read it, create ack.marker"     │
   │ ─────────────────────────────────>│
   │                                   │
   │     [Claude: touch ack.marker]    │
   │ <─────────────────────────────────│
   │                                   │
   │  === SESSION READY ===            │
```

## Marker Files

| Marker | Purpose | Created By | Timeout |
|--------|---------|------------|---------|
| `ready.marker` | Claude is ready for input | Claude | 30s |
| `ack.marker` | Claude received the prompt | Claude | 10s |
| `completed.marker` | Claude finished processing | Claude | 300s |

## Status File

`status.json` structure:
```json
{
  "state": "ready | processing | completed | error",
  "progress": 0-100,
  "message": "Human readable status",
  "phase": "init | reading_prompt | executing | writing_output",
  "updated_at": "2026-01-25T12:34:56Z"
}
```

## Initialization Protocol

1. Backend creates tmux session, starts Claude CLI
2. Backend sends: "Create ready.marker when ready"
3. Backend polls for `ready.marker` (30s timeout)
4. Backend writes `system_prompt.txt`
5. Backend sends: "Read system_prompt.txt, create ack.marker"
6. Backend polls for `ack.marker` (10s timeout)
7. Session is initialized

## Message Loop Protocol

1. Backend clears `ack.marker` and `completed.marker`
2. Backend writes message to `prompt.txt`
3. Backend sends instruction to read and process
4. Claude creates `ack.marker` immediately
5. Claude updates `status.json` as it works
6. Claude writes response to `chat_history.jsonl`
7. Claude creates `completed.marker`
8. Backend reads response

## File Structure

```
sessions/active/{guid}/
├── markers/
│   ├── ready.marker
│   ├── ack.marker
│   └── completed.marker
├── status.json
├── prompt.txt
├── system_prompt.txt
└── chat_history.jsonl
```

## Implementation Files

- `config.py` - Marker constants and path helpers
- `marker_utils.py` - Marker file operations
- `session_initializer.py` - Initialization handshake
- `session_controller.py` - Message loop protocol
- `tmux_helper.py` - Low-level tmux operations

## Benefits

1. **Reliable synchronization** - File existence is atomic
2. **No terminal parsing** - Avoids buffer/encoding issues
3. **Debuggable** - Can inspect marker files and status.json
4. **Timeout handling** - Clear timeout per operation
5. **State visibility** - Backend always knows current state
