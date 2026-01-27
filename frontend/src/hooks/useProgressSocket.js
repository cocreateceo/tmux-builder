import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * MCP Progress WebSocket URL (Channel 2)
 * Connects to the MCP server for real-time progress updates from Claude CLI
 */
const MCP_WS_URL = 'ws://localhost:8001';

/**
 * Custom hook for receiving real-time progress updates from Claude CLI via MCP WebSocket.
 *
 * Dual-channel architecture:
 * - Channel 1 (useWebSocket): UI <-> Backend (chat request/response on port 8000)
 * - Channel 2 (useProgressSocket): UI <-> MCP Server (real-time progress on port 8001)
 *
 * Message format from notify.sh:
 * { type: "status", data: "message here", guid: "...", timestamp: "..." }
 *
 * Supported message types:
 * - ack: Claude acknowledged the prompt
 * - status: Status message update
 * - working: What Claude is currently working on
 * - progress: Progress percentage (0-100)
 * - found: Report findings
 * - phase: Current phase of work
 * - created: File created
 * - deployed: Deployed URL
 * - screenshot: Screenshot taken
 * - test: Test results
 * - done/complete: Task completed
 * - error: Error occurred
 * - Any custom type: Handled via onMessage callback
 *
 * @param {string} guid - Session GUID to subscribe to
 * @param {object} handlers - Event handlers
 * @returns {object} - { connected, progress, statusMessage, phase, activityLog, reconnect, resetProgress }
 */
export function useProgressSocket(guid, handlers = {}) {
  const [connected, setConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [phase, setPhase] = useState('idle');
  const [activityLog, setActivityLog] = useState([]);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false);
  const handlersRef = useRef(handlers);
  const guidRef = useRef(guid);

  const maxReconnectAttempts = 5;

  // Keep refs updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    guidRef.current = guid;
  }, [guid]);

  /**
   * Normalize message from notify.sh format.
   * notify.sh sends: { type, data, guid, timestamp }
   * We normalize to: { type, message, data, guid, timestamp }
   */
  const normalizeMessage = (raw) => {
    return {
      type: raw.type || 'unknown',
      // Use 'data' field as message content (notify.sh format)
      message: raw.message || raw.data || '',
      // Keep original data for progress percentage parsing
      data: raw.data,
      guid: raw.guid,
      timestamp: raw.timestamp || new Date().toISOString(),
    };
  };

  /**
   * Add message to activity log
   */
  const addToActivityLog = useCallback((msg) => {
    setActivityLog((prev) => {
      const newLog = [...prev, {
        id: Date.now() + Math.random(),
        type: msg.type,
        message: msg.message,
        timestamp: msg.timestamp,
      }];
      // Keep last 100 messages
      return newLog.slice(-100);
    });
  }, []);

  // Connect to MCP WebSocket
  const connect = useCallback(() => {
    const currentGuid = guidRef.current;

    // More defensive check - handle null, undefined, empty string, and string "null"/"undefined"
    if (!currentGuid || currentGuid === 'null' || currentGuid === 'undefined') {
      console.log('[MCP-WS] No valid GUID provided, skipping connection');
      return;
    }

    if (isConnectingRef.current) {
      console.log('[MCP-WS] Already connecting, skipping');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[MCP-WS] Already connected');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log('[MCP-WS] Connection in progress, skipping');
      return;
    }

    isConnectingRef.current = true;

    // Clean up existing connection
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'Reconnecting');
      } catch (e) {
        // Ignore
      }
      wsRef.current = null;
    }

    // Connect with guid in URL path
    const wsUrl = `${MCP_WS_URL}/ws/${currentGuid}`;
    console.log(`[MCP-WS] Connecting to ${wsUrl}...`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[MCP-WS] Connected to MCP progress server');
      isConnectingRef.current = false;
      setConnected(true);
      reconnectAttempts.current = 0;
      handlersRef.current.onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const rawData = JSON.parse(event.data);
        const data = normalizeMessage(rawData);

        console.log('[MCP-WS] Received:', data.type, data);

        // Always call onMessage for any message type (generic handler)
        handlersRef.current.onMessage?.(data);

        // Add to activity log for most message types
        const logTypes = ['ack', 'status', 'working', 'progress', 'found', 'phase',
                         'created', 'deployed', 'screenshot', 'test', 'done', 'complete', 'error'];
        if (logTypes.includes(data.type) || !['connected', 'history', 'pong'].includes(data.type)) {
          addToActivityLog(data);
        }

        switch (data.type) {
          case 'ack':
            setPhase('processing');
            setStatusMessage('Processing...');
            handlersRef.current.onAck?.(data);
            break;

          case 'progress': {
            // Parse progress from data field (notify.sh sends as string)
            const progressValue = parseInt(data.data, 10) || 0;
            setProgress(Math.min(100, Math.max(0, progressValue)));
            setPhase('processing');
            handlersRef.current.onProgress?.(data);
            break;
          }

          case 'status':
            setStatusMessage(data.message);
            setPhase('processing');
            handlersRef.current.onStatus?.(data);
            break;

          case 'working':
            setStatusMessage(data.message);
            setPhase('working');
            handlersRef.current.onWorking?.(data);
            break;

          case 'found':
            setStatusMessage(`Found: ${data.message}`);
            handlersRef.current.onFound?.(data);
            break;

          case 'phase':
            setPhase(data.message || 'processing');
            handlersRef.current.onPhase?.(data);
            break;

          case 'created':
            setStatusMessage(`Created: ${data.message}`);
            handlersRef.current.onCreated?.(data);
            break;

          case 'deployed':
            setStatusMessage(`Deployed: ${data.message}`);
            setPhase('deployed');
            handlersRef.current.onDeployed?.(data);
            break;

          case 'screenshot':
            setStatusMessage(`Screenshot: ${data.message}`);
            handlersRef.current.onScreenshot?.(data);
            break;

          case 'test':
            setStatusMessage(`Test: ${data.message}`);
            handlersRef.current.onTest?.(data);
            break;

          case 'response':
            setPhase('complete');
            setProgress(100);
            handlersRef.current.onResponse?.(data);
            break;

          case 'done':
          case 'complete':
          case 'completed':
            setPhase('complete');
            setProgress(100);
            setStatusMessage('Complete');
            handlersRef.current.onComplete?.(data);
            break;

          case 'error':
            setPhase('error');
            setStatusMessage(data.message || 'An error occurred');
            handlersRef.current.onError?.(data);
            break;

          case 'connected':
            console.log('[MCP-WS] Connection confirmed for GUID:', data.guid);
            break;

          case 'history':
            // Handle message history from server
            if (rawData.messages && Array.isArray(rawData.messages)) {
              rawData.messages.forEach((msg) => {
                const normalized = normalizeMessage(msg);
                addToActivityLog(normalized);
              });
            }
            handlersRef.current.onHistory?.(rawData);
            break;

          case 'tool_log':
            handlersRef.current.onToolLog?.(data);
            break;

          default:
            // Generic handler for any custom message type
            console.log('[MCP-WS] Custom message type:', data.type, data.message);
            setStatusMessage(data.message);
            handlersRef.current.onCustom?.(data);
        }
      } catch (err) {
        console.error('[MCP-WS] Failed to parse message:', err);
      }
    };

    ws.onclose = (event) => {
      console.log('[MCP-WS] Disconnected:', event.code, event.reason);
      isConnectingRef.current = false;
      setConnected(false);

      if (wsRef.current === ws) {
        handlersRef.current.onDisconnect?.();
        wsRef.current = null;

        // Auto-reconnect with exponential backoff
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          console.log(`[MCP-WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`);

          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        }
      }
    };

    ws.onerror = (error) => {
      console.error('[MCP-WS] Error:', error);
      isConnectingRef.current = false;
    };
  }, [addToActivityLog]);

  // Disconnect
  const disconnect = useCallback(() => {
    console.log('[MCP-WS] Disconnecting...');

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'User disconnect');
      } catch (e) {
        // Ignore
      }
      wsRef.current = null;
    }

    isConnectingRef.current = false;
    setConnected(false);
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    disconnect();
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  // Reset progress state (call when starting new message)
  const resetProgress = useCallback(() => {
    setProgress(0);
    setStatusMessage('');
    setPhase('idle');
  }, []);

  // Clear activity log
  const clearActivityLog = useCallback(() => {
    setActivityLog([]);
  }, []);

  // Connect when guid is set
  useEffect(() => {
    // Defensive check - handle null, undefined, empty string, and string "null"/"undefined"
    if (!guid || guid === 'null' || guid === 'undefined') {
      console.log('[MCP-WS] No valid GUID, skipping connection');
      return;
    }

    const timer = setTimeout(() => {
      connect();
    }, 200); // Slight delay to ensure Channel 1 connects first

    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [guid]);

  return {
    connected,
    progress,
    statusMessage,
    phase,
    activityLog,
    reconnect,
    disconnect,
    resetProgress,
    clearActivityLog,
  };
}

export default useProgressSocket;
