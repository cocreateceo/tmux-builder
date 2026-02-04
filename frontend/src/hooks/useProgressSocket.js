import { useState, useEffect, useRef, useCallback } from 'react';

// Auto-detect WebSocket URL based on environment
const getWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:8082';
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocalhost) return 'ws://localhost:8082';
  // Production: use wss:// with same host (CloudFront proxies /ws/ to backend)
  return `wss://${window.location.host}`;
};

const MCP_WS_URL = getWsUrl();
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_LOG_ENTRIES = 500;

// Message types that should be logged to activity log
const LOGGABLE_TYPES = new Set([
  'ack', 'status', 'working', 'progress', 'found', 'phase',
  'created', 'deployed', 'screenshot', 'test', 'summary', 'done', 'complete', 'error'
]);

function isValidGuid(guid) {
  return guid && guid !== 'null' && guid !== 'undefined';
}

/**
 * Hook for receiving real-time progress updates from Claude CLI via WebSocket.
 *
 * Architecture:
 * - HTTP API (port 8000): Chat request/response
 * - WebSocket (port 8001): Real-time progress updates via notify.sh
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
  const idCounterRef = useRef(0);

  useEffect(() => { handlersRef.current = handlers; }, [handlers]);
  useEffect(() => { guidRef.current = guid; }, [guid]);

  function normalizeMessage(raw) {
    return {
      type: raw.type || 'unknown',
      message: raw.message || raw.data || '',
      data: raw.data,
      guid: raw.guid,
      timestamp: raw.timestamp || new Date().toISOString(),
    };
  }

  const addToActivityLog = useCallback((msg) => {
    setActivityLog((prev) => {
      idCounterRef.current += 1;
      const entry = {
        id: `${Date.now()}-${idCounterRef.current}-${Math.random().toString(36).slice(2, 9)}`,
        type: msg.type,
        message: msg.message,
        timestamp: msg.timestamp,
      };
      return [...prev, entry].slice(-MAX_LOG_ENTRIES);
    });
  }, []);

  // Message type handlers - map each type to state updates and handler calls
  const handleMessage = useCallback((rawData) => {
    const data = normalizeMessage(rawData);

    // Call generic onMessage handler for all messages
    handlersRef.current.onMessage?.(data);

    // Add to activity log if applicable
    if (LOGGABLE_TYPES.has(data.type) || !['connected', 'history', 'pong'].includes(data.type)) {
      addToActivityLog(data);
    }

    // Type-specific handling
    const typeHandlers = {
      ack: () => {
        setPhase('processing');
        setStatusMessage('Processing...');
        handlersRef.current.onAck?.(data);
      },
      progress: () => {
        const value = parseInt(data.data, 10) || 0;
        setProgress(Math.min(100, Math.max(0, value)));
        setPhase('processing');
        handlersRef.current.onProgress?.(data);
      },
      status: () => {
        setStatusMessage(data.message);
        setPhase('processing');
        handlersRef.current.onStatus?.(data);
      },
      working: () => {
        setStatusMessage(data.message);
        setPhase('working');
        handlersRef.current.onWorking?.(data);
      },
      found: () => {
        setStatusMessage(`Found: ${data.message}`);
        handlersRef.current.onFound?.(data);
      },
      phase: () => {
        setPhase(data.message || 'processing');
        handlersRef.current.onPhase?.(data);
      },
      created: () => {
        setStatusMessage(`Created: ${data.message}`);
        handlersRef.current.onCreated?.(data);
      },
      deployed: () => {
        setStatusMessage(`Deployed: ${data.message}`);
        setPhase('deployed');
        handlersRef.current.onDeployed?.(data);
      },
      screenshot: () => {
        setStatusMessage(`Screenshot: ${data.message}`);
        handlersRef.current.onScreenshot?.(data);
      },
      test: () => {
        setStatusMessage(`Test: ${data.message}`);
        handlersRef.current.onTest?.(data);
      },
      summary: () => {
        setStatusMessage('Task completed');
        setPhase('complete');
        setProgress(100);
        handlersRef.current.onSummary?.(data);
      },
      response: () => {
        setPhase('complete');
        setProgress(100);
        handlersRef.current.onResponse?.(data);
      },
      done: () => {
        setPhase('complete');
        setProgress(100);
        setStatusMessage('Complete');
        handlersRef.current.onComplete?.(data);
      },
      complete: () => typeHandlers.done(),
      completed: () => typeHandlers.done(),
      error: () => {
        setPhase('error');
        setStatusMessage(data.message || 'An error occurred');
        handlersRef.current.onError?.(data);
      },
      history: () => {
        if (rawData.messages?.length) {
          rawData.messages.forEach(msg => addToActivityLog(normalizeMessage(msg)));
        }
        handlersRef.current.onHistory?.(rawData);
      },
      tool_log: () => handlersRef.current.onToolLog?.(data),
      connected: () => {},
    };

    const handler = typeHandlers[data.type];
    if (handler) {
      handler();
    } else {
      setStatusMessage(data.message);
      handlersRef.current.onCustom?.(data);
    }
  }, [addToActivityLog]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    const currentGuid = guidRef.current;
    if (!isValidGuid(currentGuid)) return;

    // Prevent duplicate connections
    if (isConnectingRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    isConnectingRef.current = true;

    // Clean up existing connection
    if (wsRef.current) {
      try { wsRef.current.close(1000, 'Reconnecting'); } catch (e) {}
      wsRef.current = null;
    }

    console.log(`[MCP-WS] Connecting to ${MCP_WS_URL}/ws/${currentGuid}`);
    const ws = new WebSocket(`${MCP_WS_URL}/ws/${currentGuid}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[MCP-WS] Connected');
      isConnectingRef.current = false;
      setConnected(true);
      reconnectAttempts.current = 0;
      handlersRef.current.onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[MCP-WS] Received:', data.type, data.message || data.data || '');
        handleMessage(data);
      } catch (err) {
        console.error('[MCP-WS] Failed to parse message:', err);
      }
    };

    ws.onclose = (event) => {
      console.log(`[MCP-WS] Disconnected (code: ${event.code})`);
      isConnectingRef.current = false;
      setConnected(false);

      if (wsRef.current === ws) {
        handlersRef.current.onDisconnect?.();
        wsRef.current = null;

        // Don't reconnect for certain close codes
        // 1000: Normal close (intentional disconnect)
        // 1011: Server error indicating invalid/deleted session
        // Note: 1008 (Policy Violation) could be transient, so we allow retry
        const noReconnectCodes = [1000, 1011];
        if (noReconnectCodes.includes(event.code)) {
          console.log(`[MCP-WS] Not reconnecting (code ${event.code} indicates permanent close)`);
          return;
        }

        // Auto-reconnect with exponential backoff for transient errors
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          console.log(`[MCP-WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        }
      }
    };

    ws.onerror = (err) => {
      console.error('[MCP-WS] Error:', err);
      isConnectingRef.current = false;
    };
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      try { wsRef.current.close(1000, 'User disconnect'); } catch (e) {}
      wsRef.current = null;
    }
    isConnectingRef.current = false;
    setConnected(false);
  }, []);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    disconnect();
    setTimeout(connect, 100);
  }, [connect, disconnect]);

  const resetProgress = useCallback(() => {
    setProgress(0);
    setStatusMessage('');
    setPhase('idle');
  }, []);

  const clearActivityLog = useCallback(() => setActivityLog([]), []);

  // Connect when guid changes
  useEffect(() => {
    if (!isValidGuid(guid)) return;

    const timer = setTimeout(connect, 200);
    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, [guid, connect, disconnect]);

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
